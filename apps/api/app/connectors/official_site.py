"""Pembaca situs web RESMI lembaga: apa yang terbit untuk publik, dan kapan.

Sesuai batas di `base.py`, konektor ini hanya membaca berkas yang memang
diterbitkan situs untuk dibaca mesin:

* `robots.txt` (dan dipatuhi: bila situs melarang semua mesin, berhenti);
* feed RSS/Atom, baik yang diumumkan di `<link rel="alternate">` beranda
  maupun di alamat umum (`/feed`, `/rss`, ...);
* `sitemap.xml` beserta satu tingkat indeksnya.

Bila ketiganya tidak memuat butir bertanggal, ada satu jalur lagi yang
dibuka sebagai pengecualian tertulis di `base.py` (keputusan pemilik produk,
15 November 2026): HALAMAN DAFTAR berita atau siaran pers situs resmi itu,
yang alamatnya didaftarkan pengguna. Syaratnya mengikat:

* identitas jujur (`USER_AGENT` platform), tanpa menyamar sebagai peramban;
* `robots.txt` dipatuhi untuk alamat halaman itu;
* paling banyak `MAX_LIST_PAGES` halaman per situs per pembacaan, dan
  pembacaan ulang dibatasi jaraknya di router;
* yang diambil hanya judul, alamat, dan tanggal yang tampil di daftar.
  Halaman artikelnya sendiri tidak dibuka.

Pengurainya umum (tautan butir + tanggal terdekat), bukan satu per situs.
Halaman yang tata letaknya tidak cocok menghasilkan nol butir dan dilaporkan
begitu, bukan ditebak.

Yang dibaca hanya judul, alamat, dan tanggal. Isi artikel tidak diambil.
"""

from __future__ import annotations

import asyncio
import html as htmllib
import ipaddress
import re
import socket
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import urljoin, urlsplit

import httpx

from app.connectors.base import ConnectorError
from app.connectors.rss import USER_AGENT, FeedMalformed, parse_feed

REQUEST_TIMEOUT = 15.0
FEED_PATHS = ("/feed", "/rss", "/rss.xml", "/feed.xml", "/atom.xml", "/index.xml")
MAX_CHILD_SITEMAPS = 5
MAX_ITEMS = 2000
MAX_BYTES = 8_000_000
#: Halaman daftar berita yang boleh dibaca per situs per pembacaan.
MAX_LIST_PAGES = 5
#: Jarak terjauh (karakter HTML) antara tautan butir dan tanggalnya.
MAX_DATE_DISTANCE = 1500
MIN_TITLE_LENGTH = 15
#: Daftar hanya menampilkan tanggal; jam dicatat 12.00 WIB supaya harinya
#: tidak bergeser saat dibaca di zona lain.
LIST_DATE_OFFSET = timedelta(hours=5)

_HOST = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
_LINK_TAG = re.compile(r"<link\b[^>]*>", re.I)
_ATTR = re.compile(r"""([a-zA-Z-]+)\s*=\s*["']([^"']*)["']""")
_STATIC = re.compile(r"\.(pdf|jpe?g|png|gif|webp|svg|docx?|xlsx?|pptx?|zip|mp4|css|js)$", re.I)
_SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


@dataclass(frozen=True, slots=True)
class SiteItem:
    url: str
    title: str | None
    published_at: datetime


@dataclass(slots=True)
class SiteReading:
    base_url: str
    #: "rss" = feed terbaca; "sitemap" = sitemap bertanggal terbaca;
    #: "halaman" = halaman daftar berita terdaftar terbaca;
    #: "none" = tidak ada sumber terbaca mesin yang memuat butir bertanggal.
    kind: Literal["rss", "sitemap", "halaman", "none"]
    source_url: str | None = None
    items: list[SiteItem] = field(default_factory=list)
    #: Langkah yang dicoba dan hasilnya, untuk ditampilkan ke pengguna.
    notes: list[str] = field(default_factory=list)
    n_requests: int = 0


# ------------------------------------------------------------ fungsi murni ----


def normalize_base(raw: str) -> str:
    """`pertanian.go.id`, `https://www.kkp.go.id/berita` -> `https://host`."""
    value = raw.strip()
    if not value:
        raise ConnectorError("Alamat situs kosong.")
    if "://" not in value:
        value = "https://" + value
    parts = urlsplit(value)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not _HOST.match(host):
        raise ConnectorError("Alamat situs harus berupa nama domain, mis. https://lembaga.go.id")
    if parts.port not in (None, 80, 443) or parts.username or parts.password:
        raise ConnectorError("Alamat situs tidak boleh memuat port khusus atau kredensial.")
    return f"https://{host}"


