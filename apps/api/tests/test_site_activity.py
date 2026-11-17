from datetime import UTC, date, datetime, timedelta

from app.services import site_activity as sa

TODAY = date(2026, 11, 15)


class TestKategori:
    def test_dari_alamat(self) -> None:
        assert sa.guess_category("https://x.go.id/siaran-pers/abc") == "siaran_pers"
        assert sa.guess_category("https://x.go.id/pers/123") == "siaran_pers"
        assert sa.guess_category("https://x.go.id/news/main/pengumuman/1") == "pengumuman"
        assert sa.guess_category("https://x.go.id/blog/post/judul") == "berita"
        assert sa.guess_category("https://x.go.id/peraturan/pp-1") == "regulasi"

    def test_tanpa_petunjuk_lainnya(self) -> None:
        assert sa.guess_category("https://x.go.id/halaman/abc") == "lainnya"
        # Kata di query atau host tidak dihitung, hanya path.
        assert sa.guess_category("https://berita.go.id/x?berita=1") == "lainnya"


class TestCapMesin:
    def test_semua_sama_hari(self) -> None:
        same = [datetime(2025, 8, 15, 6, 59, tzinfo=UTC)] * 30
        assert sa.dates_look_generated(same) is True

    def test_tersebar(self) -> None:
        spread = [datetime(2026, 10, 1 + i, tzinfo=UTC) for i in range(20)]
        assert sa.dates_look_generated(spread) is False

    def test_terlalu_sedikit_tidak_dituduh(self) -> None:
        assert sa.dates_look_generated([datetime(2026, 1, 1, tzinfo=UTC)] * 2) is False


class TestRingkas:
    def test_kosong(self) -> None:
        a = sa.summarize([], today=TODAY)
        assert (a.n_total, a.n_window, a.last_published, a.days_since_last) == (0, 0, None, None)
        assert a.quiet is True and a.longest_gap_days is None and a.median_gap_days is None
        assert sa.status_label(a) == "belum ada terbitan tercatat"
        assert all(w.n == 0 for w in a.weeks) and a.weeks_without == len(a.weeks)

    def test_harian(self) -> None:
        items = [(TODAY - timedelta(days=i), "berita") for i in range(40)]
        a = sa.summarize(items, today=TODAY)
        assert a.n_30 == 30 and a.n_window == 40 and a.days_since_last == 0
        assert a.median_gap_days == 1.0 and a.quiet is False
        assert sa.status_label(a) == "hampir tiap hari"
        assert sum(w.n for w in a.weeks) == 40

    def test_sepi_sebulan(self) -> None:
        items = [(TODAY - timedelta(days=d), "siaran_pers") for d in (35, 40, 50)]
        a = sa.summarize(items, today=TODAY)
        assert a.quiet is True and a.days_since_last == 35 and a.n_30 == 0
        # Jeda terpanjang ikut menghitung dari terbitan terakhir sampai hari ini.
        assert a.longest_gap_days == 35
        assert a.median_gap_days is None  # kurang dari 5 butir
        assert sa.status_label(a) == "sepi: 35 hari tanpa terbitan tercatat"

    def test_batas_tepat_30_hari(self) -> None:
        assert sa.summarize([(TODAY - timedelta(days=29), "berita")], today=TODAY).quiet is False
        assert sa.summarize([(TODAY - timedelta(days=30), "berita")], today=TODAY).quiet is True

    def test_di_luar_jendela_dan_masa_depan(self) -> None:
        items = [
            (TODAY - timedelta(days=200), "berita"),
            (TODAY + timedelta(days=3), "berita"),
            (TODAY - timedelta(days=2), "berita"),
        ]
        a = sa.summarize(items, today=TODAY)
        assert a.n_total == 2 and a.n_window == 1 and a.days_since_last == 2

    def test_jeda_terpanjang_di_tengah(self) -> None:
        items = [(TODAY - timedelta(days=d), "berita") for d in (60, 59, 20, 1)]
        a = sa.summarize(items, today=TODAY)
        assert a.longest_gap_days == 39 and a.active_days == 4

    def test_kategori_dan_yang_tak_dikenal(self) -> None:
        items = [
            (TODAY, "siaran_pers"),
            (TODAY, "siaran_pers"),
            (TODAY, "berita"),
            (TODAY, "kategori-aneh"),
        ]
        a = sa.summarize(items, today=TODAY)
        assert a.categories == (("siaran_pers", 2), ("berita", 1), ("lainnya", 1))

    def test_label_jarang_dan_mingguan(self) -> None:
        weekly = [(TODAY - timedelta(days=7 * i), "berita") for i in range(6)]
        assert sa.status_label(sa.summarize(weekly, today=TODAY)).startswith("beberapa kali")
        rare = [(TODAY - timedelta(days=10), "berita")]
        assert sa.status_label(sa.summarize(rare, today=TODAY)) == "jarang"

    def test_minggu_mulai_senin(self) -> None:
        a = sa.summarize([(TODAY, "berita")], today=TODAY)
        assert all(w.start.weekday() == 0 for w in a.weeks)
        assert a.weeks[-1].n == 1 and a.weeks[-1].start == date(2026, 11, 9)
