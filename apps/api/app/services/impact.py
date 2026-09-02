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

import numpy as np
from scipy.optimize import minimize

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


# ============================================================================
# Synthetic control (Abadie, Diamond & Hainmueller)
# ============================================================================
#
# Desain pembanding kedua yang boleh mengisi pengecualian klaim kausal di
# AIEnvelope (lihat docstring modul). Dipilih ketika TIDAK ada satu kelompok
# pembanding tunggal yang meyakinkan, tapi ADA beberapa kandidat ("donor")
# yang masing-masing tidak terpapar perlakuan. Alih-alih memilih satu, metode
# ini membentuk UNIT SINTETIS: kombinasi berbobot para donor yang paling
# mendekati lintasan unit terpapar SEBELUM perlakuan.
#
# Intuisinya: kalau kombinasi donor itu berhasil meniru unit terpapar dengan
# akurat selama periode PRA-perlakuan (saat keduanya sama-sama tidak
# terpapar), maka kombinasi yang sama punya alasan kuat untuk dipercaya
# sebagai perkiraan "apa yang akan terjadi tanpa perlakuan" pada periode
# PASCA-perlakuan. Selisih antara unit terpapar sungguhan dan unit sintetis
# itulah efeknya.

#: Donor minimum. Bukan cuma supaya bobotnya tidak trivial (1 donor = bobot
#: 100% ke situ) -- juga supaya inferensi placebo (di bawah) masih punya
#: sisa donor yang cukup di tiap iterasi leave-one-out.
MIN_DONORS = 5

#: RMSPE (root mean squared prediction error) pra-perlakuan, relatif terhadap
#: simpangan baku deret unit terpapar sendiri. Di atas ini, unit sintetis
#: dianggap TIDAK cukup mirip untuk dipercaya sebagai kontrafaktual -- angka
#: pembobotan ini penilaian metodologis (rujuk Abadie et al.), bukan hasil
#: kalibrasi terhadap data proyek ini.
REL_FIT_THRESHOLD = 0.5

METHOD_SC = (
    "synthetic control (Abadie et al.) -- unit sintetis dari kombinasi "
    "berbobot donor, signifikansi dari uji permutasi placebo"
)


@dataclass(frozen=True, slots=True)
class SyntheticControlResult:
    effect: float | None
    treated_post: float | None
    synthetic_post: float | None
    #: Hanya donor dengan bobot > 0 (setelah dibulatkan) yang disertakan --
    #: donor berbobot nol tidak ikut membentuk unit sintetis sama sekali.
    weights: dict[str, float] = field(default_factory=dict)
    donors_used: int = 0
    n_pre_periods: int = 0
    pre_fit_rmspe: float | None = None
    #: True kalau RMSPE pra-perlakuan cukup kecil untuk dipercaya. False
    #: berarti unit sintetis tidak meniru unit terpapar dengan baik SEBELUM
    #: perlakuan pun -- efek pasca-perlakuan tidak boleh ditafsirkan.
    fit_quality_ok: bool | None = None
    #: Efek placebo per donor (leave-one-out: donor itu diperlakukan seolah
    #: "terpapar", sisanya jadi donor poolnya). Dipakai menghitung rank_p_value.
    placebo_effects: dict[str, float] = field(default_factory=dict)
    #: Porsi efek placebo (dari SEMUA donor) yang magnitudonya >= magnitudo
    #: efek unit terpapar sungguhan. Kecil berarti efeknya ekstrem dibanding
    #: seandainya "perlakuan" itu jatuh ke unit lain secara acak -- ini uji
    #: permutasi, BUKAN p-value uji-t klasik.
    rank_p_value: float | None = None
    method: str = METHOD_SC
    insufficient_data: bool = False
    note: str | None = None
    limitations: list[str] = field(default_factory=list)


def _fit_donor_weights(pre_matrix: np.ndarray, target_pre: np.ndarray) -> np.ndarray:
    """Bobot non-negatif berjumlah 1 yang meminimalkan galat kuadrat
    pra-perlakuan. Optimasi cembung kecil (SLSQP) -- jumlah donor di proyek
    ini tidak pernah cukup besar untuk butuh solver khusus."""
    n_donors = pre_matrix.shape[1]
    x0 = np.full(n_donors, 1.0 / n_donors)

    def objective(w: np.ndarray) -> float:
        diff = target_pre - pre_matrix @ w
        return float(diff @ diff)

    result = minimize(
        objective,
        x0,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * n_donors,
        constraints=[{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}],
        options={"maxiter": 1000, "ftol": 1e-10},
    )
    w = np.clip(result.x, 0.0, None)
    total = w.sum()
    return w / total if total > 1e-9 else x0


