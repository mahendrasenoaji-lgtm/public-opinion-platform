"""Arus informasi dan ukuran turunannya untuk modul Kinerja Komunikasi.

Empat hal, semuanya fungsi murni tanpa I/O:

* T1-T4: selang waktu internal per konten yang ditelusuri auditor
  (kerangka bagian 7 dan Lampiran B);
* C4: jam dari lonjakan percakapan sampai unggahan resmi pertama;
* C3: keselarasan pasangan pernyataan antarlembaga, dikode manusia;
* O8: porsi komentar berisi pertanyaan yang dibalas akun resmi.

Tiga aturan yang dijaga:

1. Cap waktu yang tidak dicatat auditor tetap kosong; selangnya tidak dihitung
   dan tidak ditebak dari selang lain.
2. Median tidak terbit di bawah `MIN_RECORDS`; satu atau dua konten bukan
   gambaran sebuah unit.
3. C4 dan O8 adalah SARAN skor dari data publik. Skor resmi tetap diisi
   penilai lewat formulir indikator, dengan bukti.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from statistics import median
from typing import Final, Literal

from app.services.comm_performance import score_response_hours, score_response_rate

#: Sebelas tahap model acuan (kerangka bagian 7). Nomor tahap dipakai auditor
#: untuk menandai titik hambatan sebuah konten.
STAGES: Final[tuple[tuple[int, str], ...]] = (
    (1, "Sumber informasi"),
    (2, "Pengumpulan informasi"),
    (3, "Koordinasi lintas kementerian"),
    (4, "Verifikasi dan validasi"),
    (5, "Perumusan pesan"),
    (6, "Persetujuan"),
    (7, "Produksi konten"),
    (8, "Distribusi media sosial"),
    (9, "Respons publik"),
    (10, "Monitoring"),
    (11, "Evaluasi dan umpan balik"),
)
STAGE_NAMES: Final[dict[int, str]] = dict(STAGES)

Interval = Literal["T1", "T2", "T3", "T4"]

#: (kode, cap waktu awal, cap waktu akhir, arti, tahap model yang dilalui).
INTERVALS: Final[tuple[tuple[Interval, str, str, str, tuple[int, ...]], ...]] = (
    ("T1", "requested_at", "received_at", "permintaan bahan sampai bahan diterima", (1, 2)),
    ("T2", "received_at", "verified_at", "bahan diterima sampai terverifikasi", (3, 4)),
    ("T3", "drafted_at", "approved_at", "draf sampai disetujui", (5, 6)),
    ("T4", "approved_at", "published_at", "disetujui sampai terbit", (7, 8)),
)

TIMESTAMPS: Final[tuple[str, ...]] = (
    "requested_at", "received_at", "verified_at", "drafted_at", "approved_at", "published_at",
)

#: Konten paling sedikit supaya median sebuah selang ditampilkan.
MIN_RECORDS: Final = 5


@dataclass(frozen=True)
class FlowRecord:
    """Cap waktu satu konten yang ditelusuri. Yang tidak tercatat = None."""

    requested_at: datetime | None = None
    received_at: datetime | None = None
    verified_at: datetime | None = None
    drafted_at: datetime | None = None
    approved_at: datetime | None = None
    published_at: datetime | None = None
    bottleneck_stage: int | None = None


def check_order(record: FlowRecord) -> None:
    """Tolak cap waktu yang mundur: itu salah ketik, bukan selang negatif."""
    seen: list[tuple[str, datetime]] = [
        (name, value) for name in TIMESTAMPS if (value := getattr(record, name)) is not None
    ]
    if not seen:
        raise ValueError("Isi paling sedikit satu cap waktu.")
    for (a_name, a), (b_name, b) in zip(seen, seen[1:], strict=False):
        if b < a:
            raise ValueError(f"Cap waktu {b_name} lebih awal daripada {a_name}.")
    if record.bottleneck_stage is not None and record.bottleneck_stage not in STAGE_NAMES:
        raise ValueError("Tahap hambatan harus 1 sampai 11.")


def interval_hours(record: FlowRecord) -> dict[Interval, float | None]:
    """Jam tiap selang; None bila salah satu ujungnya tidak dicatat."""
    out: dict[Interval, float | None] = {}
    for code, start, end, _, _ in INTERVALS:
        a, b = getattr(record, start), getattr(record, end)
        out[code] = None if a is None or b is None else round((b - a).total_seconds() / 3600, 2)
    return out


@dataclass(frozen=True)
class IntervalSummary:
    code: Interval
    meaning: str
    stages: tuple[int, ...]
    #: Konten yang kedua ujung selangnya tercatat.
    n: int
    #: None di bawah `MIN_RECORDS`.
    median_hours: float | None
    max_hours: float | None


@dataclass(frozen=True)
class FlowSummary:
    n_records: int
    intervals: tuple[IntervalSummary, ...]
    #: Selang dengan median terpanjang; None bila tidak ada yang terbit.
    slowest: Interval | None
    #: (tahap, nama, jumlah konten yang menandainya sebagai hambatan).
    bottlenecks: tuple[tuple[int, str, int], ...]


def summarize_flow(records: Sequence[FlowRecord]) -> FlowSummary:
    hours = [interval_hours(r) for r in records]
    intervals: list[IntervalSummary] = []
    for code, _, _, meaning, stages in INTERVALS:
        values = [h for row in hours if (h := row[code]) is not None]
        enough = len(values) >= MIN_RECORDS
        intervals.append(
            IntervalSummary(
                code=code,
                meaning=meaning,
                stages=stages,
                n=len(values),
                median_hours=round(float(median(values)), 2) if enough else None,
                max_hours=max(values) if enough else None,
            )
        )
    published = [i for i in intervals if i.median_hours is not None]
    slowest = max(published, key=lambda i: i.median_hours or 0.0).code if published else None
    marks = Counter(r.bottleneck_stage for r in records if r.bottleneck_stage is not None)
    return FlowSummary(
        n_records=len(records),
        intervals=tuple(intervals),
        slowest=slowest,
        bottlenecks=tuple((stage, name, marks[stage]) for stage, name in STAGES),
    )


# -------------------------------------------------- C4 waktu tanggap ----

#: Sama dengan definisi lonjakan di `/laporan` (services/conversation_report.py).
SPIKE_RATIO: Final = 1.5
MIN_DAYS_FOR_SPIKE: Final = 3

#: Unggahan resmi dicari sampai sekian jam sesudah awal hari lonjakan.
RESPONSE_HORIZON_HOURS: Final = 72


@dataclass(frozen=True)
class SpikeResponse:
    day: date
    volume: int
    ratio: float
    #: Jam dari awal hari lonjakan (zona yang dipilih) sampai unggahan resmi
    #: pertama. None bila tidak ada unggahan dalam `RESPONSE_HORIZON_HOURS`.
    hours: float | None
    first_post_at: datetime | None


@dataclass(frozen=True)
class ResponseTime:
    n_days: int
    median_daily_volume: float
    spikes: tuple[SpikeResponse, ...]
    #: Median antar-lonjakan yang DIJAWAB; None bila tidak ada.
    median_hours: float | None
    n_unanswered: int
    #: Saran skor C4 (1-5); None bila tidak ada lonjakan untuk dinilai.
    suggested_score: int | None


def response_time(
    daily_volume: dict[date, int],
    official_posts: Iterable[datetime],
    *,
    tz_offset_hours: int = 7,
) -> ResponseTime:
    """Selang dari tiap hari lonjakan sampai unggahan resmi pertama.

    Lonjakan didefinisikan per HARI, jadi titik awalnya pukul 00.00 hari itu
    di zona yang dipilih; selang yang dilaporkan karena itu bisa lebih panjang
    sampai 24 jam daripada selang sebenarnya. Unggahan yang dihitung adalah
    unggahan APA PUN dari akun yang dipilih pemanggil: apakah isinya menjawab
    isu harus dicek manusia.
    """
    zone = timezone(timedelta(hours=tz_offset_hours))
    posts = sorted(p if p.tzinfo else p.replace(tzinfo=UTC) for p in official_posts)
    volumes = [v for v in daily_volume.values()]
    med = float(median(volumes)) if volumes else 0.0

    spikes: list[SpikeResponse] = []
    if len(volumes) >= MIN_DAYS_FOR_SPIKE and med > 0:
        for day in sorted(daily_volume):
            ratio = daily_volume[day] / med
            if ratio < SPIKE_RATIO:
                continue
            start = datetime.combine(day, time.min, tzinfo=zone)
            limit = start + timedelta(hours=RESPONSE_HORIZON_HOURS)
            first = next((p for p in posts if start <= p <= limit), None)
            spikes.append(
                SpikeResponse(
                    day=day,
                    volume=daily_volume[day],
                    ratio=round(ratio, 2),
                    hours=(
                        None if first is None else round((first - start).total_seconds() / 3600, 1)
                    ),
                    first_post_at=first,
                )
            )

    answered = [s.hours for s in spikes if s.hours is not None]
    unanswered = len(spikes) - len(answered)
    med_hours = round(float(median(answered)), 1) if answered else None
    if not spikes:
        suggested = None
    elif unanswered > len(answered):
        # Sebagian besar lonjakan tidak dijawab dalam 72 jam: rubrik skor 1.
        suggested = score_response_hours(None)
    else:
        suggested = score_response_hours(med_hours)
    return ResponseTime(
        n_days=len(volumes),
        median_daily_volume=med,
        spikes=tuple(spikes),
        median_hours=med_hours,
        n_unanswered=unanswered,
        suggested_score=suggested,
    )


# ------------------------------------------------ C3 keselarasan pesan ----

Alignment = Literal["selaras", "beda_penekanan", "bertentangan"]
ALIGNMENTS: Final[tuple[Alignment, ...]] = ("selaras", "beda_penekanan", "bertentangan")
#: Nilai ordinal untuk alpha: makin besar makin jauh dari selaras.
ALIGNMENT_RANK: Final[dict[Alignment, int]] = {
    "selaras": 0, "beda_penekanan": 1, "bertentangan": 2,
}

#: Pasangan pernyataan paling sedikit supaya saran skor C3 ditampilkan.
MIN_PAIRS: Final = 5


@dataclass(frozen=True)
class AlignmentSummary:
    n_pairs: int
    counts: dict[Alignment, int]
    #: Pasangan bertentangan yang TIDAK diralat.
    n_contradiction_open: int
    #: Saran skor C3 menurut rubrik (1, 3, atau 5); None bila pasangan kurang.
    suggested_score: int | None


def summarize_alignment(pairs: Iterable[tuple[Alignment, bool]]) -> AlignmentSummary:
    """`pairs`: (kode, sudah_diralat) satu per pasangan pernyataan.

    Rubrik kerangka: 1 = ada pernyataan bertentangan yang tidak diralat;
    5 = selaras di semua isu yang diperiksa; 3 = selain itu.
    """
    items = list(pairs)
    counts: dict[Alignment, int] = dict.fromkeys(ALIGNMENTS, 0)
    for code, _ in items:
        counts[code] += 1
    open_contradictions = sum(1 for code, fixed in items if code == "bertentangan" and not fixed)
    if len(items) < MIN_PAIRS:
        suggested = None
    elif open_contradictions > 0:
        suggested = 1
    elif counts["selaras"] == len(items):
        suggested = 5
    else:
        suggested = 3
    return AlignmentSummary(
        n_pairs=len(items),
        counts=counts,
        n_contradiction_open=open_contradictions,
        suggested_score=suggested,
    )


# --------------------------------------------------- O8 tingkat jawab ----

_QUESTION_WORDS: Final = re.compile(
    r"^\W*(apa|apakah|bagaimana|gimana|gmn|kapan|kpn|di ?mana|dmn|ke ?mana|kenapa|knp|"
    r"mengapa|siapa|berapa|brp|bisakah|bolehkah|adakah|mohon info|minta info|tanya)\b",
    re.IGNORECASE,
)

#: Komentar berisi pertanyaan paling sedikit supaya O8 disarankan.
MIN_QUESTIONS: Final = 20


def is_question(text: str) -> bool:
    """Pertanyaan menurut bentuknya: tanda tanya, atau diawali kata tanya.

    Aturan sederhana dan sengaja terbuka. Pertanyaan retoris ikut terhitung,
    dan pertanyaan tanpa tanda tanya di tengah kalimat terlewat; karena itu
    hasilnya saran, bukan skor.
    """
    stripped = text.strip()
    if not stripped:
        return False
    return "?" in stripped or bool(_QUESTION_WORDS.match(stripped))


@dataclass(frozen=True)
class ResponseRate:
    n_comments: int
    n_questions: int
    n_answered: int
    #: Persen; None bila pertanyaan di bawah `MIN_QUESTIONS`.
    rate_pct: float | None
    suggested_score: int | None


def response_rate(threads: Iterable[tuple[str, bool]]) -> ResponseRate:
    """`threads`: (teks komentar tingkat atas, dibalas akun resmi?)."""
    n = questions = answered = 0
    for text, replied in threads:
        n += 1
        if is_question(text):
            questions += 1
            answered += 1 if replied else 0
    enough = questions >= MIN_QUESTIONS
    return ResponseRate(
        n_comments=n,
        n_questions=questions,
        n_answered=answered,
        rate_pct=round(100 * answered / questions, 1) if enough else None,
        suggested_score=score_response_rate(answered, questions) if enough else None,
    )
