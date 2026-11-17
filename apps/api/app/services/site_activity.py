"""Keaktifan situs web resmi lembaga: seberapa sering terbit, kapan terakhir.

Fungsi murni. Masukannya tanggal terbit butir (berita, siaran pers,
pengumuman) yang tercatat di proyek; keluarannya hitungan apa adanya. Modul
ini tidak menilai MUTU isi dan tidak menyimpulkan SEBAB sebuah situs sepi:
"tidak ada terbitan tercatat 30 hari" bisa berarti lembaganya diam, bisa juga
berarti datanya belum diambil. Pembeda keduanya adalah `captured_at`, yang
dibawa pemanggil ke tampilan.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import median
from urllib.parse import urlsplit

#: Jendela utama keaktifan, dalam hari.
WINDOW_DAYS = 90
#: Tanpa terbitan selama ini = "sepi" (pertanyaan pemilik produk: sebulan).
QUIET_DAYS = 30
#: Di bawah ini irama terbit (median jeda) tidak dihitung.
MIN_ITEMS_FOR_CADENCE = 5
#: Porsi `lastmod` pada hari yang sama yang membuat sitemap dianggap dicap
#: mesin sekaligus (bukan tanggal terbit).
SAME_DAY_SHARE = 0.8
MIN_DATED_FOR_CHECK = 3

CATEGORIES: tuple[tuple[str, str], ...] = (
    ("siaran_pers", "Siaran pers"),
    ("berita", "Berita"),
    ("pengumuman", "Pengumuman"),
    ("regulasi", "Regulasi"),
    ("agenda", "Agenda"),
    ("artikel", "Artikel"),
    ("lainnya", "Lainnya"),
)
CATEGORY_KEYS = frozenset(k for k, _ in CATEGORIES)

# Urutan penting: yang lebih khusus dulu ("siaran-pers" memuat "pers").
_URL_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("siaran_pers", re.compile(r"siaran[-_ ]?pers|press[-_ ]?release|/pers(/|$)|rilis")),
    ("pengumuman", re.compile(r"pengumuman|announcement")),
    ("regulasi", re.compile(r"regulasi|peraturan|produk[-_ ]?hukum|jdih")),
    ("agenda", re.compile(r"agenda|kegiatan|event")),
    ("artikel", re.compile(r"artikel|opini|article")),
    ("berita", re.compile(r"berita|news|blog|post")),
)


def guess_category(url: str) -> str:
    """Kategori dari ALAMAT butir saja (mis. `/siaran-pers/...`).

    Ini bukan pembacaan isi. Alamat yang tidak memuat petunjuk jatuh ke
    "lainnya"; pengguna bisa menimpanya lewat unggahan.
    """
    path = urlsplit(url).path.lower()
    for key, pattern in _URL_RULES:
        if pattern.search(path):
            return key
    return "lainnya"


def dates_look_generated(stamps: Sequence[datetime]) -> bool:
    """True bila hampir semua cap waktu jatuh pada hari yang sama.

    Banyak sitemap mengisi `lastmod` dengan waktu berkas dibuat. Tanggal
    seperti itu bukan tanggal terbit dan tidak boleh dipakai menghitung irama.
    """
    if len(stamps) < MIN_DATED_FOR_CHECK:
        return False
    top = Counter(s.date() for s in stamps).most_common(1)[0][1]
    return top / len(stamps) >= SAME_DAY_SHARE


@dataclass(frozen=True, slots=True)
class WeekCount:
    start: date
    n: int


@dataclass(frozen=True, slots=True)
class Activity:
    n_total: int
    n_window: int
    n_30: int
    window_days: int
    last_published: date | None
    days_since_last: int | None
    #: Jeda terpanjang (hari) antara dua terbitan berurutan DALAM jendela,
    #: termasuk dari terbitan terakhir sampai hari ini. None bila tidak ada.
    longest_gap_days: int | None
    #: Median jeda antar-terbitan dalam jendela; None bila butir kurang.
    median_gap_days: float | None
    #: Jumlah hari berbeda yang punya terbitan, dalam jendela.
    active_days: int
    weeks_without: int
    quiet: bool
    weeks: tuple[WeekCount, ...]
    categories: tuple[tuple[str, int], ...]


def summarize(
    items: Iterable[tuple[date, str]],
    *,
    today: date,
    window_days: int = WINDOW_DAYS,
) -> Activity:
    """Ringkas keaktifan dari pasangan (tanggal terbit lokal, kategori).

    Butir bertanggal sesudah `today` diabaikan (jam server atau salah ketik).
    """
    rows = sorted((d, c) for d, c in items if d <= today)
    start = today - timedelta(days=window_days - 1)
    inside = [(d, c) for d, c in rows if d >= start]
    days = [d for d, _ in inside]
    last = rows[-1][0] if rows else None
    since_last = (today - last).days if last else None

    gaps = [(b - a).days for a, b in zip(days, days[1:], strict=False)]
    longest: int | None = None
    if days:
        longest = max([*gaps, (today - days[-1]).days])
    cadence = (
        round(float(median(gaps)), 1) if len(days) >= MIN_ITEMS_FOR_CADENCE and gaps else None
    )

    # Minggu Senin-Minggu yang menyentuh jendela, terlama dulu.
    first_monday = start - timedelta(days=start.weekday())
    per_week = Counter(d - timedelta(days=d.weekday()) for d in days)
    weeks: list[WeekCount] = []
    cursor = first_monday
    while cursor <= today:
        weeks.append(WeekCount(start=cursor, n=per_week.get(cursor, 0)))
        cursor += timedelta(days=7)

    counts = Counter(c if c in CATEGORY_KEYS else "lainnya" for _, c in inside)
    return Activity(
        n_total=len(rows),
        n_window=len(inside),
        n_30=sum(1 for d in days if d > today - timedelta(days=QUIET_DAYS)),
        window_days=window_days,
        last_published=last,
        days_since_last=since_last,
        longest_gap_days=longest,
        median_gap_days=cadence,
        active_days=len(set(days)),
        weeks_without=sum(1 for w in weeks if w.n == 0),
        quiet=since_last is None or since_last >= QUIET_DAYS,
        weeks=tuple(weeks),
        categories=tuple((k, counts[k]) for k, _ in CATEGORIES if counts[k]),
    )


def status_label(activity: Activity) -> str:
    """Bacaan singkat yang hanya menyebut apa yang terhitung."""
    if activity.n_total == 0:
        return "belum ada terbitan tercatat"
    assert activity.days_since_last is not None
    if activity.quiet:
        return f"sepi: {activity.days_since_last} hari tanpa terbitan tercatat"
    if activity.n_30 >= 20:
        return "hampir tiap hari"
    if activity.n_30 >= 4:
        return "beberapa kali seminggu sampai mingguan"
    return "jarang"
