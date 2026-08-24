"""Executive Brief — narasi AI generatif pertama di proyek ini (R2 CLAUDE.md).

Pola query di sini sengaja mengikuti opinion.py: helper privat dalam file
router yang sama, bukan impor lintas-router. Lihat app/ai/brief.py untuk
agent-nya dan alasan kenapa fakta yang dikirim ke LLM dibatasi ke yang
benar tersedia (tidak ada deret waktu index historis di seed).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.ai.agents import AgentContext, Orchestrator
from app.ai.brief import BriefGenerationError, BriefPayload, ExecutiveBriefAgent
from app.ai.envelope import Confidence, EvidenceRef, ReviewStatus
from app.ai.provider import get_provider
from app.deps import CurrentUser, Role, TenantSession, require_capability, require_role
from app.models.governance import AIOutput
from app.models.measurement import MetricSnapshot, Narrative, Segment, TimelineEvent
from app.services import divergence as divergence_svc
from app.services import poi

router = APIRouter(prefix="/projects/{project_id}/brief", tags=["brief"])

_KIND = "executive_brief"


class BriefOut(BaseModel):
    id: UUID
    payload: BriefPayload
    method: str
    model_version: str
    confidence: Confidence
    evidence: list[EvidenceRef]
    limitations: str
    human_review: ReviewStatus
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    created_at: datetime


def _row_to_out(row: AIOutput) -> BriefOut:
    return BriefOut(
        id=row.id,
        payload=BriefPayload.model_validate(row.payload),
        method=row.method,
        model_version=row.model_version,
        confidence=Confidence(row.confidence.value),
        evidence=[EvidenceRef.model_validate(e) for e in row.evidence],
        limitations=row.limitations,
        human_review=ReviewStatus(row.human_review.value),
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        created_at=row.created_at,
    )


async def _gather_facts(
    session: TenantSession, project_id: UUID
) -> tuple[dict, list[EvidenceRef]]:
    """Kumpulkan fakta ASLI untuk Brief. Cuma yang benar ada di database —
    lihat catatan "Batasan data jujur" di app/ai/brief.py."""
    facts: dict = {}
    evidence: list[EvidenceRef] = []

    # Index saat ini
    dims_q = select(MetricSnapshot).where(
        MetricSnapshot.project_id == project_id,
        MetricSnapshot.province_code.is_(None),
        MetricSnapshot.segment.is_(None),
    )
    all_snaps = (await session.execute(dims_q)).scalars().all()
    poi_dims = {
        "sentiment": "Sentimen", "approval": "Persetujuan", "trust": "Kepercayaan",
        "satisfaction": "Kepuasan", "issue_perception": "Persepsi Isu", "confidence": "Keyakinan",
    }
    latest_by_metric: dict[str, MetricSnapshot] = {}
    for s in all_snaps:
        cur = latest_by_metric.get(s.metric)
        if cur is None or s.period_end > cur.period_end:
            latest_by_metric[s.metric] = s

    dims = [
        poi.Dimension(
            key=key, label=label, score=float(snap.value), weight=1.0,
            source=poi.SignalSource(snap.source), effective_n=snap.effective_n,
        )
        for key, label in poi_dims.items()
        if (snap := latest_by_metric.get(key)) is not None
    ]
    if dims:
        index = poi.compute_index(dims)
        facts["index"] = {
            "value": index.value if poi.publishable(index) else None,
            "ci_low": index.ci_low,
            "ci_high": index.ci_high,
            "effective_n": index.effective_n,
            "insufficient_data": not poi.publishable(index),
        }
        evidence.append(
            EvidenceRef(
                kind="metric_snapshot", label="Public Opinion Index proyek ini",
                source="SURVEY", n=index.effective_n,
            )
        )

    # Divergence tiga sumber
    source_meta = {
        "SURVEY": "survey_positive", "SOCIAL": "social_positive", "MEDIA": "media_positive",
    }
    readings = []
    for _src, metric_name in source_meta.items():
        snap = latest_by_metric.get(metric_name)
        if snap is None:
            snap_q = (
                select(MetricSnapshot)
                .where(
                    MetricSnapshot.project_id == project_id, MetricSnapshot.metric == metric_name,
                    MetricSnapshot.province_code.is_(None), MetricSnapshot.segment.is_(None),
                )
                .order_by(MetricSnapshot.period_end.desc()).limit(1)
            )
            snap = (await session.execute(snap_q)).scalar_one_or_none()
        if snap:
            readings.append(
                divergence_svc.SignalReading(
                    source=poi.SignalSource(snap.source), value=float(snap.value),
                    n=snap.effective_n or 0, method=snap.method, known_bias="",
                )
            )
    if len(readings) >= 2:
        div = divergence_svc.analyse(readings)
        facts["divergence"] = {
            "gap": div.gap, "is_notable": div.is_notable,
            "readings": [{"source": r.source.value, "value": r.value} for r in div.readings],
        }
        evidence.append(
            EvidenceRef(
                kind="metric_snapshot", label="Perbandingan survei/sosial/media",
                source="SURVEY", n=None,
            )
        )

    # Segmen terbesar
    seg_q = (
        select(Segment).where(Segment.project_id == project_id)
        .order_by(Segment.size_pct.desc()).limit(3)
    )
    segments = (await session.execute(seg_q)).scalars().all()
    if segments:
        facts["top_segments"] = [
            {"name": s.name, "size_pct": float(s.size_pct), "sentiment": float(s.sentiment or 0)}
            for s in segments
        ]
        evidence.append(
            EvidenceRef(kind="segment", label="Segmen publik terbesar", source="SURVEY", n=None)
        )

    # Narasi dengan momentum tertinggi
    narr_q = (
        select(Narrative).where(Narrative.project_id == project_id)
        .order_by(Narrative.momentum_7d.desc()).limit(2)
    )
    narratives = (await session.execute(narr_q)).scalars().all()
    if narratives:
        facts["top_narratives"] = [
            {"code": n.code, "statement": n.statement, "momentum_7d": float(n.momentum_7d)}
            for n in narratives
        ]
        evidence.append(
            EvidenceRef(
                kind="narrative", label="Narasi dengan momentum tertinggi",
                source="SOCIAL", n=None,
            )
        )

    # Provinsi tertinggi & terendah (yang publishable saja)
    geo_q = select(MetricSnapshot).where(
        MetricSnapshot.project_id == project_id, MetricSnapshot.metric == "poi",
        MetricSnapshot.province_code.is_not(None),
    )
    geo_rows = (await session.execute(geo_q)).scalars().all()
    publishable_geo = [
        g for g in geo_rows if g.effective_n and g.effective_n >= poi.MIN_EFFECTIVE_N
    ]
    if publishable_geo:
        ranked = sorted(publishable_geo, key=lambda g: g.value, reverse=True)
        facts["geo_extremes"] = {
            "highest": {"province_code": ranked[0].province_code, "value": float(ranked[0].value)},
            "lowest": {"province_code": ranked[-1].province_code, "value": float(ranked[-1].value)},
        }
        evidence.append(
            EvidenceRef(
                kind="metric_snapshot", label="Sebaran index per provinsi",
                source="SURVEY", n=None,
            )
        )

    # Peristiwa terbaru
    tl_q = (
        select(TimelineEvent).where(TimelineEvent.project_id == project_id)
        .order_by(TimelineEvent.occurred_at.desc()).limit(5)
    )
    events = (await session.execute(tl_q)).scalars().all()
    if events:
        facts["recent_timeline"] = [
            {"occurred_at": e.occurred_at.date().isoformat(), "kind": e.kind, "label": e.label}
            for e in events
        ]

    return facts, evidence


@router.post(
    "/generate", response_model=BriefOut, dependencies=[Depends(require_role(Role.RESEARCHER))]
)
async def generate_brief(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> BriefOut:
    """Buat Executive Brief baru dari data agregat proyek saat ini."""
    facts, evidence = await _gather_facts(session, project_id)
    if not evidence:
        raise HTTPException(404, "Belum ada data agregat untuk proyek ini.")

    ctx = AgentContext(
        project_id=str(project_id), period=datetime.now().strftime("%Y-%m-%d"),
        facts=facts, evidence=evidence,
    )
    try:
        llm = get_provider()
    except RuntimeError as e:
        # get_provider() melempar ini kalau LLM_PROVIDER belum di-set sama
        # sekali atau ANTHROPIC_API_KEY kosong (app/ai/provider.py) --
        # beda dari BriefGenerationError (provider ADA tapi hasilnya bukan
        # JSON yang diharapkan, mis. masih LLM_PROVIDER=echo).
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e

    try:
        [env] = await Orchestrator(llm).run([ExecutiveBriefAgent(llm)], ctx)
    except BriefGenerationError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e

    row = AIOutput(
        org_id=user.org_id, project_id=project_id, kind=_KIND,
        model_version=env.model_version, method=env.method, prompt_hash=env.prompt_hash or "",
        payload=env.payload.model_dump(),
        evidence=[e.model_dump(mode="json") for e in env.evidence],
        confidence=env.confidence.value, limitations=env.limitations,
        human_review=env.human_review.value,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return _row_to_out(row)


@router.get("/latest", response_model=BriefOut)
async def get_latest_brief(project_id: UUID, session: TenantSession, user: CurrentUser) -> BriefOut:
    q = (
        select(AIOutput)
        .where(AIOutput.project_id == project_id, AIOutput.kind == _KIND)
        .order_by(AIOutput.created_at.desc())
        .limit(1)
    )
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Belum ada Executive Brief untuk proyek ini.")
    return _row_to_out(row)


@router.post(
    "/{output_id}/approve",
    response_model=BriefOut,
    dependencies=[Depends(require_capability("ai_output:approve"))],
)
async def approve_brief(
    project_id: UUID, output_id: UUID, session: TenantSession, user: CurrentUser
) -> BriefOut:
    q = select(AIOutput).where(AIOutput.id == output_id, AIOutput.project_id == project_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Brief tidak ditemukan.")

    row.human_review = ReviewStatus.APPROVED.value
    row.reviewed_by = user.user_id
    row.reviewed_at = datetime.now()
    await session.flush()
    await session.refresh(row)
    return _row_to_out(row)
