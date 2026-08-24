"""Sampling engine.

Menghitung ukuran sampel dan melaporkan asumsi yang dipakai. Asumsi selalu
dikembalikan bersama angkanya — angka sampel tanpa asumsi tidak bisa diaudit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

Z = {0.80: 1.2816, 0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}


class SamplingMethod(StrEnum):
    SRS = "SRS"
    STRATIFIED = "STRATIFIED"
    CLUSTER = "CLUSTER"
    MULTISTAGE = "MULTISTAGE"
    QUOTA = "QUOTA"
    PURPOSIVE = "PURPOSIVE"


#: Design effect default per metode. Sampel klaster butuh lebih banyak
#: responden untuk presisi yang sama karena orang dalam satu klaster mirip.
DEFAULT_DEFF: dict[SamplingMethod, float] = {
    SamplingMethod.SRS: 1.0,
    SamplingMethod.STRATIFIED: 0.9,
    SamplingMethod.CLUSTER: 2.0,
    SamplingMethod.MULTISTAGE: 1.6,
    SamplingMethod.QUOTA: 1.0,
    SamplingMethod.PURPOSIVE: 1.0,
}

#: Metode yang hasilnya tidak boleh diklaim mewakili populasi.
NON_PROBABILITY = {SamplingMethod.QUOTA, SamplingMethod.PURPOSIVE}


@dataclass(frozen=True, slots=True)
class SampleSizeResult:
    recommended_n: int
    base_n: int
    design_effect: float
    finite_population_correction: bool
    assumptions: dict[str, object]
    warnings: list[str] = field(default_factory=list)


def sample_size(
    *,
    population: int | None,
    confidence: float = 0.95,
    margin_of_error: float = 0.03,
    expected_proportion: float = 0.5,
    method: SamplingMethod = SamplingMethod.MULTISTAGE,
    design_effect: float | None = None,
    expected_response_rate: float = 1.0,
) -> SampleSizeResult:
    """Ukuran sampel untuk estimasi proporsi.

    n0 = z² p(1-p) / e², lalu koreksi populasi terbatas, design effect, dan
    antisipasi non-respons.
    """
    if not 0 < margin_of_error < 1:
        raise ValueError("margin of error harus antara 0 dan 1")
    if not 0 <= expected_proportion <= 1:
        raise ValueError("proporsi harapan harus antara 0 dan 1")
    if not 0 < expected_response_rate <= 1:
        raise ValueError("response rate harus antara 0 dan 1")

    z = Z.get(confidence)
    if z is None:
        raise ValueError(f"confidence level tidak didukung: {confidence}")

    p = expected_proportion
    n0 = (z**2 * p * (1 - p)) / (margin_of_error**2)

    fpc = False
    if population and population > 0:
        n0 = n0 / (1 + (n0 - 1) / population)
        fpc = True

    base_n = math.ceil(n0)
    deff = design_effect if design_effect is not None else DEFAULT_DEFF[method]
    n = math.ceil(base_n * deff / expected_response_rate)

    warnings: list[str] = []
    if method in NON_PROBABILITY:
        warnings.append(
            f"{method.value} adalah metode non-probabilistik. Margin of error dan "
            "interval kepercayaan tidak berlaku; hasil tidak dapat digeneralisasi "
            "ke populasi."
        )
    if p == 0.5:
        warnings.append(
            "proporsi harapan 0,5 dipakai sebagai asumsi paling konservatif (varians maksimum)"
        )
    if population and n > population * 0.1:
        warnings.append("sampel melebihi 10% populasi; pertimbangkan sensus parsial")
    if expected_response_rate < 0.5:
        warnings.append(
            "response rate di bawah 50% meningkatkan risiko bias non-respons; "
            "siapkan analisis pembanding responden vs non-responden"
        )

    return SampleSizeResult(
        recommended_n=n,
        base_n=base_n,
        design_effect=deff,
        finite_population_correction=fpc,
        assumptions={
            "population": population,
            "confidence": confidence,
            "z": z,
            "margin_of_error": margin_of_error,
            "expected_proportion": p,
            "method": method.value,
            "expected_response_rate": expected_response_rate,
        },
        warnings=warnings,
    )


def margin_from_n(n: int, *, confidence: float = 0.95, p: float = 0.5, deff: float = 1.0) -> float:
    """Kebalikannya: sampel sudah terkumpul, berapa margin-nya."""
    if n <= 0:
        raise ValueError("n harus > 0")
    z = Z.get(confidence, Z[0.95])
    return z * math.sqrt(deff * p * (1 - p) / n)


@dataclass(frozen=True, slots=True)
class BalanceReport:
    achieved_n: int
    target_n: int
    response_rate: float
    max_deviation_pp: float
    strata: list[dict[str, object]]
    warnings: list[str]


def stratum_balance(
    achieved: dict[str, int],
    census_share: dict[str, float],
    target_n: int,
    *,
    tolerance_pp: float = 3.0,
) -> BalanceReport:
    """Bandingkan komposisi sampel dengan proporsi populasi.

    `census_share` diambil dari data BPS dan disimpan per proyek. Deviasi besar
    tidak otomatis berarti sampel rusak — tapi wajib dilaporkan, dan pembobotan
    pasca-stratifikasi harus dijalankan sebelum estimasi diterbitkan.
    """
    total = sum(achieved.values())
    rows: list[dict[str, object]] = []
    max_dev = 0.0

    for key, share in sorted(census_share.items()):
        got = achieved.get(key, 0)
        got_share = got / total if total else 0.0
        dev_pp = (got_share - share) * 100
        max_dev = max(max_dev, abs(dev_pp))
        rows.append(
            {
                "stratum": key,
                "achieved": got,
                "achieved_share": round(got_share, 4),
                "census_share": round(share, 4),
                "deviation_pp": round(dev_pp, 2),
                "weight": round(share / got_share, 4) if got_share > 0 else None,
                "flag": abs(dev_pp) > tolerance_pp,
            }
        )

    warnings: list[str] = []
    missing = [k for k in census_share if achieved.get(k, 0) == 0]
    if missing:
        warnings.append(
            f"strata tanpa responden: {', '.join(missing)} — tidak dapat dibobot, "
            "estimasi untuk strata ini tidak diterbitkan"
        )
    if max_dev > tolerance_pp:
        warnings.append(
            f"deviasi maksimum {max_dev:.1f} pp melebihi toleransi {tolerance_pp} pp; "
            "pembobotan pasca-stratifikasi wajib sebelum publikasi"
        )
    if total < target_n * 0.8:
        warnings.append(f"sampel tercapai {total} dari target {target_n}")

    return BalanceReport(
        achieved_n=total,
        target_n=target_n,
        response_rate=round(total / target_n, 4) if target_n else 0.0,
        max_deviation_pp=round(max_dev, 2),
        strata=rows,
        warnings=warnings,
    )
