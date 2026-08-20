"""Router copilot — kerangka Phase 1/2. Lihat CLAUDE.md §5 untuk urutan pengerjaan."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.get("")
async def index() -> dict:
    raise HTTPException(501, "Belum diimplementasikan.")
