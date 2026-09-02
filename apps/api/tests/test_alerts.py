"""Tes deteksi anomali — fungsi murni, tanpa database."""

from __future__ import annotations

from app.services.alerts import MIN_BASELINE_POINTS, AnomalyPoint, build_report, detect


def _series(values: list[float], start_day: int = 1) -> list[tuple[str, float]]:
    return [(f"2026-08-{start_day + i:02d}", v) for i, v in enumerate(values)]


class TestGating:
    def test_baseline_kurang_mengembalikan_none(self) -> None:
        r = detect(_series([60.0, 61.0, 60.0]), key="x", label="X")
        assert r is None

    def test_tepat_di_ambang_diterima(self) -> None:
        nilai = [60.0] * MIN_BASELINE_POINTS + [60.0]
        r = detect(_series(nilai), key="x", label="X")
        assert r is not None
        assert r.n_baseline == MIN_BASELINE_POINTS

    def test_deret_kosong(self) -> None:
        assert detect([], key="x", label="X") is None


class TestDeteksi:
    def test_titik_normal_tidak_notable(self) -> None:
        nilai = [60.0, 61.0, 59.0, 60.5, 60.2]  # titik terakhir dekat baseline
        r = detect(_series(nilai), key="poi", label="POI")
        assert r is not None
        assert r.notable is False
        assert r.direction is None

    def test_lonjakan_naik_terdeteksi(self) -> None:
        nilai = [60.0, 61.0, 59.0, 60.0, 95.0]  # lompatan besar di akhir
        r = detect(_series(nilai), key="poi", label="POI")
        assert r is not None
        assert r.notable is True
        assert r.direction == "naik"
        assert r.z_score is not None and r.z_score > 0

    def test_penurunan_terdeteksi(self) -> None:
        nilai = [60.0, 61.0, 59.0, 60.0, 20.0]
        r = detect(_series(nilai), key="poi", label="POI")
        assert r is not None
        assert r.notable is True
        assert r.direction == "turun"
        assert r.z_score is not None and r.z_score < 0

    def test_baseline_datar_tetap_mendeteksi_perubahan_nyata(self) -> None:
        """sd=0 tidak boleh membuat z-score tak terhitung lolos begitu saja."""
        nilai = [60.0, 60.0, 60.0, 60.0, 68.0]  # naik 13% dari baseline datar
        r = detect(_series(nilai), key="poi", label="POI")
        assert r is not None
        assert r.z_score is None  # tidak berarti secara statistik, dilaporkan apa adanya
        assert r.notable is True
        assert r.baseline_sd is None

    def test_baseline_datar_perubahan_kecil_tidak_notable(self) -> None:
        nilai = [60.0, 60.0, 60.0, 60.0, 60.5]
        r = detect(_series(nilai), key="poi", label="POI")
        assert r is not None
        assert r.notable is False

    def test_metode_selalu_disertakan(self) -> None:
        r = detect(_series([60.0, 61.0, 59.0, 60.0, 60.1]), key="poi", label="POI")
        assert r is not None
        assert "z-score" in r.method

    def test_z_threshold_bisa_diperketat(self) -> None:
        nilai = [60.0, 61.0, 59.0, 60.0, 63.0]  # deviasi sedang
        longgar = detect(_series(nilai), key="poi", label="POI", z_threshold=1.0)
        ketat = detect(_series(nilai), key="poi", label="POI", z_threshold=5.0)
        assert longgar is not None and ketat is not None
        assert longgar.notable is True
        assert ketat.notable is False


class TestBuildReport:
    def test_memisahkan_checked_dan_insufficient(self) -> None:
        hasil = {
            "poi": AnomalyPoint(
                key="poi", label="POI", latest_value=95.0, latest_period="p",
                baseline_mean=60.0, baseline_sd=1.0, z_score=35.0, n_baseline=4,
                direction="naik", notable=True,
            ),
            "trust": None,
        }
        report = build_report(hasil)
        assert report.checked == ["poi"]
        assert report.insufficient == ["trust"]
        assert len(report.alerts) == 1

    def test_tidak_notable_tidak_masuk_alerts(self) -> None:
        hasil = {
            "poi": AnomalyPoint(
                key="poi", label="POI", latest_value=60.0, latest_period="p",
                baseline_mean=60.0, baseline_sd=1.0, z_score=0.0, n_baseline=4,
                notable=False,
            ),
        }
        report = build_report(hasil)
        assert report.checked == ["poi"]
        assert report.alerts == []

    def test_diurutkan_dari_penyimpangan_terbesar(self) -> None:
        kecil = AnomalyPoint(
            key="a", label="A", latest_value=1, latest_period="p", baseline_mean=0,
            baseline_sd=1, z_score=2.5, n_baseline=4, direction="naik", notable=True,
        )
        besar = AnomalyPoint(
            key="b", label="B", latest_value=1, latest_period="p", baseline_mean=0,
            baseline_sd=1, z_score=-9.0, n_baseline=4, direction="turun", notable=True,
        )
        report = build_report({"a": kecil, "b": besar})
        assert [a.key for a in report.alerts] == ["b", "a"]

    def test_laporan_kosong(self) -> None:
        report = build_report({})
        assert report.alerts == [] and report.checked == [] and report.insufficient == []
