"""Communication Impact — satu-satunya endpoint yang boleh mengeluarkan klaim
efek (Phase 3).

Perhitungan dan penolakannya ada di `services/impact.py`. File ini merakit
empat sel DiD dari `metric_snapshots`: dua segmen (terpapar dan pembanding)
diukur pada dua periode.

## Dari mana simpangan bakunya

`metric_snapshots` tidak menyimpan `sd`, tapi ia menyimpan interval kepercayaan
dan `effective_n`. Simpangan baku diturunkan dari sana:

    se = (ci_high - ci_low) / (2 * 1.96)      # CI 95% yang lazim dipakai seed
    sd = se * sqrt(effective_n)

Snapshot tanpa interval kepercayaan TIDAK bisa dipakai — bukan karena
perhitungannya mustahil, tapi karena efek tanpa ketidakpastian yang bisa
dihitung adalah angka yang menyembunyikan apa yang tidak diketahui, dan itu
persis yang dilarang platform ini.
"""

from __future__ import annotations

import math
from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.deps import CurrentUser, TenantSession
from app.models.measurement import MetricSnapshot
from app.services.impact import (
    MIN_DONORS,
    Cell,
    NoControlGroup,
    difference_in_differences,
    synthetic_control,
)

router = APIRouter(prefix="/projects/{project_id}/impact", tags=["impact"])

#: Faktor z yang dipakai untuk membalik interval kepercayaan 95% jadi galat
#: baku. Snapshot di platform ini memakai CI 95% (lihat db/seed.py).
_Z95 = 1.9600


class ImpactRequest(BaseModel):
    """Definisi desain pembanding. Semua field wajib — tidak ada mode tanpa
    kelompok pembanding, dan itu disengaja."""

    metric: str = Field(default="approval")
    treated_segment: str = Field(min_length=1, description="Segmen yang terpapar komunikasi")
    control_segment: str = Field(
        min_length=1,
        description=(
            "Segmen pembanding yang TIDAK terpapar. Tanpa ini tidak ada klaim "
            "efek yang bisa dibuat."
        ),
    )
    pre_period_end: date = Field(description="Batas akhir periode sebelum perlakuan")
    post_period_end: date = Field(description="Batas akhir periode sesudah perlakuan")
    ci_level: float = Field(default=0.95)


class ImpactOut(BaseModel):
    effect: float | None
    ci_low: float | None
    ci_high: float | None
    ci_level: float
    treated_change: float | None
    control_change: float | None
    distinguishable_from_zero: bool
    parallel_trends_checked: bool
    parallel_trends_ok: bool | None
    method: str
    insufficient_data: bool
    note: str | None
    limitations: list[str]


async def _snapshot(
    session: TenantSession,
    project_id: UUID,
    *,
    metric: str,
    segment: str,
    period_end: date,
) -> MetricSnapshot | None:
    """Snapshot segmen pada satu periode. None kalau tidak ada."""
    return (
        await session.execute(
            select(MetricSnapshot)
            .where(
                MetricSnapshot.project_id == project_id,
                MetricSnapshot.metric == metric,
                MetricSnapshot.segment == segment,
                MetricSnapshot.period_end == period_end,
            )
            .limit(1)
        )
    ).scalar_one_or_none()


def _to_cell(row: MetricSnapshot | None, label: str) -> Cell:
    """Ubah snapshot jadi sel DiD, atau tolak dengan alasan yang jelas."""
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Tidak ada snapshot untuk {label}. Desain pembanding butuh keempat "
            "sel terukur pada periode yang sama.",
        )
    if row.ci_low is None or row.ci_high is None or not row.effective_n:
        raise HTTPException(
            422,
            f"Snapshot {label} tidak punya interval kepercayaan atau sampel "
            "efektif, sehingga ketidakpastian efeknya tidak bisa dihitung. "
            "Efek tanpa ketidakpastian tidak boleh diterbitkan.",
        )
    se = (float(row.ci_high) - float(row.ci_low)) / (2 * _Z95)
    return Cell(mean=float(row.value), sd=se * math.sqrt(row.effective_n), n=row.effective_n)


