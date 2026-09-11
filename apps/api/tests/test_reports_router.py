"""Tes end-to-end endpoint report PDF (`GET /projects/{id}/reports/summary`).

`tests/test_reports.py` menguji `build_summary_pdf` sebagai fungsi murni --
tidak ada satu pun yang memanggil endpoint-nya. Celah itulah yang membuat
bug 500 di bawah lolos CI dan baru ketahuan lewat verifikasi production
2026-09-11. File ini menutupnya: httpx.AsyncClient asli terhadap Postgres
dengan role pop_app (RLS aktif), pola sama seperti test_dashboard_reads.py.
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
    """Daftar org+user baru lalu buat satu proyek. Return (headers, project_id)."""
    slug = f"test-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Report",
            "org_slug": slug,
            "full_name": "Penguji Report",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    proj = await client.post(
        "/v1/projects", json={"name": "Proyek Tes Report"}, headers=headers
    )
    assert proj.status_code == 201, proj.text
    return headers, proj.json()["id"]


async def test_proyek_tanpa_segmen_tetap_menghasilkan_pdf(client) -> None:
    """Proyek kosong bukan error -- laporannya terbit dengan 'data tidak cukup'."""
    headers, project_id = await _register_and_create_project(client)

    r = await client.get(f"/v1/projects/{project_id}/reports/summary", headers=headers)

    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


async def test_proyek_tidak_ada_balas_404_bukan_500(client) -> None:
    """Regresi 2026-09-11: `.scalar_one()` melempar NoResultFound, dan main.py
    cuma punya handler untuk ValueError -- hasilnya 500 di production.
    """
    headers, _ = await _register_and_create_project(client)

    r = await client.get(
        f"/v1/projects/{uuid.uuid4()}/reports/summary", headers=headers
    )

    assert r.status_code == 404, r.text


async def test_proyek_org_lain_balas_404_bukan_500(client) -> None:
    """RLS menyaring proyek org lain jadi nol baris, jadi jalur kodenya sama
    dengan proyek yang memang tidak ada -- dan memang HARUS sama: balasan yang
    berbeda akan membocorkan keberadaan proyek milik org lain.
    """
    _, project_org_a = await _register_and_create_project(client)
    headers_b, _ = await _register_and_create_project(client)

    r = await client.get(
        f"/v1/projects/{project_org_a}/reports/summary", headers=headers_b
    )

    assert r.status_code == 404, r.text
