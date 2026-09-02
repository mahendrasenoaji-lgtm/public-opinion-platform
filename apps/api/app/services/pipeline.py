"""Menyatukan ingestion + sentiment jadi satu batch siap simpan.

Fungsi murni (CLAUDE.md §4): masuk daftar item mentah, keluar daftar item
terproses beserta laporan apa yang terjadi pada batch itu. Tidak menyentuh
database, tidak menyentuh jaringan.

`IncomingItem` sengaja didefinisikan di sini alih-alih memakai
`connectors.RawItem`, supaya `services/` tidak menarik httpx dan
`app.models` ke dalam pengujiannya. Routernya yang menjembatani — delapan
baris konversi, harganya murah.

## Laporan batch bukan hiasan

`BatchReport` ikut disimpan dan ditampilkan. Berapa banyak yang dibuang karena
duplikat, berapa yang bahasanya tidak bisa dipastikan, berapa yang tidak bisa
dinilai sentimennya — tiga angka itu menentukan apakah agregat di atasnya
layak dibaca. Volume 10.000 yang 60%-nya duplikat bukan percakapan 10.000
orang, dan pembaca laporan harus bisa melihat itu tanpa bertanya.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from app.services import sentiment as sentiment_svc
from app.services.ingestion import dedupe, detect_language, hash_author


@dataclass(frozen=True, slots=True)
class IncomingItem:
    """Item mentah dari konektor atau unggahan manual.

    `reply_to_handle`/`quote_of_handle` hanya diisi kalau sumbernya memang
    menyatakan relasi itu secara eksplisit (lihat catatan RawItem di
    connectors/base.py) -- dipakai services/network.py untuk graf balasan/
    kutipan setelah di-hash sama seperti author_handle.
    """

    external_id: str
    text: str
    published_at: datetime
    author_handle: str | None = None
    engagement: int = 0
    reach_est: int | None = None
    province_code: str | None = None
    reply_to_handle: str | None = None
    quote_of_handle: str | None = None
    conversation_id: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedMention:
    """Item yang siap disimpan ke tabel mentions."""

    external_id: str
    text: str
    published_at: datetime
    author_hash: str | None
    lang: str | None
    engagement: int
    reach_est: int | None
    province_code: str | None
    sentiment: float | None
    emotion: dict[str, float]
    reply_to_hash: str | None = None
    quote_of_hash: str | None = None
    conversation_id: str | None = None


@dataclass(frozen=True, slots=True)
class BatchReport:
    """Apa yang terjadi pada satu batch. Wajib ikut ditampilkan."""

    received: int
    prepared: list[PreparedMention] = field(default_factory=list)
    duplicates_dropped: int = 0
    duplicate_rate: float = 0.0
    language_rejected: int = 0
    language_unknown: int = 0
    sentiment_abstained: int = 0
    empty_dropped: int = 0

    @property
    def kept(self) -> int:
        return len(self.prepared)

    @property
    def sentiment_abstain_rate(self) -> float:
        return round(self.sentiment_abstained / self.kept, 3) if self.kept else 0.0

    def caveats(self) -> list[str]:
        """Peringatan yang pantas muncul di UI untuk batch ini."""
        out: list[str] = []
        if self.duplicate_rate >= 0.3:
            out.append(
                f"{self.duplicate_rate:.0%} konten pada batch ini adalah salinan "
                "satu sama lain dan tidak dihitung dua kali. Volume mentah akan "
                "jauh lebih besar dari jumlah percakapan yang sebenarnya berbeda."
            )
        if self.sentiment_abstain_rate >= 0.4:
            out.append(
                f"{self.sentiment_abstain_rate:.0%} konten tidak bisa dinilai "
                "sentimennya oleh leksikon. Rata-rata sentimen batch ini "
                "mewakili sisanya saja, bukan keseluruhan."
            )
        if self.language_unknown and self.kept:
            share = self.language_unknown / self.kept
            if share >= 0.3:
                out.append(
                    f"{share:.0%} konten terlalu pendek untuk dipastikan bahasanya."
                )
        return out


def _maybe_hash(handle: str | None, *, salt: str) -> str | None:
    """hash_author(), tapi None tetap None -- dipakai untuk author_handle,
    reply_to_handle, dan quote_of_handle sekaligus."""
    if handle and handle.strip():
        return hash_author(handle, salt=salt)
    return None


def prepare_batch(
    items: Sequence[IncomingItem],
    *,
    author_salt: str,
    accept_langs: frozenset[str] | None = None,
    dedupe_batch: bool = True,
) -> BatchReport:
    """Bersihkan, dedup, deteksi bahasa, dan skor sentimen satu batch.

    `accept_langs=None` berarti tidak menyaring bahasa. Kalau disaring, item
    yang bahasanya TIDAK BISA DIPASTIKAN tetap disimpan dan dihitung di
    `language_unknown` — membuang teks pendek karena heuristik menyerah akan
    menghapus justru komentar-komentar singkat yang paling banyak jumlahnya.
    Yang dibuang hanya yang terdeteksi jelas sebagai bahasa lain.
    """
    non_empty = [i for i in items if i.text and i.text.strip()]
    empty_dropped = len(items) - len(non_empty)

    if dedupe_batch and non_empty:
        result = dedupe([i.text for i in non_empty])
        survivors = [non_empty[k] for k in result.kept_indexes]
        duplicates_dropped = len(result.duplicate_of)
        duplicate_rate = result.duplicate_rate
    else:
        survivors = list(non_empty)
        duplicates_dropped = 0
        duplicate_rate = 0.0

    prepared: list[PreparedMention] = []
    language_rejected = 0
    language_unknown = 0
    abstained = 0

    for item in survivors:
        guess = detect_language(item.text)
        if guess.lang is None:
            language_unknown += 1
        elif accept_langs is not None and guess.lang not in accept_langs:
            language_rejected += 1
            continue

        scored = sentiment_svc.score(item.text)
        if scored.score is None:
            abstained += 1

        prepared.append(
            PreparedMention(
                external_id=item.external_id,
                text=item.text,
                published_at=item.published_at,
                author_hash=_maybe_hash(item.author_handle, salt=author_salt),
                lang=guess.lang,
                engagement=max(0, item.engagement),
                reach_est=item.reach_est,
                province_code=item.province_code,
                sentiment=scored.score,
                emotion=sentiment_svc.emotions(item.text),
                reply_to_hash=_maybe_hash(item.reply_to_handle, salt=author_salt),
                quote_of_hash=_maybe_hash(item.quote_of_handle, salt=author_salt),
                conversation_id=item.conversation_id,
            )
        )

    return BatchReport(
        received=len(items),
        prepared=prepared,
        duplicates_dropped=duplicates_dropped,
        duplicate_rate=duplicate_rate,
        language_rejected=language_rejected,
        language_unknown=language_unknown,
        sentiment_abstained=abstained,
        empty_dropped=empty_dropped,
    )
