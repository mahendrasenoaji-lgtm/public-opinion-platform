"""Estimasi keterpaparan akun dalam percakapan (Phase 3).

Perhitungannya di `services/influence.py`; file ini hanya merakit rekap
aktivitas per akun dari tabel mentions.

Yang keluar dari endpoint ini adalah `author_hash`, bukan nama akun — sama
seperti yang masuk. Menerjemahkannya kembali ke identitas adalah keputusan
produk yang belum diambil, dan tidak boleh terjadi diam-diam lewat sini.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.deps import CurrentUser, TenantSession
from app.models.signal import Mention
from app.schemas.common import SignalSource
from app.services.influence import AuthorActivity, estimate

router = APIRouter(prefix="/projects/{project_id}/influence", tags=["influence"])

DEFAULT_WINDOW_DAYS = 30


class InfluenceRow(BaseModel):
    author_hash: str
    posts: int
    engagement: int
    post_share_pct: float
    engagement_share_pct: float
    amplification: float
    influence_estimate: float


class InfluenceOut(BaseModel):
    top: list[InfluenceRow]
    total_authors: int
    ranked_authors: int
    total_posts: int
    total_engagement: int
    concentration_top10_pct: float
    method: str
    source: SignalSource = SignalSource.SOCIAL
    insufficient_data: bool = False
    note: str | None = None
    limitations: list[str] = []


@router.get("", response_model=InfluenceOut)
async def get_influence(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=50),
) -> InfluenceOut:
    """Akun dengan keterpaparan terbesar pada periode tertentu.

    Baca `limitations` di respons sebelum memakai angkanya: yang diukur adalah
    porsi percakapan dan keterlibatan, bukan apakah ada orang yang berubah
    pikiran. Modul ini tidak menyimpulkan koordinasi antar-akun — pola yang
    sama muncul dari kampanye terkoordinasi dan dari orang-orang yang membaca
    berita yang sama pagi itu, dan data ini tidak bisa memisahkannya.
    """
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        await session.execute(
            select(
                Mention.author_hash,
                func.count().label("posts"),
                func.coalesce(func.sum(Mention.engagement), 0).label("engagement"),
            )
            .where(
                Mention.project_id == project_id,
                Mention.published_at >= since,
                Mention.author_hash.is_not(None),
            )
            .group_by(Mention.author_hash)
        )
    ).all()

    report = estimate(
        [
            AuthorActivity(
                author_hash=str(r.author_hash),
                posts=int(r.posts),
                engagement=int(r.engagement),
            )
            for r in rows
        ],
        limit=limit,
    )

    return InfluenceOut(
        top=[
            InfluenceRow(
                author_hash=e.author_hash,
                posts=e.posts,
                engagement=e.engagement,
                post_share_pct=e.post_share_pct,
                engagement_share_pct=e.engagement_share_pct,
                amplification=e.amplification,
                influence_estimate=e.influence_estimate,
            )
            for e in report.top
        ],
        total_authors=report.total_authors,
        ranked_authors=report.ranked_authors,
        total_posts=report.total_posts,
        total_engagement=report.total_engagement,
        concentration_top10_pct=report.concentration_top10_pct,
        method=report.method,
        insufficient_data=report.insufficient_data,
        note=report.note,
        limitations=report.limitations,
    )
