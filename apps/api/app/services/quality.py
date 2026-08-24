"""Deteksi kualitas respons.

Modul ini TIDAK menyimpulkan kecurangan. Ia menghasilkan flag untuk ditinjau
manusia (CLAUDE.md §3). Responden yang ditandai tetap masuk dataset sampai
seorang peneliti memutuskan sebaliknya, dan keputusan itu tercatat di audit log.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from enum import StrEnum


class QualityFlag(StrEnum):
    SPEEDING = "SPEEDING"
    STRAIGHT_LINING = "STRAIGHT_LINING"
    INCONSISTENT = "INCONSISTENT"
    DUPLICATE_SUSPECT = "DUPLICATE_SUSPECT"
    OUT_OF_QUOTA = "OUT_OF_QUOTA"


@dataclass(frozen=True, slots=True)
class QualityResult:
    score: int
    flags: list[QualityFlag]
    reasons: list[str] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return bool(self.flags)


def assess(
    *,
    duration_sec: int,
    median_duration_sec: float,
    scale_answers: list[float],
    scale_points: int = 5,
    trap_pairs: list[tuple[float, float]] | None = None,
    speeding_ratio: float = 0.35,
) -> QualityResult:
    """Nilai satu respons.

    - speeding: durasi jauh di bawah median lapangan
    - straight lining: variasi nol pada blok skala yang cukup panjang
    - inconsistent: pasangan item yang seharusnya berlawanan dijawab sama
    """
    flags: list[QualityFlag] = []
    reasons: list[str] = []
    score = 100

    if median_duration_sec > 0 and duration_sec < median_duration_sec * speeding_ratio:
        flags.append(QualityFlag.SPEEDING)
        reasons.append(
            f"durasi {duration_sec}s, di bawah {speeding_ratio:.0%} median lapangan "
            f"({median_duration_sec:.0f}s)"
        )
        score -= 30

    if len(scale_answers) >= 6:
        sd = statistics.pstdev(scale_answers)
        if sd == 0:
            flags.append(QualityFlag.STRAIGHT_LINING)
            reasons.append(f"{len(scale_answers)} item skala dijawab dengan nilai identik")
            score -= 35
        elif sd < 0.25:
            reasons.append(f"variasi jawaban skala sangat rendah (sd={sd:.2f})")
            score -= 10

    for a, b in trap_pairs or []:
        # Item yang saling berlawanan seharusnya berjumlah mendekati skala+1
        if abs((a + b) - (scale_points + 1)) > 2:
            flags.append(QualityFlag.INCONSISTENT)
            reasons.append("pasangan item pembanding dijawab tidak konsisten")
            score -= 20
            break

    return QualityResult(score=max(0, score), flags=list(dict.fromkeys(flags)), reasons=reasons)


def dataset_quality(
    *,
    total: int,
    complete: int,
    duplicates: int,
    flagged: int,
    inconsistent: int,
    max_stratum_deviation_pp: float,
    metadata_fields_filled: float,
) -> dict[str, int]:
    """Data Quality Score 0-100 per dataset."""

    def pct(n: int, d: int) -> int:
        return round(100 * n / d) if d else 0

    completeness = pct(complete, total)
    duplicate = 100 - pct(duplicates, total)
    response_qual = 100 - pct(flagged, total)
    consistency = 100 - pct(inconsistent, total)
    balance = max(0, round(100 - max_stratum_deviation_pp * 5))
    meta = round(metadata_fields_filled * 100)

    parts = {
        "completeness": completeness,
        "duplicate": duplicate,
        "response_qual": response_qual,
        "consistency": consistency,
        "sample_balance": balance,
        "metadata_score": meta,
    }
    # Keseimbangan sampel dibobot lebih tinggi: ia yang paling menentukan
    # apakah estimasi boleh digeneralisasi.
    weights = {
        "completeness": 1,
        "duplicate": 1,
        "response_qual": 1.5,
        "consistency": 1,
        "sample_balance": 2,
        "metadata_score": 0.5,
    }
    total_w = sum(weights.values())
    parts["overall"] = round(sum(parts[k] * weights[k] for k in weights) / total_w)
    return parts
