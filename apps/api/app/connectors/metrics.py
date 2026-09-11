"""Kontrak konektor DERET WAKTU — sejajar dengan `base.Connector`, bukan turunannya.

## Kenapa ini abstraksi terpisah

`base.Connector` mengembalikan `RawItem`: satu unit KONTEN (judul berita, satu
posting) yang kemudian dinormalisasi, di-dedup, dan dinilai sentimennya lalu
disimpan sebagai `mentions`. Seluruh pipeline itu masuk akal untuk teks.

Deret waktu bukan teks. Tampilan halaman harian sebuah artikel Wikipedia adalah
satu angka per hari — tidak punya penulis, tidak punya kalimat, dan tidak punya
sentimen. Memaksanya masuk lewat `RawItem` akan salah di tiga tempat sekaligus:
`sentiment.score()` akan menilai string buatan seperti "142 tampilan" seolah itu
pernyataan seseorang, `ingestion.dedupe()` akan menganggap hari-hari dengan
angka mirip sebagai duplikat, dan tabel `mentions` akan terisi baris yang bukan
sebutan siapa pun.

Karena itu konektor deret waktu mengembalikan `RawObservation` dan berakhir di
`metric_snapshots` — tabel yang memang untuk itu, dan yang sudah dibaca
`/forecast/baseline` serta `/opinion/trend`.

## Batas legal

Sama persis dengan `base.py`: hanya API resmi atau data yang memang diterbitkan
untuk dibaca mesin, tanpa menyamar sebagai peramban, tanpa menembus rate limit
atau kontrol akses. Baca docstring `base.py` sebelum menambah konektor.

## Batas metodologis yang WAJIB dibawa tiap konektor di sini

Deret perilaku (tampilan halaman, penelusuran, unduhan) mengukur PERHATIAN,
bukan SIKAP. Naiknya tampilan halaman sebuah program tidak berarti dukungan
naik — bisa jadi justru sebaliknya. Setiap konektor di modul ini wajib
mengisi `notes` dengan batas itu, dan `method` yang ikut tersimpan di setiap
baris `metric_snapshots` wajib menyebut sumbernya, supaya pembaca laporan tahu
angka ini tidak sebanding dengan angka survei (CLAUDE.md R1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import ClassVar

from app.connectors.base import ConnectorError
from app.models.measurement import SignalSource

#: Batas kolom `metric_snapshots.value` = NUMERIC(8,3), jadi bagian bulatnya
#: maksimal 5 digit. Bukan angka yang dipilih di sini — dibaca dari
#: db/schema.sql. Konektor yang menghasilkan nilai di atas ini harus gagal
#: dengan jelas, BUKAN memotong diam-diam: deret yang terpotong di puncaknya
#: akan terbaca sebagai plateau yang tidak pernah terjadi.
MAX_METRIC_VALUE = 99_999


@dataclass(frozen=True, slots=True)
class RawObservation:
    """Satu pengamatan deret waktu, sebelum disimpan.

    `metric` adalah nama deret yang nanti diminta kembali lewat
    `/forecast/baseline?metric=...`. Ia harus stabil antar pengambilan —
    kalau namanya berubah, riwayatnya pecah jadi dua deret pendek dan model
    tidak akan pernah punya cukup pengamatan untuk di-fit.

    `method` ikut tersimpan ke `metric_snapshots.method` dan tampil di UI.
    Isinya harus menyebut dari mana angkanya, bukan sekadar "dihitung".
    """

    metric: str
    period_start: date
    period_end: date
    value: float
    source: SignalSource
    method: str
    #: Hanya diisi kalau pengamatan ini memang TERIKAT pada satu provinsi di
    #: sumbernya — mis. pengukuran instrumen pada koordinat yang diketahui.
    #: Sama seperti `RawItem.province_code`: dilarang ditebak dari isi teks.
    #: Deret nasional membiarkannya None, dan itulah yang dibaca
    #: `/forecast/baseline` (lihat routers/forecast.py:_history).
    province_code: str | None = None
    breakdown: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.period_end < self.period_start:
            raise ConnectorError(
                f"pengamatan '{self.metric}' berakhir ({self.period_end}) sebelum "
                f"dimulai ({self.period_start})"
            )
        if self.value < 0:
            raise ConnectorError(f"pengamatan '{self.metric}' bernilai negatif: {self.value}")
        if self.value > MAX_METRIC_VALUE:
            raise ConnectorError(
                f"pengamatan '{self.metric}' pada {self.period_end} bernilai "
                f"{self.value:,.0f}, di atas batas kolom metric_snapshots.value "
                f"({MAX_METRIC_VALUE:,}). Nilai TIDAK dipotong — deret yang "
                f"terpotong di puncaknya akan terbaca sebagai plateau palsu. "
                f"Pilih artikel/kata kunci dengan volume lebih kecil, atau ubah "
                f"presisi kolomnya lebih dulu."
            )


class MetricConnector(ABC):
    """Satu sumber deret waktu. Subclass mendaftar lewat `register_metric()`."""

    key: ClassVar[str]
    label: ClassVar[str]
    source: ClassVar[SignalSource]
    #: Nama env var yang dibutuhkan, None kalau tidak butuh kredensial.
    requires_credential: ClassVar[str | None] = None
    #: Kunci yang diharapkan ada di `config` DataSource.
    config_fields: ClassVar[tuple[str, ...]] = ()
    notes: ClassVar[str] = ""

    @abstractmethod
    async def fetch_series(
        self,
        config: dict[str, object],
        *,
        start: date,
        end: date,
    ) -> list[RawObservation]:
        """Ambil deret untuk rentang tanggal. Melempar ConnectorError kalau gagal.

        Rentangnya inklusif di kedua ujung. Hari yang sumbernya memang tidak
        punya datanya DIHILANGKAN, bukan diisi nol — nol berarti "diukur, dan
        hasilnya nol", sedangkan yang sebenarnya terjadi adalah "tidak diukur".
        """


_METRIC_REGISTRY: dict[str, type[MetricConnector]] = {}


def register_metric(cls: type[MetricConnector]) -> type[MetricConnector]:
    """Dekorator pendaftaran. Menolak kunci ganda supaya salah ketik ketahuan."""
    if cls.key in _METRIC_REGISTRY:
        raise ValueError(f"konektor metrik '{cls.key}' sudah terdaftar")
    _METRIC_REGISTRY[cls.key] = cls
    return cls


def get_metric_connector(key: str) -> MetricConnector:
    cls = _METRIC_REGISTRY.get(key)
    if cls is None:
        known = ", ".join(sorted(_METRIC_REGISTRY)) or "(belum ada)"
        raise ConnectorError(f"konektor metrik '{key}' tidak dikenal. Yang tersedia: {known}")
    return cls()


def available_metrics() -> list[type[MetricConnector]]:
    return sorted(_METRIC_REGISTRY.values(), key=lambda c: c.key)
