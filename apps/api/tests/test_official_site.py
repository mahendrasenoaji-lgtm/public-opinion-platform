# ruff: noqa: E501
"""Konektor situs resmi: fungsi murni + alur baca dengan transport tiruan."""

from datetime import UTC, datetime

import httpx
import pytest

from app.connectors import official_site as osite
from app.connectors.base import ConnectorError
from app.connectors.rss import FeedMalformed

BASE = "https://lembaga.go.id"

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Siaran pers satu</title><link>https://lembaga.go.id/siaran-pers/satu</link>
<pubDate>Mon, 09 Nov 2026 03:00:00 GMT</pubDate></item>
<item><title>Berita dua</title><link>https://lembaga.go.id/berita/dua</link>
<pubDate>Tue, 10 Nov 2026 03:00:00 GMT</pubDate></item></channel></rss>"""

SITEMAP = b"""<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://lembaga.go.id/</loc><lastmod>2026-11-01</lastmod></url>
<url><loc>https://lembaga.go.id/berita/a</loc><lastmod>2026-11-02T03:00:00Z</lastmod></url>
<url><loc>https://www.lembaga.go.id/berita/b</loc><lastmod>2026-11-03</lastmod></url>
<url><loc>https://lembaga.go.id/berita/tanpa-tanggal</loc></url>
<url><loc>https://lembaga.go.id/storage/berkas.pdf</loc><lastmod>2026-11-03</lastmod></url>
<url><loc>https://lembaga.go.id/berita/x?page=2</loc><lastmod>2026-11-03</lastmod></url>
<url><loc>https://lain.example.com/berita/c</loc><lastmod>2026-11-03</lastmod></url>
</urlset>"""


class TestNormalize:
    def test_bentuk_yang_diterima(self) -> None:
        assert osite.normalize_base("lembaga.go.id") == BASE
        assert osite.normalize_base(" https://WWW.Lembaga.go.id/berita?x=1 ") == (
            "https://www.lembaga.go.id"
        )

    @pytest.mark.parametrize(
        "raw",
        ["", "ftp://lembaga.go.id", "http://127.0.0.1", "localhost", "https://x.go.id:8080",
         "https://user:pw@x.go.id", "https://ada spasi.go.id"],
    )
    def test_ditolak(self, raw: str) -> None:
        with pytest.raises(ConnectorError):
            osite.normalize_base(raw)

    def test_same_site_mengabaikan_www(self) -> None:
        assert osite.same_site("https://www.lembaga.go.id/a", BASE)
        assert not osite.same_site("https://lembaga.go.id.jahat.com/a", BASE)


class TestRobots:
    def test_sitemap_dan_tidak_dilarang(self) -> None:
        text = "User-agent: *\nAllow: /\nDisallow: /admin/\nSitemap: https://lembaga.go.id/s.xml\n"
        assert osite.parse_robots(text) == (False, ["https://lembaga.go.id/s.xml"])

    def test_larangan_total_untuk_semua(self) -> None:
        assert osite.parse_robots("User-agent: *\nDisallow: /\n")[0] is True

    def test_larangan_untuk_bot_lain_tidak_berlaku(self) -> None:
        text = "User-agent: BotLain\nDisallow: /\n\nUser-agent: *\nDisallow: /admin/\n"
        assert osite.parse_robots(text)[0] is False


class TestFeedLinks:
    def test_menemukan_dan_melengkapi_alamat(self) -> None:
        html = (
            '<link rel="stylesheet" href="/a.css">'
            '<link rel="alternate" type="application/rss+xml" href="/feed/">'
            "<link href='/atom.xml' type='application/atom+xml' rel='alternate'>"
        )
        assert osite.find_feed_links(html, BASE) == [
            "https://lembaga.go.id/feed/",
            "https://lembaga.go.id/atom.xml",
        ]

    def test_tanpa_feed(self) -> None:
        assert osite.find_feed_links("<html><head></head></html>", BASE) == []


class TestSitemap:
    def test_urlset_dan_saringan_butir(self) -> None:
        kind, entries = osite.parse_sitemap(SITEMAP)
        assert kind == "urlset" and len(entries) == 7
        items = osite.article_entries(entries, BASE)
        assert [i.url for i in items] == [
            "https://lembaga.go.id/berita/a",
            "https://www.lembaga.go.id/berita/b",
        ]
        assert items[0].published_at == datetime(2026, 11, 2, 3, tzinfo=UTC)
        assert items[1].published_at.tzinfo is not None

    def test_indeks(self) -> None:
        payload = (
            b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            b"<sitemap><loc>https://lembaga.go.id/s-0.xml</loc></sitemap></sitemapindex>"
        )
        assert osite.parse_sitemap(payload) == ("index", [("https://lembaga.go.id/s-0.xml", None)])

    def test_html_ditolak(self) -> None:
        with pytest.raises(FeedMalformed):
            osite.parse_sitemap(b"<!DOCTYPE html><html><body>beranda</body></html>")
        with pytest.raises(FeedMalformed):
            osite.parse_sitemap(b"<rss></rss>")


def _client(routes: dict[str, tuple[int, str, bytes]]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        status, ctype, body = routes.get(request.url.path, (404, "text/plain", b""))
        return httpx.Response(status, headers={"content-type": ctype}, content=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestReadSite:
    @pytest.mark.asyncio
    async def test_feed_didahulukan(self) -> None:
        routes = {
            "/robots.txt": (200, "text/plain", b"User-agent: *\nAllow: /\n"),
            "/": (200, "text/html", b"<html></html>"),
            "/rss": (200, "application/rss+xml", RSS),
            "/sitemap.xml": (200, "application/xml", SITEMAP),
        }
        async with _client(routes) as client:
            got = await osite.read_site("lembaga.go.id", client=client)
        assert got.kind == "rss" and got.source_url == "https://lembaga.go.id/rss"
        assert [i.title for i in got.items] == ["Siaran pers satu", "Berita dua"]

    @pytest.mark.asyncio
    async def test_sitemap_bila_tanpa_feed(self) -> None:
        routes = {
            "/robots.txt": (200, "text/plain", b"Sitemap: https://lembaga.go.id/peta.xml\n"),
            "/": (200, "text/html", b"<html></html>"),
            "/peta.xml": (200, "application/xml", SITEMAP),
        }
        async with _client(routes) as client:
            got = await osite.read_site(BASE, client=client)
        assert got.kind == "sitemap" and got.source_url == "https://lembaga.go.id/peta.xml"
        assert len(got.items) == 2 and got.items[0].title is None

    @pytest.mark.asyncio
    async def test_situs_yang_membalas_beranda_untuk_semua_alamat(self) -> None:
        html = (200, "text/html", b"<!DOCTYPE html><html><body>beranda</body></html>")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(html[0], headers={"content-type": html[1]}, content=html[2])

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            got = await osite.read_site(BASE, client=client)
        assert got.kind == "none" and got.items == []
        assert any("sitemap" in n.lower() for n in got.notes)

    @pytest.mark.asyncio
    async def test_sitemap_hanya_halaman_tetap(self) -> None:
        static = (
            b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            b"<url><loc>https://lembaga.go.id/news</loc><lastmod>2026-08-26</lastmod></url>"
            b"</urlset>"
        )
        async with _client({"/sitemap.xml": (200, "application/xml", static)}) as client:
            got = await osite.read_site(BASE, client=client)
        assert got.kind == "none" and "halaman tetap" in got.notes[-1]

    @pytest.mark.asyncio
    async def test_robots_melarang_berhenti(self) -> None:
        routes = {
            "/robots.txt": (200, "text/plain", b"User-agent: *\nDisallow: /\n"),
            "/rss": (200, "application/rss+xml", RSS),
        }
        async with _client(routes) as client:
            got = await osite.read_site(BASE, client=client)
        assert got.kind == "none" and got.n_requests == 2


def test_host_jaringan_dalam_ditolak(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        osite.socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("10.0.0.5", 0))]
    )
    with pytest.raises(ConnectorError, match="jaringan dalam"):
        osite._assert_public("intranet.go.id")


# ------------------------------------------------- halaman daftar berita ----

LISTING = """<html><head><script>var d="1 Januari 2020";</script></head><body>
<nav><a href="/profil/visi-misi">Visi dan misi lembaga kami</a></nav>
<div class="card"><a href="/siaran-pers/menteri-resmikan-program-pangan-baru">
  <img src="data:image/png;base64,AAAA"></a>
  <span>14 Nov 2026</span>
  <h3><a href="/siaran-pers/menteri-resmikan-program-pangan-baru">Menteri Resmikan Program Pangan Baru</a></h3></div>
