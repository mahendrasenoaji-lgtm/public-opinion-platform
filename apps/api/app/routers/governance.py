"""Governance: risk score, AI output review, audit trail."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.deps import CurrentUser, TenantSession
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
