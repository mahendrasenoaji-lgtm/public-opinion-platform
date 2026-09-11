"""Entry point API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.middleware.observability import RequestLoggingMiddleware
from app.middleware.ratelimit import RateLimitMiddleware
from app.routers import (
    alerts,
    auth,
    brief,
    copilot,
    forecast,
    governance,
    impact,
    influence,
    narratives,
    network,
    opinion,
    projects,
    reports,
    risk,
    segments,
    signals,
    surveys,
    topics,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="AI Public Opinion Platform",
    version="0.1.0",
    description=(
        "Platform intelligence opini publik. Setiap metrik membawa sumber dan "
        "metodenya; setiap keluaran AI membawa bukti dan batasannya."
    ),
    lifespan=lifespan,
)

# Urutan add_middleware PENTING: Starlette membungkus dari yang terakhir
# ditambahkan ke luar (yang terakhir = paling luar). CORSMiddleware HARUS
# paling luar supaya respons apa pun dari middleware di dalamnya --
# termasuk 429 dari RateLimitMiddleware -- tetap membawa header CORS;
# kalau tidak, browser akan memblokir frontend membaca pesan errornya
# sendiri (lihat app/middleware/ratelimit.py untuk batasan rate limit-nya).
app.add_middleware(RequestLoggingMiddleware)
if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    # Guard di AIEnvelope dan services memakai ValueError. Kembalikan 422 dengan
    # pesan aslinya: pesannya memang ditulis untuk dibaca manusia.
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.env}


for r in (
    auth,
    projects,
    surveys,
    opinion,
    signals,
    forecast,
    copilot,
    governance,
    segments,
    narratives,
    brief,
    risk,
    topics,
    influence,
    impact,
    alerts,
    network,
    reports,
):
    app.include_router(r.router, prefix="/v1")
