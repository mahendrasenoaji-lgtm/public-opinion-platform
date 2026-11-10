"""Penilaian ulang sentimen satu konten yang sudah tersimpan. Fungsi murni.

Dua aturan yang tidak boleh dilanggar siapa pun yang mengubah modul ini:

0. **Koreksi manual menang.** Baris yang labelnya ditetapkan manusia
   (`sentiment_model == MANUAL_MODEL_VERSION`) tidak pernah ditimpa penilai
   otomatis; hanya pembatalan eksplisit yang mengembalikannya.
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

#: Penanda di `mentions.sentiment_model` untuk label yang ditetapkan manusia.
MANUAL_MODEL_VERSION = "manual-1"

#: Nilai wakil tiap label manual pada skala -1..1. Manusia memberi LABEL,
#: bukan besaran; nilai ini hanya supaya label ikut rata-rata, dan dipilih di
#: tengah rentang kelasnya. Ringkasan yang memuat koreksi manual wajib
#: menyebut jumlahnya (lihat routers/signals.py:summary).
MANUAL_SCORES: dict[str, float] = {"negatif": -0.5, "netral": 0.0, "positif": 0.5}


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
    if social and sentiment_model == MANUAL_MODEL_VERSION:
        return Rescored(sentiment, sentiment_model, sentiment_alt, sentiment_alt_model, False)
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


def machine_score(*, social: bool, text: str) -> tuple[float | None, str]:
    """Skor penilai otomatis terkini untuk sebuah teks, beserta versinya."""
    if social:
        return (
            sentiment_svc.score(text, register="informal").score,
            sentiment_svc.INFORMAL_MODEL_VERSION,
        )
    return sentiment_svc.score(text).score, sentiment_svc.MODEL_VERSION


def machine_label(*, social: bool, text: str) -> str | None:
    """Label penilai otomatis, atau None bila ia abstain."""
    value, _ = machine_score(social=social, text=text)
    return None if value is None else sentiment_svc.label_for(value)


def apply_manual(
    *,
    social: bool,
    label: str,
    sentiment: float | None,
    sentiment_model: str | None,
    sentiment_alt: float | None,
    sentiment_alt_model: str | None,
) -> Rescored:
    """Keadaan baru sebuah baris setelah manusia menetapkan labelnya.

    Untuk percakapan sosial, skor mesin yang digantikan diarsipkan ke kolom
    pendamping dengan aturan yang sama seperti penilaian ulang: sekali saja.
    Untuk liputan, kolom pendamping tetap milik skor ragam berita; skor mesin
    lamanya bisa dihitung ulang kapan pun dari teksnya (penilainya
    deterministik), jadi tidak ada yang hilang.
    """
    if label not in MANUAL_SCORES:
        raise ValueError(f"label tidak dikenal: {label!r}")
    new = MANUAL_SCORES[label]
    if (
        social
        and sentiment_model != MANUAL_MODEL_VERSION
        and sentiment_alt_model is None
        and sentiment is not None
    ):
        sentiment_alt = sentiment
        sentiment_alt_model = sentiment_model or sentiment_svc.MODEL_VERSION
    changed = sentiment_model != MANUAL_MODEL_VERSION or not _same(sentiment, new)
    return Rescored(new, MANUAL_MODEL_VERSION, sentiment_alt, sentiment_alt_model, changed)


def revert_manual(
    *,
    social: bool,
    text: str,
    sentiment: float | None,
    sentiment_model: str | None,
    sentiment_alt: float | None,
    sentiment_alt_model: str | None,
) -> Rescored:
    """Batalkan koreksi manual: kembali ke skor penilai otomatis terkini."""
    if sentiment_model != MANUAL_MODEL_VERSION:
        return Rescored(sentiment, sentiment_model or "", sentiment_alt, sentiment_alt_model, False)
    value, model = machine_score(social=social, text=text)
    return Rescored(value, model, sentiment_alt, sentiment_alt_model, True)


@dataclass(frozen=True, slots=True)
class CorrectionQuality:
    """Penilai otomatis dibandingkan label manusia pada konten yang dikoreksi."""

    n: int
    #: Konten berlabel manusia yang penilai otomatisnya abstain.
    machine_abstained: int
    #: Di antara yang dinilai mesin: berapa yang labelnya sama dengan manusia.
    agreed: int
    #: confusion[label_manusia][label_mesin]; label mesin "abstain" bila tidak dinilai.
    confusion: dict[str, dict[str, int]]

    @property
    def agreement(self) -> float | None:
        scored = self.n - self.machine_abstained
        return self.agreed / scored if scored else None


def correction_quality(pairs: list[tuple[str, str | None]]) -> CorrectionQuality:
    """Ringkas pasangan `(label_manusia, label_mesin_atau_None)`."""
    labels = tuple(MANUAL_SCORES)
    confusion = {h: dict.fromkeys((*labels, "abstain"), 0) for h in labels}
    abstained = agreed = n = 0
    for human, machine in pairs:
        if human not in confusion:
            continue
        n += 1
        if machine is None:
            abstained += 1
            confusion[human]["abstain"] += 1
            continue
        confusion[human][machine] = confusion[human].get(machine, 0) + 1
        agreed += human == machine
    return CorrectionQuality(n=n, machine_abstained=abstained, agreed=agreed, confusion=confusion)
