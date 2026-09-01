"""Tes estimasi model deret waktu — fungsi murni, tanpa database."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.timeseries import (
    MIN_OBSERVATIONS,
    MIN_OBSERVATIONS_FOR_TREND,
    fit,
)


def _series(values: list[float], *, step_days: int = 7) -> list[tuple[date, float]]:
    start = date(2026, 1, 5)
    return [(start + timedelta(days=i * step_days), v) for i, v in enumerate(values)]


def _naik(n: int) -> list[float]:
    """Tren naik dengan sedikit derau — bukan garis sempurna."""
    derau = [0.0, 0.4, -0.3, 0.2, -0.4, 0.3, -0.2, 0.1]
    return [60 + 0.8 * i + derau[i % len(derau)] for i in range(n)]


class TestGating:
    def test_riwayat_pendek_menolak_bukan_menebak(self) -> None:
        r = fit(_series([60, 61, 62, 61]))
        assert r.insufficient_data
        assert r.baseline is None
        assert r.spread == {}
        assert r.note is not None and str(MIN_OBSERVATIONS) in r.note

    def test_riwayat_kosong(self) -> None:
        assert fit([]).insufficient_data

    def test_tepat_di_ambang_diterima(self) -> None:
        r = fit(_series(_naik(MIN_OBSERVATIONS)))
        assert not r.insufficient_data
        assert r.baseline is not None


class TestEstimasi:
    def test_menghasilkan_spread_untuk_semua_horizon(self) -> None:
        r = fit(_series(_naik(20)))
        assert set(r.spread) == {1, 3, 7, 14, 30, 90}
        assert all(v > 0 for v in r.spread.values())

    def test_ketidakpastian_tidak_menyempit_di_horizon_jauh(self) -> None:
        """Sifat yang sama yang dijaga services/forecast.py: tahu lebih sedikit,
        bukan lebih banyak, semakin jauh ke depan."""
        r = fit(_series(_naik(24)))
        nilai = [r.spread[h] for h in sorted(r.spread)]
        assert nilai == sorted(nilai), f"spread menyempit: {nilai}"

    def test_baseline_adalah_pengamatan_terakhir(self) -> None:
        nilai = _naik(20)
        r = fit(_series(nilai))
        assert r.baseline == pytest.approx(round(nilai[-1], 2), abs=0.01)

    def test_riwayat_pendek_tanpa_komponen_tren(self) -> None:
        r = fit(_series(_naik(MIN_OBSERVATIONS)))
        assert "tanpa komponen tren" in " ".join(r.limitations)
        assert "level lokal" in r.model
        assert "tren" not in r.model

    def test_riwayat_panjang_mengestimasi_tren(self) -> None:
        r = fit(_series(_naik(MIN_OBSERVATIONS_FOR_TREND + 8)))
        assert "tren" in r.model

    def test_horizon_melampaui_riwayat_ditandai_ekstrapolasi(self) -> None:
        # 12 pengamatan berjarak 7 hari = rentang 77 hari, horizon 90 melampauinya
        r = fit(_series(_naik(12)))
        assert any("ekstrapolasi" in x for x in r.limitations)

    def test_riwayat_panjang_tidak_ditandai_ekstrapolasi(self) -> None:
        r = fit(_series(_naik(30)))  # rentang 203 hari
        assert not any("ekstrapolasi" in x for x in r.limitations)

    def test_asumsi_jarak_selalu_dilaporkan(self) -> None:
        r = fit(_series(_naik(20), step_days=14))
        assert any("berjarak sama" in x for x in r.limitations)
        assert r.median_step_days == 14.0


class TestKasusTepi:
    def test_tanggal_tidak_terurut_tetap_benar(self) -> None:
        s = _series(_naik(20))
        assert fit(list(reversed(s))).baseline == fit(s).baseline

    def test_tanggal_ganda_diambil_yang_terakhir(self) -> None:
        """Dua snapshot untuk periode sama berarti yang belakangan koreksi."""
        s = _series(_naik(20))
        with_dup = [*s, (s[-1][0], 99.0)]
        assert fit(with_dup).baseline == pytest.approx(99.0, abs=0.01)

    def test_riwayat_konstan_tidak_melempar(self) -> None:
        """Nilai yang sama persis membuat estimasi varians degenerate."""
        r = fit(_series([70.0] * 20))
        assert r.baseline is not None  # dilaporkan, bukan 500

    def test_pi_level_tidak_valid_ditolak(self) -> None:
        with pytest.raises(ValueError, match="pi_level"):
            fit(_series(_naik(20)), pi_level=1.5)

    def test_pi_level_lebih_tinggi_memberi_interval_lebih_lebar(self) -> None:
        s = _series(_naik(24))
        sempit = fit(s, pi_level=0.80)
        lebar = fit(s, pi_level=0.95)
        assert lebar.spread[30] > sempit.spread[30]

    def test_horizon_khusus_dihormati(self) -> None:
        r = fit(_series(_naik(20)), horizons=(7, 21))
        assert set(r.spread) == {7, 21}
