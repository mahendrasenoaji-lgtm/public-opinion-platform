"""Public Opinion Index.

Fungsi murni, tanpa I/O. Router menyediakan data, modul ini menghitung.

Prinsip yang ditegakkan di sini (CLAUDE.md R1): setiap dimensi membawa
`source`-nya sendiri. Indeks gabungan tetap boleh dihitung, tetapi hasilnya
selalu melaporkan komposisi sumbernya, sehingga konsumen tahu bagian mana dari
angka yang bisa digeneralisasi ke populasi dan bagian mana yang tidak.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

# Ambang minimum sampel efektif untuk menerbitkan skor wilayah.
# Di bawah ini, kembalikan None dan tampilkan "data tidak cukup".
MIN_EFFECTIVE_N = 250

# Nilai z untuk interval kepercayaan dua sisi.
Z = {0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}


class SignalSource(StrEnum):
    SURVEY = "SURVEY"
    SOCIAL = "SOCIAL"
    MEDIA = "MEDIA"
    DIGITAL = "DIGITAL"


#: Sumber yang boleh diklaim mewakili populasi.
GENERALISABLE = {SignalSource.SURVEY}


@dataclass(frozen=True, slots=True)
class Dimension:
    """Satu dimensi penyusun indeks, sudah dinormalisasi ke 0–100."""

    key: str
    label: str
    score: float
    weight: float
    source: SignalSource
    effective_n: int | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 100:
            raise ValueError(f"skor {self.key} di luar rentang 0–100: {self.score}")
        if self.weight < 0:
            raise ValueError(f"bobot {self.key} negatif")


@dataclass(frozen=True, slots=True)
class IndexResult:
    value: float
    ci_low: float | None
    ci_high: float | None
    effective_n: int | None
    method: str
    #: Proporsi bobot per sumber, mis. {"SURVEY": 0.70, "SOCIAL": 0.20}
    source_mix: dict[str, float] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)

    @property
    def generalisable_share(self) -> float:
        """Berapa bagian indeks yang berasal dari sumber probabilistik."""
        return sum(v for k, v in self.source_mix.items() if SignalSource(k) in GENERALISABLE)


def normalise_weights(dims: list[Dimension]) -> list[float]:
    """Bobot yang masuk dari konfigurasi proyek tidak dijamin berjumlah 100."""
    total = sum(d.weight for d in dims)
    if total <= 0:
        raise ValueError("total bobot harus > 0")
    return [d.weight / total for d in dims]


def effective_sample_size(weights: list[float]) -> float:
    """Kish's effective sample size — sampel berbobot 'berharga' lebih sedikit.

    n_eff = (sum w)^2 / sum(w^2). Dipakai agar CI tidak terlalu optimistis
    setelah pembobotan pasca-stratifikasi.
    """
    if not weights:
        return 0.0
    s1 = sum(weights)
    s2 = sum(w * w for w in weights)
    return (s1 * s1) / s2 if s2 > 0 else 0.0


def compute_index(
    dims: list[Dimension],
    *,
    confidence: float = 0.95,
    respondent_weights: list[float] | None = None,
) -> IndexResult:
    """Hitung POI dari dimensi yang diberikan.

    CI hanya dihitung dari komponen probabilistik. Kalau tidak ada komponen
    survei sama sekali, indeks tetap keluar tetapi tanpa interval kepercayaan —
    memberi CI pada agregasi media sosial akan menyesatkan.
    """
    if not dims:
        raise ValueError("tidak ada dimensi untuk dihitung")

    norm = normalise_weights(dims)
    value = sum(d.score * w for d, w in zip(dims, norm))

    mix: dict[str, float] = {}
    for d, w in zip(dims, norm):
        mix[d.source.value] = round(mix.get(d.source.value, 0.0) + w, 4)

    survey_dims = [(d, w) for d, w in zip(dims, norm) if d.source in GENERALISABLE]
    survey_share = sum(w for _, w in survey_dims)

    n_eff: int | None = None
    ci_low = ci_high = None
    limitations: list[str] = []

    if survey_dims:
        if respondent_weights:
            n_eff = int(effective_sample_size(respondent_weights))
        else:
            ns = [d.effective_n for d, _ in survey_dims if d.effective_n]
            n_eff = min(ns) if ns else None

        if n_eff and n_eff > 0:
            # Perlakukan skor 0–100 sebagai proporsi berskala; sd maksimum
            # pada p=0.5 memberi batas atas margin yang konservatif.
            z = Z.get(confidence, Z[0.95])
            margin = z * 50.0 / math.sqrt(n_eff)
            # Margin hanya berlaku pada porsi indeks yang berasal dari survei.
            margin *= survey_share
            ci_low = round(max(0.0, value - margin), 2)
            ci_high = round(min(100.0, value + margin), 2)

    if survey_share < 1.0:
        non_survey = sorted({d.source.value for d in dims if d.source not in GENERALISABLE})
        limitations.append(
            f"{round((1 - survey_share) * 100)}% bobot indeks berasal dari sumber "
            f"non-probabilistik ({', '.join(non_survey)}) dan tidak dapat "
            "digeneralisasi ke populasi"
        )
    if n_eff is not None and n_eff < MIN_EFFECTIVE_N:
        limitations.append(
            f"sampel efektif {n_eff} di bawah ambang publikasi {MIN_EFFECTIVE_N}"
        )
    if ci_low is None:
        limitations.append("tidak ada komponen probabilistik; interval kepercayaan tidak dihitung")

    return IndexResult(
        value=round(value, 2),
        ci_low=ci_low,
        ci_high=ci_high,
        effective_n=n_eff,
        method="rata-rata tertimbang dimensi, dinormalisasi 0–100",
        source_mix=mix,
        limitations=limitations,
    )


def publishable(result: IndexResult) -> bool:
    """Apakah skor ini boleh ditampilkan sebagai angka, atau harus 'data tidak cukup'."""
    return result.effective_n is not None and result.effective_n >= MIN_EFFECTIVE_N


def compute_change(current: IndexResult, previous: IndexResult) -> dict[str, object]:
    """Perubahan antar periode, disertai penanda apakah perubahan itu berarti.

    Dua CI yang bertumpang tindih bukan bukti tidak ada perubahan, tapi CI yang
    tidak bertumpang tindih adalah indikasi yang cukup kuat untuk dilaporkan.
    """
    delta = round(current.value - previous.value, 2)
    separated = (
        current.ci_low is not None
        and previous.ci_high is not None
        and current.ci_high is not None
        and previous.ci_low is not None
        and (current.ci_low > previous.ci_high or current.ci_high < previous.ci_low)
    )
    return {
        "delta": delta,
        "direction": "naik" if delta > 0 else "turun" if delta < 0 else "tetap",
        "intervals_separated": separated,
        "note": (
            "interval kepercayaan tidak bertumpang tindih"
            if separated
            else "interval kepercayaan bertumpang tindih; perubahan belum tentu berarti"
        ),
    }