<a class="kartu" href="news/news-detail/bantuan-benih-disalurkan-AbC1.html">
  <span>Senin, 9 November 2026</span><span>Siaran Pers</span>
  <b>Bantuan Benih Disalurkan ke Tiga Provinsi</b></a>
<div><h5><a href="https://lembaga.go.id/news/view/8307">Produksi Gula Tertinggi dalam Sedekade</a></h5>
  <small>2026-11-11</small></div>
<a href="https://lain.example.com/berita/artikel-di-situs-lain-yang-panjang">Artikel di situs lain 10 November 2026</a>
<a href="/berita/tautan-tanpa-judul-yang-cukup-panjang">Baca</a> 8 November 2026
</body></html>"""


class TestListing:
    def test_tautan_butir_dipasangkan_dengan_tanggal_terdekat(self) -> None:
        items = {i.url: i for i in osite.parse_listing(LISTING, "https://lembaga.go.id/berita")}
        assert set(items) == {
            "https://lembaga.go.id/siaran-pers/menteri-resmikan-program-pangan-baru",
            "https://lembaga.go.id/news/news-detail/bantuan-benih-disalurkan-AbC1.html",
            "https://lembaga.go.id/news/view/8307",
        }
        a = items["https://lembaga.go.id/siaran-pers/menteri-resmikan-program-pangan-baru"]
        assert a.title == "Menteri Resmikan Program Pangan Baru"
        assert a.published_at == datetime(2026, 11, 14, 5, tzinfo=UTC)
        b = items["https://lembaga.go.id/news/news-detail/bantuan-benih-disalurkan-AbC1.html"]
        # Tanggal dan label di awal kartu dibuang dari judul.
        assert b.title == "Bantuan Benih Disalurkan ke Tiga Provinsi"
        assert b.published_at.date().isoformat() == "2026-11-09"
        assert items["https://lembaga.go.id/news/view/8307"].published_at.day == 11

    def test_tanpa_tanggal_tidak_menebak(self) -> None:
        html = '<a href="/berita/judul-berita-yang-cukup-panjang-sekali">Judul berita yang panjang</a>'
        assert osite.parse_listing(html, "https://lembaga.go.id/berita") == []

    def test_tanggal_terlalu_jauh_dibuang(self) -> None:
        html = (
            '<a href="/berita/judul-berita-yang-cukup-panjang-sekali">Judul berita yang panjang</a>'
            + "x" * 2000
            + "14 November 2026"
        )
        assert osite.parse_listing(html, "https://lembaga.go.id/berita") == []

    def test_tanggal_mustahil_diabaikan(self) -> None:
        html = '<a href="/berita/judul-berita-yang-cukup-panjang-sekali">Judul berita panjang</a> 31 Feb 2026'
        assert osite.parse_listing(html, "https://lembaga.go.id/berita") == []


class TestRobotsAllows:
    text = "User-agent: *\nDisallow: /admin/\nDisallow: /news/draf/\nAllow: /news/\n"

    def test_awalan_terpanjang_menang(self) -> None:
        assert osite.robots_allows(self.text, "/news/main/berita") is True
        assert osite.robots_allows(self.text, "/news/draf/x") is False
        assert osite.robots_allows(self.text, "/admin/") is False
        assert osite.robots_allows("", "/apa-saja") is True

    def test_larangan_total(self) -> None:
        assert osite.robots_allows("User-agent: *\nDisallow: /\n", "/berita") is False
        assert osite.robots_allows("User-agent: BotLain\nDisallow: /\n", "/berita") is True


class TestListUrls:
    def test_relatif_dilengkapi_dan_ganda_dibuang(self) -> None:
        assert osite.normalize_list_urls(["/berita", "berita", " ", BASE + "/pers"], BASE) == [
            BASE + "/berita",
            BASE + "/pers",
        ]

    def test_situs_lain_dan_terlalu_banyak_ditolak(self) -> None:
        with pytest.raises(ConnectorError, match="harus berada di"):
            osite.normalize_list_urls(["https://jahat.example.com/berita"], BASE)
        with pytest.raises(ConnectorError, match="Paling banyak"):
            osite.normalize_list_urls([f"/hal-{i}" for i in range(6)], BASE)


class TestReadListing:
    @pytest.mark.asyncio
    async def test_dibaca_bila_tanpa_feed_dan_sitemap(self) -> None:
        routes = {
            "/robots.txt": (200, "text/plain", b"User-agent: *\nDisallow: /admin/\n"),
            "/": (200, "text/html", b"<html></html>"),
            "/berita": (200, "text/html; charset=utf-8", LISTING.encode()),
        }
        async with _client(routes) as client:
            got = await osite.read_site(BASE, client=client, list_urls=[BASE + "/berita"])
        assert got.kind == "halaman" and len(got.items) == 3
        assert got.source_url == BASE + "/berita"

    @pytest.mark.asyncio
    async def test_robots_melarang_halaman_itu(self) -> None:
        routes = {
            "/robots.txt": (200, "text/plain", b"User-agent: *\nDisallow: /berita\n"),
            "/berita": (200, "text/html", LISTING.encode()),
        }
        async with _client(routes) as client:
            got = await osite.read_site(BASE, client=client, list_urls=[BASE + "/berita"])
        assert got.kind == "none" and any("melarang" in n for n in got.notes)

    @pytest.mark.asyncio
    async def test_feed_tetap_didahulukan(self) -> None:
        routes = {
            "/rss": (200, "application/rss+xml", RSS),
            "/berita": (200, "text/html", LISTING.encode()),
        }
        async with _client(routes) as client:
            got = await osite.read_site(BASE, client=client, list_urls=[BASE + "/berita"])
        assert got.kind == "rss"

    @pytest.mark.asyncio
    async def test_sitemap_bercap_mesin_dilewati_ke_halaman(self) -> None:
        stamped = b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + b"".join(
            b"<url><loc>https://lembaga.go.id/blog/butir-%d</loc>"
            b"<lastmod>2025-08-15T06:59:23Z</lastmod></url>" % i
            for i in range(10)
        ) + b"</urlset>"
        routes = {
            "/sitemap.xml": (200, "application/xml", stamped),
            "/berita": (200, "text/html", LISTING.encode()),
        }
        async with _client(routes) as client:
            got = await osite.read_site(BASE, client=client, list_urls=[BASE + "/berita"])
        assert got.kind == "halaman" and any("cap waktu pembuatan" in n for n in got.notes)
