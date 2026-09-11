"""Tes middleware observability + rate limiting — app FastAPI minimal, tanpa
database (kedua middleware ini murni ASGI, tidak menyentuh Postgres).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

from app.main import install_middleware
from app.middleware.observability import RequestLoggingMiddleware
from app.middleware.ratelimit import STRICT_LIMIT_PER_WINDOW, RateLimitMiddleware


def _dummy_app() -> FastAPI:
    app = FastAPI()

    @app.get("/dummy")
    async def dummy() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/v1/auth/login")
    async def login() -> dict[str, bool]:
        return {"ok": True}

    return app


class TestRequestLogging:
    def test_menambah_header_request_id(self) -> None:
        app = _dummy_app()
        app.add_middleware(RequestLoggingMiddleware)
        client = TestClient(app)

        r = client.get("/dummy")
        assert r.status_code == 200
        assert "x-request-id" in r.headers
        assert len(r.headers["x-request-id"]) == 36  # format UUID4 dengan dash

    def test_request_id_beda_tiap_request(self) -> None:
        app = _dummy_app()
        app.add_middleware(RequestLoggingMiddleware)
        client = TestClient(app)

        id_a = client.get("/dummy").headers["x-request-id"]
        id_b = client.get("/dummy").headers["x-request-id"]
        assert id_a != id_b


class TestRateLimit:
    def test_di_bawah_limit_lolos(self) -> None:
        app = _dummy_app()
        app.add_middleware(RateLimitMiddleware, limit_per_window=3)
        client = TestClient(app)

        for _ in range(3):
            assert client.get("/dummy").status_code == 200

    def test_melebihi_limit_ditolak_429(self) -> None:
        app = _dummy_app()
        app.add_middleware(RateLimitMiddleware, limit_per_window=3)
        client = TestClient(app)

        for _ in range(3):
            client.get("/dummy")
        r = client.get("/dummy")
        assert r.status_code == 429
        assert "retry-after" in r.headers

    def test_health_tidak_pernah_dibatasi(self) -> None:
        app = _dummy_app()
        app.add_middleware(RateLimitMiddleware, limit_per_window=1)
        client = TestClient(app)

        for _ in range(10):
            assert client.get("/health").status_code == 200

    def test_path_ketat_punya_limit_terpisah_dari_limit_umum(self) -> None:
        """Endpoint auth (login/register) dibatasi lebih ketat, dan tidak
        ikut memotong jatah endpoint lain milik klien yang sama.
        """
        app = _dummy_app()
        # limit umum sengaja besar supaya beda perilakunya jelas kelihatan
        # cuma berasal dari STRICT_LIMIT_PER_WINDOW, bukan limit umum.
        app.add_middleware(RateLimitMiddleware, limit_per_window=1000)
        client = TestClient(app)

        for _ in range(STRICT_LIMIT_PER_WINDOW):
            assert client.post("/v1/auth/login").status_code == 200
        assert client.post("/v1/auth/login").status_code == 429
        # endpoint lain (limit umum) masih longgar, tidak ikut kena batas ketat
        assert client.get("/dummy").status_code == 200

    def test_klien_berbeda_tidak_saling_memotong_jatah(self) -> None:
        """Rate limit dikunci per-IP (tanpa token) -- satu klien yang habis
        jatahnya tidak boleh memblokir klien lain.
        """
        app = _dummy_app()
        app.add_middleware(RateLimitMiddleware, limit_per_window=1)
        client_a = TestClient(app, client=("10.0.0.1", 1234))
        client_b = TestClient(app, client=("10.0.0.2", 1234))

        assert client_a.get("/dummy").status_code == 200
        assert client_a.get("/dummy").status_code == 429
        # klien B pakai IP beda -> bucket beda -> belum kena limit
        assert client_b.get("/dummy").status_code == 200


class TestUrutanMiddleware:
    """Urutan tumpukan middleware seperti yang dipasang `app/main.py`.

    Dites lewat `install_middleware` yang sama persis dipakai `main.py`, bukan
    dengan menyusun ulang tumpukannya di sini -- tes yang menduplikasi urutan
    yang mau dijaganya tidak menjaga apa pun.
    """

    def test_respons_429_tetap_membawa_request_id(self) -> None:
        """Regresi 2026-09-11: rate limiter sempat dipasang di LUAR logger,
        jadi 429 di-short-circuit sebelum logger sempat jalan -- request yang
        diblokir tidak muncul di log sama sekali, padahal justru itu yang
        paling perlu terlihat (brute-force login).
        """
        app = _dummy_app()
        install_middleware(app, rate_limit_enabled=True)
        client = TestClient(app)

        for _ in range(STRICT_LIMIT_PER_WINDOW):
            assert client.post("/v1/auth/login").status_code == 200
        blocked = client.post("/v1/auth/login")

        assert blocked.status_code == 429
        assert "x-request-id" in blocked.headers, (
            "respons 429 harus tetap melewati RequestLoggingMiddleware"
        )

    def test_cors_paling_luar_rate_limit_paling_dalam(self) -> None:
        app = FastAPI()
        install_middleware(app, rate_limit_enabled=True)

        # user_middleware[0] = paling luar (Starlette membungkus dari belakang).
        urutan = [m.cls for m in app.user_middleware]
        assert urutan == [
            CORSMiddleware,
            RequestLoggingMiddleware,
            RateLimitMiddleware,
        ]

    def test_rate_limit_bisa_dimatikan_tanpa_mengubah_urutan_sisanya(self) -> None:
        app = FastAPI()
        install_middleware(app, rate_limit_enabled=False)

        urutan = [m.cls for m in app.user_middleware]
        assert urutan == [CORSMiddleware, RequestLoggingMiddleware]
