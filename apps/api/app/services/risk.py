"""Opinion Risk Score dan Polarization Index.

Bobot bisa dikonfigurasi per proyek. Yang tidak bisa dikonfigurasi adalah
kewajiban melaporkan bobot yang dipakai bersama skornya.
"""

from __future__ import annotations

from dataclasses import dataclass, field

RISK_BANDS = [
    (0, 20, "Low"),
    (21, 40, "Moderate"),
    (41, 60, "Elevated"),
    (61, 80, "High"),
    (81, 100, "Critical"),
]

DEFAULT_RISK_WEIGHTS = {
    "negative_sentiment": 0.18,
    "sentiment_velocity": 0.16,
    "issue_growth": 0.12,
    "narrative_polarization": 0.12,
    "influencer_amplification": 0.10,
    "geographic_spread": 0.10,
    "media_escalation": 0.10,
    "trust_decline": 0.07,
    "approval_decline": 0.05,
}


@dataclass(frozen=True, slots=True)
class RiskResult:
    score: int
    band: str
    components: dict[str, float]
    weights: dict[str, float]
    top_contributors: list[tuple[str, float]] = field(default_factory=list)


def band_for(score: float) -> str:
    for lo, hi, name in RISK_BANDS:
        if lo <= score <= hi:
            return name
    return "Critical"


def risk_score(components: dict[str, float], weights: dict[str, float] | None = None) -> RiskResult:
    """Setiap komponen sudah dinormalisasi 0-100."""
    w = weights or DEFAULT_RISK_WEIGHTS
    missing = set(w) - set(components)
    if missing:
        raise ValueError(f"komponen risiko belum lengkap: {', '.join(sorted(missing))}")

    total_w = sum(w.values())
    contributions = {k: components[k] * w[k] / total_w for k in w}
    score = round(sum(contributions.values()))
    top = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)[:3]

    return RiskResult(
        score=score,
        band=band_for(score),
        components=components,
        weights=w,
        top_contributors=[(k, round(v, 2)) for k, v in top],
    )


def polarization(segment_positions: list[tuple[str, float, float]]) -> dict[str, object]:
    """Ukur jarak antar-segmen pada sumbu opini.

    Input: (nama_segmen, posisi_-100..100, ukuran_persen).
    Bimodalitas berbobot ukuran lebih informatif daripada varians biasa: publik
    bisa punya varians tinggi tanpa terpolarisasi, kalau sebarannya rata.
    """
    if len(segment_positions) < 2:
        raise ValueError("perlu minimal dua segmen")

    total = sum(s for _, _, s in segment_positions)
    mean = sum(p * s for _, p, s in segment_positions) / total
    var = sum(s * (p - mean) ** 2 for _, p, s in segment_positions) / total

    poles = [(n, p, s) for n, p, s in segment_positions if abs(p) > 40]
    pole_mass = sum(s for _, _, s in poles) / total
    middle_mass = sum(s for _, p, s in segment_positions if abs(p) <= 20) / total

    score = round(min(100, (var**0.5) * 0.6 + pole_mass * 60))
    if pole_mass > 0.45 and middle_mass < 0.25:
        state = "terpolarisasi"
    elif middle_mass > 0.5:
        state = "menuju konsensus"
    else:
        state = "terfragmentasi"

    return {
        "polarization_score": score,
        "state": state,
        "pole_mass": round(pole_mass, 3),
        "middle_mass": round(middle_mass, 3),
        "spread": round(var**0.5, 2),
        "method": "bimodalitas berbobot ukuran segmen",
        "limitations": "Skor mengukur jarak posisi antar-segmen, bukan intensitas "
        "permusuhan antar-kelompok.",
    }
