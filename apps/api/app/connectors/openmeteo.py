"""Kualitas udara per provinsi lewat Open-Meteo Air Quality API.

## Apa ini, dan apa yang ia BUKAN

Ini pengukuran instrumen: konsentrasi PM2.5 harian pada koordinat ibu kota
provinsi. Ia BUKAN opini, bukan sentimen, dan bukan perilaku siapa pun.

Ia ada di platform ini sebagai **kovariat eksogen** — variabel di luar opini
yang bisa menjelaskan pergerakan opini. Untuk studi karhutla, kabut asap
justru variabel yang paling masuk akal dijadikan pembanding: pertanyaannya
bukan "apa kata orang", tapi "apakah yang dikatakan orang berubah ketika
udaranya memang memburuk". Modul Communication Impact (`services/impact.py`)
yang punya desain pembanding adalah tempat yang benar untuk memakainya.

## Koreksi atas klaim yang lebih longgar

Konektor ini TIDAK mengisi komponen risiko `geographic_spread`. Komponen itu
menghitung berapa banyak provinsi yang PERCAKAPANNYA tersebar
(`routers/risk.py`: provinsi berbeda di antara mention yang punya geotag
resmi). Udara buruk di 12 provinsi bukan percakapan yang tersebar di 12
provinsi — mengisi komponen itu dari sini akan mengubah arti skornya diam-diam
dan persis melanggar R1. `geographic_spread` tetap kosong sampai ada mention
yang benar-benar bergeotag.

Yang ia buka betulan: lapisan data per-provinsi yang georeferensinya ASLI
(koordinat yang diukur, bukan provinsi yang ditebak dari teks), yang memenuhi
syarat CLAUDE.md §6 untuk peta MapLibre — untuk lapisan kualitas udaranya
sendiri, bukan untuk skor opini per provinsi.

## Soal `source = DIGITAL` — keputusan yang perlu ditinjau pengguna

Tidak ada nilai `SignalSource` yang benar-benar pas. Enum-nya SURVEY / SOCIAL
/ MEDIA / DIGITAL, dan pengukuran instrumen bukan salah satunya; DIGITAL
paling dekat ("perilaku terukur, bukan pernyataan") tapi tetap meleset —
kualitas udara bukan perilaku.

Yang benar secara desain adalah menambah nilai enum baru (mis. `SENSOR`).
Itu TIDAK dilakukan di sini karena butuh `ALTER TYPE signal_source ADD VALUE`
di Supabase — migrasi manual yang, persis kelas ini, pernah menjatuhkan tiga
halaman production pada 2026-09-02 (docs/deployment-status.md). Menambahkannya
diam-diam berarti kode ini jalan di lokal dan gagal 500 di production.

Sampai keputusan itu diambil, setiap baris membawa peringatannya di `method`,
yang ikut tampil di UI.

## Batas legal

Open-Meteo adalah API terbuka tanpa kunci, dan penggunaan non-komersial
diizinkan tanpa registrasi. Satu permintaan mengambil seluruh rentang untuk
satu koordinat; tidak ada rate limit yang dilewati dan tidak ada penyamaran
sebagai peramban.

Parsing dipisah dari pengambilan (`parse_air_quality` fungsi murni) supaya
bisa dites tanpa jaringan.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime
from typing import ClassVar

import httpx

from app.connectors.base import ConnectorError, require
from app.connectors.metrics import MetricConnector, RawObservation, register_metric
from app.models.measurement import SignalSource

REQUEST_TIMEOUT = 25.0
USER_AGENT = "AIPublicOpinionPlatform/0.1 (+public opinion research; contact via platform admin)"

_BASE = "https://air-quality-api.open-meteo.com/v1/air-quality"

#: Nama deret. Diawali `airquality_` dengan alasan yang sama seperti
#: `pageviews_` di wikipedia.py: kalau bertabrakan dengan metrik survei
#: (`poi`, `trust`, `approval`), riwayat Public Opinion Index akan tercampur
#: konsentrasi PM2.5 dan tidak ada catatan kaki yang bisa membatalkan itu.
METRIC = "airquality_pm25"

#: Peringatan yang ikut ke setiap baris `metric_snapshots.method`, dan dari
#: sana ke layar. Bukan komentar kode — ini yang dibaca pembaca laporan.
METHOD_NOTE = "pengukuran instrumen, BUKAN opini"

#: Ibu kota provinsi, kode mengikuti BPS (sama dengan db/seed.py:PROVINCES).
#:
#: SENGAJA subset, bukan 38 provinsi. Yang masuk hanya provinsi yang kode dan
#: koordinat ibu kotanya bisa dipastikan: 16 provinsi yang sudah dipakai
#: db/seed.py, ditambah 4 provinsi inti karhutla (Jambi, Kalimantan Barat,
#: Tengah, Selatan). Provinsi hasil pemekaran 2022 di Papua sengaja tidak
#: ditebak — koordinat yang salah akan tersimpan sebagai georeferensi "asli"
#: dan itu justru kesalahan yang paling mahal di modul ini.
PROVINCE_CAPITALS: dict[str, tuple[str, float, float]] = {
    "12": ("Sumatera Utara", 3.59, 98.67),
    "14": ("Riau", 0.51, 101.45),
    "15": ("Jambi", -1.61, 103.61),
    "16": ("Sumatera Selatan", -2.98, 104.76),
    "31": ("DKI Jakarta", -6.21, 106.85),
    "32": ("Jawa Barat", -6.91, 107.61),
    "33": ("Jawa Tengah", -6.97, 110.42),
    "34": ("DI Yogyakarta", -7.80, 110.36),
    "35": ("Jawa Timur", -7.25, 112.75),
    "36": ("Banten", -6.12, 106.15),
    "51": ("Bali", -8.65, 115.22),
    "52": ("Nusa Tenggara Barat", -8.58, 116.12),
    "53": ("Nusa Tenggara Timur", -10.18, 123.61),
    "61": ("Kalimantan Barat", -0.02, 109.34),
    "62": ("Kalimantan Tengah", -2.21, 113.92),
    "63": ("Kalimantan Selatan", -3.32, 114.59),
    "64": ("Kalimantan Timur", -0.50, 117.15),
    "73": ("Sulawesi Selatan", -5.15, 119.43),
    "81": ("Maluku", -3.70, 128.18),
    "94": ("Papua", -2.53, 140.72),
}


def daily_means(
    times: list[str], values: list[float | None]
) -> list[tuple[date, float, int]]:
    """Rata-ratakan deret per jam menjadi per hari. Fungsi murni.

    Open-Meteo membalas per jam; yang dipakai platform ini harian, supaya
    sebanding dengan deret lain (`pageviews_*`, snapshot survei).

    Jam yang nilainya null DILEWATI, dan jumlah jam yang benar-benar terpakai
    ikut dikembalikan. Hari yang cuma punya beberapa jam data bukan hari yang
    setara dengan hari penuh — pemanggil yang memutuskan mau menerimanya atau
    tidak, bukan fungsi ini yang diam-diam membulatkan.
    """
    buckets: dict[date, list[float]] = defaultdict(list)
    for stamp, value in zip(times, values, strict=False):
        if value is None:
            continue
        try:
            day = datetime.fromisoformat(stamp).date()
        except (TypeError, ValueError):
            continue
        buckets[day].append(float(value))

    return [
        (day, round(sum(vals) / len(vals), 3), len(vals))
        for day, vals in sorted(buckets.items())
        if vals
    ]


def parse_air_quality(
    payload: bytes,
    *,
    province_code: str,
    method: str,
    min_hours: int,
) -> list[RawObservation]:
    """Ubah respons Open-Meteo menjadi RawObservation harian. Fungsi murni.

    `min_hours` menjaga hari yang datanya terlalu tipis tidak masuk sebagai
    pengamatan setara — pola gating yang sama dengan `MIN_EFFECTIVE_N` di
    services/poi.py: lebih baik hari itu hilang daripada hadir dengan bobot
    yang tidak dia punya.
    """
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise ConnectorError(f"respons Open-Meteo bukan JSON yang valid: {e}") from e

    if not isinstance(data, dict):
        raise ConnectorError("respons Open-Meteo bukan objek JSON")
    if "error" in data:
        raise ConnectorError(f"Open-Meteo menolak permintaan: {data.get('reason', 'tanpa alasan')}")

    hourly = data.get("hourly")
    if not isinstance(hourly, dict):
        raise ConnectorError("respons Open-Meteo tidak memuat blok 'hourly'")

    times = hourly.get("time")
    values = hourly.get("pm2_5")
    if not isinstance(times, list) or not isinstance(values, list):
        raise ConnectorError("respons Open-Meteo tidak memuat deret 'time' dan 'pm2_5'")

    province_name = PROVINCE_CAPITALS.get(province_code, ("", 0.0, 0.0))[0]

    return [
        RawObservation(
            metric=METRIC,
            period_start=day,
            period_end=day,
            value=mean,
            source=SignalSource.DIGITAL,
            method=method,
            province_code=province_code,
            breakdown={
                "province_name": province_name,
                "unit": "ug/m3",
                "hours_used": str(hours),
            },
        )
        for day, mean, hours in daily_means(times, values)
        if hours >= min_hours
    ]


@register_metric
class OpenMeteoAirQualityConnector(MetricConnector):
    """Konsentrasi PM2.5 harian di ibu kota provinsi."""

    key: ClassVar[str] = "openmeteo_air_quality"
    label: ClassVar[str] = "Open-Meteo — PM2.5 harian per provinsi"
    source: ClassVar[SignalSource] = SignalSource.DIGITAL
    requires_credential: ClassVar[str | None] = None
    config_fields: ClassVar[tuple[str, ...]] = ("province_code",)
    notes: ClassVar[str] = (
        "Pengukuran instrumen (PM2.5, µg/m³), BUKAN opini dan bukan perilaku. "
        "Dipakai sebagai kovariat eksogen — variabel di luar opini yang bisa "
        "menjelaskan pergerakannya — bukan sebagai sinyal opini. Jangan "
        "dibandingkan langsung dengan Public Opinion Index. Tidak mengisi "
        "komponen risiko 'geographic_spread': itu mengukur sebaran PERCAKAPAN, "
        "bukan sebaran udara buruk."
    )

    #: Minimal jam terukur sebelum sebuah hari dihitung. 18 dari 24 jam —
    #: ambang yang sama semangatnya dengan gating n<250 di services/poi.py.
    min_hours: ClassVar[int] = 18

    async def fetch_series(
        self,
        config: dict[str, object],
        *,
        start: date,
        end: date,
    ) -> list[RawObservation]:
        cfg = require(config, self.config_fields)
        code = cfg["province_code"]

        capital = PROVINCE_CAPITALS.get(code)
        if capital is None:
            raise ConnectorError(
                f"kode provinsi '{code}' belum punya koordinat di konektor ini. "
                f"Yang tersedia: {', '.join(sorted(PROVINCE_CAPITALS))}. "
                f"Koordinat TIDAK ditebak — georeferensi yang salah lebih buruk "
                f"daripada provinsi yang belum didukung."
            )
        if end < start:
            raise ConnectorError(f"rentang terbalik: {start} sampai {end}")

        name, lat, lon = capital
        params = {
            "latitude": f"{lat}",
            "longitude": f"{lon}",
            "hourly": "pm2_5",
            "start_date": f"{start:%Y-%m-%d}",
            "end_date": f"{end:%Y-%m-%d}",
            "timezone": "Asia/Jakarta",
        }

        try:
            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            ) as client:
                response = await client.get(_BASE, params=params)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ConnectorError(
                f"Open-Meteo menolak permintaan ({e.response.status_code})"
            ) from e
        except httpx.HTTPError as e:
            raise ConnectorError(f"deret kualitas udara tidak bisa diambil: {e}") from e

        return parse_air_quality(
            response.content,
            province_code=code,
            method=(
                f"Open-Meteo Air Quality API · PM2.5 µg/m³ · {name} "
                f"({lat}, {lon}) · rata-rata harian dari ≥{self.min_hours} jam · "
                f"{METHOD_NOTE}"
            ),
            min_hours=self.min_hours,
        )