class SyntheticControlRequest(BaseModel):
    """Definisi desain synthetic control. Alternatif dari DiD untuk kasus
    tanpa satu kelompok pembanding tunggal yang meyakinkan, tapi ADA beberapa
    kandidat donor -- lihat services/impact.py bagian synthetic control."""

    metric: str = Field(default="approval")
    treated_segment: str = Field(min_length=1, description="Segmen yang terpapar komunikasi")
    donor_segments: list[str] = Field(
        min_length=MIN_DONORS,
        description=f"Kandidat donor, minimal {MIN_DONORS} segmen yang TIDAK terpapar.",
    )
    pre_period_end: date = Field(
        description="Snapshot dengan period_end <= ini dipakai sebagai deret pra-perlakuan"
    )
    post_period_end: date = Field(description="Titik pasca-perlakuan yang dibandingkan")


class SyntheticControlOut(BaseModel):
    effect: float | None
    treated_post: float | None
    synthetic_post: float | None
    weights: dict[str, float]
    donors_used: int
    n_pre_periods: int
    pre_fit_rmspe: float | None
    fit_quality_ok: bool | None
    placebo_effects: dict[str, float]
    rank_p_value: float | None
    method: str
    insufficient_data: bool
    note: str | None
    limitations: list[str]


async def _aligned_pre_series(
    session: TenantSession,
    project_id: UUID,
    *,
    metric: str,
    segments: list[str],
    pre_period_end: date,
) -> dict[str, list[float]]:
    """Deret pra-perlakuan tiap segmen, HANYA pada period_end yang tersedia
    untuk SEMUA segmen sekaligus (irisan, bukan gabungan).

    Synthetic control mencocokkan titik demi titik antar deret -- period_end
    yang cuma dipunyai sebagian segmen tidak bisa dipasangkan, jadi dibuang
    dari SEMUA deret, bukan diisi nilai reka-reka.
    """
    rows = (
        (
            await session.execute(
                select(MetricSnapshot).where(
                    MetricSnapshot.project_id == project_id,
                    MetricSnapshot.metric == metric,
                    MetricSnapshot.segment.in_(segments),
                    MetricSnapshot.period_end <= pre_period_end,
                )
            )
        )
        .scalars()
        .all()
    )
    by_period: dict[date, dict[str, float]] = {}
    for r in rows:
        if r.segment is None:  # tersaring oleh filter .in_(segments) di atas, tapi
            continue  # kolomnya nullable secara skema -- jaga mypy tetap jujur
        by_period.setdefault(r.period_end, {})[r.segment] = float(r.value)

    common_periods = sorted(
        p for p, values in by_period.items() if set(segments) <= set(values)
    )
    return {seg: [by_period[p][seg] for p in common_periods] for seg in segments}


@router.post("/synthetic-control", response_model=SyntheticControlOut)
async def analyze_synthetic_control(
    project_id: UUID, body: SyntheticControlRequest, session: TenantSession, user: CurrentUser
) -> SyntheticControlOut:
    """Ukur efek komunikasi dengan synthetic control (Abadie et al.).

    Dipilih di atas DiD ketika tidak ada satu kelompok pembanding tunggal
    yang meyakinkan, tapi ada beberapa kandidat donor. Menolak kalau donor
    kurang dari MIN_DONORS, atau kalau jumlah periode pra-perlakuan yang
    SEJAJAR antar semua segmen tidak lebih banyak dari jumlah donor -- lihat
    services/impact.py:synthetic_control() untuk alasannya.
    """
    if body.treated_segment in body.donor_segments:
        raise HTTPException(
            422,
            "Segmen terpapar tidak boleh ikut jadi donornya sendiri.",
        )
    if len(set(body.donor_segments)) != len(body.donor_segments):
        raise HTTPException(422, "Daftar segmen donor memuat duplikat.")

    all_segments = [body.treated_segment, *body.donor_segments]
    pre_series = await _aligned_pre_series(
        session,
        project_id,
        metric=body.metric,
        segments=all_segments,
        pre_period_end=body.pre_period_end,
    )

    async def _post_value(segment: str) -> float:
        row = await _snapshot(
            session,
            project_id,
            metric=body.metric,
            segment=segment,
            period_end=body.post_period_end,
        )
        if row is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Tidak ada snapshot pasca-perlakuan untuk segmen '{segment}' "
                f"pada {body.post_period_end}.",
            )
        return float(row.value)

    treated_post = await _post_value(body.treated_segment)
    donors_post = {seg: await _post_value(seg) for seg in body.donor_segments}

    try:
        result = synthetic_control(
            treated_pre=pre_series[body.treated_segment],
            treated_post=treated_post,
            donors_pre={seg: pre_series[seg] for seg in body.donor_segments},
            donors_post=donors_post,
        )
    except ValueError as e:
        raise HTTPException(422, str(e)) from e

    return SyntheticControlOut(
        effect=result.effect,
        treated_post=result.treated_post,
        synthetic_post=result.synthetic_post,
        weights=result.weights,
        donors_used=result.donors_used,
        n_pre_periods=result.n_pre_periods,
        pre_fit_rmspe=result.pre_fit_rmspe,
        fit_quality_ok=result.fit_quality_ok,
        placebo_effects=result.placebo_effects,
        rank_p_value=result.rank_p_value,
        method=result.method,
        insufficient_data=result.insufficient_data,
        note=result.note,
        limitations=result.limitations,
    )


