"""Media monitoring lewat feed RSS/Atom.

Feed adalah bentuk publikasi yang memang disediakan penerbit untuk dibaca
mesin, jadi ia satu-satunya sumber media di paket ini yang tidak butuh
kredensial. Tetap berlaku batasnya: yang diambil hanya feed yang diterbitkan
terbuka, tanpa menyamar sebagai peramban dan tanpa menembus paywall.

Yang tersimpan dari sebuah artikel adalah judul dan ringkasan yang penerbit
sendiri taruh di feed — bukan isi lengkap artikelnya. Selain menghormati hak
cipta penerbit, ringkasan memang cukup untuk analisis agenda: yang diukur di
sini adalah APA yang diangkat redaksi dan seberapa sering, bukan isi
paragrafnya.

Parsing dipisah dari pengambilan (`parse_feed` adalah fungsi murni) supaya bisa
dites tanpa jaringan.

## Penyaring kata kunci (`keywords`, opsional)

Feed media umum ("terkini", "nasional") memuat semua berita. Proyek riset
bertema — mis. program Makan Bergizi Gratis — hanya butuh yang menyinggung
temanya; tanpa penyaring, satu sumber Antara saja akan membanjiri proyek
dengan ratusan berita yang tidak relevan dan merusak setiap agregat di atasnya.

`keywords` adalah daftar frasa dipisah koma, dicocokkan sebagai KATA UTUH tanpa
membedakan huruf besar/kecil (`"mbg"` cocok dengan "MBG" tapi tidak dengan
"kambing"). Sengaja bukan regex bebas: pola yang ditulis pengguna dijalankan di
server untuk setiap item feed, dan regex bebas membuka jalan pola yang bisa
membuat server macet (backtracking katastrofik). Frasa yang di-escape tidak
bisa begitu.

Penyaring berlaku SEBELUM `limit`: batas item berlaku pada yang relevan, bukan
membuang yang relevan karena kalah urutan dengan berita lain.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import ClassVar

import httpx

from app.connectors.base import (
    Connector,
    ConnectorError,
    FetchStats,
    RawItem,
    register,
    require,
)
from app.models.measurement import SignalSource

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

#: Namespace Atom. RSS 2.0 tidak memakai namespace.
_ATOM = "{http://www.w3.org/2005/Atom}"

REQUEST_TIMEOUT = 20.0

#: User-Agent yang menyebut diri apa adanya. Sengaja BUKAN string peramban:
#: menyamar sebagai Chrome adalah cara melewati pembatasan penerbit, dan itu
#: dilarang di paket ini (lihat connectors/base.py).
USER_AGENT = "AIPublicOpinionPlatform/0.1 (+feed reader; contact via platform admin)"


#: Batas jumlah dan panjang frasa. Bukan batas teknis regex — batas supaya
#: konfigurasi yang jelas keliru (tempelan satu paragraf) ditolak saat sumber
#: didaftarkan, bukan diam-diam tidak pernah cocok dengan apa pun.
MAX_KEYWORDS = 50
MAX_KEYWORD_LENGTH = 100


def compile_keywords(raw: str) -> re.Pattern[str]:
    """Ubah `"makan bergizi gratis, mbg"` jadi pola kata-utuh. Fungsi murni.

    Setiap frasa di-escape (tidak ada metakarakter regex dari pengguna yang
    hidup), spasi di dalam frasa cocok dengan spasi apa pun, dan batas kata
    dipasang di kedua ujung. Melempar ConnectorError untuk daftar kosong —
    penyaring yang tidak menyaring apa pun hampir pasti salah ketik, dan
    diam-diam menerima SEMUA item adalah kegagalan yang paling mahal.
    """
    phrases = [p.strip() for p in raw.split(",")]
    phrases = [p for p in phrases if p]
    if not phrases:
        raise ConnectorError("keywords diisi tapi tidak berisi frasa apa pun")
    if len(phrases) > MAX_KEYWORDS:
        raise ConnectorError(f"keywords maksimal {MAX_KEYWORDS} frasa")
    too_long = [p for p in phrases if len(p) > MAX_KEYWORD_LENGTH]
    if too_long:
        raise ConnectorError(f"frasa keywords maksimal {MAX_KEYWORD_LENGTH} karakter")
    alternatives = "|".join(
        r"\s+".join(re.escape(word) for word in phrase.split()) for phrase in phrases
    )
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", text))).strip()


def _parse_date(raw: str | None) -> datetime | None:
    """Tanggal feed datang dalam dua format berbeda dan sering cacat.

    Item tanpa tanggal yang bisa dibaca dikembalikan None dan dibuang oleh
    pemanggil — memberinya `now()` akan menaruh artikel lama di puncak tren
    hari ini.
    """
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    try:  # RSS 2.0: RFC 822
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        pass
    try:  # Atom: ISO 8601
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _ensure_aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _text_of(node: ET.Element | None) -> str | None:
    return node.text if node is not None else None


def _identity(link: str, guid: str) -> str:
    """Identitas item: permalink artikel kalau ada, guid kalau tidak.

    Guid saja tidak cukup. Liputan6 (diperiksa 2026-09-15) menulis guid berupa
    angka ("8292436") — unik, tapi tidak bisa ditelusuri balik ke artikelnya,
    sehingga `_recover_source_url` di routers/signals.py tidak punya apa pun
    untuk dipulihkan. Permalink bisa. Ini juga identitas yang dipakai skrip
    ingest proyek riset sebelum jalur ini ada, jadi item yang sudah masuk
    lewat skrip itu tidak tergandakan ketika sumber yang sama mulai ditarik
    dari sini: dedup berjalan pada (project, connector, external_id).
    """
    if link.startswith(("http://", "https://")):
        return link
    return guid


def parse_feed(payload: bytes) -> list[RawItem]:
    """Ubah XML feed menjadi RawItem. Fungsi murni — inti yang dites.

    Mendukung RSS 2.0 (`<item>`) dan Atom (`<entry>`). Item tanpa judul
    maupun ringkasan dibuang: tidak ada yang bisa dianalisis darinya.
    """
    head = payload[:512].lstrip().lower()
    if head.startswith((b"<!doctype html", b"<html")):
        # Kontan (diperiksa 2026-09-15): URL feed lamanya membalas 200 dengan
        # halaman HTML. "XML tidak valid, baris 8 kolom 1512" benar tapi
        # menyesatkan — yang perlu diketahui peneliti adalah feednya sudah
        # tidak ada di alamat itu.
        raise ConnectorError(
            "alamat ini mengembalikan halaman HTML, bukan feed RSS/Atom — "
            "feed kemungkinan sudah dipindah atau dihentikan penerbit"
        )
    try:
        root = ET.fromstring(payload)  # noqa: S314 — feed publik, bukan input pengguna
    except ET.ParseError as e:
        raise ConnectorError(f"feed bukan XML yang valid: {e}") from e

    items: list[RawItem] = []

    for node in root.iter():
        tag = node.tag
        if tag == "item":  # RSS 2.0
            title = _clean(_text_of(node.find("title")))
            summary = _clean(_text_of(node.find("description")))
            link = (_text_of(node.find("link")) or "").strip()
            guid = (_text_of(node.find("guid")) or link).strip()
            published = _parse_date(_text_of(node.find("pubDate")))
            author = _clean(_text_of(node.find("author"))) or None
        elif tag == f"{_ATOM}entry":  # Atom
            title = _clean(_text_of(node.find(f"{_ATOM}title")))
            summary = _clean(
                _text_of(node.find(f"{_ATOM}summary")) or _text_of(node.find(f"{_ATOM}content"))
            )
            link_node = node.find(f"{_ATOM}link")
            link = (link_node.get("href", "") if link_node is not None else "").strip()
            guid = (_text_of(node.find(f"{_ATOM}id")) or link).strip()
            published = _parse_date(
                _text_of(node.find(f"{_ATOM}published"))
                or _text_of(node.find(f"{_ATOM}updated"))
            )
            author_node = node.find(f"{_ATOM}author")
            author = (
                _clean(_text_of(author_node.find(f"{_ATOM}name"))) or None
                if author_node is not None
                else None
            )
        else:
            continue

        text = " — ".join(p for p in (title, summary) if p)
        identity = _identity(link, guid)
        if not text or not identity or published is None:
            continue

        items.append(
            RawItem(
                external_id=identity,
                text=text,
                published_at=_ensure_aware(published),
                author_handle=author,
                url=link or None,
                extra={"title": title} if title else {},
            )
        )

    return items


@register
class RSSConnector(Connector):
    """Liputan media dari feed yang diterbitkan penerbit."""

    key: ClassVar[str] = "rss"
    label: ClassVar[str] = "Feed RSS/Atom media"
    source: ClassVar[SignalSource] = SignalSource.MEDIA
    requires_credential: ClassVar[str | None] = None
    config_fields: ClassVar[tuple[str, ...]] = ("feed_url",)
    optional_fields: ClassVar[tuple[str, ...]] = ("keywords", "label")
    notes: ClassVar[str] = (
        "Hanya judul dan ringkasan yang disediakan penerbit di feed, bukan isi "
        "artikel lengkap. Liputan menunjukkan agenda redaksi, bukan opini "
        "pembaca — jangan dibaca sebagai sentimen publik. Isi `keywords` "
        "(frasa dipisah koma, dicocokkan sebagai kata utuh) untuk hanya "
        "menyimpan berita yang menyinggung tema proyek."
    )

    def validate_config(self, config: dict[str, str]) -> None:
        url = config.get("feed_url", "").strip()
        if not url.startswith(("http://", "https://")):
            raise ConnectorError("feed_url harus URL http/https")
        if "keywords" in config:
            compile_keywords(config["keywords"])

    async def fetch(
        self,
        config: dict[str, object],
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[RawItem]:
        cfg = require(config, self.config_fields)
        url = cfg["feed_url"]
        if not url.startswith(("http://", "https://")):
            raise ConnectorError("feed_url harus URL http/https")
        keywords = config.get("keywords")
        pattern = compile_keywords(str(keywords)) if keywords is not None else None

        try:
            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ConnectorError(
                f"penerbit menolak permintaan feed ({e.response.status_code})"
            ) from e
        except httpx.HTTPError as e:
            raise ConnectorError(f"feed tidak bisa diambil: {e}") from e

        offered = parse_feed(response.content)
        items = filter_items(offered, pattern=pattern, since=since)
        items.sort(key=lambda i: i.published_at, reverse=True)
        self.last_fetch = FetchStats(
            offered=len(offered),
            oldest_offered=min((i.published_at for i in offered), default=None),
            matched=len(items),
        )
        return items[:limit]


def filter_items(
    items: list[RawItem],
    *,
    pattern: re.Pattern[str] | None,
    since: datetime | None,
) -> list[RawItem]:
    """Saring menurut tanggal lalu kata kunci. Fungsi murni.

    Kata kunci dicocokkan pada teks yang tersimpan (judul + ringkasan), jadi
    siapa pun yang memvalidasi data bisa melihat sendiri kenapa sebuah item
    lolos — tidak ada kecocokan pada bagian yang tidak disimpan.
    """
    if since is not None:
        cutoff = _ensure_aware(since)
        items = [i for i in items if i.published_at >= cutoff]
    if pattern is not None:
        items = [i for i in items if pattern.search(i.text)]
    return items
