"""Signal divergence — pembeda utama produk.

Menjawab: kenapa survei, media sosial, dan media bisa memberi angka berbeda
untuk pertanyaan yang sama, dan seberapa besar bedanya patut dikhawatirkan.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.services.poi import SignalSource

#: Selisih di bawah ini normal untuk instrumen yang berbeda; di atasnya layak
#: dijelaskan ke pengguna. Angka empiris, disetel per proyek bila perlu.
NOTABLE_GAP = 15.0


@dataclass(frozen=True, slots=True)
class SignalReading:
    source: SignalSource
    value: float
    n: int
    method: str
    known_bias: str


@dataclass(frozen=True, slots=True)
class DivergenceResult:
    readings: list[SignalReading]
    gap: float
    lowest: SignalSource
    highest: SignalSource
    is_notable: bool
    explanations: list[dict[str, str]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


#: Penjelasan kandidat. Yang dipilih hanya yang kondisinya terpenuhi — bukan
#: semuanya ditempel setiap saat.
_EXPLANATIONS: list[tuple[str, str, Callable[[float, float, float], bool]]] = [
    (
        "Self-selection",
        "Yang menulis di media sosial cenderung yang punya keluhan. Kelompok "
        "puas jarang memposting, sehingga sentiment sosial secara sistematis "
        "lebih rendah dari survei.",
        lambda s, so, m: so < s - 10,
    ),
    (
        "Komposisi demografis",
        "Percakapan didominasi usia muda dan wilayah urban. Segmen usia lanjut "
        "yang biasanya lebih mendukung hampir tidak terwakili.",
        lambda s, so, m: abs(s - so) > 10,
    ),
    (
        "Waktu pengukuran",
        "Gelombang survei ditutup lebih awal dari puncak percakapan, sehingga "
        "sebagian pergeseran opini belum tertangkap survei.",
        lambda s, so, m: True,
    ),
    (
        "Framing media",
        "Media memberi ruang pada beberapa narasi sekaligus, sehingga stance "
        "agregatnya berada di antara survei dan percakapan sosial.",
        lambda s, so, m: min(s, so) < m < max(s, so),
    ),
]


def analyse(readings: list[SignalReading]) -> DivergenceResult:
    if len(readings) < 2:
        raise ValueError("perlu minimal dua sumber untuk membandingkan")

    by_source = {r.source: r.value for r in readings}
    lo = min(readings, key=lambda r: r.value)
    hi = max(readings, key=lambda r: r.value)
    gap = round(hi.value - lo.value, 1)

    s = by_source.get(SignalSource.SURVEY, 0.0)
    so = by_source.get(SignalSource.SOCIAL, 0.0)
    m = by_source.get(SignalSource.MEDIA, (s + so) / 2)

    explanations = [
        {"factor": name, "text": text} for name, text, cond in _EXPLANATIONS if cond(s, so, m)
    ]

    limitations = [
        "Kontribusi tiap faktor adalah estimasi kualitatif, bukan dekomposisi varians yang eksak.",
        "Angka media sosial tidak dapat dibobot ke populasi nasional.",
    ]
    small = [r for r in readings if r.source is SignalSource.SURVEY and r.n < 400]
    if small:
        limitations.append(
            "Sampel survei di bawah 400; selisih sebagian bisa berasal dari galat sampling."
        )

    return DivergenceResult(
        readings=readings,
        gap=gap,
        lowest=lo.source,
        highest=hi.source,
        is_notable=gap >= NOTABLE_GAP,
        explanations=explanations,
        limitations=limitations,
    )
