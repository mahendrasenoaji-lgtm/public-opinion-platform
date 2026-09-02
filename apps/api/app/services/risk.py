"""Opinion Risk Score dan Polarization Index.

Bobot bisa dikonfigurasi per proyek. Yang tidak bisa dikonfigurasi adalah
kewajiban melaporkan bobot yang dipakai bersama skornya.
"""

from __future__ import annotations

from collections.abc import Sequence
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


#: Berapa bagian bobot yang harus punya data sebelum skor gabungan boleh
#: diterbitkan.
#:
#: Angka ini yang membedakan "skor dari data yang tidak lengkap, dan kami
#: sebutkan mana yang hilang" dari "skor yang berpura-pura lengkap". Di bawah
#: ambang ini, yang benar adalah tidak memberi skor sama sekali: sebuah angka
#: 0-100 yang dihitung dari sepertiga bobotnya akan dibaca sebagai penilaian
#: risiko yang utuh, dan tidak ada catatan kaki yang bisa membatalkan kesan itu.
MIN_COVERAGE = 0.6


@dataclass(frozen=True, slots=True)
class RiskResult:
    score: int
    band: str
    components: dict[str, float]
    weights: dict[str, float]
    top_contributors: list[tuple[str, float]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PartialRiskResult:
    """Skor dari komponen yang datanya ada, beserta yang tidak ada.

    `coverage` adalah bagian bobot yang benar-benar punya data. Ia BUKAN
    metadata pelengkap: skor 62 dengan coverage 0.95 dan skor 62 dengan
    coverage 0.61 adalah dua pernyataan yang sangat berbeda, dan keduanya
    harus terbaca berbeda di layar.
    """

    score: int | None
    band: str | None
    components: dict[str, float]
    weights: dict[str, float]
    coverage: float
    missing: list[str]
    top_contributors: list[tuple[str, float]] = field(default_factory=list)
    insufficient_data: bool = False
    note: str | None = None


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


#: Skala yang menerjemahkan besaran mentah menjadi komponen 0-100.
#:
#: Semua angka di bawah adalah PENILAIAN, bukan hasil kalibrasi terhadap
#: kejadian nyata — belum ada dataset krisis opini berlabel untuk
#: mengkalibrasinya. Konsekuensinya nyata dan wajib disebut ke pengguna: skor
#: risiko ini berguna untuk MEMBANDINGKAN periode atau proyek dengan skala yang
#: sama, bukan sebagai ambang absolut ("di atas 60 berarti krisis").
#:
#: Menaruhnya sebagai konstanta bernama, bukan angka sisipan di dalam rumus,
#: supaya asumsinya bisa dilihat dan diperdebatkan tanpa membaca kode.
SENTIMENT_DROP_AT_FULL_RISK = 0.4
GROWTH_PCT_AT_FULL_RISK = 200.0
POINT_DECLINE_AT_FULL_RISK = 15.0


def _clip100(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def share_negative(scores: Sequence[float]) -> float | None:
    """Persentase konten bersentimen negatif. None bila tidak ada yang dinilai."""
    if not scores:
        return None
    negative = sum(1 for s in scores if s < -0.15)
    return _clip100(100 * negative / len(scores))


def velocity_component(recent_mean: float | None, previous_mean: float | None) -> float | None:
    """Risiko dari sentimen yang MEMBURUK, bukan dari besarnya perubahan.

    Sentimen yang membaik tajam adalah perubahan besar juga, tapi ia bukan
    risiko. Karena itu hanya arah menurun yang dihitung; perbaikan menghasilkan
    nol, bukan angka negatif yang nanti mengurangi komponen lain.
    """
    if recent_mean is None or previous_mean is None:
        return None
    drop = previous_mean - recent_mean
    return _clip100(100 * drop / SENTIMENT_DROP_AT_FULL_RISK)


def growth_component(momentum_pct: float | None) -> float | None:
    """Risiko dari pertumbuhan volume (isu atau liputan) dalam persen."""
    if momentum_pct is None:
        return None
    return _clip100(100 * momentum_pct / GROWTH_PCT_AT_FULL_RISK)


def decline_component(latest: float | None, earlier: float | None) -> float | None:
    """Risiko dari penurunan metrik berskala 0-100 (kepercayaan, persetujuan)."""
    if latest is None or earlier is None:
        return None
    return _clip100(100 * (earlier - latest) / POINT_DECLINE_AT_FULL_RISK)


def partial_risk_score(
    components: dict[str, float],
    weights: dict[str, float] | None = None,
    *,
    min_coverage: float = MIN_COVERAGE,
) -> PartialRiskResult:
    """Skor dari komponen yang tersedia saja, dengan cakupan dilaporkan.

    Berbeda dari `risk_score()` yang menolak bekerja tanpa komponen lengkap.
    Fungsi ini ada karena kenyataannya beberapa komponen menunggu sumber data
    yang mungkin tidak pernah ada di sebuah proyek — geographic_spread butuh
    geotag resmi, dan sebagian besar percakapan tidak punya itu. Menunggu
    kelengkapan sempurna berarti fitur ini tidak pernah menyala.

    Yang TIDAK dilakukan: mengisi komponen kosong dengan nol, rata-rata, atau
    tebakan. Komponen yang hilang dikeluarkan dari perhitungan dan disebut
    namanya, dan bobot yang tersisa dinormalisasi ulang.

    Perhatikan bahwa normalisasi ulang membawa asumsinya sendiri: ia
    memperlakukan komponen yang hilang seolah berperilaku seperti rata-rata
    yang ada. Itu asumsi, bukan pengukuran — dan itulah kenapa `coverage`
    wajib ikut ditampilkan alih-alih hanya skornya.
    """
    w = weights or DEFAULT_RISK_WEIGHTS
    if not 0 < min_coverage <= 1:
        raise ValueError("min_coverage harus di antara 0 dan 1")

    available = {k: components[k] for k in w if k in components}
    missing = sorted(set(w) - set(available))
    total_weight = sum(w.values())
    covered_weight = sum(w[k] for k in available)
    coverage = round(covered_weight / total_weight, 3) if total_weight else 0.0

    if coverage < min_coverage or not available:
        return PartialRiskResult(
            score=None,
            band=None,
            components=available,
            weights=w,
            coverage=coverage,
            missing=missing,
            insufficient_data=True,
            note=(
                f"Hanya {coverage:.0%} bobot risiko yang punya data "
                f"(minimum {min_coverage:.0%}). Komponen yang belum tersedia: "
                f"{', '.join(missing) if missing else '-'}."
            ),
        )

    contributions = {k: available[k] * w[k] / covered_weight for k in available}
    score = round(sum(contributions.values()))
    top = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)[:3]

    return PartialRiskResult(
        score=score,
        band=band_for(score),
        components=available,
        weights=w,
        coverage=coverage,
        missing=missing,
        top_contributors=[(k, round(v, 2)) for k, v in top],
        note=(
            None
            if not missing
            else (
                f"Dihitung dari {coverage:.0%} bobot; komponen tanpa data "
                f"dikeluarkan, bukan diisi nol: {', '.join(missing)}."
            )
        ),
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