def _site_key(host: str) -> str:
    return host.lower().removeprefix("www.")


def same_site(url: str, base_url: str) -> bool:
    """True bila `url` berada di host yang sama (mengabaikan `www.`)."""
    return _site_key(urlsplit(url).hostname or "") == _site_key(urlsplit(base_url).hostname or "")


def parse_robots(text: str) -> tuple[bool, list[str]]:
    """(dilarang untuk semua mesin?, daftar alamat Sitemap)."""
    sitemaps: list[str] = []
    agents: list[str] = []
    in_rules = False
    blocked = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (p.strip() for p in line.split(":", 1))
        key = key.lower()
        if key == "sitemap" and value:
            sitemaps.append(value)
        elif key == "user-agent":
            if in_rules:
                agents, in_rules = [], False
            agents.append(value.lower())
        elif key in ("disallow", "allow"):
            in_rules = True
            if key == "disallow" and value == "/" and "*" in agents:
                blocked = True
    return blocked, sitemaps


def find_feed_links(html: str, base_url: str) -> list[str]:
    """Alamat feed yang diumumkan beranda lewat `<link rel="alternate">`."""
    found: list[str] = []
    for tag in _LINK_TAG.findall(html[:400_000]):
        attrs = {k.lower(): v for k, v in _ATTR.findall(tag)}
        kind = attrs.get("type", "").lower()
        if "alternate" in attrs.get("rel", "").lower() and ("rss" in kind or "atom" in kind):
            href = attrs.get("href", "").strip()
            if href:
                url = urljoin(base_url + "/", href)
                if url not in found:
                    found.append(url)
    return found


