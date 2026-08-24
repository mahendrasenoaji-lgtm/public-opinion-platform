"""Public Segments — kelompok publik dari latent class analysis.

Baca langsung dari tabel segments (Phase 1, sudah di-seed). Bukan LLM,
bukan keluaran generatif — angka statistik murni, tidak perlu AIEnvelope
(R2 cuma wajib untuk keluaran model bahasa/generatif, bukan semua statistik).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentUser, TenantSession
from app.models.measurement import Segment

router = APIRouter(prefix="/projects/{project_id}/segments", tags=["segments"])


class SegmentOut(BaseModel):
    name: str
    size_pct: Decimal
    sentiment: Decimal | None
    trust: Decimal | None
    #: Isi bebas per segmen (mis. age/geo/concern) — apa adanya dari seed/
    #: pipeline segmentasi, tidak ditegakkan skema tetap karena bisa beda
    #: per metodologi.
    profile: dict
    method: str
    entropy: Decimal | None


@router.get("", response_model=list[SegmentOut])
async def list_segments(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> list[SegmentOut]:
    """Segmen publik proyek, terurut dari yang terbesar.

    Latent class analysis, bukan LLM — lihat catatan modul. Ukuran (`size_pct`)
    dan komposisi ditentukan dari respons survei dan variabel demografis yang
    dikumpulkan dengan consent (CLAUDE.md §3: tidak ada inferensi atribut
    sensitif).
    """
    q = (
        select(Segment)
        .where(Segment.project_id == project_id)
        .order_by(Segment.size_pct.desc())
    )
    result = await session.execute(q)
    rows = result.scalars().all()

    return [
        SegmentOut(
            name=s.name,
            size_pct=s.size_pct,
            sentiment=s.sentiment,
            trust=s.trust,
            profile=s.profile,
            method=s.method,
            entropy=s.entropy,
        )
        for s in rows
    ]
