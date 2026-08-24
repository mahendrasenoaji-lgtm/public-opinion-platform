"""Entry point API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import (
    auth,
    brief,
    copilot,
    forecast,
    governance,
    narratives,
    opinion,
    projects,
    segments,
    signals,
    surveys,
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
):
    app.include_router(r.router, prefix="/v1")
