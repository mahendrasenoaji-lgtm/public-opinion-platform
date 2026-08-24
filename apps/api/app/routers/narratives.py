"""Narrative Map — narasi yang beredar per proyek.

Baca langsung dari tabel narratives (Phase 1, sudah di-seed dengan label
manual). Pelabelan-oleh-LLM sungguhan (embedding + HDBSCAN + verifikasi
manusia) adalah Phase 2 — endpoint ini cuma membaca hasil yang sudah ada,
tidak menjalankan pipeline apa pun.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentUser, TenantSession
from app.models.measurement import Narrative
from app.schemas.common import SignalSource

router = APIRouter(prefix="/projects/{project_id}/narratives", tags=["narratives"])


class NarrativeOut(BaseModel):
    id: UUID
    code: str
    statement: str
    origin_source: SignalSource
    volume_pct: Decimal
    momentum_7d: Decimal
    sentiment: Decimal | None
    media_pickup: int
    unclustered_pct: Decimal
    detected_at: datetime


@router.get("", response_model=list[NarrativeOut])
async def list_narratives(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> list[NarrativeOut]:
    """Narasi proyek, terurut dari volume percakapan terbesar."""
    q = (
        select(Narrative)
        .where(Narrative.project_id == project_id)
        .order_by(Narrative.volume_pct.desc())
    )
    result = await session.execute(q)
    rows = result.scalars().all()

    return [
        NarrativeOut(
            id=n.id,
            code=n.code,
            statement=n.statement,
            origin_source=SignalSource(n.origin_source.value),
            volume_pct=n.volume_pct,
            momentum_7d=n.momentum_7d,
            sentiment=n.sentiment,
            media_pickup=n.media_pickup,
            unclustered_pct=n.unclustered_pct,
            detected_at=n.detected_at,
        )
        for n in rows
    ]
