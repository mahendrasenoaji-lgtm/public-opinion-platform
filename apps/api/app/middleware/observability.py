"""Observability dasar: request ID + log terstruktur per permintaan.

Phase 4 (docs/roadmap.md) menyebut "observability: tracing, evaluasi model,
deteksi drift" sebagai item yang butuh trafik produksi nyata dulu supaya
berguna. Ini BUKAN itu — bukan APM/tracing distribusi pihak ketiga
(Datadog/Sentry/Honeycomb/dst), yang butuh keputusan vendor + akun pihak
ketiga di luar wewenang agen (CLAUDE.md §8, dan lihat batas kredensial di
docs/deployment-status.md). Ini lapisan paling minimal yang genuinely
berguna TANPA vendor: tiap request dapat ID unik yang dicetak di log DAN
dikembalikan lewat header `X-Request-ID`, supaya satu request bisa
ditelusuri lintas baris log — Render menangkap stdout sebagai log platform
tanpa konfigurasi tambahan apa pun.

Log dalam format JSON satu baris per request (bukan format bebas) supaya
bisa di-grep/di-parse kalau nanti memang dipasang log aggregator sungguhan
tanpa perlu menulis ulang formatnya.
"""

from __future__ import annotations

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Satu baris JSON log per request + header `X-Request-ID` di respons.

    Sengaja TIDAK mencatat `org_id`/`user_id`: mendekode JWT di middleware
    berarti dua jalur validasi token (di sini dan di app/deps.py) yang bisa
    berbeda perilaku diam-diam. `request_id` sudah cukup untuk korelasi;
    identitas pemanggil tetap ada di log level aplikasi/audit log
    (`app/models/governance.py:AuditLog`) yang sudah dijalankan di dalam
    request dengan sesi ter-otentikasi.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.exception(
                json.dumps(
                    {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": 500,
                        "duration_ms": duration_ms,
                    }
                )
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                }
            )
        )
        return response
