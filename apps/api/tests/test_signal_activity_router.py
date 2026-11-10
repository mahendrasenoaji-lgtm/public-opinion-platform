"""Tes end-to-end emosi, aktivitas/jam ramai, dan jendela tanggal mutlak.

Pola sama dengan test_signals_router.py: Postgres nyata, role pop_app (RLS
aktif), data masuk lewat POST /signals/ingest.
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
    slug = f"akt-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Aktivitas",
            "org_slug": slug,
            "full_name": "Penguji Aktivitas",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Aktivitas"}, headers=headers)
    assert proj.status_code == 201, proj.text
    return headers, proj.json()["id"]


def _item(i: int, text: str, *, at: datetime, engagement: int = 0) -> dict:
    return {
        "external_id": f"akt-{uuid.uuid4().hex[:8]}-{i}",
        "text": text,
        "published_at": at.isoformat(),
        "engagement": engagement,
    }


async def _ingest(client, headers, pid, items, source="SOCIAL") -> None:
    r = await client.post(
        f"/v1/projects/{pid}/signals/ingest",
        json={"items": items, "source": source},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["stored"] == len(items), r.text


YESTERDAY = datetime.now(UTC) - timedelta(days=1)


class TestEmosi:
    async def test_di_bawah_ambang_sebaran_ditahan_hitungan_tetap_ada(self, client) -> None:
        headers, pid = await _new_project(client)
        items = [
            _item(i, f"warga marah dan kecewa soal antrean nomor {i}", at=YESTERDAY)
            for i in range(5)
        ] + [_item(99, "antrean panjang di spbu nomor sembilan", at=YESTERDAY)]
        await _ingest(client, headers, pid, items)

        r = await client.get(f"/v1/projects/{pid}/signals/emotions", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert [s["source"] for s in body["by_source"]] == ["SOCIAL"]
        social = body["by_source"][0]
        assert social["n_total"] == 6
        assert social["n_with_emotion"] == 5
        assert social["insufficient_data"] is True
        assert social["share"] is None and social["dominant"] is None
        assert "belum dievaluasi" in social["method"]
        assert body["limitations"]

    async def test_di_atas_ambang_sebaran_terbit_per_sumber(self, client) -> None:
        headers, pid = await _new_project(client)
        marah = [
            _item(i, f"saya marah sekali melihat antrean ini nomor {i}", at=YESTERDAY)
            for i in range(24)
        ]
        takut = [
            _item(100 + i, f"kami takut stok habis besok nomor {i}", at=YESTERDAY)
            for i in range(8)
        ]
        await _ingest(client, headers, pid, marah + takut)
        berita = [
            _item(200 + i, f"warga khawatir pasokan terganggu laporan {i}", at=YESTERDAY)
            for i in range(3)
        ]
        await _ingest(client, headers, pid, berita, source="MEDIA")

        body = (await client.get(f"/v1/projects/{pid}/signals/emotions", headers=headers)).json()
        by = {s["source"]: s for s in body["by_source"]}
        assert set(by) == {"SOCIAL", "MEDIA"}
        assert by["SOCIAL"]["insufficient_data"] is False
        assert by["SOCIAL"]["share"]["anger"] == 0.75
        assert by["SOCIAL"]["share"]["fear"] == 0.25
        assert by["SOCIAL"]["dominant"]["anger"] == 24
        # Liputan tidak ikut penyebut percakapan, dan 3 konten tidak diterbitkan.
        assert by["MEDIA"]["n_total"] == 3
        assert by["MEDIA"]["share"] is None

    async def test_proyek_kosong(self, client) -> None:
        headers, pid = await _new_project(client)
        r = await client.get(f"/v1/projects/{pid}/signals/emotions", headers=headers)
        assert r.status_code == 200
        assert r.json()["by_source"] == []


class TestAktivitas:
    async def test_engagement_jam_ramai_dan_konten_teratas(self, client) -> None:
        headers, pid = await _new_project(client)
        # 03.15 UTC = 10.15 WIB = 11.15 WITA.
        base = (datetime.now(UTC) - timedelta(days=2)).replace(
            hour=3, minute=15, second=0, microsecond=0
        )
        items = [
            _item(i, f"antrean bbm panjang sekali hari ini nomor {i}", at=base, engagement=i)
            for i in range(8)
        ]
        await _ingest(client, headers, pid, items)

        r = await client.get(f"/v1/projects/{pid}/signals/activity", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["timezone"] == "WIB"
        assert len(body["weekdays"]) == 7
        social = body["by_source"][0]
        assert social["source"] == "SOCIAL"
        assert social["n"] == 8
        assert social["engagement_total"] == sum(range(8))
        assert social["n_with_engagement"] == 7
        assert social["peak_hour"] == 10 and social["peak_count"] == 8
        assert social["by_hour"][10] == 8 and sum(social["by_hour"]) == 8
        assert len(social["heatmap"]) == 7 and len(social["heatmap"][0]) == 24
        assert [t["engagement"] for t in social["top"]] == [7, 6, 5, 4, 3]
        assert sum(d["volume"] for d in social["by_day"]) == 8

        wita = (
            await client.get(f"/v1/projects/{pid}/signals/activity?tz=WITA", headers=headers)
        ).json()
        assert wita["by_source"][0]["peak_hour"] == 11

    async def test_zona_tak_dikenal_ditolak(self, client) -> None:
        headers, pid = await _new_project(client)
        r = await client.get(f"/v1/projects/{pid}/signals/activity?tz=GMT", headers=headers)
        assert r.status_code == 422


class TestJendelaMutlak:
    async def test_data_lama_terlihat_lewat_tanggal_mutlak(self, client) -> None:
        """Data di luar jendela 30 hari bawaan tetap bisa dibaca."""
        headers, pid = await _new_project(client)
        lama = (datetime.now(UTC) - timedelta(days=60)).replace(hour=5, minute=0)
        items = [
            _item(i, f"saya kecewa dengan pelayanan ini nomor {i}", at=lama, engagement=2)
            for i in range(6)
        ]
        await _ingest(client, headers, pid, items)

        bawaan = (await client.get(f"/v1/projects/{pid}/signals/summary", headers=headers)).json()
        assert bawaan["volume"]["value"] == 0

        day = lama.date().isoformat()
        q = f"start={day}&end={day}"
        mutlak = (
            await client.get(f"/v1/projects/{pid}/signals/summary?{q}", headers=headers)
        ).json()
        assert mutlak["volume"]["value"] == 6
        assert mutlak["period_start"] == day and mutlak["period_end"] == day

        trend = (await client.get(f"/v1/projects/{pid}/signals/trend?{q}", headers=headers)).json()
        assert [p["volume"] for p in trend] == [6]
        mentions = (await client.get(f"/v1/projects/{pid}/mentions?{q}", headers=headers)).json()
        assert len(mentions) == 6
        emo = (
            await client.get(f"/v1/projects/{pid}/signals/emotions?{q}", headers=headers)
        ).json()
        assert emo["by_source"][0]["n_total"] == 6
        act = (
            await client.get(f"/v1/projects/{pid}/signals/activity?{q}", headers=headers)
        ).json()
        assert act["by_source"][0]["engagement_total"] == 12

    async def test_jendela_setengah_atau_terbalik_ditolak(self, client) -> None:
        headers, pid = await _new_project(client)
        for q in ("start=2026-10-11", "end=2026-10-20", "start=2026-10-20&end=2026-10-11"):
            r = await client.get(f"/v1/projects/{pid}/signals/summary?{q}", headers=headers)
            assert r.status_code == 422, q


class TestIsolasiTenant:
    async def test_emosi_dan_aktivitas_org_lain_tidak_terlihat(self, client) -> None:
        headers_a, pid_a = await _new_project(client)
        headers_b, _ = await _new_project(client)
        await _ingest(
            client,
            headers_a,
            pid_a,
            [
                _item(i, f"saya marah soal harga nomor {i}", at=YESTERDAY, engagement=3)
                for i in range(35)
            ],
        )
        emo = await client.get(f"/v1/projects/{pid_a}/signals/emotions", headers=headers_b)
        act = await client.get(f"/v1/projects/{pid_a}/signals/activity", headers=headers_b)
        assert emo.status_code == 200 and act.status_code == 200
        assert emo.json()["by_source"] == [], "RLS bocor: org lain melihat emosi"
        assert act.json()["by_source"] == [], "RLS bocor: org lain melihat aktivitas"
