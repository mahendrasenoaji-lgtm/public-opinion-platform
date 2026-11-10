"""Bahan laporan percakapan: kata, tagar, emoji, lonjakan, sentimen harian,
media, dan tema. Fungsi murni, satu lintasan atas konten.

Laporan percakapan menjawab pertanyaan yang biasa diajukan pada pemantauan
isu (apa yang dibicarakan, kapan melonjak, bersamaan dengan apa, siapa
medianya), dengan aturan platform ini tetap berlaku:

- tidak ada angka lintas sumber yang digabung (R1): setiap bagian dihitung
  per sumber;
- lonjakan dilaporkan bersama konten yang TERBIT PADA HARI YANG SAMA, bukan
  sebagai penyebabnya (CLAUDE.md bagian 3: tidak ada klaim kausal dari data
  observasional);
- akun penulis tidak pernah keluar dari sini, bahkan sebagai hash. Yang
  disebut namanya hanya media (lembaga), lewat domain tautannya.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone
from urllib.parse import urlsplit

from app.services.ingestion import normalize_text, wordset
from app.services.sentiment import label_for
from app.services.signal_stats import TIMEZONES
from app.services.topics import STOPWORDS_ID

#: Sama dengan ambang agregat sentimen di routers/signals.py.
MIN_SCORED = 30

#: Hari disebut lonjakan bila volumenya minimal sekian kali median harian.
SPIKE_RATIO = 1.5
MAX_PEAKS = 3
TOP_PER_PEAK = 3

_HASHTAG_RE = re.compile(r"#(\w{2,50})")
_VARIATION_SELECTOR = "️"

#: Kata umum percakapan yang lolos dari `STOPWORDS_ID` tetapi tidak
#: menceritakan isi (kata tugas, sapaan, partikel ragam cakap).
_EXTRA_STOP = wordset("""
    yg dgn utk tdk gak ga nggak enggak gk tak udah sdh udh blm klo kalo kl
    aja jd jg jgn dr pd krn karna tp tpi sm sama lg lagi bgt banget dah
    nya lah kah pun si sih deh dong nih tuh kok ya yaa iya gitu gini
    itu ini di ke dari buat bikin biar mau maka malah cuma hanya masih
    pak bu bapak ibu mas mbak bang bro gan om kak
    kita kami saya aku gue gw lu lo kamu anda dia mereka kalian
    apa kenapa gimana bagaimana mana siapa kapan
    the and to of in is for you this that
    bisa ada jadi juga sudah akan dengan untuk pada yang tidak
    jangan semua punya suruh kalau sampai harus
    tau tahu baru pasti hari sekali lebih atau karena oleh memang seperti begitu
    sendiri orang dulu nanti kalau bukan belum tapi
