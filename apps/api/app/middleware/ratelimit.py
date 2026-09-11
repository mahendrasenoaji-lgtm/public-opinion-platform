"""Rate limiting per tenant — Phase 4, versi minimal (docs/roadmap.md).

docs/progress.md mencatat item ini sebagai "menyusul API publik" — makna
aslinya: rate limiting jadi PENTING begitu API dibuka ke pihak luar yang
tidak dikenal. Belum ada API publik, tapi endpoint yang sudah ada (auth,
ingest) tetap bisa disalahgunakan sekarang (brute-force login, spam
registrasi, banjir ingest) — jadi versi minimal dipasang lebih awal,
bukan menunggu.

**Batasan yang harus dibaca sebelum mempercayai angkanya**: penghitung ini
in-memory per proses (dict Python biasa), BUKAN Redis/terdistribusi —
`redis` sudah jadi dependency proyek (`config.py:redis_url`) tapi belum
pernah benar-benar dipakai di mana pun, dan menyambungkannya butuh
instance Redis sungguhan yang belum ter-provisioning di Render (keputusan
infra, bukan cuma kode). Konsekuensinya:
- Reset ke nol tiap kali proses restart/redeploy — bukan bug, cuma sifat
  in-memory.
- Kalau nanti Render dijalankan lebih dari satu instance (workers>1 atau
  autoscale), tiap instance punya hitungannya sendiri-sendiri — limit
  efektif jadi (limit x jumlah instance), bukan limit terpadu.
- Cukup untuk kondisi sekarang (Render free tier, satu instance, tanpa
  proses `uvicorn --workers`) tapi harus diganti backend Redis sebelum
  proyek ini benar-benar diskalakan horizontal atau dibuka jadi API publik.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.deps import decode_token

#: Jendela geser 60 detik. Nilai default cukup longgar untuk pemakaian
#: normal satu tenant (dashboard yang di-refresh berkali-kali, batch ingest
#: kecil) tapi tetap membatasi penyalahgunaan sekali sesi (brute-force
#: login berulang, script yang lupa nge-throttle diri sendiri).
WINDOW_SECONDS = 60.0
DEFAULT_LIMIT_PER_WINDOW = 120

#: Endpoint tanpa kredensial yang paling rawan disalahgunakan (brute-force,
#: spam registrasi) dapat batas lebih ketat, dikunci per-IP karena belum
#: ada token untuk dijadikan kunci per-tenant.
STRICT_PATHS = {"/v1/auth/login", "/v1/auth/register"}
STRICT_LIMIT_PER_WINDOW = 10

#: Tidak pernah dibatasi — health check dipanggil platform (Render) sendiri
#: di luar kendali pengguna, dan dokumentasi API harus selalu bisa dibuka.
EXEMPT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}


def _client_key(request: Request) -> str:
    """Kunci pembatas: org_id kalau token valid, kalau tidak IP klien.

    Dekode token best-effort — TIDAK menolak request di sini kalau token
    tidak ada/tidak valid (itu tetap tugas `app/deps.py` di endpoint
    tujuan). Kegagalan decode di sini cuma berarti "pakai kunci IP",
    bukan 401.
    """
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            principal = decode_token(auth[7:])
            return f"org:{principal.org_id}"
        except Exception:  # noqa: BLE001 — best-effort, bukan lapisan otentikasi
            pass
    client = request.client
    return f"ip:{client.host}" if client else "ip:unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app: ASGIApp, *, limit_per_window: int = DEFAULT_LIMIT_PER_WINDOW
    ) -> None:
        super().__init__(app)
        self.limit_per_window = limit_per_window
        #: key -> deque timestamp permintaan dalam WINDOW_SECONDS terakhir.
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _check(self, key: str, limit: int) -> tuple[bool, int]:
        now = time.monotonic()
        hits = self._hits[key]
        cutoff = now - WINDOW_SECONDS
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = max(1, round(WINDOW_SECONDS - (now - hits[0])))
            return False, retry_after
        hits.append(now)
        return True, 0

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path in EXEMPT_PATHS:
            return await call_next(request)

        key = _client_key(request)
        limit = STRICT_LIMIT_PER_WINDOW if path in STRICT_PATHS else self.limit_per_window
        # Endpoint ketat dikunci per-kombinasi path+kunci supaya limit login
        # tidak ikut memotong jatah endpoint lain milik tenant yang sama.
        bucket_key = f"{path}:{key}" if path in STRICT_PATHS else key

        allowed, retry_after = self._check(bucket_key, limit)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        "Terlalu banyak permintaan dalam waktu singkat. "
                        f"Coba lagi dalam {retry_after} detik."
                    )
                },
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
