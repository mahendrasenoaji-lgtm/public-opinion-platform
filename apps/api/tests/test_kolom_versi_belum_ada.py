"""Database yang BELUM menjalankan migrasi kolom versi penilai (2026-10-12).

Terjadi sungguhan di production pada hari kodenya tayang: setiap sumber yang
punya item baru gagal disimpan. Yang dijaga di sini: tanpa kolom itu konten
tetap tersimpan, ringkasan tetap terbit, dan penilaian ulang menolak dengan
pesan yang menyebut obatnya.

Tes ini MENGHAPUS lalu memulihkan tiga kolom di database tes (lewat
ADMIN_DATABASE_URL, karena pop_app tidak berhak DDL), jadi dilewati kalau
salah satu DSN tidak ada.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

DSN = os.getenv("TEST_DATABASE_URL_APP")
ADMIN_DSN = os.getenv("ADMIN_DATABASE_URL")

if DSN:
    os.environ["DATABASE_URL"] = DSN
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")

pytestmark = pytest.mark.asyncio(loop_scope="session")

_DROP = (
    "ALTER TABLE mentions DROP COLUMN IF EXISTS sentiment_model, "
    "DROP COLUMN IF EXISTS sentiment_alt, DROP COLUMN IF EXISTS sentiment_alt_model"
)
_RESTORE = (
    "ALTER TABLE mentions ADD COLUMN IF NOT EXISTS sentiment_model text, "
    "ADD COLUMN IF NOT EXISTS sentiment_alt numeric(4,3), "
    "ADD COLUMN IF NOT EXISTS sentiment_alt_model text"
)


@pytest.fixture
async def client():
    if not DSN or not ADMIN_DSN:
        pytest.skip("TEST_DATABASE_URL_APP / ADMIN_DATABASE_URL tidak diset")

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def tanpa_kolom_versi(client):
    import psycopg

    assert ADMIN_DSN
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        conn.execute(_DROP)
    try:
        yield
    finally:
        with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
            conn.execute(_RESTORE)


async def _new_project(client) -> tuple[dict[str, str], str]:
    slug = f"kol-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Kolom",
            "org_slug": slug,
            "full_name": "Penguji Kolom",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Kolom"}, headers=headers)
    assert proj.status_code == 201, proj.text
    return headers, proj.json()["id"]


def _items(n: int) -> list[dict]:
    return [
        {
            "external_id": uuid.uuid4().hex,
            "text": f"Program gagal dan mengecewakan warga nomor {i}",
            "published_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        }
        for i in range(n)
    ]


async def test_konten_tetap_tersimpan_dan_ringkasan_tetap_terbit(
    client, tanpa_kolom_versi
) -> None:
    headers, pid = await _new_project(client)
    r = await client.post(
        f"/v1/projects/{pid}/signals/ingest",
        json={"source": "MEDIA", "connector": "manual_media", "items": _items(35)},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] == 35
    assert any("Versi penilai tidak tercatat" in c for c in body["caveats"])

    summary = await client.get(
        f"/v1/projects/{pid}/signals/summary", params={"source": "MEDIA"}, headers=headers
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["sentiment"]["value"] < 0
    assert summary.json()["sentiment_revised"] is None


async def test_penilaian_ulang_menolak_dengan_obatnya(client, tanpa_kolom_versi) -> None:
    headers, pid = await _new_project(client)
    r = await client.post(f"/v1/projects/{pid}/signals/rescore", headers=headers)
    assert r.status_code == 409
    assert "BAGIAN A" in r.json()["detail"]


async def test_sesudah_migrasi_versi_tercatat_lagi(client) -> None:
    """Penjaga urutan: fixture di atas benar-benar memulihkan kolomnya."""
    headers, pid = await _new_project(client)
    r = await client.post(
        f"/v1/projects/{pid}/signals/ingest",
        json={"source": "MEDIA", "connector": "manual_media", "items": _items(2)},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert not any("Versi penilai" in c for c in r.json()["caveats"])
