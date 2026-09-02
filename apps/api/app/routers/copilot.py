"""AI Copilot — tanya jawab atas data agregat proyek (Phase 2).

Menggantikan kerangka 501 yang ada di sini sebelumnya.

Kartu fakta disusun di file ini dari tabel agregat yang sudah ada; pemilihan
kartu yang relevan ada di `app/ai/retrieval.py` (fungsi murni, dites
terpisah); penyusunan jawabannya ada di `app/ai/copilot.py`.

Yang TIDAK pernah masuk kartu fakta: isi `mentions` per baris. Alasan lengkap
ada di docstring app/ai/retrieval.py — ringkasnya, `EvidenceRef` memang
dirancang hanya menerima rujukan agregat, dan Copilot tidak boleh jadi pintu
belakang yang melewatinya.

Setiap jawaban ditulis ke `ai_outputs` sebelum dikembalikan. Itu bukan
pencatatan opsional: R2 mensyaratkan setiap keluaran AI punya jejak yang bisa
ditinjau, dan halaman AI Governance membacanya dari tabel itu.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.ai.agents import AgentContext, Orchestrator
from app.ai.copilot import CopilotAgent, CopilotAnswer, CopilotError, as_facts
from app.ai.envelope import AIEnvelope, Confidence, EvidenceRef, ReviewStatus
from app.ai.provider import get_provider
from app.ai.retrieval import FactCard, select_relevant
from app.deps import CurrentUser, TenantSession
from app.models.governance import AIOutput, ConfidenceBand
from app.models.governance import ReviewStatus as DBReviewStatus
from app.models.measurement import MetricSnapshot, Narrative, Segment
from app.models.signal import Mention, Topic
from app.services import topics as topics_svc

router = APIRouter(prefix="/projects/{project_id}/copilot", tags=["copilot"])

_KIND = "copilot_answer"
SIGNAL_WINDOW_DAYS = 30

#: Sejalan dengan MIN_MENTIONS_FOR_AGGREGATE di routers/signals.py — kartu
#: sinyal tidak dibuat dari volume yang terlalu tipis untuk dibaca.
MIN_MENTIONS_FOR_CARD = 30


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class AskResponse(BaseModel):
    id: UUID
    payload: CopilotAnswer
    method: str
    model_version: str
    confidence: Confidence
    evidence: list[EvidenceRef]
    limitations: str
    human_review: ReviewStatus
    matched_terms: dict[str, list[str]]
    cards_considered: int
    cards_used: int


async def _fact_cards(session: TenantSession, project_id: UUID) -> list[FactCard]:
    """Susun kartu fakta agregat proyek. Tidak pernah menyentuh isi mention."""
    cards: list[FactCard] = []

    # --- dimensi index dari metric_snapshots -------------------------------
    dim_rows = (
        (
            await session.execute(
                select(MetricSnapshot).where(
                    MetricSnapshot.project_id == project_id,
                    MetricSnapshot.province_code.is_(None),
                    MetricSnapshot.segment.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for row in dim_rows:
        cards.append(
            FactCard(
                key=f"metric:{row.metric}",
                label=f"Metrik {row.metric}",
                payload={
                    "metrik": row.metric,
                    "nilai": float(row.value),
                    "sumber": row.source.value,
                    "metode": row.method,
                    "ci_low": float(row.ci_low) if row.ci_low is not None else None,
                    "ci_high": float(row.ci_high) if row.ci_high is not None else None,
                    "effective_n": row.effective_n,
                    "periode": f"{row.period_start} s/d {row.period_end}",
                },
                evidence=EvidenceRef(
                    kind="metric_snapshot",
                    ref_id=row.id,
                    label=f"Snapshot metrik {row.metric} ({row.source.value})",
                    period=f"{row.period_start}/{row.period_end}",
                    n=row.effective_n,
                    source=row.source.value,  # type: ignore[arg-type]
                ),
                keywords=frozenset({row.metric, row.source.value.lower()}),
                is_core=row.metric in {"poi", "trust", "approval"},
            )
        )

    # --- segmen -------------------------------------------------------------
    segments = (
        (await session.execute(select(Segment).where(Segment.project_id == project_id)))
        .scalars()
        .all()
    )
    for seg in segments:
        cards.append(
            FactCard(
                key=f"segment:{seg.name}",
                label=f"Segmen {seg.name}",
                payload={
                    "nama": seg.name,
                    "ukuran_persen": float(seg.size_pct),
                    "sentimen": float(seg.sentiment) if seg.sentiment is not None else None,
                    "kepercayaan": float(seg.trust) if seg.trust is not None else None,
                    "metode": seg.method,
                },
                evidence=EvidenceRef(
                    kind="segment",
                    ref_id=seg.id,
                    label=f"Segmen publik: {seg.name}",
                    source="SURVEY",
                ),
                keywords=frozenset(seg.name.lower().split()) | {"segmen", "kelompok"},
                is_core=True,
            )
        )

    # --- narasi -------------------------------------------------------------
    narratives = (
        (await session.execute(select(Narrative).where(Narrative.project_id == project_id)))
        .scalars()
        .all()
    )
    for nar in narratives:
        cards.append(
            FactCard(
                key=f"narrative:{nar.code}",
                label=f"Narasi {nar.code}",
                payload={
                    "pernyataan": nar.statement,
                    "volume_persen": float(nar.volume_pct),
                    "momentum_7h": float(nar.momentum_7d),
                    "sumber_asal": nar.origin_source.value,
                    "tidak_terklaster_persen": float(nar.unclustered_pct),
                },
                evidence=EvidenceRef(
                    kind="narrative",
                    ref_id=nar.id,
                    label=f"Narasi {nar.code}: {nar.statement[:60]}",
                    source=nar.origin_source.value,  # type: ignore[arg-type]
                ),
                keywords=frozenset(nar.statement.lower().split()) | {"narasi", "isu"},
            )
        )

    # --- tema hasil topic discovery ----------------------------------------
    topics = (
        (await session.execute(select(Topic).where(Topic.project_id == project_id)))
        .scalars()
        .all()
    )
    for topic in topics:
        # Pakai label yang sudah ditinjau manusia bila ada dan disetujui --
        # fungsi murni yang sama dipakai tampilan /tema (services/topics.py),
        # supaya revisi seorang peninjau juga mengubah apa yang dibaca Copilot,
        # bukan cuma apa yang terlihat di satu halaman.
        label = topics_svc.effective_label(
            topic.label, topic.reviewed_label, topic.review_status.value
        )
        cards.append(
            FactCard(
                key=f"topic:{topic.id}",
                label=f"Tema {label}",
                payload={
                    "label": label,
                    "kata_kunci": list(topic.keywords),
                    "volume": topic.volume,
                },
                evidence=EvidenceRef(
                    kind="mention_aggregate",
                    ref_id=topic.id,
                    label=f"Tema percakapan: {label}",
                    n=topic.volume,
                    source="SOCIAL",
                ),
                keywords=frozenset(topic.keywords) | {"tema", "topik", "percakapan"},
            )
        )

    # --- ringkasan sinyal ---------------------------------------------------
    since = datetime.now(UTC) - timedelta(days=SIGNAL_WINDOW_DAYS)
    signal_row = (
        await session.execute(
            select(
                func.count().label("volume"),
                func.avg(Mention.sentiment).label("mean"),
                func.count(Mention.sentiment).label("scored"),
            ).where(Mention.project_id == project_id, Mention.published_at >= since)
        )
    ).one()

    if int(signal_row.volume) >= MIN_MENTIONS_FOR_CARD:
        cards.append(
            FactCard(
                key="signal:summary",
                label="Ringkasan percakapan media sosial",
                payload={
                    "volume": int(signal_row.volume),
                    "sentimen_rata_rata": (
                        round(float(signal_row.mean), 3) if signal_row.mean is not None else None
                    ),
                    "jumlah_dinilai": int(signal_row.scored),
                    "jendela_hari": SIGNAL_WINDOW_DAYS,
                    "peringatan": (
                        "Self-selected, tidak bisa digeneralisasi ke populasi."
                    ),
                },
                evidence=EvidenceRef(
                    kind="mention_aggregate",
                    label=(
                        f"Agregat {int(signal_row.volume)} konten media sosial "
                        f"{SIGNAL_WINDOW_DAYS} hari terakhir"
                    ),
                    n=int(signal_row.volume),
                    source="SOCIAL",
                ),
                keywords=frozenset(
                    {"sosial", "medsos", "percakapan", "sentimen", "volume", "netizen"}
                ),
                is_core=True,
            )
        )

    return cards


@router.post("/ask", response_model=AskResponse)
async def ask(
    project_id: UUID, body: AskRequest, session: TenantSession, user: CurrentUser
) -> AskResponse:
    """Jawab pertanyaan tentang proyek dari data agregatnya.

    Menolak menjawab kalau proyek belum punya satu pun kartu fakta — bukan
    dengan mengarang, dan bukan dengan envelope berbukti kosong (AIEnvelope
    memang menolak divalidasi tanpa bukti; 409 di sini menjelaskannya ke
    pengguna alih-alih membiarkannya jadi 422 yang membingungkan).
    """
    cards = await _fact_cards(session, project_id)
    if not cards:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Proyek ini belum punya data agregat yang bisa dijadikan bukti. "
            "Masukkan data survei atau sinyal lebih dulu.",
        )

    retrieved = select_relevant(body.question, cards)
    if not retrieved.cards:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Tidak ada data proyek yang berkaitan dengan pertanyaan itu.",
        )

    try:
        provider = get_provider()
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e

    ctx = AgentContext(
        project_id=str(project_id),
        period=f"{SIGNAL_WINDOW_DAYS} hari terakhir",
        facts=as_facts(
            body.question,
            {c.key: c.payload for c in retrieved.cards},
            general=retrieved.fell_back_to_core,
        ),
        evidence=[c.evidence for c in retrieved.cards],
    )

    try:
        results = await Orchestrator(provider).run([CopilotAgent(provider)], ctx)
    except CopilotError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e

    envelope: AIEnvelope[CopilotAnswer] = results[0]
    payload = CopilotAnswer.model_validate(envelope.payload)

    row = AIOutput(
        org_id=user.org_id,
        project_id=project_id,
        kind=_KIND,
        model_version=envelope.model_version,
        method=envelope.method,
        prompt_hash=envelope.prompt_hash or "",
        payload=payload.model_dump(),
        evidence=[e.model_dump(mode="json") for e in envelope.evidence],
        confidence=ConfidenceBand(envelope.confidence.value),
        limitations=envelope.limitations,
        human_review=DBReviewStatus(envelope.human_review.value),
    )
    session.add(row)
    await session.flush()

    return AskResponse(
        id=row.id,
        payload=payload,
        method=envelope.method,
        model_version=envelope.model_version,
        confidence=envelope.confidence,
        evidence=envelope.evidence,
        limitations=envelope.limitations,
        human_review=envelope.human_review,
        matched_terms=retrieved.matched_terms,
        cards_considered=len(cards),
        cards_used=len(retrieved.cards),
    )


@router.get("/history", response_model=list[AskResponse])
async def history(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> list[AskResponse]:
    """Pertanyaan yang pernah dijawab, terbaru dulu.

    Dibaca dari `ai_outputs` — sumber yang sama dengan halaman AI Governance,
    jadi jejaknya satu, bukan dua catatan yang bisa berbeda.
    """
    rows = (
        (
            await session.execute(
                select(AIOutput)
                .where(AIOutput.project_id == project_id, AIOutput.kind == _KIND)
                .order_by(AIOutput.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return [
        AskResponse(
            id=r.id,
            payload=CopilotAnswer.model_validate(r.payload),
            method=r.method,
            model_version=r.model_version,
            confidence=Confidence(r.confidence.value),
            evidence=[EvidenceRef.model_validate(e) for e in r.evidence],
            limitations=r.limitations,
            human_review=ReviewStatus(r.human_review.value),
            matched_terms={},
            cards_considered=0,
            cards_used=len(r.evidence),
        )
        for r in rows
    ]
