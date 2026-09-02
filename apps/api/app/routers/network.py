"""Graf interaksi balasan/kutipan antar akun (Phase 3).

Perhitungannya di `services/network.py`; file ini hanya merakit relasi
balasan/kutipan dari tabel mentions. Sama seperti routers/influence.py: yang
keluar dari endpoint ini adalah `author_hash`, bukan nama akun.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentUser, TenantSession
from app.models.signal import Mention
from app.services.network import InteractionEdge, NetworkReport, build

router = APIRouter(prefix="/projects/{project_id}/network", tags=["network"])

DEFAULT_WINDOW_DAYS = 30


class AccountPositionOut(BaseModel):
    author_hash: str
    replies_received: int
    quotes_received: int
    in_degree: int
    distinct_sources: int


class NetworkOut(BaseModel):
    top: list[AccountPositionOut]
    total_accounts: int
    total_edges: int
    method: str
    insufficient_data: bool = False
    note: str | None = None
    limitations: list[str] = []


def _report_to_out(report: NetworkReport) -> NetworkOut:
    return NetworkOut(
        top=[
            AccountPositionOut(
                author_hash=p.author_hash,
                replies_received=p.replies_received,
                quotes_received=p.quotes_received,
                in_degree=p.in_degree,
                distinct_sources=p.distinct_sources,
            )
            for p in report.top
        ],
        total_accounts=report.total_accounts,
        total_edges=report.total_edges,
        method=report.method,
        insufficient_data=report.insufficient_data,
        note=report.note,
        limitations=report.limitations,
    )


@router.get("", response_model=NetworkOut)
async def get_network(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=50),
) -> NetworkOut:
    """Akun yang paling sering dibalas/dikutip akun lain pada periode tertentu.

    Baca `limitations` sebelum memakai angkanya: graf ini hanya memuat relasi
    antar akun yang KEDUANYA muncul sebagai penulis dalam data yang berhasil
    diambil. Ini bukan ukuran pengaruh kausal, kendali atas opini, atau bukti
    koordinasi antar-akun (CLAUDE.md §3).
    """
    since = datetime.now(UTC) - timedelta(days=days)

    # Dua kolom target berbeda (reply_to_hash, quote_of_hash) pada tabel yang
    # sama -- diambil sebagai dua query terpisah, bukan UNION di SQL, supaya
    # `kind`-nya eksplisit di sisi Python tanpa CASE WHEN yang rapuh.
    reply_rows = (
        await session.execute(
            select(Mention.author_hash, Mention.reply_to_hash).where(
                Mention.project_id == project_id,
                Mention.published_at >= since,
                Mention.author_hash.is_not(None),
                Mention.reply_to_hash.is_not(None),
            )
        )
    ).all()
    quote_rows = (
        await session.execute(
            select(Mention.author_hash, Mention.quote_of_hash).where(
                Mention.project_id == project_id,
                Mention.published_at >= since,
                Mention.author_hash.is_not(None),
                Mention.quote_of_hash.is_not(None),
            )
        )
    ).all()

    edges = [
        InteractionEdge(str(r.author_hash), str(r.reply_to_hash), "reply") for r in reply_rows
    ] + [InteractionEdge(str(r.author_hash), str(r.quote_of_hash), "quote") for r in quote_rows]

    report = build(edges, limit=limit)
    return _report_to_out(report)
