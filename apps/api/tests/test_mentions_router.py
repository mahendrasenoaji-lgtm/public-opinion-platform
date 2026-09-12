"""Tes end-to-end `GET /projects/{id}/mentions` -- daftar item mentah untuk
validasi manual (akuntabilitas riset), ditambahkan 2026-09-11.

httpx.AsyncClient asli terhadap Postgres dengan role pop_app (RLS aktif),
pola sama seperti test_dashboard_reads.py / test_reports_router.py. Data
dimasukkan lewat POST /signals/ingest sungguhan (bukan INSERT SQL langsung)
supaya `url` ikut teruji lewat pipeline penuh, bukan cuma lewat ORM.
"""

import os
import uuid

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


async def _register_and_create_project(client) -> tuple[dict[str, str], str]:
    slug = f"test-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Mentions",
            "org_slug": slug,
            "full_name": "Penguji Mentions",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    proj = await client.post(
        "/v1/projects", json={"name": "Proyek Tes Mentions"}, headers=headers
    )
    assert proj.status_code == 201, proj.text
    return headers, proj.json()["id"]


async def _ingest(client, project_id: str, headers: dict[str, str], **item_overrides):
    item = {
        "external_id": f"ext-{uuid.uuid4().hex[:12]}",
        "text": "opini warga tentang kebijakan ini cukup panjang untuk lolos deteksi bahasa",
        "published_at": "2026-09-10T12:00:00Z",
    }
    item.update(item_overrides)
    r = await client.post(
        f"/v1/projects/{project_id}/signals/ingest",
        json={"connector": "manual", "source": "MEDIA", "items": [item]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["stored"] == 1, r.text
    return item


async def test_url_tersimpan_dan_terbaca_lewat_endpoint(client) -> None:
    headers, project_id = await _register_and_create_project(client)
    await _ingest(client, project_id, headers, url="https://contoh.id/artikel/asli")

    r = await client.get(f"/v1/projects/{project_id}/mentions", headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["url"] == "https://contoh.id/artikel/asli"
    assert body[0]["source_url"] == "https://contoh.id/artikel/asli"
    assert body[0]["source_url_origin"] == "kolom_url"


async def test_item_lama_tanpa_url_tetap_dapat_tautan_dari_guid(client) -> None:
    """Item bergaya RSS lama: `url` kosong, guid berisi permalink artikel.

    `url` sengaja tetap None di respons -- keadaan tabel harus tetap terbaca
    apa adanya; yang terisi adalah `source_url` beserta asal-usulnya.
    """
    headers, project_id = await _register_and_create_project(client)
    permalink = "https://www.antaranews.com/berita/999/karhutla-habitat-gajah-sumsel"
    await _ingest(client, project_id, headers, external_id=permalink)

    r = await client.get(f"/v1/projects/{project_id}/mentions", headers=headers)

    assert r.status_code == 200, r.text
    row = r.json()[0]
    assert row["url"] is None
    assert row["source_url"] == permalink
    assert row["source_url_origin"] == "guid_feed"


async def test_tanpa_url_balas_none_bukan_string_kosong(client) -> None:
    headers, project_id = await _register_and_create_project(client)
    await _ingest(client, project_id, headers)  # external_id "ext-..." bukan URL

    r = await client.get(f"/v1/projects/{project_id}/mentions", headers=headers)

    assert r.status_code == 200, r.text
    row = r.json()[0]
    assert row["url"] is None
    # Guid-nya bukan URL, jadi tidak ada yang bisa dipulihkan -- dan tidak ada
    # yang ditebak. Baris ini tetap "tidak ada URL sumber" di UI.
    assert row["source_url"] is None
    assert row["source_url_origin"] is None


async def test_filter_source_hanya_mengembalikan_sumber_diminta(client) -> None:
    headers, project_id = await _register_and_create_project(client)
    await client.post(
        f"/v1/projects/{project_id}/signals/ingest",
        json={
            "connector": "manual",
            "source": "SOCIAL",
            "items": [
                {
                    "external_id": f"soc-{uuid.uuid4().hex[:8]}",
                    "text": "komentar warganet soal isu ini yang cukup panjang untuk lolos deteksi",
                    "published_at": "2026-09-10T12:00:00Z",
                }
            ],
        },
        headers=headers,
    )
    await _ingest(client, project_id, headers)  # MEDIA default

    r = await client.get(
        f"/v1/projects/{project_id}/mentions",
        params={"source": "SOCIAL"},
        headers=headers,
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["source"] == "SOCIAL"


async def test_urutan_terbaru_dulu_dan_limit_dihormati(client) -> None:
    headers, project_id = await _register_and_create_project(client)
    await _ingest(client, project_id, headers, published_at="2026-09-08T12:00:00Z")
    await _ingest(client, project_id, headers, published_at="2026-09-10T12:00:00Z")

    r = await client.get(
        f"/v1/projects/{project_id}/mentions",
        params={"limit": 1},
        headers=headers,
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["published_at"].startswith("2026-09-10")


async def test_isolasi_tenant_org_lain_tidak_terlihat(client) -> None:
    """RLS harus menyaring mention org lain -- org B tidak boleh melihat
    satu pun mention milik org A lewat endpoint ini.
    """
    headers_a, project_a = await _register_and_create_project(client)
    await _ingest(client, project_a, headers_a, url="https://contoh.id/rahasia-org-a")

    headers_b, _ = await _register_and_create_project(client)

    r = await client.get(f"/v1/projects/{project_a}/mentions", headers=headers_b)

    assert r.status_code == 200, r.text
    assert r.json() == []
