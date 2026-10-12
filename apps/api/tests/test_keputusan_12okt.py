"""Tes murni untuk keputusan 12 Oktober 2026: penilai kedua, ragam berita,
penilaian ulang, dan penemuan video YouTube. Tanpa database, tanpa jaringan.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.connectors import get_connector, youtube_search
from app.connectors.base import ConnectorError, CredentialMissing
from app.connectors.youtube_search import (
    DiscoveredVideo,
    is_due,
    parse_config,
    parse_search,
    video_label,
)
from app.services import sentiment
from app.services.rescoring import rescore
from app.services.sentiment_eval_field import FIELD
from app.services.sentiment_eval_rater2 import (
    LABELS,
    RATER2,
    cohen_kappa,
    evaluate_agreement,
)

# ------------------------------------------------------------ penilai kedua


class TestPenilaiKedua:
    def test_satu_label_sah_per_komentar(self) -> None:
        assert len(RATER2) == len(FIELD) == 440
        assert set(RATER2) <= set(LABELS)

    def test_kappa_sempurna_dan_kebetulan(self) -> None:
        a = ["positif", "negatif", "netral", "negatif"]
        assert cohen_kappa(a, a) == pytest.approx(1.0)
        # Sepakat persis sebanyak yang diharapkan dari kebetulan -> 0.
        x = ["positif", "positif", "negatif", "negatif"]
        y = ["positif", "negatif", "positif", "negatif"]
        assert cohen_kappa(x, y) == pytest.approx(0.0)

    def test_kappa_lebih_rendah_dari_kesepakatan_mentah(self) -> None:
        """Itulah gunanya: 3 dari 4 sama, tapi sebagian karena sebaran yang timpang."""
        x = ["negatif", "negatif", "negatif", "positif"]
        y = ["negatif", "negatif", "negatif", "negatif"]
        assert cohen_kappa(x, y) < 0.75

    def test_kappa_menolak_panjang_berbeda_dan_kosong(self) -> None:
        with pytest.raises(ValueError):
            cohen_kappa(["positif"], [])
        with pytest.raises(ValueError):
            cohen_kappa([], [])

    def test_laporan_konsisten_dengan_labelnya(self) -> None:
        r = evaluate_agreement()
        assert r.n == 440
        assert sum(sum(row.values()) for row in r.confusion.values()) == 440
        diagonal = sum(r.confusion[label][label] for label in LABELS)
        assert r.observed_agreement == pytest.approx(diagonal / 440, abs=1e-3)
        assert r.kappa < r.observed_agreement
        assert sum(r.rater2_distribution.values()) == 440
        # Komentar uji yang disepakati tidak mungkin lebih banyak dari belahan uji.
        assert 0 < r.agreed_test_n <= sum(1 for i in FIELD if i.split == "uji")
        assert "AI" in r.caveat

    def test_angka_yang_dilaporkan_di_dokumen(self) -> None:
        """Dikunci supaya mengubah satu label tidak diam-diam mengubah angka terbitan."""
        r = evaluate_agreement()
        assert (r.observed_agreement, r.kappa) == (0.925, 0.823)


# -------------------------------------------------------------- ragam berita


class TestRagamBerita:
    def test_dukungan_korporat_tidak_lagi_terbaca_positif(self) -> None:
        text = "Pertamina dukung Grand Prix Mandalika"
        assert sentiment.score(text).label == "positif"
        assert sentiment.score(text, register="berita").abstained

    def test_apresiasi_di_nama_program_tidak_dinilai(self) -> None:
        assert sentiment.score("Program Apresiasi Guru dibuka", register="berita").abstained

    def test_kata_lain_tidak_berubah(self) -> None:
        for text in (
            "Program ini gagal dan mengecewakan warga",
            "Pelayanan membaik dan warga puas",
            "Warga menolak kenaikan tarif",
        ):
            assert (
                sentiment.score(text, register="berita").score == sentiment.score(text).score
            )

    def test_tidak_pernah_menilai_yang_baku_tidak_nilai(self) -> None:
        assert set(sentiment.NEWS_LEXICON) < set(sentiment.LEXICON)

    def test_leksikon_baku_tidak_tersentuh(self) -> None:
        """Deret MEDIA yang sedang berjalan memakai ini; ia tidak boleh bergeser."""
        for word in sentiment.NEWS_NEUTRALIZED:
            assert word in sentiment.LEXICON

    def test_versi_per_ragam(self) -> None:
        assert sentiment.model_version_for("baku") == sentiment.MODEL_VERSION
        assert sentiment.model_version_for("informal") == sentiment.INFORMAL_MODEL_VERSION
        assert sentiment.model_version_for("berita") == sentiment.NEWS_MODEL_VERSION
        assert sentiment.NEWS_MODEL_VERSION in sentiment.method_for("berita")
        assert len({sentiment.model_version_for(r) for r in ("baku", "informal", "berita")}) == 3


# ----------------------------------------------------------- penilaian ulang

OLD = sentiment.MODEL_VERSION
INFORMAL = sentiment.INFORMAL_MODEL_VERSION
NEWS = sentiment.NEWS_MODEL_VERSION


class TestPenilaianUlang:
    def test_liputan_skor_utama_tidak_pernah_berubah(self) -> None:
        text = "Pertamina mendukung ajang balap nasional"
        old = sentiment.score(text).score
        r = rescore(
            social=False,
            text=text,
            sentiment=old,
            sentiment_model=None,
            sentiment_alt=None,
            sentiment_alt_model=None,
        )
        assert r.sentiment == old and r.primary_changed is False
        assert r.sentiment_model == OLD
        assert r.sentiment_alt is None  # ragam berita abstain pada teks ini
        assert r.sentiment_alt_model == NEWS

    def test_liputan_dengan_skor_yang_tidak_bisa_direproduksi_tetap_utuh(self) -> None:
        """Skor tersimpan tidak dihitung ulang — bahkan bila leksikon sudah berubah sejak itu."""
        r = rescore(
            social=False,
            text="Program ini gagal",
            sentiment=0.123,
            sentiment_model=OLD,
            sentiment_alt=None,
            sentiment_alt_model=None,
        )
        assert r.sentiment == 0.123
        assert r.sentiment_alt == sentiment.score("Program ini gagal", register="berita").score

    def test_komentar_lama_dinilai_ulang_dan_skor_lamanya_diarsipkan(self) -> None:
        text = "gk becus bgt programnya"
        new = sentiment.score(text, register="informal").score
        assert new is not None
        r = rescore(
            social=True,
            text=text,
            sentiment=None,  # leksikon baku dulu abstain
            sentiment_model=None,
            sentiment_alt=None,
            sentiment_alt_model=None,
        )
        assert r.primary_changed is True
        assert (r.sentiment, r.sentiment_model) == (new, INFORMAL)
        assert (r.sentiment_alt, r.sentiment_alt_model) == (None, OLD)

    def test_komentar_yang_skornya_sudah_sama_hanya_diberi_versi(self) -> None:
        text = "gk becus bgt programnya"
        new = sentiment.score(text, register="informal").score
        r = rescore(
            social=True,
            text=text,
            sentiment=new,
            sentiment_model=None,
            sentiment_alt=None,
            sentiment_alt_model=None,
        )
        assert r.primary_changed is False
        assert (r.sentiment, r.sentiment_model, r.sentiment_alt_model) == (new, INFORMAL, None)

    def test_idempoten(self) -> None:
        text = "program ini parah"
        first = rescore(
            social=True,
            text=text,
            sentiment=0.5,
            sentiment_model=None,
            sentiment_alt=None,
            sentiment_alt_model=None,
        )
        second = rescore(
            social=True,
            text=text,
            sentiment=first.sentiment,
            sentiment_model=first.sentiment_model,
            sentiment_alt=first.sentiment_alt,
            sentiment_alt_model=first.sentiment_alt_model,
        )
        assert second.primary_changed is False
        assert (second.sentiment, second.sentiment_alt) == (first.sentiment, first.sentiment_alt)

    def test_arsip_tidak_ditimpa_pada_penilaian_ulang_berikutnya(self) -> None:
        r = rescore(
            social=True,
            text="program ini parah",
            sentiment=0.9,
            sentiment_model="versi-antara",
            sentiment_alt=0.1,
            sentiment_alt_model=OLD,
        )
        assert r.primary_changed is True
        assert (r.sentiment_alt, r.sentiment_alt_model) == (0.1, OLD)


# ------------------------------------------------------ penemuan video YouTube


class TestPenemuanVideo:
    NOW: datetime = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)

    def test_nilai_bawaan(self) -> None:
        cfg = parse_config({"query": "makan bergizi gratis"})
        assert (cfg.max_videos, cfg.interval_hours, cfg.published_within_days) == (5, 24, 14)

    def test_batas_konfigurasi(self) -> None:
        for bad in (
            {"query": ""},
            {"query": "x" * 121},
            {"query": "mbg", "max_videos": "26"},
            {"query": "mbg", "max_videos": "nol"},
            {"query": "mbg", "interval_hours": "1"},
            {"query": "mbg", "published_within_days": "91"},
        ):
            with pytest.raises(ConnectorError):
                parse_config(bad)

    def test_validasi_saat_didaftarkan(self) -> None:
        connector = get_connector(youtube_search.KEY)
        with pytest.raises(ConnectorError, match="interval_hours"):
            connector.validate_config({"query": "mbg", "interval_hours": "2"})
        connector.validate_config({"query": "mbg", "max_videos": "10"})

    def test_belum_waktunya_tidak_mencari(self) -> None:
        cfg = parse_config({"query": "mbg"})
        assert is_due(cfg, last_run=None, now=self.NOW) is True
        assert is_due(cfg, last_run=self.NOW - timedelta(hours=23), now=self.NOW) is False
        assert is_due(cfg, last_run=self.NOW - timedelta(hours=24), now=self.NOW) is True

    def test_jadwal_30_menit_tidak_menghabiskan_kuota(self) -> None:
        """48 run sehari, satu pencarian: itulah yang menjaga 10.000 unit per hari."""
        cfg = parse_config({"query": "mbg"})
        last: datetime | None = None
        searches = 0
        for tick in range(48):
            now = self.NOW + timedelta(minutes=30 * tick)
            if is_due(cfg, last_run=last, now=now):
                searches += 1
                last = now
        assert searches == 1
        assert searches * youtube_search.SEARCH_QUOTA_UNITS == 100

    def test_hasil_pencarian_terbaca(self) -> None:
        payload = {
            "items": [
                {
                    "id": {"kind": "youtube#video", "videoId": "abc123"},
                    "snippet": {
                        "title": "Keracunan MBG di sekolah",
                        "channelTitle": "Kanal Berita",
                        "publishedAt": "2026-10-11T03:00:00Z",
                    },
                },
                {"id": {"kind": "youtube#channel", "channelId": "UC1"}, "snippet": {}},
                {"id": {"videoId": "abc123"}, "snippet": {"title": "ganda"}},
                {"id": {"videoId": "def456"}, "snippet": {"publishedAt": "bukan-tanggal"}},
            ]
        }
        videos = parse_search(payload)
        assert [v.video_id for v in videos] == ["abc123", "def456"]
        assert videos[0].published_at == datetime(2026, 10, 11, 3, 0, tzinfo=UTC)
        assert videos[1].published_at is None and videos[1].title == ""

    def test_payload_kosong(self) -> None:
        assert parse_search({}) == []

    def test_label_sumber_dari_judul_dan_kanal(self) -> None:
        video = DiscoveredVideo("abc", "Judul", "Kanal", None)
        assert video_label(video) == "Judul — Kanal"
        assert video_label(DiscoveredVideo("abc", "", "", None)) == "abc"
        assert len(video_label(DiscoveredVideo("abc", "j" * 300, "Kanal", None))) == 140

    async def test_tanpa_kunci_menyebut_env_var(self) -> None:
        connector = get_connector(youtube_search.KEY)
        assert isinstance(connector, youtube_search.YouTubeSearchConnector)
        with pytest.raises(CredentialMissing, match="YOUTUBE_API_KEY"):
            await connector.discover({"query": "mbg"})

    async def test_fetch_tidak_mengambil_konten(self) -> None:
        assert await get_connector(youtube_search.KEY).fetch({"query": "mbg"}) == []
