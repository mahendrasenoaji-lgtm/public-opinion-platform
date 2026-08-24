"""Governance: risk score, AI output review, audit trail."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.ai.envelope import Confidence, ReviewStatus
from app.deps import CurrentUser, TenantSession
from app.models.governance import AIOutput, DataQualityScore
from app.services.risk import polarization, risk_score

router = APIRouter(prefix="/projects/{project_id}/governance", tags=["governance"])


class RiskRequest(BaseModel):
    components: dict[str, float]
    weights: dict[str, float] | None = None


class RiskResponse(BaseModel):
    score: int
    band: str
    components: dict[str, float]
    weights: dict[str, float]
    top_contributors: list[list]


@router.post("/risk-score", response_model=RiskResponse)
async def compute_risk(
    project_id: UUID,
    body: RiskRequest,
    session: TenantSession,
    user: CurrentUser,
) -> RiskResponse:
    """Hitung Opinion Risk Score."""
    try:
        result = risk_score(body.components, body.weights)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e

    return RiskResponse(
        score=result.score,
        band=result.band,
        components=result.components,
        weights=result.weights,
        top_contributors=[list(t) for t in result.top_contributors],
    )


class PolarizationRequest(BaseModel):
    segments: list[list]  # [[name, position, size_pct], ...]


@router.post("/polarization")
async def compute_polarization(
    project_id: UUID,
    body: PolarizationRequest,
    session: TenantSession,
    user: CurrentUser,
) -> dict:
    """Ukur polarisasi antar-segmen."""
    try:
        positions = [(s[0], float(s[1]), float(s[2])) for s in body.segments]
        result = polarization(positions)
    except (ValueError, IndexError) as e:
        raise HTTPException(422, str(e)) from e
    return result


class AIOutputOut(BaseModel):
    id: UUID
    kind: str
    model_version: str
    method: str
    confidence: Confidence
    human_review: ReviewStatus
    created_at: datetime


@router.get("/ai-outputs", response_model=list[AIOutputOut])
async def list_ai_outputs(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> list[AIOutputOut]:
    """Jejak keputusan model — wajib ada untuk tiap keluaran AI (R2).

    Kosong sampai fitur AI generatif pertama (Executive Brief) membuat
    barisnya yang pertama — itu kondisi jujur, bukan bug.
    """
    q = (
        select(AIOutput)
        .where(AIOutput.project_id == project_id)
        .order_by(AIOutput.created_at.desc())
    )
    rows = (await session.execute(q)).scalars().all()
    return [
        AIOutputOut(
            id=r.id,
            kind=r.kind,
            model_version=r.model_version,
            method=r.method,
            confidence=Confidence(r.confidence.value),
            human_review=ReviewStatus(r.human_review.value),
            created_at=r.created_at,
        )
        for r in rows
    ]


class DataQualityOut(BaseModel):
    dataset: str
    completeness: int
    duplicate: int
    response_qual: int
    consistency: int
    sample_balance: int
    metadata_score: int
    overall: int
    computed_at: datetime


@router.get("/data-quality", response_model=list[DataQualityOut])
async def list_data_quality(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> list[DataQualityOut]:
    q = (
        select(DataQualityScore)
        .where(DataQualityScore.project_id == project_id)
        .order_by(DataQualityScore.computed_at.desc())
    )
    rows = (await session.execute(q)).scalars().all()
    return [
        DataQualityOut(
            dataset=r.dataset,
            completeness=r.completeness,
            duplicate=r.duplicate,
            response_qual=r.response_qual,
            consistency=r.consistency,
            sample_balance=r.sample_balance,
            metadata_score=r.metadata_score,
            overall=r.overall,
            computed_at=r.computed_at,
        )
        for r in rows
    ]
