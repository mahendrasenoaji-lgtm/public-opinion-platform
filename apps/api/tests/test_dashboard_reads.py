"""Tes end-to-end untuk endpoint baca dashboard baru: /segments, /narratives,
/opinion/geo. Sama seperti test_auth_router.py: httpx.AsyncClient asli
terhadap Postgres nyata dengan role pop_app (RLS aktif) -- bukan mock.

Data segments/narratives/metric_snapshots di sini di-INSERT langsung lewat
SQL dalam sesi yang sudah men-set app.current_org (pola sama dengan
test_tenant_isolation.py:_seed_two_orgs) -- endpoint-endpoint ini sengaja
read-only, tidak ada jalur tulis lewat API (segments/narratives memang
diisi lewat pipeline seed/ingest, bukan dibuat user).
"""

import os
import uuid
from decimal import Decimal

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


async def _register_and_create_project(client) -> tuple[str, str, str]:
    """Daftar org+user baru (SUPER_ADMIN) lalu buat satu proyek.

    Return (access_token, org_id, project_id).
    """
    slug = f"test-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Dashboard",
            "org_slug": slug,
            "full_name": "Penguji",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    proj = await client.post(
        "/v1/projects", json={"name": "Proyek Tes"}, headers=headers
    )
    assert proj.status_code == 201, proj.text
    body = proj.json()
    return token, body["org_id"], body["id"]


async def _insert_as_org(org_id: str, sql: str, params: dict) -> None:
    """INSERT langsung lewat sesi dengan app.current_org ter-set (RLS aktif),
    meniru cara pipeline seed/ingest menulis -- bukan lewat endpoint API
    (segments/narratives read-only lewat HTTP)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(DSN)
    try:
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s, s.begin():
            await s.execute(
                text("SELECT set_config('app.current_org', :o, true)"), {"o": org_id}
            )
            await s.execute(text(sql), params)
    finally:
        await engine.dispose()


async def test_segments_kosong_balas_list_kosong(client):
    token, _org_id, project_id = await _register_and_create_project(client)
    res = await client.get(
        f"/v1/projects/{project_id}/segments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == []


async def test_segments_terurut_dari_terbesar(client):
    token, org_id, project_id = await _register_and_create_project(client)
    await _insert_as_org(
        org_id,
        """INSERT INTO segments (id, org_id, project_id, name, size_pct,
           sentiment, trust, profile, method, entropy)
           VALUES (gen_random_uuid(), :org, :proj, 'Kecil', 10, 5, 50,
                   '{"age":"18-24"}', 'latent_class', 0.5),
                  (gen_random_uuid(), :org, :proj, 'Besar', 40, -10, 30,
                   '{"age":"45+"}', 'latent_class', 0.5)""",
        {"org": org_id, "proj": project_id},
    )

    res = await client.get(
        f"/v1/projects/{project_id}/segments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    names = [s["name"] for s in res.json()]
    assert names == ["Besar", "Kecil"]
    assert res.json()[0]["profile"] == {"age": "45+"}


async def test_narratives_balas_data_asli(client):
    token, org_id, project_id = await _register_and_create_project(client)
    await _insert_as_org(
        org_id,
        """INSERT INTO narratives (id, org_id, project_id, code, statement,
           origin_source, volume_pct, momentum_7d, sentiment, media_pickup,
           unclustered_pct)
           VALUES (gen_random_uuid(), :org, :proj, 'A', 'Narasi tes',
                   'SOCIAL', 12.5, 3.1, -0.4, 42, 6.2)""",
        {"org": org_id, "proj": project_id},
    )

    res = await client.get(
        f"/v1/projects/{project_id}/narratives",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body) == 1
    assert body[0]["code"] == "A"
    assert body[0]["origin_source"] == "SOCIAL"
    assert Decimal(str(body[0]["volume_pct"])) == Decimal("12.5")


async def test_geo_provinsi_n_rendah_ditandai_data_tidak_cukup(client):
    """Inti aturan CLAUDE.md §3: achieved_n < 250 -> insufficient_data, bukan
    angka dengan CI lebar. Satu provinsi n tinggi (publishable), satu n
    rendah (tidak)."""
    token, org_id, project_id = await _register_and_create_project(client)
    await _insert_as_org(
        org_id,
        """INSERT INTO metric_snapshots
           (id, org_id, project_id, metric, source, method, period_start,
            period_end, value, effective_n, province_code)
           VALUES
           (gen_random_uuid(), :org, :proj, 'poi', 'SURVEY', 'estimasi area kecil',
            '2026-01-01', '2026-01-08', 70, 900, '31'),
           (gen_random_uuid(), :org, :proj, 'trust', 'SURVEY', 'estimasi area kecil',
            '2026-01-01', '2026-01-08', 65, 900, '31'),
           (gen_random_uuid(), :org, :proj, 'approval', 'SURVEY', 'estimasi area kecil',
            '2026-01-01', '2026-01-08', 72, 900, '31'),
           (gen_random_uuid(), :org, :proj, 'poi', 'SURVEY', 'estimasi area kecil',
            '2026-01-01', '2026-01-08', 55, 80, '94')""",
        {"org": org_id, "proj": project_id},
    )

    res = await client.get(
        f"/v1/projects/{project_id}/opinion/geo",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    by_code = {p["province_code"]: p for p in res.json()}

    jakarta = by_code["31"]
    assert jakarta["poi"]["value"] == 70.0
    assert jakarta["poi"]["insufficient_data"] is False
    assert jakarta["province_name"] == "DKI Jakarta"

    papua = by_code["94"]
    assert papua["poi"]["value"] is None
    assert papua["poi"]["insufficient_data"] is True
    assert papua["poi"]["note"] is not None
