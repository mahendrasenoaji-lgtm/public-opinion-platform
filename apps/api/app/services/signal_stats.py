"""Ringkasan deskriptif sinyal: emosi, engagement harian, jam ramai.

Fungsi murni di atas kolom yang SUDAH tersimpan di `mentions` (`emotion`,
`engagement`, `published_at`). Tidak ada model dan tidak ada estimasi di sini:
semuanya hitungan, dan setiap hasil membawa penyebutnya sendiri supaya
pembaca tahu angka itu mewakili berapa konten.

Tiga hal yang sengaja TIDAK dilakukan:

- Emosi tidak dijadikan label per konten. Leksikon emosi di
  `services/sentiment.py` tidak melihat negasi dan belum dievaluasi terhadap
  label manusia, jadi yang dilaporkan hanya porsi penanda, bersama berapa
  banyak konten yang sama sekali tidak memuat penanda.
- Engagement antarsumber tidak dijumlahkan. "Engagement" komentar YouTube
  (suka + balasan) dan engagement artikel RSS (hampir selalu 0) bukan besaran
  yang sama (R1).
- Jam ramai tidak menebak zona waktu penulis. Zona dipilih pemanggil dan
  dikembalikan apa adanya di hasil.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

from app.services.sentiment import EMOTION_LEXICON

#: Urutan tetap untuk tampilan; sama dengan kunci `EMOTION_LEXICON`.
EMOTION_KEYS: tuple[str, ...] = tuple(EMOTION_LEXICON)

EMOTION_METHOD = (
    "leksikon emosi lexicon-id-1 (penanda kata, tanpa negasi); belum dievaluasi "
    "terhadap label manusia"
)

#: Zona waktu Indonesia. Offset tetap (tanpa DST), jadi tidak perlu tzdata.
TIMEZONES: dict[str, int] = {"WIB": 7, "WITA": 8, "WIT": 9}

#: Indeks hari mengikuti `datetime.weekday()`: 0 = Senin.
WEEKDAYS: tuple[str, ...] = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")


@dataclass(frozen=True)
class EmotionSummary:
    """Sebaran penanda emosi atas sekumpulan konten satu sumber."""

    n_total: int
    #: Konten yang memuat minimal satu penanda emosi. Penyebut `share`.
    n_with_emotion: int
    #: Rata-rata porsi tiap emosi di antara konten berpenanda. Jumlahnya ~1.
    share: dict[str, float]
    #: Berapa konten yang emosi terkuatnya adalah kunci ini. Seri dihitung ke
    #: semua yang seri, jadi jumlahnya bisa melebihi `n_with_emotion`.
    dominant: dict[str, int]

    @property
    def coverage(self) -> float:
        return self.n_with_emotion / self.n_total if self.n_total else 0.0


def summarize_emotions(
    rows: Iterable[Mapping[str, float] | None], *, keys: Sequence[str] = EMOTION_KEYS
) -> EmotionSummary:
    """Gabungkan nilai kolom `mentions.emotion` menjadi satu sebaran.

    Baris `None` atau `{}` berarti leksikon tidak menemukan penanda; baris itu
    ikut `n_total` tetapi tidak ikut penyebut `share`. Kunci di luar
    `keys` diabaikan, supaya data lama dengan kunci lain tidak
    menggeser porsi.
    """
    n_total = 0
    n_with = 0
    sums: dict[str, float] = dict.fromkeys(keys, 0.0)
    dominant: dict[str, int] = dict.fromkeys(keys, 0)

    for row in rows:
        n_total += 1
        if not row:
            continue
        known = {k: float(v) for k, v in row.items() if k in sums and v and float(v) > 0}
        weight = sum(known.values())
        if weight <= 0:
            continue
        n_with += 1
        top = max(known.values())
        for key, value in known.items():
            sums[key] += value / weight
            if value == top:
                dominant[key] += 1

    share = {k: (round(v / n_with, 4) if n_with else 0.0) for k, v in sums.items()}
    return EmotionSummary(n_total=n_total, n_with_emotion=n_with, share=share, dominant=dominant)


@dataclass(frozen=True)
class DayActivity:
    day: date
    volume: int
    engagement: int


@dataclass(frozen=True)
class ActivitySummary:
    """Kapan sebuah sumber ramai, menurut zona waktu yang diminta."""

    timezone: str
    n: int
    engagement_total: int
    #: Konten dengan engagement > 0. Sumber yang tidak melaporkan engagement
    #: (kebanyakan RSS) akan bernilai 0 di sini; itu "tidak diukur", bukan sepi.
    n_with_engagement: int
    by_day: list[DayActivity]
    #: `heatmap[hari][jam]`, hari 0 = Senin, jam 0..23 waktu lokal. Isinya
    #: jumlah konten yang terbit pada jam itu.
    heatmap: list[list[int]]
    #: (hari, jam, jumlah) sel paling ramai; None bila tidak ada konten.
    peak: tuple[int, int, int] | None


class ActivityAccumulator:
    """`summarize_activity` yang diisi sepotong demi sepotong.

    Hanya hitungan per hari dan per sel jam yang disimpan, bukan barisnya.
    Hasilnya sama persis dengan `summarize_activity` atas gabungan potongan.
    """

    __slots__ = (
        "_engagement_by_day",
        "_heatmap",
        "_n",
        "_total",
        "_tz",
        "_volume_by_day",
        "_with_engagement",
        "_zone",
    )

    def __init__(self, *, tz: str = "WIB") -> None:
        if tz not in TIMEZONES:
            raise ValueError(f"zona waktu tidak dikenal: {tz!r}")
        self._tz = tz
        self._zone = timezone(timedelta(hours=TIMEZONES[tz]))
        self._heatmap = [[0] * 24 for _ in range(7)]
        self._volume_by_day: dict[date, int] = defaultdict(int)
        self._engagement_by_day: dict[date, int] = defaultdict(int)
        self._n = 0
        self._total = 0
        self._with_engagement = 0

    def add(self, rows: Iterable[tuple[datetime, int]]) -> None:
        for published_at, engagement in rows:
            moment = published_at if published_at.tzinfo else published_at.replace(tzinfo=UTC)
            local = moment.astimezone(self._zone)
            value = max(0, int(engagement or 0))
            self._n += 1
            self._total += value
            if value > 0:
                self._with_engagement += 1
            self._heatmap[local.weekday()][local.hour] += 1
            self._volume_by_day[local.date()] += 1
            self._engagement_by_day[local.date()] += value

    def result(self) -> ActivitySummary:
        by_day = [
            DayActivity(day=d, volume=self._volume_by_day[d], engagement=self._engagement_by_day[d])
            for d in sorted(self._volume_by_day)
        ]
        peak: tuple[int, int, int] | None = None
        for weekday, hours in enumerate(self._heatmap):
            for hour, count in enumerate(hours):
                if count and (peak is None or count > peak[2]):
                    peak = (weekday, hour, count)
        return ActivitySummary(
            timezone=self._tz,
            n=self._n,
            engagement_total=self._total,
            n_with_engagement=self._with_engagement,
            by_day=by_day,
            heatmap=[list(row) for row in self._heatmap],
            peak=peak,
        )


def summarize_activity(rows: Iterable[tuple[datetime, int]], *, tz: str = "WIB") -> ActivitySummary:
    """Ringkas `(published_at, engagement)` menjadi deret harian dan peta jam.

    `published_at` tanpa zona dianggap UTC, sama dengan cara kolomnya disimpan
    (`timestamptz`). Hari pada `by_day` adalah tanggal LOKAL zona yang diminta,
    jadi komentar pukul 23.30 WITA tidak pindah ke hari berikutnya.
    """
    acc = ActivityAccumulator(tz=tz)
    acc.add(rows)
    return acc.result()


def hourly_totals(heatmap: Sequence[Sequence[int]]) -> list[int]:
    """Jumlah konten per jam lokal, dijumlahkan lintas hari (24 angka)."""
    return [sum(day[hour] for day in heatmap) for hour in range(24)]


class WindowError(ValueError):
    """Jendela tanggal yang diminta tidak sah."""


#: Rentang terpanjang yang dilayani, sama dengan batas `days` di router.
MAX_WINDOW_DAYS = 366


def resolve_window(
    *,
    days: int,
    start: date | None,
    end: date | None,
    now: datetime,
) -> tuple[datetime, datetime]:
    """Jendela waktu sebuah agregat: tanggal mutlak bila diberikan, relatif bila tidak.

    Tanpa `start`/`end` hasilnya sama persis dengan perilaku lama (`now - days`
    sampai `now`). Dengan keduanya, jendela mencakup kedua tanggal itu penuh
    dalam UTC, yaitu satuan hari yang juga dipakai deret harian. Jendela
    mutlak dibutuhkan untuk data historis: data Oktober tidak boleh hilang
    dari tampilan hanya karena hari ini sudah lewat 30 hari.
    """
    if start is None and end is None:
        return now - timedelta(days=days), now
    if start is None or end is None:
        raise WindowError("`start` dan `end` harus diberikan bersama.")
    if end < start:
        raise WindowError("`end` tidak boleh lebih awal dari `start`.")
    if (end - start).days + 1 > MAX_WINDOW_DAYS:
        raise WindowError(f"Rentang paling panjang {MAX_WINDOW_DAYS} hari.")
    since = datetime(start.year, start.month, start.day, tzinfo=UTC)
    until = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(days=1)
    return since, until - timedelta(microseconds=1)
