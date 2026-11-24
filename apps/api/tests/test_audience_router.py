"""Tes end-to-end GET /projects/{id}/audience (P11).

Pola sama dengan test_signal_activity_router.py: Postgres nyata, role pop_app
(RLS aktif), data masuk lewat POST /signals/ingest.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

DSN = os.getenv("TEST_DATABASE_URL_APP")

if DSN:
    os.environ["DATABASE_URL"] = DSN
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
async def client():
    if not DSN:
        pytest.skip("TEST_DATABASE_URL_APP tidak diset")

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _new_project(client) -> tuple[dict[str, str], str]:
    slug = f"aud-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Audiens",
            "org_slug": slug,
            "full_name": "Penguji Audiens",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Audiens"}, headers=headers)
    assert proj.status_code == 201, proj.text
    return headers, proj.json()["id"]


YESTERDAY = datetime.now(UTC) - timedelta(days=1)


def _item(i: int, text: str, author: str) -> dict:
    return {
        "external_id": f"aud-{uuid.uuid4().hex[:8]}-{i}",
        "text": text,
        "published_at": (YESTERDAY - timedelta(minutes=i)).isoformat(),
        "author_handle": author,
    }


async def _ingest(client, headers, pid, items, source="SOCIAL") -> None:
    r = await client.post(
        f"/v1/projects/{pid}/signals/ingest",
        json={"items": items, "source": source},
        headers=headers,
    )
    assert r.status_code == 200, r.text


class TestToOut:
    def test_sentimen_segmen_butuh_banyak_akun(self) -> None:
        from datetime import datetime

        from app.routers.audience import to_out
        from app.services.profiling import AudienceStats, SegmentSentiment

        stats = AudienceStats(
            n_accounts=100,
            n_comments=500,
            gender={"L": 0, "P": 0},
            age={},
            pyramid={},
            interests={},
            interests_by_gender={},
            evidence={},
            sentiment=[
                SegmentSentiment("minat:gim", accounts=3, scored=90, mean=-0.4),
                SegmentSentiment("minat:kuliner", accounts=12, scored=40, mean=0.1),
            ],
        )
        now = datetime.now(UTC)
        out = to_out(stats, now, now)
        means = {s.segment: s.mean for s in out.sentiment}
        assert means == {"minat:gim": None, "minat:kuliner": 0.1}


class TestAudiens:
    async def test_sedikit_akun_ditahan_tanpa_hash(self, client) -> None:
        headers, pid = await _new_project(client)
        await _ingest(
            client,
            headers,
            pid,
            [
                _item(1, "saya ibu rumah tangga, harga naik terus", "akun_a"),
                _item(2, "gue cowok umur gue 20 tahun, kecewa sekali", "akun_b"),
            ],
        )
        r = await client.get(f"/v1/projects/{pid}/audience?days=7", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "SOCIAL"
        assert body["evaluated"] is False
        assert body["n_accounts"] == 2
        assert body["insufficient_data"] is True
        assert body["gender"]["known"] == 2
        # di bawah ambang: hitungan ada, persen ditahan
        assert all(v["share"] is None for v in body["gender"]["values"])
        # sel piramida 1 akun -> disembunyikan
        cell = next(c for c in body["pyramid"] if c["age"] == "18-24" and c["gender"] == "L")
        assert cell["accounts"] is None
        assert body["limitations"]
        # tidak ada hash akun atau handle di respons
        assert "akun_a" not in r.text and "author_hash" not in r.text

    async def test_banyak_akun_persen_terbit(self, client) -> None:
        headers, pid = await _new_project(client)
        items = [_item(i, f"saya seorang ibu, komentar nomor {i}", f"ibu_{i}") for i in range(20)]
        items += [_item(100 + i, f"saya bapak tiga anak no {i}", f"bpk_{i}") for i in range(15)]
        items += [_item(200 + i, f"mabar dulu {i}", f"gamer_{i}") for i in range(10)]
        items += [_item(300 + i, f"game baru seru {i}", f"gamer_{i}") for i in range(10)]
        await _ingest(client, headers, pid, items)
        # liputan media tidak dihitung sebagai akun
        await _ingest(client, headers, pid, [_item(900, "saya ibu", "redaksi")], source="MEDIA")
        r = await client.get(f"/v1/projects/{pid}/audience?days=7", headers=headers)
        body = r.json()
        assert body["n_accounts"] == 45
        g = {v["value"]: v for v in body["gender"]["values"]}
        assert g["P"]["accounts"] == 20 and g["L"]["accounts"] == 15
        assert g["P"]["share"] == pytest.approx(57.1)
        assert body["gender"]["unknown"] == 10
        gim = next(i for i in body["interests"] if i["value"] == "gim")
        assert gim["accounts"] == 10
        assert gim["share_of_accounts"] is None  # 10 akun berminat < 30

    async def test_kata_topik_dikecualikan(self, client) -> None:
        headers, pid = await _new_project(client)
        items = [_item(i, f"martabak lagi {i}", "akun_m") for i in range(3)]
        await _ingest(client, headers, pid, items)
        r = await client.get(f"/v1/projects/{pid}/audience?days=7", headers=headers)
        assert [i["value"] for i in r.json()["interests"]] == ["kuliner"]
        r = await client.get(
            f"/v1/projects/{pid}/audience?days=7&exclude=Martabak,%20,kopi", headers=headers
        )
        body = r.json()
        assert body["interests"] == []
        assert body["excluded"] == ["kopi", "martabak"]

    async def test_isolasi_tenant(self, client) -> None:
        headers_a, pid_a = await _new_project(client)
        await _ingest(client, headers_a, pid_a, [_item(1, "saya ibu", "x")])
        headers_b, _ = await _new_project(client)
        r = await client.get(f"/v1/projects/{pid_a}/audience?days=7", headers=headers_b)
        # RLS: org lain tidak melihat satu baris pun
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert r.json()["n_accounts"] == 0

    async def test_tanpa_login_ditolak(self, client) -> None:
        r = await client.get(f"/v1/projects/{uuid.uuid4()}/audience")
        assert r.status_code == 401
