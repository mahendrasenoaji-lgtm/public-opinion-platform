"""Deteksi anomali sederhana untuk "Peringatan aktif" (Command Center).

## Apa yang modul ini boleh dan tidak boleh klaim

Ini BUKAN deteksi krisis, BUKAN prediksi, dan BUKAN penilaian penyebab. Yang
dihitung murni statistik deskriptif: apakah titik data TERBARU dari sebuah
deret menyimpang jauh dari pola historisnya sendiri. Itu saja.

Konsekuensi yang mengikat:

- Tidak pernah menyebut "krisis" atau "berbahaya" — hanya "menyimpang dari
  pola historis", dengan angka z-score yang bisa diperiksa ulang.
- Tidak pernah menyimpulkan penyebab. Endpoint yang memanggil modul ini
  boleh menautkan sebuah alert ke `timeline_events` terdekat sebagai
  konteks, tapi kata yang dipakai adalah "berdekatan waktu dengan", bukan
  "disebabkan oleh" (CLAUDE.md §3).
- Butuh riwayat minimum sebelum sebuah titik bisa dinilai "menyimpang".
  Titik pertama tidak pernah anomali — tidak ada baseline untuk
  dibandingkan. Ini gating yang sama semangatnya dengan MIN_OBSERVATIONS
  di services/timeseries.py.

## Kenapa dihitung saat diminta (on-the-fly), bukan lewat worker terjadwal

Belum ada infrastruktur worker/queue di proyek ini (lihat catatan di
docs/progress.md). Pola yang sama dipakai `routers/risk.py` dan
`routers/forecast.py:baseline` — dihitung ulang setiap GET dari data yang
ada, bukan disimpan sebelumnya. Untuk volume data proyek yang wajar ini
cukup cepat; kalau kelak jumlah proyek/deret jadi besar, ini kandidat
pertama yang dipindah ke worker.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from statistics import mean, pstdev

#: Titik pengamatan minimum SEBELUM titik terakhir agar baseline dianggap
#: cukup untuk dibandingkan. Di bawah ini, penyimpangan tidak dilaporkan --
#: bukan karena tidak ada, tapi karena "biasa"-nya sendiri belum diketahui.
MIN_BASELINE_POINTS = 4

#: |z-score| di atas ini dianggap "menyimpang". 2.0 kira-kira dua simpangan
#: baku -- longgar dengan sengaja: proyek ini lebih suka menandai terlalu
#: banyak lalu ditinjau manusia, daripada diam saat sesuatu bergerak.
Z_THRESHOLD = 2.0

#: Dipakai saat baseline punya simpangan baku nyaris nol (deret nyaris
#: konstan). Simpangan MUTLAK relatif terhadap rata-rata baseline di atas
#: ambang ini tetap dilaporkan, supaya "harga selalu 60.0 lalu tiba-tiba 68"
#: tidak lolos hanya karena sd=0 membuat z-score tidak terhitung.
FLAT_BASELINE_REL_THRESHOLD = 0.05


@dataclass(frozen=True, slots=True)
class AnomalyPoint:
    """Hasil pemeriksaan satu deret. `notable=False` bukan berarti gagal --
    itu jawaban yang sah: titik terbaru masih dalam pola historisnya."""

    key: str
    label: str
    latest_value: float
    latest_period: str
    baseline_mean: float
    baseline_sd: float | None
    z_score: float | None
    n_baseline: int
    direction: str | None = None  # "naik" | "turun" | None (tidak notable)
    notable: bool = False
    method: str = "z-score terhadap baseline historis deret sendiri"


def detect(
    series: Sequence[tuple[str, float]],
    *,
    key: str,
    label: str,
    min_baseline: int = MIN_BASELINE_POINTS,
    z_threshold: float = Z_THRESHOLD,
) -> AnomalyPoint | None:
    """Periksa apakah titik TERAKHIR sebuah deret menyimpang dari sisanya.

    `series` adalah pasangan (label_periode, nilai) terurut naik waktu.
    Mengembalikan None kalau baseline (semua titik SELAIN yang terakhir)
    kurang dari `min_baseline` -- bukan AnomalyPoint dengan notable=False,
    supaya pemanggil bisa membedakan "sudah diperiksa, tidak menyimpang"
    dari "belum bisa diperiksa sama sekali".
    """
    if len(series) < min_baseline + 1:
        return None

    baseline = [v for _, v in series[:-1]]
    latest_period, latest_value = series[-1]

    base_mean = mean(baseline)
    base_sd = pstdev(baseline)

    z: float | None
    notable: bool
    if base_sd > 1e-9:
        z = (latest_value - base_mean) / base_sd
        notable = abs(z) >= z_threshold
    else:
        # Baseline nyaris konstan -- z-score tidak berarti (pembagi ~0).
        # Jatuh ke ambang relatif supaya perubahan nyata dari deret datar
        # tetap terlaporkan, bukan diam-diam lolos.
        z = None
        denom = max(abs(base_mean), 1e-9)
        notable = abs(latest_value - base_mean) / denom >= FLAT_BASELINE_REL_THRESHOLD

    direction = None
    if notable:
        direction = "naik" if latest_value > base_mean else "turun"

    return AnomalyPoint(
        key=key,
        label=label,
        latest_value=round(latest_value, 3),
        latest_period=latest_period,
        baseline_mean=round(base_mean, 3),
        baseline_sd=round(base_sd, 3) if base_sd > 1e-9 else None,
        z_score=round(z, 2) if z is not None else None,
        n_baseline=len(baseline),
        direction=direction,
        notable=notable,
    )


@dataclass(frozen=True, slots=True)
class AlertsReport:
    """Ringkasan seluruh deret yang diperiksa untuk sebuah proyek."""

    alerts: list[AnomalyPoint] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)
    insufficient: list[str] = field(default_factory=list)


def build_report(results: dict[str, AnomalyPoint | None]) -> AlertsReport:
    """Susun laporan dari hasil `detect()` per deret.

    Dipisah dari `detect()` supaya router yang mengumpulkan banyak deret
    (volume sinyal, sentimen sinyal, tiap metrik snapshot) bisa memakai satu
    fungsi murni untuk merangkumnya -- dites tanpa database.
    """
    report = AlertsReport()
    for key, point in results.items():
        if point is None:
            report.insufficient.append(key)
            continue
        report.checked.append(key)
        if point.notable:
            report.alerts.append(point)
    # Alert paling ekstrem (|z| terbesar) duluan -- yang tanpa z (baseline
    # datar) diletakkan di akhir karena tidak bisa dibandingkan setara.
    report.alerts.sort(key=lambda a: abs(a.z_score) if a.z_score is not None else 0.0, reverse=True)
    return report
