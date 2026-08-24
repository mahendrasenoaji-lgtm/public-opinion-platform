"""Tes end-to-end untuk /auth/register, /auth/login, /auth/refresh lewat
HTTP asli (httpx.AsyncClient + ASGITransport), terhadap Postgres nyata
dengan role pop_app (RLS aktif) — bukan mock, bukan superuser.

Ini persis kelas bug yang lolos sebelum sesi 2026-08-24: ketiga endpoint
ini query/INSERT tanpa app.current_org ter-set, kena FORCE ROW LEVEL
SECURITY, dan gagal (senyap untuk SELECT, keras untuk INSERT). Tes dengan
superuser TIDAK akan menangkap ini — RLS diabaikan untuk superuser, sama
seperti peringatan di test_tenant_isolation.py. Harus pop_app.

Butuh database nyata (docker compose up db, lalu buat+migrasi database
pop_test — lihat Makefile target `test-db`).
"""

import os
import uuid

import pytest

DSN = os.getenv("TEST_DATABASE_URL_APP")

# Settings() di-cache (lru_cache) begitu pertama kali dipanggil siapa pun —
# harus di-set SEBELUM app.main diimpor supaya engine terhubung ke
# database tes, bukan database dev.
if DSN:
    os.environ["DATABASE_URL"] = DSN
    # Nilai sama dengan test_auth_service.py: JWT_SECRET di-cache lewat
    # get_settings() (lru_cache) begitu dipanggil siapa pun lebih dulu di
    # sesi pytest yang sama — kalau beda, tes lain yang hardcode nilai ini
    # untuk verifikasi manual (test_access_token_bisa_didecode) akan gagal.
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")

# loop_scope="session": app.db.engine dibuat sekali di level modul (bukan
# per-request), terikat ke event loop yang aktif saat pertama kali dipakai.
# pytest-asyncio default-nya function-scoped (loop baru tiap tes) — begitu
# tes kedua jalan di loop baru, pool asyncpg dari tes pertama jadi orphan
# ("Event loop is closed"). test_tenant_isolation.py tidak kena ini karena
# fixture-nya bikin engine baru tiap tes sendiri; di sini enginenya punya
# app (lewat app.db, bukan fixture kita), jadi loop-nya yang disamakan.
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


def _register_body(
    slug: str, *, email: str | None = None, password: str = "PasswordAsli123"
) -> dict:
    return {
        "org_name": "Org Tes",
        "org_slug": slug,
        "full_name": "Penguji",
        "email": email or f"{slug}@example.com",
        "password": password,
    }


def _unique_slug() -> str:
    return f"test-org-{uuid.uuid4().hex[:10]}"


async def test_register_lalu_login_berhasil(client):
    slug = _unique_slug()
    password = "SangatRahasia123"
    email = f"{slug}@example.com"

    reg = await client.post(
        "/v1/auth/register", json=_register_body(slug, email=email, password=password)
    )
    assert reg.status_code == 201, reg.text
    reg_body = reg.json()
    assert reg_body["access_token"]
    assert reg_body["refresh_token"]

    login = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    assert login.json()["access_token"]


async def test_login_password_salah_ditolak_401(client):
    slug = _unique_slug()
    email = f"{slug}@example.com"
    await client.post(
        "/v1/auth/register", json=_register_body(slug, email=email, password="PasswordAsli123")
    )

    res = await client.post("/v1/auth/login", json={"email": email, "password": "password-salah"})
    assert res.status_code == 401


async def test_login_email_tidak_terdaftar_ditolak_401(client):
    res = await client.post(
        "/v1/auth/login",
        json={"email": f"tidak-ada-{uuid.uuid4().hex[:8]}@example.com", "password": "apa saja"},
    )
    assert res.status_code == 401


async def test_register_slug_duplikat_ditolak_409(client):
    slug = _unique_slug()
    first = await client.post(
        "/v1/auth/register", json=_register_body(slug, email=f"{slug}-1@example.com")
    )
    assert first.status_code == 201

    second = await client.post(
        "/v1/auth/register", json=_register_body(slug, email=f"{slug}-2@example.com")
    )
    assert second.status_code == 409


async def test_refresh_mengembalikan_pasangan_token_baru(client):
    slug = _unique_slug()
    reg = await client.post("/v1/auth/register", json=_register_body(slug))
    refresh_token = reg.json()["refresh_token"]

    res = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert res.status_code == 200, res.text
    assert res.json()["access_token"]


async def test_refresh_dengan_token_tidak_valid_ditolak_401(client):
    res = await client.post("/v1/auth/refresh", json={"refresh_token": "bukan-token-jwt-valid"})
    assert res.status_code == 401


async def test_refresh_dengan_access_token_ditolak_401(client):
    """Access token bukan refresh token — decode_refresh_token() harus menolaknya."""
    slug = _unique_slug()
    reg = await client.post("/v1/auth/register", json=_register_body(slug))
    access_token = reg.json()["access_token"]

    res = await client.post("/v1/auth/refresh", json={"refresh_token": access_token})
    assert res.status_code == 401
