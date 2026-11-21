"""Bagian bersama konektor "Tarik tema" (YouTube, TikTok, Instagram).

Pekerja di ``app/routers/theme_pulls.py`` memperlakukan ketiga platform dengan
alur yang sama — cari → detail → ambil komentar per unggahan — sehingga galat
dan bentuk halamannya juga harus sama.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.connectors.base import ConnectorError, RawItem


class QuotaExceeded(ConnectorError):
    """Kuota/batas laju API habis; pekerjaan menunggu lalu lanjut sendiri."""


class ItemUnavailable(ConnectorError):
    """Komentar dimatikan, unggahan dihapus, atau privat — lewati unggahannya."""


class PullRejected(ConnectorError):
    """API menolak permintaan ini secara permanen (izin belum disetujui, batas
    mingguan tagar Instagram habis, dsb.). Mengulang tidak menolong; pekerjaan
    langsung gagal dengan pesan yang bisa ditindaklanjuti."""


@dataclass(frozen=True, slots=True)
class CommentPage:
    items: list[RawItem]
    next_token: str | None
    #: Unit kuota/permintaan yang dipakai halaman ini.
    units: int


@dataclass(frozen=True, slots=True)
class SearchPage:
    """Satu halaman pencarian platform yang sudah membawa detail unggahan.

    ``details``: dict berkunci sama dengan keluaran ``youtube_theme.parse_videos``
    (id, title, description, channel, published_at, comment_count).
    ``items``: konten yang langsung disimpan dari halaman ini (Instagram:
    keterangan unggahan, karena komentarnya tidak bisa diambil).
    """

    details: list[dict[str, Any]]
    next_token: str | None
    units: int
    items: list[RawItem] = field(default_factory=list)
