"""Forecast dan What-If simulation.

Model produksi (state-space / SARIMAX) hidup di worker terpisah. Modul ini
berisi lapisan deterministik yang dipakai API: penerapan skenario ke baseline,
pelebaran interval prediksi, dan pelabelan hasil sebagai simulasi.

Catatan penting: ketidakpastian TIDAK boleh menyempit ketika pengguna menambah
asumsi. Skenario yang lebih ekstrem berarti kita tahu lebih sedikit, bukan lebih
banyak.
"""

from __future__ import annotations

from dataclasses import dataclass, field

HORIZONS = (1, 3, 7, 14, 30, 90)


@dataclass(frozen=True, slots=True)
class Driver:
    """Regresor eksogen beserta koefisiennya pada horizon penuh."""

    key: str
    label: str
    coefficient: float
    unit: str
    #: Seberapa besar driver ini melebarkan ketidakpastian per unit.
    uncertainty_per_unit: float = 0.06


DEFAULT_DRIVERS = [
    Driver("food_price", "Kenaikan harga pangan", -0.72, "%", 0.05),
    Driver("comms_intensity", "Intensitas komunikasi publik", 0.34, "unit", 0.04),
    Driver("negative_coverage", "Eskalasi liputan negatif", -0.28, "unit", 0.09),
]


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    horizon_days: int
    expected: float
    pi_low: float
    pi_high: float


@dataclass(frozen=True, slots=True)
class ForecastResult:
    points: list[ForecastPoint]
    pi_level: float
    model: str
    is_simulation: bool
    scenario: dict[str, float] = field(default_factory=dict)
    driver_contributions: list[dict[str, object]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


def _ramp(horizon: int, max_horizon: int) -> float:
    """Efek skenario tidak instan; ia menumpuk sepanjang horizon."""
    return min(1.0, horizon / max_horizon)


def project(
    *,
    baseline: float,
    base_spread: dict[int, float],
    scenario: dict[str, float] | None = None,
    drivers: list[Driver] | None = None,
    pi_level: float = 0.80,
    model: str = "state-space + regresor eksogen",
) -> ForecastResult:
    """Hasilkan lintasan forecast, dengan atau tanpa skenario.

    `base_spread` adalah setengah lebar interval prediksi baseline per horizon,
    hasil estimasi historis dari worker.
    """
    drivers = drivers or DEFAULT_DRIVERS
    scenario = {k: v for k, v in (scenario or {}).items() if v}
    by_key = {d.key: d for d in drivers}

    unknown = set(scenario) - set(by_key)
    if unknown:
        raise ValueError(f"driver tidak dikenal: {', '.join(sorted(unknown))}")

    max_h = max(base_spread)
    total_effect = sum(by_key[k].coefficient * v for k, v in scenario.items())
    extra_uncertainty = sum(by_key[k].uncertainty_per_unit * abs(v) for k, v in scenario.items())

    points: list[ForecastPoint] = []
    for h in sorted(base_spread):
        r = _ramp(h, max_h)
        expected = baseline + total_effect * r
        spread = base_spread[h] + extra_uncertainty * r
        points.append(
            ForecastPoint(
                horizon_days=h,
                expected=round(expected, 1),
                pi_low=round(max(0.0, expected - spread), 1),
                pi_high=round(min(100.0, expected + spread), 1),
            )
        )

    contributions = [
        {
            "driver": by_key[k].label,
            "input": v,
            "unit": by_key[k].unit,
            "effect_at_max_horizon": round(by_key[k].coefficient * v, 2),
        }
        for k, v in scenario.items()
    ]

    limitations = [
        "Koefisien diestimasi pada periode tanpa guncangan besar dan tidak valid "
        "untuk skenario ekstrem.",
        "Interval prediksi mencakup ketidakpastian model, bukan peristiwa yang "
        "belum pernah terjadi dalam data historis.",
    ]
    if scenario:
        limitations.insert(
            0,
            "Angka ini hasil simulasi berdasarkan koefisien historis, bukan "
            "prediksi yang dijamin, dan tidak boleh menjadi dasar tunggal "
            "pengambilan keputusan.",
        )

    return ForecastResult(
        points=points,
        pi_level=pi_level,
        model=model,
        is_simulation=bool(scenario),
        scenario=scenario,
        driver_contributions=contributions,
        limitations=limitations,
    )


DEFAULT_SPREAD = {1: 0.8, 3: 1.5, 7: 2.3, 14: 3.3, 30: 4.5, 90: 7.2}