def synthetic_control(
    *,
    treated_pre: Sequence[float],
    treated_post: float,
    donors_pre: dict[str, Sequence[float]],
    donors_post: dict[str, float],
    min_donors: int = MIN_DONORS,
) -> SyntheticControlResult:
    """Estimasi efek lewat unit sintetis dari kombinasi berbobot donor.

    `donors_pre` dan `donors_post` HARUS memuat unit yang sama persis, dan
    setiap deret pra-perlakuan donor harus sepanjang `treated_pre`.

    Menolak (insufficient_data) kalau donor kurang dari `min_donors`, ATAU
    kalau jumlah periode pra-perlakuan TIDAK LEBIH BANYAK dari jumlah donor.
    Yang kedua bukan kehati-hatian berlebihan: dengan donor >= periode,
    optimasi bisa mencocokkan deret unit terpapar secara SEMPURNA meski
    donornya sama sekali tidak mirip secara substantif -- derajat kebebasan
    yang cukup untuk overfit selalu ada. RMSPE pra-perlakuan yang tampak
    bagus dalam keadaan itu tidak membuktikan apa-apa.
    """
    if set(donors_pre) != set(donors_post):
        raise ValueError("donors_pre dan donors_post harus memuat unit yang sama persis")

    n_donors = len(donors_pre)
    n_pre = len(treated_pre)

    if n_donors < min_donors:
        return SyntheticControlResult(
            effect=None, treated_post=None, synthetic_post=None,
            donors_used=n_donors, n_pre_periods=n_pre,
            insufficient_data=True,
            note=f"Perlu minimal {min_donors} unit donor; tersedia {n_donors}.",
        )
    if any(len(s) != n_pre for s in donors_pre.values()):
        raise ValueError(
            "setiap donor harus punya jumlah periode pra-perlakuan yang sama "
            "dengan unit terpapar"
        )
    if n_pre <= n_donors:
        return SyntheticControlResult(
            effect=None, treated_post=None, synthetic_post=None,
            donors_used=n_donors, n_pre_periods=n_pre,
            insufficient_data=True,
            note=(
                f"Jumlah periode pra-perlakuan ({n_pre}) harus lebih banyak "
                f"dari jumlah donor ({n_donors}), kalau tidak kecocokan "
                "pra-perlakuan bisa sempurna secara trivial tanpa berarti "
                "apa-apa (derajat kebebasan cukup untuk overfit)."
            ),
        )

    names = sorted(donors_pre)  # urutan deterministik -> hasil bisa direproduksi
    pre_matrix = np.array([donors_pre[n] for n in names], dtype=float).T
    treated_arr = np.array(treated_pre, dtype=float)

    w = _fit_donor_weights(pre_matrix, treated_arr)
    weights = {names[i]: round(float(w[i]), 4) for i in range(len(names)) if w[i] > 1e-4}

    synthetic_pre = pre_matrix @ w
    rmspe = float(np.sqrt(np.mean((treated_arr - synthetic_pre) ** 2)))
    treated_sd = float(np.std(treated_arr))
    fit_ok = rmspe <= REL_FIT_THRESHOLD * treated_sd if treated_sd > 1e-9 else rmspe < 1e-6

    synthetic_post = float(sum(w[i] * donors_post[names[i]] for i in range(len(names))))
    effect = treated_post - synthetic_post

    # Placebo leave-one-out: tiap donor bergiliran diperlakukan seolah
    # "terpapar" dengan sisa donor sebagai pool-nya sendiri. Distribusi efek
    # placebo ini adalah dasar rank_p_value -- bukan asumsi distribusi normal.
    placebo_effects: dict[str, float] = {}
    for name in names:
        others = [n for n in names if n != name]
        if len(others) < 3:
            continue
        other_matrix = np.array([donors_pre[n] for n in others], dtype=float).T
        placebo_target = np.array(donors_pre[name], dtype=float)
        w_p = _fit_donor_weights(other_matrix, placebo_target)
        synth_p_post = float(sum(w_p[i] * donors_post[others[i]] for i in range(len(others))))
        placebo_effects[name] = round(donors_post[name] - synth_p_post, 3)

    rank_p_value = None
    if placebo_effects:
        count_ge = sum(1 for v in placebo_effects.values() if abs(v) >= abs(effect))
        rank_p_value = round((count_ge + 1) / (len(placebo_effects) + 1), 3)

    limitations = [
        "Efek dibandingkan terhadap unit SINTETIS (kombinasi berbobot donor), "
        "bukan satu kelompok pembanding tunggal. Keandalannya bergantung "
        "sepenuhnya pada seberapa dekat unit sintetis meniru unit terpapar "
        "SEBELUM perlakuan -- lihat pre_fit_rmspe dan fit_quality_ok.",
        "rank_p_value dari uji permutasi (placebo leave-one-out pada donor), "
        "bukan uji-t klasik: ia menjawab 'seberapa ekstrem efek ini "
        "dibandingkan seandainya perlakuan jatuh ke unit lain secara acak', "
        "bukan probabilitas dari asumsi distribusi tertentu.",
        "Efek rata-rata pada unit terpapar. Tidak mengatakan siapa yang "
        "berubah, dan tidak menjamin efeknya bertahan.",
    ]
    if not fit_ok:
        limitations.insert(
            0,
            "Unit sintetis TIDAK meniru unit terpapar dengan cukup baik pada "
            "periode pra-perlakuan (RMSPE melebihi ambang). Efek pasca-"
            "perlakuan di bawah ini tidak boleh ditafsirkan sebagai estimasi "
            "yang bisa dipercaya.",
        )

    return SyntheticControlResult(
        effect=round(effect, 3),
        treated_post=round(treated_post, 3),
        synthetic_post=round(synthetic_post, 3),
        weights=weights,
        donors_used=n_donors,
        n_pre_periods=n_pre,
        pre_fit_rmspe=round(rmspe, 3),
        fit_quality_ok=fit_ok,
        placebo_effects=placebo_effects,
        rank_p_value=rank_p_value,
        insufficient_data=False,
        note=None if fit_ok else "Kecocokan pra-perlakuan buruk -- lihat limitations.",
        limitations=limitations,
    )
