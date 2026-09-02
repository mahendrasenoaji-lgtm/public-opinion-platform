"""Tes komponen risiko parsial dan penskalaannya — fungsi murni.

Melengkapi tests/test_risk.py yang menguji `risk_score()` versi ketat (menolak
tanpa komponen lengkap). Di sini yang diuji adalah jalur yang benar-benar
dipakai endpoint: menghitung dari komponen yang ada, dan MENOLAK menerbitkan
angka kalau bobot yang terhitung terlalu sedikit.
"""

from __future__ import annotations

import pytest

from app.services.risk import (
    DEFAULT_RISK_WEIGHTS,
    MIN_COVERAGE,
    decline_component,
    growth_component,
    partial_risk_score,
    share_negative,
    velocity_component,
)


class TestShareNegative:
    def test_semua_negatif(self) -> None:
        assert share_negative([-0.8, -0.5, -0.9]) == 100.0

    def test_semua_positif(self) -> None:
        assert share_negative([0.8, 0.5]) == 0.0

    def test_netral_tidak_dihitung_negatif(self) -> None:
        assert share_negative([0.0, -0.1, 0.1]) == 0.0

    def test_kosong_none_bukan_nol(self) -> None:
        """Nol berarti "diukur, tidak ada yang negatif"; None berarti tidak diukur."""
        assert share_negative([]) is None


class TestVelocity:
    def test_memburuk_menghasilkan_risiko(self) -> None:
        v = velocity_component(-0.2, 0.2)  # turun 0.4
        assert v == 100.0

    def test_membaik_menghasilkan_nol_bukan_negatif(self) -> None:
        """Perbaikan tajam bukan risiko, dan tidak boleh mengurangi komponen lain."""
        assert velocity_component(0.5, -0.3) == 0.0

    def test_stabil_nol(self) -> None:
        assert velocity_component(0.1, 0.1) == 0.0

    def test_periode_pembanding_hilang(self) -> None:
        assert velocity_component(0.1, None) is None


class TestGrowth:
    def test_pertumbuhan_penuh(self) -> None:
        assert growth_component(200.0) == 100.0

    def test_penyusutan_nol(self) -> None:
        assert growth_component(-50.0) == 0.0

    def test_pertumbuhan_ekstrem_dibatasi(self) -> None:
        assert growth_component(9000.0) == 100.0

    def test_tidak_ada_data(self) -> None:
        assert growth_component(None) is None


class TestDecline:
    def test_penurunan_penuh(self) -> None:
        assert decline_component(50.0, 65.0) == 100.0

    def test_kenaikan_nol(self) -> None:
        assert decline_component(70.0, 60.0) == 0.0

    def test_kurang_pembanding(self) -> None:
        assert decline_component(70.0, None) is None


class TestPartialRiskScore:
    def _lengkap(self) -> dict[str, float]:
        return dict.fromkeys(DEFAULT_RISK_WEIGHTS, 50.0)

    def test_komponen_lengkap_menghasilkan_skor(self) -> None:
        r = partial_risk_score(self._lengkap())
        assert r.score == 50
        assert r.coverage == 1.0
        assert r.missing == []
        assert not r.insufficient_data

    def test_cakupan_di_bawah_ambang_menolak_memberi_angka(self) -> None:
        """Skor 0-100 dari sepertiga bobot akan dibaca sebagai penilaian utuh."""
        r = partial_risk_score({"negative_sentiment": 80.0})
        assert r.insufficient_data
        assert r.score is None
        assert r.band is None
        assert r.note is not None and "bobot risiko" in r.note

    def test_komponen_hilang_disebut_namanya(self) -> None:
        komponen = self._lengkap()
        del komponen["geographic_spread"]
        r = partial_risk_score(komponen)
        assert r.missing == ["geographic_spread"]
        assert r.note is not None and "geographic_spread" in r.note

    def test_komponen_hilang_tidak_diisi_nol(self) -> None:
        """Mengisi nol akan menurunkan skor seolah risikonya memang rendah."""
        komponen = self._lengkap()
        del komponen["geographic_spread"]
        r = partial_risk_score(komponen)
        assert r.score == 50, "komponen hilang tampaknya ikut dihitung sebagai 0"
        assert "geographic_spread" not in r.components

    def test_bobot_dinormalisasi_ulang_atas_yang_tersedia(self) -> None:
        komponen = {"negative_sentiment": 100.0, "sentiment_velocity": 0.0}
        # bobot 0.18 dan 0.16 -> skor = 100*0.18/0.34 = 52.9 -> 53
        r = partial_risk_score(komponen, min_coverage=0.1)
        assert r.score == 53

    def test_cakupan_dilaporkan_apa_adanya(self) -> None:
        r = partial_risk_score({"negative_sentiment": 50.0}, min_coverage=0.1)
        assert r.coverage == pytest.approx(0.18, abs=0.005)

    def test_penyumbang_teratas_dilaporkan(self) -> None:
        komponen = self._lengkap()
        komponen["negative_sentiment"] = 100.0
        r = partial_risk_score(komponen)
        assert r.top_contributors[0][0] == "negative_sentiment"

    def test_tanpa_komponen_sama_sekali(self) -> None:
        r = partial_risk_score({})
        assert r.insufficient_data and r.score is None and r.coverage == 0.0

    def test_min_coverage_tidak_valid_ditolak(self) -> None:
        with pytest.raises(ValueError, match="min_coverage"):
            partial_risk_score(self._lengkap(), min_coverage=0)

    def test_ambang_bawaan_masuk_akal(self) -> None:
        """Regresi: ambang tidak boleh diturunkan diam-diam ke nilai permisif."""
        assert MIN_COVERAGE >= 0.6
