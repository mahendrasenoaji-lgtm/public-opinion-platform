"""Communication Impact — difference-in-differences (Phase 3).

## Kenapa modul ini istimewa

Di seluruh platform ini, klaim sebab-akibat dilarang. `AIEnvelope` menolak
divalidasi kalau keluaran memuat kata "menyebabkan" atau "mengakibatkan
(app/ai/envelope.py:CAUSAL_TERMS), KECUALI `method`-nya menyebut desain
pembanding — difference-in-differences, RCT, atau synthetic control.

Modul ini satu-satunya yang berhak mengisi pengecualian itu, dan ia hanya
berhak melakukannya kalau desainnya benar-benar ada. Karena itu
`difference_in_differences()` **menolak berjalan tanpa kelompok pembanding**.
Tidak ada parameter untuk melewatinya, tidak ada mode "perkiraan kasar".
Kalau tidak ada pembanding, yang dihasilkan bukan efek yang lebih lemah —
yang dihasilkan bukan efek sama sekali, cuma perubahan sebelum-sesudah yang
tidak bisa dibedakan dari tren yang memang sudah berjalan.

## Yang diperlukan sebuah klaim efek

1. **Kelompok terpapar dan kelompok pembanding**, keduanya diukur pada dua
   periode: sebelum dan sesudah.
2. **Tren paralel sebelum perlakuan.** Inti DiD adalah asumsi bahwa tanpa
   perlakuan, kedua kelompok akan bergerak sejajar. Kalau sebelum perlakuan
   saja keduanya sudah bergerak berbeda arah, asumsi itu jatuh dan angkanya
   tidak berarti apa-apa. Modul ini memeriksanya bila datanya diberikan, dan
   MENURUNKAN status hasil kalau gagal.
3. **Ketidakpastian yang dilaporkan.** Selisih dari selisih menumpuk galat
   dari empat estimasi; interval kepercayaannya hampir selalu lebih lebar
   daripada yang diduga orang.

## Yang tetap tidak bisa dijawab

DiD memberi efek RATA-RATA pada kelompok terpapar. Ia tidak mengatakan siapa
yang berubah, tidak menjamin efeknya bertahan, dan tidak berlaku untuk
kelompok yang tidak diamati. Ia juga runtuh kalau ada hal lain yang terjadi
pada kelompok terpapar tepat pada saat yang sama — dan data ini tidak bisa
membuktikan tidak ada.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

#: Nilai z untuk interval kepercayaan yang lazim dipakai.
_Z = {0.80: 1.2816, 0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}

#: Ukuran minimum tiap sel. Empat sel dengan n kecil menghasilkan interval
#: yang begitu lebar sampai angka tengahnya tidak berarti.
MIN_CELL_N = 30

#: Selisih kemiringan tren pra-perlakuan (per periode) yang masih dianggap
#: sejajar. Di atas ini, asumsi paralel dianggap gagal.
PARALLEL_TREND_TOLERANCE = 0.5

METHOD = (
    "difference-in-differences dengan kelompok pembanding, "
    "galat baku dari empat sel independen"
)


class NoControlGroup(ValueError):
    """Diminta menghitung efek tanpa kelompok pembanding.

    Sengaja subclass ValueError supaya penanganan ValueError yang sudah ada di
    app/main.py menerjemahkannya jadi 422 dengan pesan aslinya — pesannya
    memang ditulis untuk dibaca manusia.
    """


@dataclass(frozen=True, slots=True)
class Cell:
    """Satu sel pengukuran: satu kelompok pada satu periode."""

    mean: float
    sd: float
    n: int

    def __post_init__(self) -> None:
        if self.n < 0 or self.sd < 0:
            raise ValueError("n dan sd tidak boleh negatif")

    @property
    def se(self) -> float:
        return self.sd / math.sqrt(self.n) if self.n > 0 else math.inf


@dataclass(frozen=True, slots=True)
class ImpactResult:
    """Efek rata-rata pada kelompok terpapar, atau penolakan yang beralasan."""

    effect: float | None
    ci_low: float | None
    ci_high: float | None
    ci_level: float
    #: Perubahan mentah tiap kelompok, dilaporkan supaya pembaca bisa melihat
    #: dari mana selisihnya datang.
    treated_change: float | None
    control_change: float | None
    #: True bila interval kepercayaan tidak memuat nol.
    distinguishable_from_zero: bool = False
    parallel_trends_checked: bool = False
    parallel_trends_ok: bool | None = None
    method: str = METHOD
    insufficient_data: bool = False
    note: str | None = None
    limitations: list[str] = field(default_factory=list)


def _slope(series: Sequence[float]) -> float:
    """Kemiringan rata-rata per periode. Deret pendek dianggap datar."""
    if len(series) < 2:
        return 0.0
    steps = [b - a for a, b in zip(series, series[1:], strict=False)]
    return sum(steps) / len(steps)


def check_parallel_trends(
    treated_pre: Sequence[float],
    control_pre: Sequence[float],
    *,
    tolerance: float = PARALLEL_TREND_TOLERANCE,
) -> tuple[bool, float]:
    """Apakah kedua kelompok bergerak sejajar SEBELUM perlakuan.

    Mengembalikan (lolos, selisih_kemiringan). Butuh minimal dua titik pra di
    kedua kelompok; kurang dari itu tidak bisa diperiksa, dan pemanggil harus
    memperlakukannya sebagai "tidak diperiksa", bukan "lolos".
    """
    if len(treated_pre) < 2 or len(control_pre) < 2:
        raise ValueError("perlu minimal dua pengamatan pra-perlakuan di kedua kelompok")
    difference = abs(_slope(treated_pre) - _slope(control_pre))
    return difference <= tolerance, round(difference, 3)


def difference_in_differences(
    *,
    treated_pre: Cell,
    treated_post: Cell,
    control_pre: Cell | None,
    control_post: Cell | None,
    ci_level: float = 0.95,
    treated_pre_series: Sequence[float] | None = None,
    control_pre_series: Sequence[float] | None = None,
) -> ImpactResult:
    """Efek rata-rata perlakuan, atau penolakan bila desainnya tidak memadai.

    `control_pre` / `control_post` yang None memicu NoControlGroup. Itu bukan
    kekakuan berlebihan: tanpa pembanding, yang tersisa hanyalah selisih
    sebelum-sesudah, dan selisih sebelum-sesudah tidak bisa dibedakan dari
    tren yang memang sudah berjalan. Menyebutnya "efek" akan salah, dan
    laporan yang memuatnya akan salah dengan cara yang tidak terlihat.
    """
    if control_pre is None or control_post is None:
        raise NoControlGroup(
            "Communication Impact membutuhkan kelompok pembanding yang diukur "
            "pada periode yang sama. Tanpa itu, yang bisa dihitung hanyalah "
            "perubahan sebelum-sesudah pada kelompok terpapar — dan perubahan "
            "itu tidak bisa dipisahkan dari tren yang sudah berjalan, sehingga "
            "tidak boleh disebut sebagai efek komunikasi."
        )

    if ci_level not in _Z:
        raise ValueError(f"ci_level harus salah satu dari {sorted(_Z)}")

    cells = {
        "terpapar sebelum": treated_pre,
        "terpapar sesudah": treated_post,
        "pembanding sebelum": control_pre,
        "pembanding sesudah": control_post,
    }
    thin = [name for name, c in cells.items() if c.n < MIN_CELL_N]
    if thin:
        return ImpactResult(
            effect=None,
            ci_low=None,
            ci_high=None,
            ci_level=ci_level,
            treated_change=None,
            control_change=None,
            insufficient_data=True,
            note=(
                f"Setiap sel perlu minimal {MIN_CELL_N} pengamatan. Yang belum "
                f"memenuhi: {', '.join(thin)}."
            ),
        )

    treated_change = treated_post.mean - treated_pre.mean
    control_change = control_post.mean - control_pre.mean
    effect = treated_change - control_change

    # Galat menumpuk dari keempat sel — inilah kenapa interval DiD hampir
    # selalu lebih lebar daripada yang orang duga saat melihat dua angka saja.
    se = math.sqrt(sum(c.se**2 for c in cells.values()))
    margin = _Z[ci_level] * se
    low, high = effect - margin, effect + margin

    parallel_ok: bool | None = None
    checked = False
    slope_gap = 0.0
    if treated_pre_series and control_pre_series:
        try:
            parallel_ok, slope_gap = check_parallel_trends(
                treated_pre_series, control_pre_series
            )
            checked = True
        except ValueError:
            parallel_ok, checked = None, False

    limitations = [
        "Efek yang dilaporkan adalah rata-rata pada kelompok terpapar. Ia tidak "
        "mengatakan siapa yang berubah, dan tidak menjamin efeknya bertahan.",
        "Desain ini runtuh bila ada peristiwa lain yang mengenai kelompok "
        "terpapar pada periode yang sama. Data ini tidak bisa membuktikan tidak "
        "ada peristiwa seperti itu.",
    ]
    if not checked:
        limitations.append(
            "Asumsi tren paralel TIDAK diperiksa karena tidak ada deret "
            "pra-perlakuan yang diberikan. Tanpa pemeriksaan itu, angka ini "
            "bersandar pada asumsi yang belum diuji."
        )
    elif parallel_ok is False:
        limitations.append(
            f"Asumsi tren paralel GAGAL: kedua kelompok sudah bergerak berbeda "
            f"{slope_gap} per periode sebelum perlakuan. Angka di atas tidak "
            "boleh dibaca sebagai efek."
        )

    distinguishable = (low > 0) or (high < 0)
    note = None
    if not distinguishable:
        note = (
            "Interval kepercayaan memuat nol: data ini belum cukup untuk "
            "membedakan efeknya dari nol. Itu bukan bukti bahwa efeknya tidak "
            "ada, melainkan bahwa pengukuran ini tidak bisa memastikannya."
        )
    if parallel_ok is False:
        note = (
            "Asumsi tren paralel gagal, sehingga selisih di atas tidak bisa "
            "ditafsirkan sebagai efek komunikasi."
        )

    return ImpactResult(
        effect=round(effect, 3),
        ci_low=round(low, 3),
        ci_high=round(high, 3),
        ci_level=ci_level,
        treated_change=round(treated_change, 3),
        control_change=round(control_change, 3),
        distinguishable_from_zero=distinguishable and parallel_ok is not False,
        parallel_trends_checked=checked,
        parallel_trends_ok=parallel_ok,
        insufficient_data=False,
        note=note,
        limitations=limitations,
    )
