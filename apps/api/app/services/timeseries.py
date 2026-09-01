"""Estimasi model deret waktu untuk forecast (Phase 3).

`services/forecast.py` sejak awal memuat lapisan deterministik — penerapan
skenario ke sebuah baseline dan pelebaran interval — dengan catatan bahwa
"model produksi (state-space / SARIMAX) hidup di worker terpisah". Worker itu
tidak pernah ada, dan `DEFAULT_SPREAD` yang dipakai selama ini adalah angka
tetap yang ditulis tangan, bukan hasil estimasi dari data proyek mana pun.

Modul ini yang mengisinya: state-space (`UnobservedComponents`) yang benar-
benar di-fit pada riwayat `metric_snapshots` proyek, menghasilkan baseline dan
lebar interval prediksi dari data proyek itu sendiri.

## Tiga hal yang menentukan apakah hasilnya boleh dipercaya

**Panjang riwayat.** Di bawah MIN_OBSERVATIONS, modul ini MENOLAK memberi
angka. State-space akan tetap menghasilkan sesuatu dari 4 titik; sesuatu itu
adalah garis yang ditarik lewat derau, dan ia akan ditampilkan dengan interval
prediksi yang tampak meyakinkan. Lebih baik mengatakan riwayatnya belum cukup.

**Jarak antar-pengamatan.** Snapshot survei tidak datang setiap hari; ia datang
per gelombang, dan jaraknya tidak selalu sama. Model di-fit pada urutan
pengamatan (dianggap berjarak sama), lalu horizon dalam HARI diterjemahkan ke
langkah memakai jarak median antar-pengamatan. Asumsi itu dilaporkan sebagai
batasan, tidak disembunyikan — kalau gelombangnya sangat tidak teratur,
terjemahan itu kasar.

**Horizon melampaui riwayat.** Meramal 90 hari ke depan dari riwayat 60 hari
adalah ekstrapolasi, bukan estimasi. Modul ini tetap menghitungnya (intervalnya
akan melebar sendiri) tapi menandainya di `limitations`.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from statistics import median

import numpy as np
from statsmodels.tsa.statespace.structural import UnobservedComponents

#: Di bawah ini, tidak ada angka yang diterbitkan. Bukan batas teknis
#: statsmodels — batas kelayakan. Delapan pengamatan adalah minimum kasar
#: untuk memisahkan level dari derau; di bawah itu yang terestimasi adalah
#: deraunya sendiri.
MIN_OBSERVATIONS = 8

#: Di bawah ini, tren tidak ikut diestimasi — hanya level. Local linear trend
#: punya dua komponen varians yang harus diestimasi; pada riwayat pendek
#: keduanya tidak teridentifikasi dan hasilnya tren palsu yang tajam.
MIN_OBSERVATIONS_FOR_TREND = 12

DEFAULT_HORIZONS = (1, 3, 7, 14, 30, 90)


@dataclass(frozen=True, slots=True)
class FittedForecast:
    """Hasil estimasi. `insufficient_data` menentukan sisanya boleh dipakai."""

    baseline: float | None
    #: horizon (hari) -> setengah lebar interval prediksi
    spread: dict[int, float] = field(default_factory=dict)
    #: horizon (hari) -> nilai harapan model, sebelum skenario diterapkan
    expected: dict[int, float] = field(default_factory=dict)
    model: str = ""
    n_observations: int = 0
    observed_span_days: int = 0
    median_step_days: float = 0.0
    insufficient_data: bool = False
    note: str | None = None
    limitations: list[str] = field(default_factory=list)


def _model_name(with_trend: bool) -> str:
    komponen = "level lokal + tren" if with_trend else "level lokal"
    return f"state-space ({komponen}), di-fit pada riwayat proyek"


def fit(
    observations: Sequence[tuple[date, float]],
    *,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    pi_level: float = 0.80,
) -> FittedForecast:
    """Estimasi model dari riwayat sebuah metrik.

    `observations` adalah pasangan (tanggal, nilai) yang TIDAK harus terurut —
    diurutkan di sini. Tanggal ganda diambil yang terakhir: dua snapshot untuk
    periode yang sama berarti yang belakangan adalah koreksi.
    """
    if not 0.5 <= pi_level < 1.0:
        raise ValueError("pi_level harus di antara 0.5 dan 1.0")

    by_date: dict[date, float] = {}
    for when, value in sorted(observations, key=lambda o: o[0]):
        by_date[when] = value

    dates = sorted(by_date)
    values = [by_date[d] for d in dates]
    n = len(values)

    if n < MIN_OBSERVATIONS:
        return FittedForecast(
            baseline=None,
            n_observations=n,
            insufficient_data=True,
            note=(
                f"Perlu minimal {MIN_OBSERVATIONS} pengamatan historis untuk "
                f"mengestimasi model; tersedia {n}."
            ),
        )

    # strict=False disengaja: dates[1:] memang satu lebih pendek — itu yang
    # membuatnya berpasangan sebagai (sebelum, sesudah).
    steps_days = [(b - a).days for a, b in zip(dates, dates[1:], strict=False)]
    median_step = float(median(steps_days)) if steps_days else 1.0
    if median_step <= 0:
        median_step = 1.0
    span_days = (dates[-1] - dates[0]).days

    with_trend = n >= MIN_OBSERVATIONS_FOR_TREND
    endog = np.asarray(values, dtype=float)

    try:
        with warnings.catch_warnings():
            # statsmodels berisik soal konvergensi dan tanggal yang tidak
            # punya frekuensi; keduanya sudah kita tangani secara eksplisit
            # (riwayat pendek ditolak di atas, jarak dihitung sendiri).
            warnings.simplefilter("ignore")
            fitted = UnobservedComponents(
                endog,
                level="local linear trend" if with_trend else "local level",
            ).fit(disp=False)

            max_steps = max(1, int(np.ceil(max(horizons) / median_step)))
            prediction = fitted.get_forecast(steps=max_steps)
            mean = np.asarray(prediction.predicted_mean, dtype=float)
            interval = np.asarray(
                prediction.conf_int(alpha=1 - pi_level), dtype=float
            )
    except (ValueError, np.linalg.LinAlgError) as e:
        # Riwayat yang konstan sempurna atau degenerate membuat estimasi
        # gagal. Itu keadaan yang sah untuk dilaporkan, bukan 500.
        return FittedForecast(
            baseline=values[-1],
            n_observations=n,
            insufficient_data=True,
            note=f"Model tidak bisa diestimasi dari riwayat ini: {e}",
        )

    spread: dict[int, float] = {}
    expected: dict[int, float] = {}
    for horizon in sorted(horizons):
        idx = min(max_steps - 1, max(0, int(np.ceil(horizon / median_step)) - 1))
        half_width = float(interval[idx][1] - interval[idx][0]) / 2
        # Interval yang lebih sempit di horizon jauh tidak masuk akal secara
        # struktural; kalau optimizer menghasilkannya, tahan agar monoton.
        if spread:
            half_width = max(half_width, max(spread.values()))
        spread[horizon] = round(abs(half_width), 2)
        expected[horizon] = round(float(mean[idx]), 2)

    limitations = [
        "Model diestimasi dari riwayat metrik ini sendiri dan tidak mengetahui "
        "peristiwa yang belum pernah terjadi dalam riwayat itu.",
        f"Pengamatan dianggap berjarak sama; jarak median yang terpakai "
        f"{median_step:.0f} hari. Bila gelombang pengukuran sangat tidak "
        "teratur, terjemahan horizon ke langkah model menjadi kasar.",
    ]
    if not with_trend:
        limitations.append(
            f"Riwayat baru {n} pengamatan, jadi hanya level yang diestimasi, "
            "tanpa komponen tren. Arah pergerakan tidak diproyeksikan."
        )
    longest = max(horizons)
    if span_days and longest > span_days:
        limitations.append(
            f"Horizon terjauh ({longest} hari) melampaui panjang riwayat yang "
            f"tersedia ({span_days} hari). Bagian itu ekstrapolasi, bukan "
            "estimasi."
        )

    return FittedForecast(
        baseline=round(float(values[-1]), 2),
        spread=spread,
        expected=expected,
        model=_model_name(with_trend),
        n_observations=n,
        observed_span_days=span_days,
        median_step_days=median_step,
        limitations=limitations,
    )
