"""Tes konektor — hanya bagian yang murni (parsing + registry).

Pengambilan lewat jaringan sengaja TIDAK dites di sini: tes yang memanggil API
sungguhan akan merah karena kuota habis, token kedaluwarsa, atau feed penerbit
sedang berubah — kegagalan yang tidak mengatakan apa pun tentang kode ini.
Yang bisa salah di kode kita adalah parsing dan penanganan kredensial kosong,
dan itu yang diuji.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.connectors import available, get_connector
from app.connectors.base import (
    Connector,
    ConnectorError,
    CredentialMissing,
    RawItem,
    register,
    require,
)
from app.connectors.rss import (
    MAX_KEYWORDS,
    RSSConnector,
    compile_keywords,
    filter_items,
    parse_feed,
)
from app.connectors.x import parse_search
from app.connectors.youtube import parse_comment_threads
from app.models.measurement import SignalSource

RSS_SAMPLE = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Contoh Media</title>
  <item>
    <title>Pemerintah umumkan program bantuan</title>
    <description>&lt;p&gt;Ringkasan &amp;amp; isi singkat.&lt;/p&gt;</description>
    <link>https://contoh.id/a</link>
    <guid>https://contoh.id/a</guid>
    <pubDate>Tue, 26 Aug 2026 08:00:00 +0700</pubDate>
  </item>
  <item>
    <title>Tanpa tanggal</title>
    <description>Isi</description>
    <guid>https://contoh.id/b</guid>
  </item>
</channel></rss>"""

ATOM_SAMPLE = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Judul Atom</title>
    <summary>Ringkasan atom</summary>
    <id>tag:contoh.id,2026:1</id>
    <link href="https://contoh.id/atom-1"/>
    <published>2026-08-26T01:00:00Z</published>
    <author><name>Redaksi</name></author>
  </entry>
</feed>"""


class TestRSSParsing:
    def test_item_rss_terbaca(self) -> None:
        items = parse_feed(RSS_SAMPLE)
        assert len(items) == 1  # yang tanpa tanggal dibuang
        item = items[0]
        assert item.external_id == "https://contoh.id/a"
        assert "Pemerintah umumkan program bantuan" in item.text
        assert item.published_at.tzinfo is not None

    def test_html_dan_entity_dibersihkan(self) -> None:
        text = parse_feed(RSS_SAMPLE)[0].text
        assert "<p>" not in text
        assert "&amp;" not in text
        assert "&" in text  # entity ter-unescape jadi karakter aslinya

    def test_item_tanpa_tanggal_dibuang_bukan_diberi_now(self) -> None:
        ids = [i.external_id for i in parse_feed(RSS_SAMPLE)]
        assert "https://contoh.id/b" not in ids

    def test_atom_terbaca(self) -> None:
        items = parse_feed(ATOM_SAMPLE)
        assert len(items) == 1
        # Permalink menang atas <id> — lihat TestIdentitasItem.
        assert items[0].external_id == "https://contoh.id/atom-1"
        assert items[0].url == "https://contoh.id/atom-1"
        assert items[0].author_handle == "Redaksi"

    def test_xml_rusak_ditolak_dengan_pesan_jelas(self) -> None:
        with pytest.raises(ConnectorError, match="bukan XML"):
            parse_feed(b"<rss><channel>")

    def test_halaman_html_disebut_apa_adanya(self) -> None:
        with pytest.raises(ConnectorError, match="halaman HTML, bukan feed"):
            parse_feed(b"\n  <!DOCTYPE html><html><head><script>x</script></head></html>")

    def test_feed_kosong_bukan_error(self) -> None:
        assert parse_feed(b'<rss version="2.0"><channel/></rss>') == []


class TestIdentitasItem:
    """external_id = permalink kalau ada. Lihat `_identity` di connectors/rss.py."""

    LIPUTAN6_STYLE = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Mendagri minta pemda hati-hati</title>
    <link>https://www.liputan6.com/news/read/8292436/mendagri-minta</link>
    <guid isPermaLink="false">8292436</guid>
    <pubDate>Tue, 15 Sep 2026 20:09:14 +0700</pubDate>
  </item>
</channel></rss>"""

    TANPA_LINK = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Hanya guid</title>
    <guid>arsip-77</guid>
    <pubDate>Tue, 15 Sep 2026 20:09:14 +0700</pubDate>
  </item>
