"""Tes end-to-end graf interaksi balasan/kutipan (services/network.py + router).

Sama seperti test_influence_impact_router.py: gating dan isolasi tenant lebih
penting untuk dites daripada aritmetikanya, yang sudah ditutupi
test_network.py tanpa database.
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


async def _new_project(client) -> tuple[dict[str, str], str, str]:
    slug = f"net-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Network",
            "org_slug": slug,
            "full_name": "Penguji Network",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Network"}, headers=headers)
    body = proj.json()
    return headers, body["org_id"], body["id"]


async def _ingest_relasi(
    client,
    headers: dict[str, str],
    project_id: str,
    *,
    author: str,
    reply_to: str | None = None,
    quote_of: str | None = None,
    n: int = 1,
    days_ago: int = 1,
) -> None:
    """Kirim n item lewat endpoint ingest resmi -- bukan INSERT langsung --
    supaya pipeline hashing (services/pipeline.py) yang sungguhan dipakai,
    persis seperti yang dipakai konektor X."""
    now = datetime.now(UTC)
    items = [
        {
            "external_id": f"net-{uuid.uuid4().hex[:10]}-{i}",
            "text": f"pendapat warga tentang kebijakan nomor {i} yang cukup panjang",
            "published_at": (now - timedelta(days=days_ago)).isoformat(),
            "author_handle": author,
            "reply_to_handle": reply_to,
            "quote_of_handle": quote_of,
        }
        for i in range(n)
    ]
    r = await client.post(
        f"/v1/projects/{project_id}/signals/ingest",
        json={"items": items},
        headers=headers,
    )
    assert r.status_code == 200, r.text


async def _isi_graf_lolos_gating(client, headers, pid) -> None:
    """>= MIN_ACCOUNTS akun, >= MIN_EDGES edge, satu akun ("populer") jadi
    tujuan dari semuanya."""
    for i in range(16):
        await _ingest_relasi(client, headers, pid, author=f"warga_{i}", reply_to="populer")


class TestNetworkGating:
    async def test_proyek_kosong_insufficient(self, client) -> None:
        headers, _org, pid = await _new_project(client)
        r = await client.get(f"/v1/projects/{pid}/network", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["insufficient_data"] is True
        assert body["top"] == []

    async def test_akun_kurang_dari_minimum_insufficient(self, client) -> None:
        headers, _org, pid = await _new_project(client)
        # Cuma 3 akun berelasi, jauh di bawah MIN_ACCOUNTS.
        await _ingest_relasi(client, headers, pid, author="a", reply_to="c")
        await _ingest_relasi(client, headers, pid, author="b", reply_to="c")
        r = await client.get(f"/v1/projects/{pid}/network", headers=headers)
        body = r.json()
        assert body["insufficient_data"] is True

    async def test_mention_tanpa_relasi_tidak_membentuk_edge(self, client) -> None:
        """Percakapan biasa (bukan balasan/kutipan) tidak pernah masuk graf,
        walau jumlahnya banyak dan lolos ambang MIN_MENTIONS lain di sistem."""
        headers, _org, pid = await _new_project(client)
        for i in range(30):
            await _ingest_relasi(client, headers, pid, author=f"warga_{i}")
        r = await client.get(f"/v1/projects/{pid}/network", headers=headers)
        assert r.json()["insufficient_data"] is True


class TestNetworkPeringkat:
    async def test_akun_paling_banyak_dibalas_naik_ke_atas(self, client) -> None:
        headers, _org, pid = await _new_project(client)
        await _isi_graf_lolos_gating(client, headers, pid)
        r = await client.get(f"/v1/projects/{pid}/network", headers=headers)
        body = r.json()
        assert body["insufficient_data"] is False
        assert body["top"][0]["replies_received"] == 16
        assert body["top"][0]["distinct_sources"] == 16

    async def test_hanya_hash_yang_keluar_bukan_handle(self, client) -> None:
        headers, _org, pid = await _new_project(client)
        await _isi_graf_lolos_gating(client, headers, pid)
        body = (await client.get(f"/v1/projects/{pid}/network", headers=headers)).json()
        assert body["top"]
        assert all("populer" not in p["author_hash"] for p in body["top"])
        assert all("warga_" not in p["author_hash"] for p in body["top"])

    async def test_metode_dan_batasan_menyatakan_bukan_kausal(self, client) -> None:
        headers, _org, pid = await _new_project(client)
        await _isi_graf_lolos_gating(client, headers, pid)
        body = (await client.get(f"/v1/projects/{pid}/network", headers=headers)).json()
        assert "in-degree" in body["method"]
        assert any("bukan bukti pengaruh kausal" in x for x in body["limitations"])

    async def test_jendela_waktu_membatasi_periode(self, client) -> None:
        """Relasi 40 hari lalu tidak ikut pada jendela 30 hari (default),
        tapi ikut begitu jendela diperlebar."""
        headers, _org, pid = await _new_project(client)
        for i in range(16):
            await _ingest_relasi(
                client, headers, pid, author=f"warga_{i}", reply_to="lama", days_ago=40
            )

        default_window = (await client.get(f"/v1/projects/{pid}/network", headers=headers)).json()
        assert default_window["insufficient_data"] is True

        wider = (
            await client.get(
                f"/v1/projects/{pid}/network", params={"days": 60}, headers=headers
            )
        ).json()
        assert wider["insufficient_data"] is False
        assert wider["top"][0]["replies_received"] == 16


class TestNetworkIsolasiTenant:
    async def test_org_lain_tidak_melihat_relasi(self, client) -> None:
        headers_a, _org_a, pid_a = await _new_project(client)
        headers_b, _org_b, _pid_b = await _new_project(client)
        await _isi_graf_lolos_gating(client, headers_a, pid_a)
        body = (await client.get(f"/v1/projects/{pid_a}/network", headers=headers_b)).json()
        assert body["total_accounts"] == 0
        assert body["insufficient_data"] is True
