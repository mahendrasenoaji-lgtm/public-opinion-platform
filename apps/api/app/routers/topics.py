"""Tema percakapan — penemuan dan pembacaan (Phase 2).

Penemuan tema adalah operasi yang MENULIS: ia mengganti isi tabel `topics`
proyek dan menetapkan `topic_id` pada mentions. Karena itu ia POST dengan
peran minimal RESEARCHER, bukan GET yang diam-diam mengubah keadaan.

Hasil sebelumnya diganti seluruhnya, bukan ditambah. Alasannya: tema adalah
partisi dari korpus pada satu titik waktu. Menggabungkan hasil dua kali
penjalanan menghasilkan tema yang tumpang tindih dan volume yang dihitung dua
kali — angka yang terlihat lebih kaya sambil kehilangan artinya.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import delete, select, update

from app.deps import CurrentUser, Role, TenantSession, require_role
from app.models.governance import AuditLog
from app.models.signal import Mention, Topic
from app.schemas.common import SignalSource
from app.services import topics as topics_svc

router = APIRouter(prefix="/projects/{project_id}/topics", tags=["topics"])

DEFAULT_WINDOW_DAYS = 30


class TopicOut(BaseModel):
    id: UUID
    label: str
    keywords: list[str]
    volume: int
    share_pct: float | None = None
    coherence: float | None = None
    sentiment: float | None = None
    scored: int = 0
    momentum_pct: float | None = None
    source: SignalSource = SignalSource.SOCIAL


class DiscoveryResult(BaseModel):
    topics: list[TopicOut]
    n_analysed: int
    unclustered: int
    unclustered_pct: float
    method: str
    insufficient_data: bool = False
    note: str | None = None
    limitations: list[str] = []


@router.post(
    "/discover",
    response_model=DiscoveryResult,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
    status_code=status.HTTP_200_OK,
)
async def discover_topics(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=1, le=365),
    min_cluster_size: int = Query(default=topics_svc.DEFAULT_MIN_CLUSTER_SIZE, ge=2, le=100),
) -> DiscoveryResult:
    """Temukan tema dari percakapan pada jendela waktu tertentu.

    Sentimen per tema dihitung dari mention yang BISA dinilai saja, dan
    `scored` dilaporkan di sebelahnya supaya pembaca tahu penyebutnya. Tema
    dengan `scored` kecil punya sentimen yang tidak layak dibaca sebagai sikap
    publik terhadap tema itu.
    """
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        (
            await session.execute(
                select(Mention)
                .where(Mention.project_id == project_id, Mention.published_at >= since)
                .order_by(Mention.published_at)
            )
        )
        .scalars()
        .all()
    )

    result = topics_svc.discover(
        [r.text for r in rows], min_cluster_size=min_cluster_size
    )

    # Hasil lama dibuang lebih dulu — lihat catatan modul soal kenapa diganti,
    # bukan ditambah. topic_id pada mentions ikut dikosongkan supaya tidak ada
    # yang menunjuk ke tema yang sudah tidak ada.
    await session.execute(
        update(Mention).where(Mention.project_id == project_id).values(topic_id=None)
    )
    await session.execute(delete(Topic).where(Topic.project_id == project_id))

    if result.insufficient_data:
        return DiscoveryResult(
            topics=[],
            n_analysed=result.n,
            unclustered=len(result.unclustered_indexes),
            unclustered_pct=result.unclustered_pct,
            method=result.method,
            insufficient_data=True,
            note=result.note,
        )

    volumes = {str(i): c.size for i, c in enumerate(result.clusters)}
    shares = topics_svc.share_of_voice(volumes)

    out: list[TopicOut] = []
    for i, cluster in enumerate(result.clusters):
        topic = Topic(
            org_id=user.org_id,
            project_id=project_id,
            label=cluster.label,
            keywords=cluster.keywords,
            volume=cluster.size,
        )
        session.add(topic)
        await session.flush()

        members = [rows[j] for j in cluster.member_indexes]
        for mention in members:
            mention.topic_id = topic.id

        scored = [float(m.sentiment) for m in members if m.sentiment is not None]
        out.append(
            TopicOut(
                id=topic.id,
                label=cluster.label,
                keywords=cluster.keywords,
                volume=cluster.size,
                share_pct=shares.get(str(i)),
                coherence=cluster.coherence,
                sentiment=round(sum(scored) / len(scored), 3) if scored else None,
                scored=len(scored),
                source=SignalSource(members[0].source.value) if members else SignalSource.SOCIAL,
            )
        )

    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="discover",
            entity="topics",
            metadata_={
                "project_id": str(project_id),
                "topics": str(len(out)),
                "method": result.method,
            },
        )
    )

    return DiscoveryResult(
        topics=out,
        n_analysed=result.n,
        unclustered=len(result.unclustered_indexes),
        unclustered_pct=result.unclustered_pct,
        method=result.method,
        limitations=result.limitations,
    )


@router.get("", response_model=list[TopicOut])
async def list_topics(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> list[TopicOut]:
    """Tema hasil penjalanan terakhir, terurut dari yang terbesar.

    Momentum dihitung dengan membandingkan volume tema pada tujuh hari terakhir
    dengan tujuh hari sebelumnya. None berarti tema itu tidak ada pada periode
    pembanding — pertumbuhan dari nol tidak punya persentase yang bermakna
    (services/topics.py:momentum).
    """
    rows = (
        (
            await session.execute(
                select(Topic)
                .where(Topic.project_id == project_id)
                .order_by(Topic.volume.desc())
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return []

    now = datetime.now(UTC)
    recent_start, previous_start = now - timedelta(days=7), now - timedelta(days=14)

    mentions = (
        (
            await session.execute(
                select(Mention).where(
                    Mention.project_id == project_id,
                    Mention.topic_id.is_not(None),
                    Mention.published_at >= previous_start,
                )
            )
        )
        .scalars()
        .all()
    )

    recent: dict[UUID, int] = {}
    previous: dict[UUID, int] = {}
    for m in mentions:
        if m.topic_id is None:
            continue
        bucket = recent if m.published_at >= recent_start else previous
        bucket[m.topic_id] = bucket.get(m.topic_id, 0) + 1

    shares = topics_svc.share_of_voice({str(r.id): r.volume for r in rows})
    return [
        TopicOut(
            id=r.id,
            label=r.label,
            keywords=list(r.keywords),
            volume=r.volume,
            share_pct=shares.get(str(r.id)),
            momentum_pct=topics_svc.momentum(recent.get(r.id, 0), previous.get(r.id, 0)),
        )
        for r in rows
    ]
