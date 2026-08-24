"""Forecast dan What-If simulation endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.deps import CurrentUser, TenantSession
from app.services.forecast import DEFAULT_SPREAD, project

router = APIRouter(prefix="/projects/{project_id}/forecast", tags=["forecast"])


class ScenarioRequest(BaseModel):
    baseline: float = Field(ge=0, le=100)
    scenario: dict[str, float] = Field(default_factory=dict)
    pi_level: float = Field(default=0.80, ge=0.5, le=0.99)


class ForecastPointOut(BaseModel):
    horizon_days: int
    expected: float
    pi_low: float
    pi_high: float


class ForecastResponse(BaseModel):
    points: list[ForecastPointOut]
    pi_level: float
    model: str
    is_simulation: bool
    scenario: dict[str, float]
    driver_contributions: list[dict]
    limitations: list[str]


@router.post("/what-if", response_model=ForecastResponse)
async def what_if(
    project_id: UUID,
    body: ScenarioRequest,
    session: TenantSession,
    user: CurrentUser,
) -> ForecastResponse:
    """Jalankan simulasi what-if.

    Statistik dihitung oleh services/forecast.py; endpoint ini hanya
    meneruskan input dan mengembalikan hasil. Lihat CLAUDE.md aturan tentang
    simulasi: angka ini bukan prediksi terjamin.
    """
    try:
        result = project(
            baseline=body.baseline,
            base_spread=DEFAULT_SPREAD,
            scenario=body.scenario if body.scenario else None,
            pi_level=body.pi_level,
        )
    except ValueError as e:
        raise HTTPException(422, str(e)) from e

    return ForecastResponse(
        points=[
            ForecastPointOut(
                horizon_days=p.horizon_days,
                expected=p.expected,
                pi_low=p.pi_low,
                pi_high=p.pi_high,
            )
            for p in result.points
        ],
        pi_level=result.pi_level,
        model=result.model,
        is_simulation=result.is_simulation,
        scenario=result.scenario,
        driver_contributions=result.driver_contributions,
        limitations=result.limitations,
    )
