"""Penilaian ulang sentimen satu konten yang sudah tersimpan. Fungsi murni.

Dua aturan yang tidak boleh dilanggar siapa pun yang mengubah modul ini:

1. **Deret liputan (bukan SOCIAL) tidak pernah bergeser.** Skor utamanya tetap
   apa pun yang tersimpan; yang ditambahkan hanya skor ragam berita di kolom
   pendamping.
2. **Menilai ulang percakapan tidak menghapus skor lamanya.** Begitu skor
   utama diganti, skor lama pindah ke kolom pendamping lengkap dengan versi
   penilainya — sekali saja, supaya penilaian ulang kedua tidak menimpa arsip
   dengan skor yang sudah baru.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services import sentiment as sentiment_svc

_TOLERANCE = 5e-4  # kolomnya numeric(4,3)


@dataclass(frozen=True, slots=True)
class Rescored:
    sentiment: float | None
    sentiment_model: str
    sentiment_alt: float | None
    sentiment_alt_model: str | None
    #: True bila skor UTAMA berubah (hanya mungkin untuk percakapan sosial).
    primary_changed: bool


def _same(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) < _TOLERANCE


def rescore(
    *,
    social: bool,
    text: str,
    sentiment: float | None,
    sentiment_model: str | None,
    sentiment_alt: float | None,
    sentiment_alt_model: str | None,
) -> Rescored:
    """Keadaan baru satu baris `mentions` setelah dinilai dengan penilai terkini.

    `sentiment_model` None berarti baris lama dari sebelum versi penilai
    dicatat. Untuk percakapan sosial, penilai lama pasti leksikon baku —
    hanya dua penilai yang pernah ada — jadi skor yang berbeda dari ragam
    informal diarsipkan sebagai `lexicon-id-1`.
    """
    if not social:
        news = sentiment_svc.score(text, register="berita").score
        return Rescored(
            sentiment=sentiment,
            sentiment_model=sentiment_model or sentiment_svc.MODEL_VERSION,
            sentiment_alt=news,
            sentiment_alt_model=sentiment_svc.NEWS_MODEL_VERSION,
            primary_changed=False,
        )

    current = sentiment_svc.INFORMAL_MODEL_VERSION
    if sentiment_model == current:
        return Rescored(sentiment, current, sentiment_alt, sentiment_alt_model, False)

    new = sentiment_svc.score(text, register="informal").score
    if _same(sentiment, new):
        return Rescored(sentiment, current, sentiment_alt, sentiment_alt_model, False)
    if sentiment_alt_model is None:
        sentiment_alt = sentiment
        sentiment_alt_model = sentiment_model or sentiment_svc.MODEL_VERSION
    return Rescored(new, current, sentiment_alt, sentiment_alt_model, True)