@router.post("/analyze", response_model=ImpactOut)
async def analyze(
    project_id: UUID, body: ImpactRequest, session: TenantSession, user: CurrentUser
) -> ImpactOut:
    """Ukur efek komunikasi dengan difference-in-differences.

    Menolak bekerja kalau salah satu dari empat sel tidak ada. Itu bukan
    kekakuan berlebihan: tanpa pembanding, yang tersisa hanyalah selisih
    sebelum-sesudah pada kelompok terpapar, dan selisih itu tidak bisa
    dipisahkan dari tren yang memang sudah berjalan.
    """
    if body.treated_segment == body.control_segment:
        raise HTTPException(
            422,
            "Segmen terpapar dan segmen pembanding tidak boleh sama — "
            "membandingkan kelompok dengan dirinya sendiri selalu menghasilkan "
            "efek nol tanpa menguji apa pun.",
        )

    cells = {}
    for label, segment, period_end in (
        ("terpapar sebelum", body.treated_segment, body.pre_period_end),
        ("terpapar sesudah", body.treated_segment, body.post_period_end),
        ("pembanding sebelum", body.control_segment, body.pre_period_end),
        ("pembanding sesudah", body.control_segment, body.post_period_end),
    ):
        row = await _snapshot(
            session,
            project_id,
            metric=body.metric,
            segment=segment,
            period_end=period_end,
        )
        cells[label] = _to_cell(row, label)

    # Deret pra-perlakuan untuk memeriksa asumsi tren paralel, kalau ada.
    async def _pre_series(segment: str) -> list[float]:
        rows = (
            (
                await session.execute(
                    select(MetricSnapshot)
                    .where(
                        MetricSnapshot.project_id == project_id,
                        MetricSnapshot.metric == body.metric,
                        MetricSnapshot.segment == segment,
                        MetricSnapshot.period_end <= body.pre_period_end,
                    )
                    .order_by(MetricSnapshot.period_end)
                )
            )
            .scalars()
            .all()
        )
        return [float(r.value) for r in rows]

    treated_series = await _pre_series(body.treated_segment)
    control_series = await _pre_series(body.control_segment)
    checkable = len(treated_series) >= 2 and len(control_series) >= 2

    try:
        result = difference_in_differences(
            treated_pre=cells["terpapar sebelum"],
            treated_post=cells["terpapar sesudah"],
            control_pre=cells["pembanding sebelum"],
            control_post=cells["pembanding sesudah"],
            ci_level=body.ci_level,
            treated_pre_series=treated_series if checkable else None,
            control_pre_series=control_series if checkable else None,
        )
    except NoControlGroup as e:
        raise HTTPException(422, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e

    return ImpactOut(
        effect=result.effect,
        ci_low=result.ci_low,
        ci_high=result.ci_high,
        ci_level=result.ci_level,
        treated_change=result.treated_change,
        control_change=result.control_change,
        distinguishable_from_zero=result.distinguishable_from_zero,
        parallel_trends_checked=result.parallel_trends_checked,
        parallel_trends_ok=result.parallel_trends_ok,
        method=result.method,
        insufficient_data=result.insufficient_data,
        note=result.note,
        limitations=result.limitations,
    )
