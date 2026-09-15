"""Kontrak konektor sumber data.

## Batas yang mengikat setiap konektor di paket ini

Konektor HANYA boleh mengambil data lewat API resmi yang aksesnya diberikan
kepada organisasi pengguna, atau lewat feed yang memang diterbitkan untuk
dibaca mesin (RSS/Atom). Yang tidak boleh, tanpa pengecualian:

- mengambil halaman dengan menyamar sebagai peramban untuk melewati
  pembatasan platform;
- memakai kredensial akun pribadi untuk mengakses yang tidak terbuka;
- melewati rate limit, paywall, atau kontrol akses apa pun;
- mengumpulkan konten dari akun privat.

Ini bukan preferensi gaya. Platform ini menjual pertanggungjawaban metodologis
ke pemerintah dan lembaga riset; data yang diambil dengan cara yang tidak bisa
dijelaskan asal-usulnya merusak seluruh nilai jualnya, selain melanggar
ketentuan platform sumbernya.

## Kenapa konektor bukan `services/`

`services/` berisi fungsi murni tanpa I/O (CLAUDE.md §4) supaya bisa dites
tanpa jaringan. Konektor justru seluruhnya I/O. Karena itu ia hidup di paket
sendiri: yang bisa dites tanpa jaringan (parsing) dipisah ke fungsi murni di
dalam modul konektornya, dan itulah yang dites.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar

from app.models.measurement import SignalSource


class ConnectorError(RuntimeError):
    """Kegagalan yang bisa dijelaskan ke pengguna, bukan stack trace."""


class CredentialMissing(ConnectorError):
    """Konektor butuh kunci API yang belum dikonfigurasi di deployment ini.

    Dibedakan dari ConnectorError biasa supaya API bisa membalas 503 dengan
    pesan yang menyebut env var mana yang kurang — bukan 500 yang membuat
    pengguna menebak.
    """


@dataclass(frozen=True, slots=True)
class RawItem:
    """Satu unit konten apa adanya dari sumbernya, sebelum diproses.

    `province_code` hanya diisi kalau SUMBERNYA memberi geotag resmi. Konektor
    dilarang menebaknya dari isi teks — lihat catatan di services/ingestion.py.

    `reply_to_handle`/`quote_of_handle`/`conversation_id` hanya diisi kalau
    SUMBERNYA memang menyatakan relasi itu secara eksplisit (mis. field
    `referenced_tweets` di X API) — bukan ditebak dari isi teks (mis. "@user"
    di awal kalimat bisa berarti macam-macam). Dipakai services/network.py
    untuk graf balasan/kutipan; konektor yang tidak punya relasi ini
    (RSS, YouTube, unggahan manual) membiarkannya None.
    """

    external_id: str
    text: str
    published_at: datetime
    author_handle: str | None = None
    engagement: int = 0
    reach_est: int | None = None
    url: str | None = None
    province_code: str | None = None
    reply_to_handle: str | None = None
    quote_of_handle: str | None = None
    conversation_id: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FetchStats:
    """Apa yang DITAWARKAN sumber pada satu pengambilan, sebelum disaring.

    Ada untuk satu pertanyaan yang tidak bisa dijawab dari item yang
    tersimpan: "apakah ada yang terlewat?". Feed RSS hanya memuat N item
    terakhir — Antara nasional 50 item, yang pada 2026-09-15 berarti kurang
    dari 1,5 jam berita. Kalau item TERTUA yang masih ditawarkan feed lebih
    baru dari pengambilan sebelumnya, berita di antara keduanya sudah jatuh
    dari feed dan tidak akan pernah terlihat. Itu harus dilaporkan, bukan
    didiamkan jadi "hari yang sepi".
    """

    offered: int
    oldest_offered: datetime | None
    matched: int


@dataclass(frozen=True, slots=True)
class ConnectorInfo:
    """Deskripsi konektor untuk ditampilkan di UI pengaturan."""

    key: str
    label: str
    source: SignalSource
    requires_credential: str | None
    config_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    notes: str


class Connector(ABC):
    """Satu sumber data. Subclass mendaftar lewat `register()`."""

    key: ClassVar[str]
    label: ClassVar[str]
    source: ClassVar[SignalSource]
    #: Nama env var yang dibutuhkan, None kalau tidak butuh kredensial.
    requires_credential: ClassVar[str | None] = None
    #: Kunci yang diharapkan ada di `config` DataSource.
    config_fields: ClassVar[tuple[str, ...]] = ()
    #: Kunci yang boleh ada tapi tidak wajib (mis. penyaring kata kunci).
    optional_fields: ClassVar[tuple[str, ...]] = ()
    notes: ClassVar[str] = ""

    def __init__(self) -> None:
        #: Diisi konektor yang tahu apa yang ditawarkan sumbernya; None kalau
        #: tidak. Instans dibuat baru per pengambilan (`get_connector`).
        self.last_fetch: FetchStats | None = None

    def validate_config(self, config: dict[str, str]) -> None:  # noqa: B027
        """Tolak konfigurasi yang pasti gagal SAAT sumber didaftarkan.

        Default tidak memeriksa apa pun selain field wajib (dicek pemanggil).
        Melempar ConnectorError dengan pesan untuk pengguna.
        """

    @abstractmethod
    async def fetch(
        self,
        config: dict[str, object],
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[RawItem]:
        """Ambil konten terbaru. Melempar ConnectorError kalau gagal."""

    @classmethod
    def info(cls) -> ConnectorInfo:
        return ConnectorInfo(
            key=cls.key,
            label=cls.label,
            source=cls.source,
            requires_credential=cls.requires_credential,
            config_fields=cls.config_fields,
            optional_fields=cls.optional_fields,
            notes=cls.notes,
        )


_REGISTRY: dict[str, type[Connector]] = {}


def register(cls: type[Connector]) -> type[Connector]:
    """Dekorator pendaftaran. Menolak kunci ganda supaya salah ketik ketahuan."""
    if cls.key in _REGISTRY:
        raise ValueError(f"konektor '{cls.key}' sudah terdaftar")
    _REGISTRY[cls.key] = cls
    return cls


def get_connector(key: str) -> Connector:
    cls = _REGISTRY.get(key)
    if cls is None:
        known = ", ".join(sorted(_REGISTRY)) or "(belum ada)"
        raise ConnectorError(f"konektor '{key}' tidak dikenal. Yang tersedia: {known}")
    return cls()


def available() -> list[ConnectorInfo]:
    return sorted((c.info() for c in _REGISTRY.values()), key=lambda i: i.key)


def require(config: dict[str, object], keys: tuple[str, ...]) -> dict[str, str]:
    """Ambil field wajib dari config DataSource, atau gagal dengan jelas."""
    missing = [k for k in keys if not str(config.get(k, "")).strip()]
    if missing:
        raise ConnectorError(f"konfigurasi konektor kurang: {', '.join(missing)}")
    return {k: str(config[k]).strip() for k in keys}
