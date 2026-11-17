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
from collections import Counter
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


@dataclass(slots=True)
class _Day:
    volume: int = 0
    scored: int = 0
    total: float = 0.0
    negative: int = 0
    #: Paling banyak TOP_PER_PEAK kandidat konten teramai (engagement > 0).
    top: list[tuple[int, datetime, int, Row]] = field(default_factory=list)


@dataclass(slots=True)
class _Source:
    n: int = 0
    words: Counter[str] = field(default_factory=Counter)
    tags: Counter[str] = field(default_factory=Counter)
    emoji: Counter[str] = field(default_factory=Counter)
    labels: Counter[str] = field(default_factory=Counter)
    days: dict[date, _Day] = field(default_factory=dict)


@dataclass(slots=True)
class _Topic:
    n: int = 0
    engagement: int = 0
    scored: int = 0
    total: float = 0.0


def _keep(
    bucket: list[tuple[int, datetime, int, Row]], entry: tuple[int, datetime, int, Row]
) -> None:
    """Simpan `entry` bila termasuk TOP_PER_PEAK terkecil menurut (kunci, waktu, urutan masuk)."""
    if len(bucket) < TOP_PER_PEAK:
        bucket.append(entry)
        bucket.sort(key=lambda e: e[:3])
    elif entry[:3] < bucket[-1][:3]:
        bucket[-1] = entry
        bucket.sort(key=lambda e: e[:3])


class Builder:
    """`build` yang diisi sepotong demi sepotong.

    Yang disimpan hanya hitungan dan paling banyak `TOP_PER_PEAK` konten per
    hari per sumber, bukan seluruh konten jendela. Dipakai router yang membaca
    konten per potongan dari database. Hasilnya sama persis dengan `build`
    atas gabungan semua potongan dalam urutan yang sama.
    """

    def __init__(self, *, tz: str = "WIB", sources: Sequence[str] = ("SOCIAL", "MEDIA")) -> None:
        if tz not in TIMEZONES:
            raise ValueError(f"zona waktu tidak dikenal: {tz!r}")
        self._tz = tz
        self._zone = timezone(timedelta(hours=TIMEZONES[tz]))
        self._sources = tuple(sources)
        self._by_source: dict[str, _Source] = {}
        #: Liputan paling awal per hari, untuk "liputan hari yang sama".
        self._media_by_day: dict[date, list[tuple[int, datetime, int, Row]]] = {}
        self._outlets: Counter[str] = Counter()
        self._topics: dict[tuple[str, str], _Topic] = {}
        self._seq = 0

    def add(self, rows: Iterable[Row]) -> None:
        for row in rows:
            if row.source not in self._sources:
                continue
            moment = row.published_at
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=UTC)
            day = moment.astimezone(self._zone).date()
            seq = self._seq
            self._seq += 1

            acc = self._by_source.setdefault(row.source, _Source())
            acc.n += 1
            acc.words.update(words_in(row.text))
            acc.tags.update(hashtags_in(row.text))
            acc.emoji.update(emoji_in(row.text))
            acc.labels["tidak dinilai" if row.sentiment is None else label_for(row.sentiment)] += 1

            d = acc.days.setdefault(day, _Day())
            d.volume += 1
            if row.sentiment is not None:
                d.scored += 1
                d.total += row.sentiment
                if label_for(row.sentiment) == "negatif":
                    d.negative += 1
            if row.engagement > 0:
                _keep(d.top, (-row.engagement, row.published_at, seq, row))

            if row.source == "MEDIA":
                _keep(self._media_by_day.setdefault(day, []), (0, row.published_at, seq, row))
                domain = domain_of(row.url)
                if domain:
                    self._outlets[domain] += 1

            if row.topic_id:
                t = self._topics.setdefault((row.topic_id, row.source), _Topic())
                t.n += 1
                t.engagement += max(0, row.engagement)
                if row.sentiment is not None:
                    t.scored += 1
                    t.total += row.sentiment

    def result(self, *, word_limit: int = 30, tag_limit: int = 15) -> Report:
        reports: list[SourceReport] = []
        for source in self._sources:
            acc = self._by_source.get(source)
            if acc is None:
                continue
            days: list[DaySentiment] = []
            for day in sorted(acc.days):
                tally = acc.days[day]
                enough = tally.scored >= MIN_SCORED
                days.append(
                    DaySentiment(
                        day=day,
                        volume=tally.volume,
                        scored=tally.scored,
                        mean=round(tally.total / tally.scored, 3) if enough else None,
                        negative_share=(
                            round(tally.negative / tally.scored, 3) if enough else None
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
                same_day = [] if source == "MEDIA" else self._media_by_day.get(d.day, [])
                peaks.append(
                    Peak(
                        day=d.day,
                        volume=d.volume,
                        ratio=ratio,
                        is_spike=is_spike,
                        top_content=[_item(e[3]) for e in acc.days[d.day].top],
                        same_day_media=[_item(e[3]) for e in same_day],
                    )
                )

            reports.append(
                SourceReport(
                    source=source,
                    n=acc.n,
                    scored=sum(v for k, v in acc.labels.items() if k != "tidak dinilai"),
                    labels=dict(acc.labels),
                    days=days,
                    peaks=peaks,
                    words=_top(acc.words, word_limit),
                    hashtags=_top(acc.tags, tag_limit),
                    emoji=_top(acc.emoji, tag_limit),
                )
            )

        topics = [
            TopicStat(
                topic_id=topic_id,
                source=source,
                n=t.n,
                engagement=t.engagement,
                scored=t.scored,
                mean=round(t.total / t.scored, 3) if t.scored >= MIN_SCORED else None,
            )
            for (topic_id, source), t in self._topics.items()
        ]
        topics.sort(key=lambda t: (-t.n, t.topic_id, t.source))

        return Report(
            timezone=self._tz,
            sources=reports,
            outlets=[Outlet(domain=d, n=n) for d, n in _top(self._outlets, 15)],
            outlets_total=len(self._outlets),
            topics=topics,
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
    builder = Builder(tz=tz, sources=sources)
    builder.add(rows)
    return builder.result(word_limit=word_limit, tag_limit=tag_limit)
