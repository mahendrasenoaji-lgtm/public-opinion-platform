"""Forecast dan What-If simulation endpoints.

Sampai Phase 3, `POST /what-if` selalu memakai `DEFAULT_SPREAD` — enam angka
tetap yang ditulis tangan di services/forecast.py, bukan hasil estimasi dari
data proyek mana pun. Sekarang lebar intervalnya diestimasi dari riwayat
metrik proyek itu sendiri (`services/timeseries.py`), dan endpoint ini
mengatakan yang mana yang dipakai lewat `model` dan `fitted`.

Yang TIDAK berubah: kalau riwayatnya belum cukup, sistem tidak diam-diam
memakai angka tetap seolah-olah itu hasil estimasi. Ia tetap menghitung
simulasi (pengguna berhak menjajal skenario) tapi menandainya sebagai
"lebar interval bawaan, belum ada model terpasang" — di `model` dan di
`limitations`, dua tempat yang keduanya sampai ke layar.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.deps import CurrentUser, TenantSession
from app.models.measurement import MetricSnapshot
from app.services import timeseries
from app.services.forecast import DEFAULT_SPREAD, project

router = APIRouter(prefix="/projects/{project_id}/forecast", tags=["forecast"])

#: Dipakai saat riwayat belum cukup untuk mengestimasi model. Namanya ikut ke
#: respons supaya tidak ada yang mengira ini hasil fitting.
FALLBACK_MODEL = "lebar interval bawaan (belum ada model terpasang)"

_FALLBACK_LIMITATION = (
    "Riwayat metrik ini belum cukup panjang untuk mengestimasi model, jadi "
    "lebar interval yang dipakai adalah angka bawaan sistem — bukan hasil "
    "perhitungan dari data proyek Anda. Perlakukan bentuk lintasannya sebagai "
    "ilustrasi skenario, bukan sebagai ramalan."
)


class ScenarioRequest(BaseModel):
    baseline: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "Kosongkan untuk memakai nilai terakhir metrik dari riwayat proyek."
        ),
    )
    metric: str = Field(default="poi")
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
    #: True bila lebar interval berasal dari model yang di-fit pada data proyek.
    fitted: bool
    is_simulation: bool
    scenario: dict[str, float]
    driver_contributions: list[dict]
    limitations: list[str]


class BaselineResponse(BaseModel):
    metric: str
    baseline: float | None
    expected: dict[int, float]
    spread: dict[int, float]
    model: str
    n_observations: int
    observed_span_days: int
    median_step_days: float
    insufficient_data: bool = False
    note: str | None = None
    limitations: list[str] = []


async def _history(
    session: TenantSession, project_id: UUID, metric: str
) -> list[tuple[date, float]]:
    """Riwayat nasional sebuah metrik, terurut naik.

    Hanya baris tanpa `province_code` dan tanpa `segment`: deret nasional dan
    deret per-provinsi tidak boleh tercampur jadi satu riwayat, itu akan
    membuat "pengamatan" yang sebenarnya potongan populasi berbeda.
    """
    rows = (
        (
            await session.execute(
                select(MetricSnapshot)
                .where(
                    MetricSnapshot.project_id == project_id,
                    MetricSnapshot.metric == metric,
                    MetricSnapshot.province_code.is_(None),
                    MetricSnapshot.segment.is_(None),
                )
                .order_by(MetricSnapshot.period_end)
            )
        )
        .scalars()
        .all()
    )
    return [(r.period_end, float(r.value)) for r in rows]


@router.get("/baseline", response_model=BaselineResponse)
async def baseline(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    metric: str = Query(default="poi"),
    pi_level: float = Query(default=0.80, ge=0.5, le=0.99),
) -> BaselineResponse:
    """Estimasi model dari riwayat metrik proyek, tanpa skenario apa pun.

    Menjawab "ke mana angka ini bergerak kalau tidak ada yang berubah" —
    pertanyaan yang berbeda dari what-if, dan yang harus dijawab lebih dulu
    sebelum skenario apa pun berarti.
    """
    observations = await _history(session, project_id, metric)
    result = timeseries.fit(observations, pi_level=pi_level)
    return BaselineResponse(
        metric=metric,
        baseline=result.baseline,
        expected=result.expected,
        spread=result.spread,
        model=result.model or FALLBACK_MODEL,
        n_observations=result.n_observations,
        observed_span_days=result.observed_span_days,
        median_step_days=result.median_step_days,
        insufficient_data=result.insufficient_data,
        note=result.note,
        limitations=result.limitations,
    )


@router.post("/what-if", response_model=ForecastResponse)
async def what_if(
    project_id: UUID,
    body: ScenarioRequest,
    session: TenantSession,
    user: CurrentUser,
) -> ForecastResponse:
    """Jalankan simulasi what-if di atas lintasan baseline.

    Statistik skenario dihitung services/forecast.py; lebar interval
    baselinenya dari services/timeseries.py bila riwayatnya cukup. Lihat
    CLAUDE.md soal simulasi: angka ini bukan prediksi terjamin, dan
    `is_simulation` di respons yang menandainya.
    """
    observations = await _history(session, project_id, body.metric)
    fitted = timeseries.fit(observations, pi_level=body.pi_level)

    use_fitted = not fitted.insufficient_data and bool(fitted.spread)
    spread = fitted.spread if use_fitted else DEFAULT_SPREAD

    start = body.baseline if body.baseline is not None else fitted.baseline
    if start is None:
        raise HTTPException(
            422,
            "Proyek belum punya riwayat metrik ini, jadi baseline harus "
            "disebutkan sendiri di permintaan.",
        )

    try:
        result = project(
            baseline=start,
            base_spread=spread,
            scenario=body.scenario if body.scenario else None,
            pi_level=body.pi_level,
            model=(
                f"{fitted.model} + regresor eksogen"
                if use_fitted
                else f"{FALLBACK_MODEL} + regresor eksogen"
            ),
        )
    except ValueError as e:
        raise HTTPException(422, str(e)) from e

    limitations = list(result.limitations)
    limitations.extend(fitted.limitations if use_fitted else [_FALLBACK_LIMITATION])

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
        fitted=use_fitted,
        is_simulation=result.is_simulation,
        scenario=result.scenario,
        driver_contributions=result.driver_contributions,
        limitations=limitations,
    )
