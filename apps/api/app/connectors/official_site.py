"""Pembaca situs web RESMI lembaga: apa yang terbit untuk publik, dan kapan.

Sesuai batas di `base.py`, konektor ini hanya membaca berkas yang memang
diterbitkan situs untuk dibaca mesin:

* `robots.txt` (dan dipatuhi: bila situs melarang semua mesin, berhenti);
* feed RSS/Atom, baik yang diumumkan di `<link rel="alternate">` beranda
  maupun di alamat umum (`/feed`, `/rss`, ...);
* `sitemap.xml` beserta satu tingkat indeksnya.

Halaman berita TIDAK diurai. Akibatnya nyata: situs tanpa feed dan dengan
sitemap yang tidak bertanggal tidak bisa dibaca otomatis, dan itu dilaporkan
apa adanya (`kind="none"`), bukan ditambal dengan menggaruk HTML. Untuk situs
seperti itu jalurnya unggahan manual.

Yang dibaca hanya judul, alamat, dan tanggal. Isi artikel tidak diambil.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
    #: "none" = tidak ada sumber terbaca mesin yang memuat butir bertanggal.
    kind: Literal["rss", "sitemap", "none"]
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


# --------------------------------------------------------------------- I/O ----


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


async def read_site(base: str, client: httpx.AsyncClient | None = None) -> SiteReading:
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
            return await _read(base_url, own)
    return await _read(base_url, client)


async def _read(base_url: str, client: httpx.AsyncClient) -> SiteReading:
    reading = SiteReading(base_url=base_url, kind="none")
    notes = reading.notes

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

    if used is None:
        notes.append("Tidak ada sitemap.xml yang terbaca.")
        return reading
    items = article_entries(entries, base_url)[:MAX_ITEMS]
    if not items:
        notes.append(
            f"Sitemap terbaca ({len(entries)} alamat) tetapi tidak memuat halaman butir "
            "bertanggal, hanya halaman tetap."
        )
        return reading
    reading.kind, reading.source_url, reading.items = "sitemap", used, items
    notes.append(f"Sitemap terbaca: {len(items)} alamat butir bertanggal dari {len(entries)}.")
    return reading