""")

_STOP = STOPWORDS_ID | _EXTRA_STOP


@dataclass(frozen=True, slots=True)
class Row:
    """Satu konten, hanya kolom yang dibutuhkan laporan."""

    source: str
    text: str
    sentiment: float | None
    published_at: datetime
    engagement: int
    url: str | None
    topic_id: str | None = None


@dataclass(frozen=True, slots=True)
class Item:
    text: str
    engagement: int
    url: str | None
    published_at: datetime


@dataclass(frozen=True, slots=True)
class Peak:
    day: date
    volume: int
    #: Volume dibagi median volume harian sumber ini; None bila median nol.
    ratio: float | None
    #: True bila `ratio >= SPIKE_RATIO`. Hari teramai yang bukan lonjakan
    #: tetap dilaporkan, dengan tanda ini False.
    is_spike: bool
    top_content: list[Item]
    #: Liputan yang terbit pada hari yang sama (bukan penyebab).
    same_day_media: list[Item]


@dataclass(frozen=True, slots=True)
class DaySentiment:
    day: date
    volume: int
    scored: int
    #: None di bawah `MIN_SCORED`.
    mean: float | None
    negative_share: float | None


@dataclass(frozen=True, slots=True)
class SourceReport:
    source: str
    n: int
    scored: int
    #: Jumlah konten per label; kunci "tidak dinilai" untuk yang abstain.
    labels: dict[str, int]
    days: list[DaySentiment]
    peaks: list[Peak]
    #: (kata, jumlah konten yang memuatnya), terbanyak dulu.
    words: list[tuple[str, int]]
    hashtags: list[tuple[str, int]]
    emoji: list[tuple[str, int]]


@dataclass(frozen=True, slots=True)
class Outlet:
    domain: str
    n: int


@dataclass(frozen=True, slots=True)
class TopicStat:
    topic_id: str
    source: str
    n: int
    engagement: int
    scored: int
    mean: float | None


@dataclass(frozen=True, slots=True)
class Report:
    timezone: str
    sources: list[SourceReport]
    outlets: list[Outlet]
    outlets_total: int
    topics: list[TopicStat] = field(default_factory=list)


def _is_emoji(ch: str) -> bool:
    code = ord(ch)
    if code < 0x2190:
        return False
    return unicodedata.category(ch) == "So" and (
        code >= 0x1F000 or 0x2600 <= code <= 0x27BF or 0x2B00 <= code <= 0x2BFF
    )


def emoji_in(text: str) -> list[str]:
    """Emoji di teks, masing-masing sekali (pengulangan adalah penekanan)."""
    seen: list[str] = []
    for ch in text:
        if ch != _VARIATION_SELECTOR and _is_emoji(ch) and ch not in seen:
            seen.append(ch)
    return seen


def hashtags_in(text: str) -> list[str]:
    seen: list[str] = []
    for match in _HASHTAG_RE.finditer(text):
        tag = "#" + match.group(1).casefold()
        if tag not in seen:
            seen.append(tag)
    return seen


def words_in(text: str) -> set[str]:
    """Kata isi di teks: tanpa kata umum, tanpa angka, minimal tiga huruf."""
    return {
        tok
        for tok in normalize_text(text).split()
        if len(tok) >= 3 and tok not in _STOP and not tok.isdigit()
    }


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    host = urlsplit(url).hostname
    if not host:
        return None
    return host.removeprefix("www.").casefold()


def _top(counter: Counter[str], limit: int) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]


def _item(row: Row) -> Item:
    return Item(
        text=row.text, engagement=row.engagement, url=row.url, published_at=row.published_at
    )


def build(
    rows: Iterable[Row],
    *,
    tz: str = "WIB",
    sources: Sequence[str] = ("SOCIAL", "MEDIA"),
    word_limit: int = 30,
    tag_limit: int = 15,
) -> Report:
    """Susun bahan laporan dari konten satu jendela waktu."""
    if tz not in TIMEZONES:
        raise ValueError(f"zona waktu tidak dikenal: {tz!r}")
    zone = timezone(timedelta(hours=TIMEZONES[tz]))

    by_source: dict[str, list[tuple[date, Row]]] = defaultdict(list)
    for row in rows:
        if row.source not in sources:
            continue
        moment = row.published_at
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        by_source[row.source].append((moment.astimezone(zone).date(), row))

    media_by_day: dict[date, list[Row]] = defaultdict(list)
    for day, row in by_source.get("MEDIA", []):
        media_by_day[day].append(row)

    reports: list[SourceReport] = []
    topic_acc: dict[tuple[str, str], list[Row]] = defaultdict(list)

    for source in sources:
        entries = by_source.get(source)
        if not entries:
            continue
        words: Counter[str] = Counter()
        tags: Counter[str] = Counter()
        emoji: Counter[str] = Counter()
        labels: Counter[str] = Counter()
        per_day: dict[date, list[Row]] = defaultdict(list)
        for day, row in entries:
            per_day[day].append(row)
            words.update(words_in(row.text))
            tags.update(hashtags_in(row.text))
            emoji.update(emoji_in(row.text))
            labels["tidak dinilai" if row.sentiment is None else label_for(row.sentiment)] += 1
            if row.topic_id:
                topic_acc[(row.topic_id, source)].append(row)

        days: list[DaySentiment] = []
        for day in sorted(per_day):
            scored = [r.sentiment for r in per_day[day] if r.sentiment is not None]
            enough = len(scored) >= MIN_SCORED
            days.append(
                DaySentiment(
                    day=day,
                    volume=len(per_day[day]),
                    scored=len(scored),
                    mean=round(sum(scored) / len(scored), 3) if enough else None,
                    negative_share=(
                        round(sum(label_for(s) == "negatif" for s in scored) / len(scored), 3)
                        if enough
                        else None
                    ),
                )
            )

        median = statistics.median(d.volume for d in days)
        ranked = sorted(days, key=lambda d: (-d.volume, d.day))[:MAX_PEAKS]
        peaks: list[Peak] = []
        for d in ranked:
            ratio = round(d.volume / median, 2) if median else None
            is_spike = len(days) >= 3 and ratio is not None and ratio >= SPIKE_RATIO
            if peaks and not is_spike:
                continue  # hanya hari teramai yang dilaporkan bila bukan lonjakan
            top = sorted(
                (r for r in per_day[d.day] if r.engagement > 0),
                key=lambda r: (-r.engagement, r.published_at),
            )[:TOP_PER_PEAK]
            same_day = (
                []
                if source == "MEDIA"
                else sorted(media_by_day.get(d.day, []), key=lambda r: r.published_at)[
                    :TOP_PER_PEAK
                ]
            )
            peaks.append(
                Peak(
                    day=d.day,
                    volume=d.volume,
                    ratio=ratio,
                    is_spike=is_spike,
                    top_content=[_item(r) for r in top],
                    same_day_media=[_item(r) for r in same_day],
                )
            )

        reports.append(
            SourceReport(
                source=source,
                n=len(entries),
                scored=sum(v for k, v in labels.items() if k != "tidak dinilai"),
                labels=dict(labels),
                days=days,
                peaks=peaks,
                words=_top(words, word_limit),
                hashtags=_top(tags, tag_limit),
                emoji=_top(emoji, tag_limit),
            )
        )

    outlet_counts: Counter[str] = Counter()
    for _, row in by_source.get("MEDIA", []):
        domain = domain_of(row.url)
        if domain:
            outlet_counts[domain] += 1

    topics: list[TopicStat] = []
    for (topic_id, source), members in topic_acc.items():
        scored = [r.sentiment for r in members if r.sentiment is not None]
        topics.append(
            TopicStat(
                topic_id=topic_id,
                source=source,
                n=len(members),
                engagement=sum(max(0, r.engagement) for r in members),
                scored=len(scored),
                mean=round(sum(scored) / len(scored), 3) if len(scored) >= MIN_SCORED else None,
            )
        )
    topics.sort(key=lambda t: (-t.n, t.topic_id, t.source))

    return Report(
        timezone=tz,
        sources=reports,
        outlets=[Outlet(domain=d, n=n) for d, n in _top(outlet_counts, 15)],
        outlets_total=len(outlet_counts),
        topics=topics,
    )