def _stamp(raw: str | None) -> datetime | None:
    value = (raw or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


Entry = tuple[str, datetime | None]


def parse_sitemap(payload: bytes) -> tuple[Literal["index", "urlset"], list[Entry]]:
    """Urai sitemap. Mengangkat `FeedMalformed` bila bukan XML sitemap."""
    if b"<!DOCTYPE" in payload[:2000].upper() and b"<!ENTITY" in payload[:20000].upper():
        raise FeedMalformed("sitemap memuat deklarasi entitas; ditolak")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as e:
        raise FeedMalformed(f"bukan XML: {e}") from e
    tag = root.tag.removeprefix(_SM)
    if tag not in ("urlset", "sitemapindex"):
        raise FeedMalformed(f"bukan sitemap (akar <{tag}>)")
    child = "sitemap" if tag == "sitemapindex" else "url"
    out: list[tuple[str, datetime | None]] = []
    for node in root.iter(f"{_SM}{child}"):
        loc = (node.findtext(f"{_SM}loc") or "").strip()
        if loc.startswith(("http://", "https://")):
            out.append((loc, _stamp(node.findtext(f"{_SM}lastmod"))))
    return ("index" if tag == "sitemapindex" else "urlset"), out


def article_entries(
    entries: list[tuple[str, datetime | None]], base_url: str
) -> list[SiteItem]:
    """Saring entri sitemap menjadi calon butir: bertanggal, di situs yang
    sama, bukan berkas statis, dan bukan halaman tingkat atas."""
    items: list[SiteItem] = []
    seen: set[str] = set()
    for loc, stamp in entries:
        parts = urlsplit(loc)
        depth = len([p for p in parts.path.split("/") if p])
        if (
            stamp is None
            or depth < 2
            or parts.query
            or _STATIC.search(parts.path)
            or not same_site(loc, base_url)
            or loc in seen
        ):
            continue
        seen.add(loc)
        items.append(SiteItem(url=loc, title=None, published_at=stamp))
    return items


_MONTHS = {
    "jan": 1, "januari": 1, "january": 1, "feb": 2, "februari": 2, "february": 2,
    "mar": 3, "maret": 3, "march": 3, "apr": 4, "april": 4, "mei": 5, "may": 5,
    "jun": 6, "juni": 6, "june": 6, "jul": 7, "juli": 7, "july": 7,
    "agu": 8, "ags": 8, "agt": 8, "agustus": 8, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9, "okt": 10, "oktober": 10, "oct": 10,
    "october": 10, "nov": 11, "nop": 11, "november": 11, "nopember": 11,
    "des": 12, "desember": 12, "dec": 12, "december": 12,
}  # fmt: skip
_DATE = re.compile(
    r"\b(\d{1,2})[\s\-]+([A-Za-z]{3,9})\.?[\s\-,]+(20\d\d)\b"
    r"|\b(20\d\d)-(\d\d)-(\d\d)\b"
    r"|\b(\d{1,2})/(\d{1,2})/(20\d\d)\b"
)
_NOISE = re.compile(r"<(script|style|noscript|svg)\b.*?</\1>", re.S | re.I)
_DATA_URI = re.compile(r"""=\s*["']data:[^"']*["']""")
_ANCHOR = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.S | re.I)
_HEADING = re.compile(r"<h[1-6]\b[^>]*>(.*?)</h[1-6]>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_SHORT_ID = re.compile(r"-\w{4}\.html$")
# Kartu yang seluruhnya tautan: "Selasa, 10 November 2026 Siaran Pers Judul".
_LEAD = re.compile(
    r"^(?:[A-Za-z]+,\s*)?\d{1,2}\s+[A-Za-z]{3,9}\s+20\d\d\s*"
    r"(?:(?:Siaran Pers|Berita|Artikel|Pengumuman)\s+)?"
)


def _plain(fragment: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(_TAG.sub(" ", fragment))).strip()


def _list_date(match: re.Match[str]) -> datetime | None:
    try:
        if match.group(1):
            month = _MONTHS.get(match.group(2).lower())
            if month is None:
                return None
            y, m, d = int(match.group(3)), month, int(match.group(1))
        elif match.group(4):
            y, m, d = int(match.group(4)), int(match.group(5)), int(match.group(6))
        else:  # hari/bulan/tahun, urutan Indonesia
            y, m, d = int(match.group(9)), int(match.group(8)), int(match.group(7))
        return datetime(y, m, d, tzinfo=UTC) + LIST_DATE_OFFSET
    except ValueError:
        return None


def _looks_like_article(path: str) -> bool:
    """Alamat butir, bukan menu: slug panjang, nomor di kedalaman >= 3, atau
    berakhiran id pendek (`...-AbCd.html`)."""
    segments = [p for p in path.split("/") if p]
    if len(segments) < 2 or _STATIC.search(path):
        return False
    last = segments[-1]
    return (
        len(last) >= 20
        or (len(segments) >= 3 and last.isdigit() and len(last) >= 2)
        or bool(_SHORT_ID.search(last))
    )


def parse_listing(html: str, page_url: str) -> list[SiteItem]:
    """Butir dari satu halaman DAFTAR berita: tautan butir + tanggal terdekat.

    Tautan tanpa tanggal dalam jarak `MAX_DATE_DISTANCE` dibuang, begitu juga
    tautan tanpa judul yang layak. Tidak ada yang ditebak.
    """
    body = _DATA_URI.sub('=""', _NOISE.sub(" ", html[:MAX_BYTES]))
    dates = [(m.start(), d) for m in _DATE.finditer(body) if (d := _list_date(m)) is not None]
    if not dates:
        return []
    found: dict[str, tuple[list[tuple[int, int]], str]] = {}
    for m in _ANCHOR.finditer(body):
        attrs = {k.lower(): v for k, v in _ATTR.findall(m.group(1))}
        href = htmllib.unescape(attrs.get("href", "")).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        url = urljoin(page_url, href).split("#", 1)[0]
        parts = urlsplit(url)
        if parts.query or not same_site(url, page_url) or not _looks_like_article(parts.path):
            continue
        heading = _HEADING.search(m.group(2))
        title = _plain(heading.group(1)) if heading else _plain(m.group(2))
        if len(title) < MIN_TITLE_LENGTH:
            title = htmllib.unescape(attrs.get("title", "")).strip() or title
        title = _LEAD.sub("", title, count=1).strip()
        spans, best = found.get(url, ([], ""))
        spans.append((m.start(), m.end()))
        found[url] = (spans, title if len(title) > len(best) else best)

    items: list[SiteItem] = []
    for url, (spans, title) in found.items():
        if len(title) < MIN_TITLE_LENGTH:
            continue
        nearest: tuple[int, datetime] | None = None
        for start, end in spans:
            for pos, stamp in dates:
                gap = 0 if start <= pos <= end else min(abs(pos - start), abs(pos - end))
                if gap <= MAX_DATE_DISTANCE and (nearest is None or gap < nearest[0]):
                    nearest = (gap, stamp)
        if nearest is not None:
            items.append(SiteItem(url=url, title=title[:500], published_at=nearest[1]))
    return items


def robots_allows(text: str, path: str) -> bool:
    """Apakah `robots.txt` mengizinkan semua mesin (`*`) membaca `path`?

    Aturan terpanjang yang cocok menang; `Allow` menang bila sama panjang.
    Pola berbintang tidak dibaca, kecuali `Disallow: /` yang melarang semuanya.
    """
    rules: list[tuple[str, str]] = []
    agents: list[str] = []
    in_rules = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (p.strip() for p in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if in_rules:
                agents, in_rules = [], False
            agents.append(value.lower())
        elif key in ("allow", "disallow"):
            in_rules = True
            if "*" in agents and value and "*" not in value and "$" not in value:
                rules.append((key, value))
    verdict, length = True, -1
    for key, prefix in rules:
        if path.startswith(prefix) and (
            len(prefix) > length or (len(prefix) == length and key == "allow")
        ):
            verdict, length = key == "allow", len(prefix)
    return verdict


def normalize_list_urls(raw: list[str], base_url: str) -> list[str]:
    """Saring alamat halaman daftar: http(s), di situs yang sama, tanpa ganda."""
    out: list[str] = []
    for value in raw:
        url = value.strip()
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            url = urljoin(base_url + "/", url.lstrip("/"))
        if not same_site(url, base_url):
            raise ConnectorError(f"Halaman daftar harus berada di {base_url}: {url[:120]}")
        if url not in out:
            out.append(url)
    if len(out) > MAX_LIST_PAGES:
        raise ConnectorError(f"Paling banyak {MAX_LIST_PAGES} halaman daftar per situs.")
    return out


# --------------------------------------------------------------------- I/O ----


SAME_DAY_SHARE = 0.8
MIN_DATED_FOR_CHECK = 3


def _same_day(items: list[SiteItem]) -> bool:
    """Hampir semua `lastmod` pada hari yang sama = cap pembuatan berkas."""
    if len(items) < MIN_DATED_FOR_CHECK:
        return False
    days: dict[object, int] = {}
    for i in items:
        days[i.published_at.date()] = days.get(i.published_at.date(), 0) + 1
    return max(days.values()) / len(items) >= SAME_DAY_SHARE


def _assert_public(host: str) -> None:
    """Tolak host yang mengarah ke jaringan dalam (SSRF)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as e:
        raise ConnectorError(f"Nama domain tidak ditemukan: {host}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ConnectorError("Alamat situs mengarah ke jaringan dalam; ditolak.")


async def _guard(request: httpx.Request) -> None:
    await asyncio.to_thread(_assert_public, request.url.host)


async def _get(client: httpx.AsyncClient, url: str, reading: SiteReading) -> httpx.Response | None:
    reading.n_requests += 1
    try:
        response = await client.get(url)
    except ConnectorError:
        raise
    except httpx.HTTPError:
        return None
    if response.status_code != 200 or len(response.content) > MAX_BYTES:
        return None
    return response


async def read_site(
    base: str,
    client: httpx.AsyncClient | None = None,
    *,
    list_urls: list[str] | None = None,
) -> SiteReading:
    """Cari sumber terbaca mesin di satu situs dan ambil butir bertanggalnya."""
    base_url = normalize_base(base)
    if client is None:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            max_redirects=4,
            headers={"User-Agent": USER_AGENT},
            event_hooks={"request": [_guard]},
        ) as own:
            return await _read(base_url, own, list_urls or [])
    return await _read(base_url, client, list_urls or [])


async def _read_listings(
    client: httpx.AsyncClient, reading: SiteReading, list_urls: list[str], robots_text: str
) -> bool:
    """Baca halaman daftar terdaftar. True bila ada butir bertanggal."""
    merged: dict[str, SiteItem] = {}
    read = 0
    for url in list_urls[:MAX_LIST_PAGES]:
        if not robots_allows(robots_text, urlsplit(url).path or "/"):
            reading.notes.append(f"robots.txt melarang {url}; dilewati.")
            continue
        response = await _get(client, url, reading)
        if response is None or "html" not in response.headers.get("content-type", "html"):
            reading.notes.append(f"Halaman daftar tidak bisa dibuka: {url}")
            continue
        read += 1
        found = parse_listing(response.text, str(response.url))
        reading.notes.append(f"Halaman daftar {url}: {len(found)} butir bertanggal.")
        for item in found:
            merged.setdefault(item.url, item)
    if not merged:
        if read:
            reading.notes.append(
                "Halaman daftar terbuka tetapi tidak ada tautan butir dengan tanggal di dekatnya "
                "(mungkin dimuat lewat JavaScript atau tata letaknya berbeda)."
            )
        return False
    reading.kind, reading.source_url = "halaman", list_urls[0]
    reading.items = list(merged.values())[:MAX_ITEMS]
    return True


async def _read(base_url: str, client: httpx.AsyncClient, list_urls: list[str]) -> SiteReading:
    reading = SiteReading(base_url=base_url, kind="none")
    notes = reading.notes
    robots_text = ""

    # Beranda dulu: situs yang pindah ke www sering membalas alamat lain
    # di host lama dengan halaman beranda, termasuk robots.txt.
    feed_urls: list[str] = []
    home = await _get(client, base_url + "/", reading)
    if home is None:
        notes.append("Beranda tidak bisa dibuka.")
    else:
        feed_urls = [u for u in find_feed_links(home.text, base_url) if same_site(u, base_url)]
        # Situs yang pindah ke www: pakai host akhirnya untuk alamat tebakan.
        final = f"https://{home.url.host}"
        if same_site(final, base_url):
            base_url = final
    sitemap_urls: list[str] = []
    robots = await _get(client, base_url + "/robots.txt", reading)
    if robots is not None and "text/plain" in robots.headers.get("content-type", ""):
        robots_text = robots.text
        blocked, declared = parse_robots(robots.text)
        if blocked:
            notes.append("robots.txt melarang semua mesin membaca situs ini; tidak dilanjutkan.")
            return reading
        sitemap_urls = [u for u in declared if same_site(u, base_url)]
        if len(sitemap_urls) < len(declared):
            notes.append("robots.txt menyebut sitemap di luar situs ini; diabaikan.")
    else:
        notes.append("robots.txt tidak ada atau bukan teks.")

    if not feed_urls:
        notes.append("Beranda tidak mengumumkan feed RSS/Atom.")
    for path in FEED_PATHS:
        url = base_url + path
        if url not in feed_urls:
            feed_urls.append(url)

    for url in feed_urls:
        response = await _get(client, url, reading)
        if response is None:
            continue
        try:
            raw = parse_feed(response.content)
        except ConnectorError:  # bukan feed (mis. situs membalas beranda HTML)
            continue
        if raw:
            reading.kind, reading.source_url = "rss", url
            reading.items = [
                SiteItem(url=i.url, title=(i.extra.get("title") or i.text)[:500] or None,
                         published_at=i.published_at)
                for i in raw
                if i.url
            ][:MAX_ITEMS]
            notes.append(f"Feed terbaca: {len(reading.items)} butir.")
            return reading
    notes.append("Tidak ada feed RSS/Atom di alamat umum.")

    for url in (
        base_url + "/sitemap.xml",
        base_url + "/sitemap_index.xml",
        base_url + "/sitemap-index.xml",
    ):
        if url not in sitemap_urls:
            sitemap_urls.append(url)
    entries: list[tuple[str, datetime | None]] = []
    used: str | None = None
    for url in sitemap_urls:
        response = await _get(client, url, reading)
        if response is None:
            continue
        try:
            kind, found = parse_sitemap(response.content)
        except FeedMalformed:
            continue
        used = used or url
        if kind == "urlset":
            entries.extend(found)
            continue
        for child, _ in [f for f in found if same_site(f[0], base_url)][:MAX_CHILD_SITEMAPS]:
            sub = await _get(client, child, reading)
            if sub is None:
                continue
            try:
                sub_kind, sub_found = parse_sitemap(sub.content)
            except FeedMalformed:
                continue
            if sub_kind == "urlset":
                entries.extend(sub_found)
        if entries:
            break

    items = article_entries(entries, base_url)[:MAX_ITEMS] if used else []
    if used is None:
        notes.append("Tidak ada sitemap.xml yang terbaca.")
    elif not items:
        notes.append(
            f"Sitemap terbaca ({len(entries)} alamat) tetapi tidak memuat halaman butir "
            "bertanggal, hanya halaman tetap."
        )
    elif _same_day(items):
        notes.append(
            f"Tanggal di sitemap hampir semuanya sama ({len(items)} alamat), jadi itu cap waktu "
            "pembuatan berkas, bukan tanggal terbit. Tidak dipakai."
        )
    else:
        reading.kind, reading.source_url, reading.items = "sitemap", used, items
        notes.append(f"Sitemap terbaca: {len(items)} alamat butir bertanggal dari {len(entries)}.")
        return reading

    if list_urls:
        await _read_listings(client, reading, list_urls, robots_text)
    return reading