</channel></rss>"""

    def test_guid_angka_kalah_dari_permalink(self) -> None:
        # Liputan6 menulis guid berupa angka. Menyimpannya membuat item tidak
        # bisa ditelusuri DAN menggandakan item yang dulu masuk lewat skrip
        # ingest (yang memakai permalink).
        item = parse_feed(self.LIPUTAN6_STYLE)[0]
        assert item.external_id == "https://www.liputan6.com/news/read/8292436/mendagri-minta"

    def test_tanpa_link_guid_tetap_dipakai(self) -> None:
        assert parse_feed(self.TANPA_LINK)[0].external_id == "arsip-77"


def _raw(text: str, *, hours_ago: float = 1.0) -> RawItem:
    return RawItem(
        external_id=f"https://contoh.id/{abs(hash(text))}",
        text=text,
        published_at=datetime.now(UTC) - timedelta(hours=hours_ago),
    )


class TestKataKunci:
    MBG = "makan bergizi gratis, mbg, badan gizi nasional, bgn"

    def test_kata_utuh_bukan_potongan_kata(self) -> None:
        p = compile_keywords("mbg")
        assert p.search("Anggaran MBG naik")
        assert p.search("program (MBG), kata menteri")
        assert not p.search("harga kambing naik")
        assert not p.search("mbgx bukan kata itu")

    def test_frasa_spasi_apa_pun_dan_huruf_besar_kecil(self) -> None:
        p = compile_keywords("makan bergizi gratis")
        assert p.search("Program Makan  Bergizi\nGratis dimulai")
        assert not p.search("makan bergizi saja")

    def test_metakarakter_regex_tidak_hidup(self) -> None:
        # "." dan "(" dari pengguna harus berarti karakter itu sendiri.
        p = compile_keywords("b.g.n, (mbg")
        assert p.search("singkatan b.g.n tertulis begitu")
        assert not p.search("singkatan bxgxn")

    def test_setara_dengan_pola_skrip_riset_mbg(self) -> None:
        """Penyaring baru harus memilih artikel yang SAMA dengan skrip lama.

        Skrip ingest_mbg.py (routine cloud, 2026-09-11) memakai regex
        `makan bergizi gratis|\\bmbg\\b|badan gizi nasional|\\bbgn\\b`. Kalau
        penyaring ini lebih longgar atau lebih ketat, data sebelum dan
        sesudah perpindahan jalur tidak sebanding.
        """
        import re

        lama = re.compile(r"makan bergizi gratis|\bmbg\b|badan gizi nasional|\bbgn\b", re.I)
        baru = compile_keywords(self.MBG)
        kalimat = [
            "Keracunan MBG di sekolah dasar",
            "Badan Gizi Nasional (BGN) bantah hoaks",
            "Program Makan Bergizi Gratis dievaluasi",
            "Harga kambing dan sapi naik jelang Iduladha",
            "Kejagung periksa pejabat bgn",
            "gizi buruk di daerah terpencil",
            "mbg: anggaran 2027 dibahas DPR",
        ]
        assert [bool(baru.search(k)) for k in kalimat] == [bool(lama.search(k)) for k in kalimat]

    def test_daftar_kosong_ditolak(self) -> None:
        with pytest.raises(ConnectorError, match="tidak berisi frasa"):
            compile_keywords(" , ,")

    def test_terlalu_banyak_frasa_ditolak(self) -> None:
        with pytest.raises(ConnectorError, match="maksimal"):
            compile_keywords(",".join(f"kata{i}" for i in range(MAX_KEYWORDS + 1)))

    def test_saring_tanggal_lalu_kata_kunci(self) -> None:
        items = [
            _raw("MBG baru", hours_ago=1),
            _raw("MBG lama sekali", hours_ago=100),
            _raw("berita lain", hours_ago=1),
        ]
        kept = filter_items(
            items,
            pattern=compile_keywords("mbg"),
            since=datetime.now(UTC) - timedelta(hours=24),
        )
        assert [i.text for i in kept] == ["MBG baru"]

    def test_tanpa_pola_semua_lolos(self) -> None:
        items = [_raw("apa saja"), _raw("lainnya")]
        assert len(filter_items(items, pattern=None, since=None)) == 2


class TestValidasiKonfigurasiRSS:
    def test_keywords_kosong_ditolak_saat_didaftarkan(self) -> None:
        with pytest.raises(ConnectorError):
            RSSConnector().validate_config({"feed_url": "https://contoh.id/rss", "keywords": ""})

    def test_url_bukan_http_ditolak(self) -> None:
        with pytest.raises(ConnectorError, match="http"):
            RSSConnector().validate_config({"feed_url": "file:///etc/passwd"})

    def test_konfigurasi_sah_diterima(self) -> None:
        RSSConnector().validate_config({"feed_url": "https://contoh.id/rss", "keywords": "mbg"})


class TestYouTubeParsing:
    def _payload(self) -> dict:
        return {
            "items": [
                {
                    "id": "t1",
                    "snippet": {
                        "totalReplyCount": 3,
                        "topLevelComment": {
                            "id": "c1",
                            "snippet": {
                                "textOriginal": "Programnya membantu sekali",
                                "authorDisplayName": "Warga A",
                                "publishedAt": "2026-08-20T10:00:00Z",
                                "likeCount": 7,
                                "videoId": "vid1",
                            },
                        },
                    },
                },
                {"id": "t2", "snippet": {"topLevelComment": {"id": "c2", "snippet": {}}}},
            ]
        }

    def test_komentar_terbaca(self) -> None:
        items = parse_comment_threads(self._payload())
        assert len(items) == 1  # yang tanpa teks/tanggal dilewati
        assert items[0].external_id == "c1"
        assert items[0].author_handle == "Warga A"

    def test_balasan_ikut_dihitung_sebagai_keterlibatan(self) -> None:
        assert parse_comment_threads(self._payload())[0].engagement == 10  # 7 suka + 3 balasan

    def test_payload_kosong(self) -> None:
        assert parse_comment_threads({}) == []


class TestXParsing:
    def _payload(self) -> dict:
        return {
            "data": [
                {
                    "id": "111",
                    "text": "Kebijakan ini memberatkan",
                    "created_at": "2026-08-25T03:00:00Z",
                    "author_id": "u1",
                    "lang": "id",
                    "public_metrics": {
                        "retweet_count": 2,
                        "reply_count": 1,
                        "like_count": 5,
                        "quote_count": 1,
                    },
                },
                {"id": "222", "text": "", "created_at": "2026-08-25T03:00:00Z"},
            ],
            "includes": {"users": [{"id": "u1", "username": "warga_b"}]},
        }

    def test_tweet_terbaca_dengan_handle_dari_includes(self) -> None:
        items = parse_search(self._payload())
        assert len(items) == 1
        assert items[0].author_handle == "warga_b"

    def test_keterlibatan_menjumlahkan_empat_metrik(self) -> None:
        assert parse_search(self._payload())[0].engagement == 9

    def test_tanpa_includes_handle_none_bukan_error(self) -> None:
        payload = self._payload()
        del payload["includes"]
        assert parse_search(payload)[0].author_handle is None

    def test_referenced_tweets_menghasilkan_reply_dan_quote_handle(self) -> None:
        payload = {
            "data": [
                {
                    "id": "333",
                    "text": "Setuju sama pendapat ini",
                    "created_at": "2026-08-25T04:00:00Z",
                    "author_id": "u2",
                    "conversation_id": "111",
                    "referenced_tweets": [{"type": "replied_to", "id": "111"}],
                },
                {
                    "id": "444",
                    "text": "Kutip ini penting",
                    "created_at": "2026-08-25T05:00:00Z",
                    "author_id": "u3",
                    "referenced_tweets": [{"type": "quoted", "id": "111"}],
                },
            ],
            "includes": {
                "users": [
                    {"id": "u1", "username": "warga_b"},
                    {"id": "u2", "username": "warga_c"},
                    {"id": "u3", "username": "warga_d"},
                ],
                # tweet 111 sendiri tidak lolos kueri pencarian, tapi ikut
                # kembali di sini karena expansions referenced_tweets.id.
                "tweets": [{"id": "111", "author_id": "u1"}],
            },
        }
        items = {i.external_id: i for i in parse_search(payload)}
        assert items["333"].reply_to_handle == "warga_b"
        assert items["333"].quote_of_handle is None
        assert items["333"].conversation_id == "111"
        assert items["444"].quote_of_handle == "warga_b"
        assert items["444"].reply_to_handle is None

    def test_retweeted_tidak_diambil_sebagai_reply_atau_quote(self) -> None:
        payload = self._payload()
        payload["data"][0]["referenced_tweets"] = [{"type": "retweeted", "id": "999"}]
        payload["includes"]["tweets"] = [{"id": "999", "author_id": "u1"}]
        items = parse_search(payload)
        assert items[0].reply_to_handle is None
        assert items[0].quote_of_handle is None

    def test_tanpa_includes_tweets_reply_handle_none_bukan_error(self) -> None:
        payload = self._payload()
        payload["data"][0]["referenced_tweets"] = [{"type": "replied_to", "id": "999"}]
        items = parse_search(payload)
        assert items[0].reply_to_handle is None


class TestRegistry:
    def test_konektor_bawaan_terdaftar(self) -> None:
        keys = {i.key for i in available()}
        assert {"rss", "youtube_api", "x_api", "manual"} <= keys

    def test_sumber_dilabeli_benar(self) -> None:
        by_key = {i.key: i for i in available()}
        assert by_key["rss"].source is SignalSource.MEDIA
        assert by_key["youtube_api"].source is SignalSource.SOCIAL

    def test_setiap_konektor_menjelaskan_batasannya(self) -> None:
        """Tidak boleh ada konektor tanpa catatan batasan (semangat R1)."""
        for info in available():
            assert len(info.notes) > 20, f"{info.key} tidak menjelaskan batasannya"

    def test_konektor_asing_ditolak_dengan_daftar_yang_ada(self) -> None:
        with pytest.raises(ConnectorError, match="tidak dikenal"):
            get_connector("tiktok_scrape")

    def test_kunci_ganda_ditolak(self) -> None:
        with pytest.raises(ValueError, match="sudah terdaftar"):

            @register
            class Duplikat(Connector):
                key = "rss"
                label = "x"
                source = SignalSource.MEDIA

                async def fetch(
                    self,
                    config: dict[str, object],
                    *,
                    since: datetime | None = None,
                    limit: int = 100,
                ) -> list:
                    return []


class TestRequire:
    def test_field_lengkap(self) -> None:
        assert require({"feed_url": " https://a.id "}, ("feed_url",)) == {
            "feed_url": "https://a.id"
        }

    def test_field_kurang_disebut_namanya(self) -> None:
        with pytest.raises(ConnectorError, match="feed_url"):
            require({}, ("feed_url",))

    def test_string_kosong_dianggap_kurang(self) -> None:
        with pytest.raises(ConnectorError, match="query"):
            require({"query": "   "}, ("query",))


class TestKredensial:
    async def test_youtube_tanpa_kunci_menyebut_env_var(self) -> None:
        with pytest.raises(CredentialMissing, match="YOUTUBE_API_KEY"):
            await get_connector("youtube_api").fetch({"video_id": "abc"})

    async def test_x_tanpa_token_menyebut_env_var(self) -> None:
        with pytest.raises(CredentialMissing, match="X_BEARER_TOKEN"):
            await get_connector("x_api").fetch({"query": "kebijakan"})

    async def test_manual_mengarahkan_ke_endpoint_ingest(self) -> None:
        with pytest.raises(ConnectorError, match="signals/ingest"):
            await get_connector("manual").fetch({})

    async def test_rss_menolak_url_non_http(self) -> None:
        with pytest.raises(ConnectorError, match="http"):
            await get_connector("rss").fetch({"feed_url": "file:///etc/passwd"})


def test_timezone_selalu_disertakan() -> None:
    """Tanggal naif akan salah membandingkan lintas zona waktu Indonesia."""
    for item in parse_feed(RSS_SAMPLE) + parse_feed(ATOM_SAMPLE):
        assert item.published_at.tzinfo is not None
        assert item.published_at.astimezone(UTC).year == 2026
