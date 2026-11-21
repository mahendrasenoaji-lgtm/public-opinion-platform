"""Graf interaksi balasan/kutipan antar akun (Phase 3).

Perhitungannya di `services/network.py`; file ini hanya merakit relasi
balasan/kutipan dari tabel mentions. Sama seperti routers/influence.py: yang
keluar dari endpoint ini adalah `author_hash`, bukan nama akun.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import and_, case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.deps import CurrentUser, Role, TenantSession, require_role
from app.models.governance import AuditLog
from app.models.measurement import SignalSource as ModelSignalSource
from app.models.signal import Mention
from app.routers.windowing import EndDate, StartDate, window
from app.services import sna
from app.services.network import InteractionEdge, NetworkReport, build
from app.services.sentiment import NEGATIVE_THRESHOLD, POSITIVE_THRESHOLD

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
    start: date | None = StartDate,
    end: date | None = EndDate,
    limit: int = Query(default=10, ge=1, le=50),
) -> NetworkOut:
    """Akun yang paling sering dibalas/dikutip akun lain pada periode tertentu.

    Baca `limitations` sebelum memakai angkanya: graf ini hanya memuat relasi
    antar akun yang KEDUANYA muncul sebagai penulis dalam data yang berhasil
    diambil. Ini bukan ukuran pengaruh kausal, kendali atas opini, atau bukti
    koordinasi antar-akun (CLAUDE.md §3).
    """
    since, until = window(days, start, end)

    # Dua kolom target berbeda (reply_to_hash, quote_of_hash) pada tabel yang
    # sama -- diambil sebagai dua query terpisah, bukan UNION di SQL, supaya
    # `kind`-nya eksplisit di sisi Python tanpa CASE WHEN yang rapuh.
    reply_rows = (
        await session.execute(
            select(Mention.author_hash, Mention.reply_to_hash).where(
                Mention.project_id == project_id,
                Mention.published_at >= since,
                Mention.published_at <= until,
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
                Mention.published_at <= until,
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


# ---------------------------------------------------------------- SNA ----
#
# Analisis jaringan lengkap (services/sna.py). Relasi diagregasi di SQL menjadi
# pasangan berbobot supaya yang masuk memori hanya (sumber, tujuan, jumlah),
# bukan satu baris per komentar.

#: Sumber konten yang dibaca. Relasi balasan/kutipan memang hanya ada di SOSIAL,
#: tapi menyebutnya eksplisit menjaga R1 bila sumber lain kelak punya relasi.
SNA_SOURCE = ModelSignalSource.SOCIAL
#: Akun per komunitas yang teksnya dibaca untuk kata dominan, dan batas teks.
TERM_AUTHORS_PER_COMMUNITY = 60
TERM_TEXT_LIMIT = 6000


class AccountMetricsOut(BaseModel):
    author_hash: str
    in_degree: int
    out_degree: int
    partners: int
    betweenness: float | None
    closeness: float | None
    pagerank: float
    eigenvector: float | None
    community: int


class CommunityOut(BaseModel):
    id: int
    size: int
    share: float
    internal_edges: int
    external_edges: int
    density: float
    top_accounts: list[str]
    contents: int
    scored: int
    sentiment_mean: float | None
    negative_share: float | None
    neutral_share: float | None
    positive_share: float | None
    top_terms: list[tuple[str, int]]


class VizNodeOut(BaseModel):
    id: str
    x: float
    y: float
    community: int
    pagerank: float
    in_degree: int
    out_degree: int


class VizEdgeOut(BaseModel):
    source: str
    target: str
    weight: int


class GraphSummaryOut(BaseModel):
    nodes: int
    original_nodes: int
    edges: int
    interactions: int
    density: float
    reciprocity: float
    components: int
    largest_component_share: float
    avg_clustering: float | None
    modularity: float | None
    communities: int


class SNAOut(BaseModel):
    source: Literal["SOCIAL"] = "SOCIAL"
    start: datetime
    end: datetime
    summary: GraphSummaryOut
    accounts: list[AccountMetricsOut]
    communities: list[CommunityOut]
    viz_nodes: list[VizNodeOut]
    viz_edges: list[VizEdgeOut]
    insufficient_data: bool
    note: str | None
    notes: list[str]
    method: str
    limitations: list[str]
    min_scored: int = sna.MIN_SCORED


class ContainerOut(BaseModel):
    container: str
    url: str | None
    commenters: int
    comments: int
    shared_share: float


class CrossAccountOut(BaseModel):
    author_hash: str
    containers: int
    comments: int


class OverlapOut(BaseModel):
    a: str
    b: str
    shared: int
    jaccard: float


class BridgesOut(BaseModel):
    source: Literal["SOCIAL"] = "SOCIAL"
    accounts: int
    containers: int
    comments: int
    cross_accounts: int
    cross_share: float
    top_containers: list[ContainerOut]
    top_cross_accounts: list[CrossAccountOut]
    overlaps: list[OverlapOut]
    insufficient_data: bool
    note: str | None
    method: str
    limitations: list[str]


def _in_window(project_id: UUID, since: datetime, until: datetime) -> list[Any]:
    return [
        Mention.project_id == project_id,
        Mention.published_at >= since,
        Mention.published_at <= until,
        Mention.author_hash.is_not(None),
    ]


#: Catatan yang ditambahkan bila sebagian relasi berasal dari id utas.
THREAD_NOTE = (
    "{n} relasi balasan diturunkan dari id utas YouTube (conversation_id = id komentar "
    "utama yang dinyatakan API) karena kolom balasan tidak terisi saat data diunggah: "
    "penulis balasan \u2192 penulis komentar utama di utas yang sama."
)


async def _thread_edges(
    session: AsyncSession, project_id: UUID, since: datetime, until: datetime
) -> list[sna.WeightedEdge]:
    """Relasi balasan dari id utas, untuk konten yang `reply_to_hash`-nya kosong.

    Data yang diunggah lewat JSON (mis. BBM Bali, Gibran) membawa
    `conversation_id` = id komentar utama (dari `parentId` YouTube) tetapi tidak
    membawa nama akun yang dibalas. Penulis komentar utama itu ada di tabel yang
    sama, jadi relasinya bisa dibaca kembali tanpa menebak dari teks. Komentar
    utama boleh terbit di luar periode; balasannya yang harus di dalam periode.
    """
    parent = aliased(Mention)
    rows = (
        await session.execute(
            select(Mention.author_hash, parent.author_hash, func.count())
            .join(
                parent,
                and_(
                    parent.project_id == Mention.project_id,
                    parent.connector == Mention.connector,
                    parent.external_id == Mention.conversation_id,
                ),
            )
            .where(
                *_in_window(project_id, since, until),
                Mention.reply_to_hash.is_(None),
                Mention.conversation_id.is_not(None),
                Mention.conversation_id != Mention.external_id,
                parent.author_hash.is_not(None),
            )
            .group_by(Mention.author_hash, parent.author_hash)
        )
    ).all()
    return [sna.WeightedEdge(str(a), str(t), "reply", int(c)) for a, t, c in rows]


async def _weighted_edges(
    session: AsyncSession, project_id: UUID, since: datetime, until: datetime
) -> tuple[list[sna.WeightedEdge], int]:
    """(relasi teragregasi, jumlah interaksi yang diturunkan dari id utas)."""
    where = _in_window(project_id, since, until)
    edges: list[sna.WeightedEdge] = []
    for col, kind in ((Mention.reply_to_hash, "reply"), (Mention.quote_of_hash, "quote")):
        rows = (
            await session.execute(
                select(Mention.author_hash, col, func.count())
                .where(*where, col.is_not(None))
                .group_by(Mention.author_hash, col)
            )
        ).all()
        edges.extend(
            sna.WeightedEdge(str(a), str(t), kind, int(c))  # type: ignore[arg-type]
            for a, t, c in rows
        )
    thread = await _thread_edges(session, project_id, since, until)
    edges.extend(thread)
    return edges, sum(e.weight for e in thread if e.source != e.target)


def _thread_note(derived: int) -> str | None:
    return THREAD_NOTE.format(n=f"{derived:,}".replace(",", ".")) if derived else None


async def _author_stats(
    session: AsyncSession, project_id: UUID, since: datetime, until: datetime
) -> dict[str, sna.AuthorStats]:
    s = Mention.sentiment
    rows = (
        await session.execute(
            select(
                Mention.author_hash,
                func.count(),
                func.count(s),
                func.coalesce(func.sum(s), 0),
                func.count(case((s < NEGATIVE_THRESHOLD, 1))),
                func.count(case((s.between(NEGATIVE_THRESHOLD, POSITIVE_THRESHOLD), 1))),
                func.count(case((s > POSITIVE_THRESHOLD, 1))),
            )
            .where(*_in_window(project_id, since, until), Mention.source == SNA_SOURCE)
            .group_by(Mention.author_hash)
        )
    ).all()
    return {
        str(a): sna.AuthorStats(
            contents=int(n), scored=int(k), sentiment_sum=float(total),
            negative=int(neg), neutral=int(neu), positive=int(pos),
        )
        for a, n, k, total, neg, neu, pos in rows
    }


async def _texts(
    session: AsyncSession,
    project_id: UUID,
    since: datetime,
    until: datetime,
    authors: list[str],
) -> dict[str, list[str]]:
    if not authors:
        return {}
    rows = (
        await session.execute(
            select(Mention.author_hash, Mention.text)
            .where(*_in_window(project_id, since, until), Mention.author_hash.in_(authors))
            .limit(TERM_TEXT_LIMIT)
        )
    ).all()
    out: dict[str, list[str]] = {}
    for a, t in rows:
        out.setdefault(str(a), []).append(str(t))
    return out


@router.get("/sna", response_model=SNAOut)
async def get_sna(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=1, le=365),
    start: date | None = StartDate,
    end: date | None = EndDate,
) -> SNAOut:
    """Social Network Analysis: sentralitas, komunitas, struktur, konten per komunitas.

    Semua angka adalah posisi struktural dalam graf yang teramati (CLAUDE.md §3);
    baca `limitations` dan `notes` sebelum memakainya.
    """
    since, until = window(days, start, end)
    edges, derived = await _weighted_edges(session, project_id, since, until)
    # Perhitungan graf memakan CPU beberapa detik pada proyek besar: jalankan di
    # thread supaya permintaan lain (dan pekerja tarik tema) tidak ikut tertahan.
    report = await asyncio.to_thread(sna.analyze, edges)
    note = _thread_note(derived)
    if note:
        report.notes.insert(0, note)

    content: dict[int, sna.CommunityContent] = {}
    if report.communities:
        stats = await _author_stats(session, project_id, since, until)
        authors: list[str] = []
        for c in report.communities:
            members = [a for a, cid in report.membership.items() if cid == c.id]
            members.sort(key=lambda a: (-(stats[a].contents if a in stats else 0), a))
            authors.extend(members[:TERM_AUTHORS_PER_COMMUNITY])
        texts = await _texts(session, project_id, since, until, authors)
        for cc in sna.summarize_communities(
            report.membership, stats, texts, [c.id for c in report.communities]
        ):
            content[cc.id] = cc

    def community_out(c: sna.CommunityInfo) -> CommunityOut:
        cc = content.get(c.id)
        return CommunityOut(
            **asdict(c),
            contents=cc.contents if cc else 0,
            scored=cc.scored if cc else 0,
            sentiment_mean=cc.sentiment_mean if cc else None,
            negative_share=cc.negative_share if cc else None,
            neutral_share=cc.neutral_share if cc else None,
            positive_share=cc.positive_share if cc else None,
            top_terms=cc.top_terms if cc else [],
        )

    return SNAOut(
        start=since,
        end=until,
        summary=GraphSummaryOut(**asdict(report.summary)),
        accounts=[AccountMetricsOut(**asdict(a)) for a in report.accounts],
        communities=[community_out(c) for c in report.communities],
        viz_nodes=[VizNodeOut(**asdict(v)) for v in report.viz_nodes],
        viz_edges=[VizEdgeOut(**asdict(e)) for e in report.viz_edges],
        insufficient_data=report.insufficient_data,
        note=report.note,
        notes=report.notes,
        method=report.method,
        limitations=report.limitations,
    )


@router.get("/bridges", response_model=BridgesOut)
async def get_bridges(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=1, le=365),
    start: date | None = StartDate,
    end: date | None = EndDate,
) -> BridgesOut:
    """Graf akun–unggahan: unggahan dengan komentator terbanyak, akun lintas
    unggahan, dan tumpang-tindih komentator antar-unggahan."""
    since, until = window(days, start, end)
    yt = func.substring(Mention.url, r"[?&]v=([A-Za-z0-9_-]{11})")
    tt = func.substring(Mention.url, r"tiktok\.com/.*/?video/([0-9]+)")
    container = func.coalesce(literal("yt:") + yt, literal("tt:") + tt)
    rows = (
        await session.execute(
            select(Mention.author_hash, container.label("c"), func.count())
            .where(
                *_in_window(project_id, since, until),
                Mention.source == SNA_SOURCE,
                Mention.url.is_not(None),
            )
            .group_by(Mention.author_hash, "c")
        )
    ).all()
    report = sna.bridges((str(a), str(c), int(n)) for a, c, n in rows if c)
    return BridgesOut(
        accounts=report.accounts,
        containers=report.containers,
        comments=report.comments,
        cross_accounts=report.cross_accounts,
        cross_share=report.cross_share,
        top_containers=[ContainerOut(**asdict(c)) for c in report.top_containers],
        top_cross_accounts=[CrossAccountOut(**asdict(a)) for a in report.top_cross_accounts],
        overlaps=[OverlapOut(**asdict(o)) for o in report.overlaps],
        insufficient_data=report.insufficient_data,
        note=report.note,
        method=report.method,
        limitations=report.limitations,
    )


@router.get(
    "/export",
    dependencies=[Depends(require_role(Role.DATA_ANALYST))],
    response_class=Response,
)
async def export_network(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    format: Literal["gexf", "nodes", "edges"] = "gexf",
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=1, le=365),
    start: date | None = StartDate,
    end: date | None = EndDate,
) -> Response:
    """Ekspor graf untuk Gephi (GEXF, atau CSV simpul/relasi).

    Hanya hash akun dan angka relasi, tanpa teks konten. Peran minimal
    DATA_ANALYST; setiap ekspor dicatat di audit log.
    """
    since, until = window(days, start, end)
    edges, _derived = await _weighted_edges(session, project_id, since, until)
    report = await asyncio.to_thread(sna.analyze, edges)
    membership = report.membership
    if format == "gexf":
        body = await asyncio.to_thread(sna.to_gexf, edges, membership)
        media, ext = "application/gexf+xml", "gexf"
    else:
        nodes_csv, edges_csv = await asyncio.to_thread(sna.to_csv, edges, membership)
        body = nodes_csv if format == "nodes" else edges_csv
        media, ext = "text/csv; charset=utf-8", "csv"
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="network_export",
            entity="project",
            entity_id=project_id,
            metadata_={
                "format": format,
                "start": since.isoformat(),
                "end": until.isoformat(),
                "edges": len(edges),
            },
        )
    )
    await session.flush()
    name = f"jaringan-{since:%Y%m%d}-{until:%Y%m%d}-{format}.{ext}"
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
