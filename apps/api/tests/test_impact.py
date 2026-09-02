"""Tes Communication Impact (difference-in-differences) — fungsi murni.

Modul yang diuji di sini adalah satu-satunya di platform ini yang berhak
menghasilkan klaim efek. Tes yang paling penting bukan yang memverifikasi
aritmetikanya, melainkan yang memverifikasi ia MENOLAK bekerja ketika
desainnya tidak memadai.
"""

from __future__ import annotations

import pytest

from app.services.impact import (
    MIN_CELL_N,
    Cell,
    NoControlGroup,
    check_parallel_trends,
    difference_in_differences,
)


def _cell(mean: float, *, sd: float = 10.0, n: int = 400) -> Cell:
    return Cell(mean=mean, sd=sd, n=n)


class TestMenolakTanpaPembanding:
    def test_tanpa_kelompok_pembanding_ditolak(self) -> None:
        """Inti aturan CLAUDE.md: tanpa pembanding, tidak ada klaim efek."""
        with pytest.raises(NoControlGroup, match="kelompok pembanding"):
            difference_in_differences(
                treated_pre=_cell(50),
                treated_post=_cell(58),
                control_pre=None,
                control_post=None,
            )

    def test_pembanding_setengah_juga_ditolak(self) -> None:
        with pytest.raises(NoControlGroup):
            difference_in_differences(
                treated_pre=_cell(50),
                treated_post=_cell(58),
                control_pre=_cell(50),
                control_post=None,
            )

    def test_pesannya_menjelaskan_kenapa_bukan_sekadar_menolak(self) -> None:
        with pytest.raises(NoControlGroup) as e:
            difference_in_differences(
                treated_pre=_cell(50),
                treated_post=_cell(58),
                control_pre=None,
                control_post=None,
            )
        assert "tren yang sudah berjalan" in str(e.value)

    def test_turunan_valueerror_agar_jadi_422_bukan_500(self) -> None:
        assert issubclass(NoControlGroup, ValueError)


class TestPerhitungan:
    def test_efek_adalah_selisih_dari_selisih(self) -> None:
        r = difference_in_differences(
            treated_pre=_cell(50),
            treated_post=_cell(58),  # +8
            control_pre=_cell(50),
            control_post=_cell(53),  # +3
        )
        assert r.effect == 5.0
        assert r.treated_change == 8.0
        assert r.control_change == 3.0

    def test_tren_bersama_bukan_efek(self) -> None:
        """Kedua kelompok naik sama banyak -> efeknya nol, bukan +8."""
        r = difference_in_differences(
            treated_pre=_cell(50),
            treated_post=_cell(58),
            control_pre=_cell(40),
            control_post=_cell(48),
        )
        assert r.effect == 0.0
        assert not r.distinguishable_from_zero

    def test_interval_memuat_efek(self) -> None:
        r = difference_in_differences(
            treated_pre=_cell(50),
            treated_post=_cell(58),
            control_pre=_cell(50),
            control_post=_cell(53),
        )
        assert r.ci_low is not None and r.ci_high is not None
        assert r.ci_low < r.effect < r.ci_high

    def test_galat_menumpuk_dari_empat_sel(self) -> None:
        """Interval DiD harus lebih lebar daripada interval satu sel."""
        r = difference_in_differences(
            treated_pre=_cell(50, sd=10, n=100),
            treated_post=_cell(58, sd=10, n=100),
            control_pre=_cell(50, sd=10, n=100),
            control_post=_cell(53, sd=10, n=100),
        )
        satu_sel = 1.96 * 10 / 10  # se satu sel = 1.0
        assert r.ci_high is not None and r.effect is not None
        assert (r.ci_high - r.effect) > satu_sel * 1.9

    def test_sampel_lebih_besar_mempersempit_interval(self) -> None:
        kecil = difference_in_differences(
            treated_pre=_cell(50, n=50),
            treated_post=_cell(58, n=50),
            control_pre=_cell(50, n=50),
            control_post=_cell(53, n=50),
        )
        besar = difference_in_differences(
            treated_pre=_cell(50, n=5000),
            treated_post=_cell(58, n=5000),
            control_pre=_cell(50, n=5000),
            control_post=_cell(53, n=5000),
        )
        assert kecil.ci_high is not None and besar.ci_high is not None
        assert (besar.ci_high - besar.ci_low) < (kecil.ci_high - kecil.ci_low)  # type: ignore[operator]

    def test_interval_memuat_nol_dilaporkan_jujur(self) -> None:
        r = difference_in_differences(
            treated_pre=_cell(50, sd=40),
            treated_post=_cell(51, sd=40),
            control_pre=_cell(50, sd=40),
            control_post=_cell(50, sd=40),
        )
        assert not r.distinguishable_from_zero
        assert r.note is not None
        assert "bukan bukti bahwa efeknya tidak ada" in r.note


class TestSelTipis:
    def test_sel_di_bawah_ambang_menolak_memberi_angka(self) -> None:
        r = difference_in_differences(
            treated_pre=_cell(50, n=10),
            treated_post=_cell(58, n=400),
            control_pre=_cell(50, n=400),
            control_post=_cell(53, n=400),
        )
        assert r.insufficient_data
        assert r.effect is None
        assert r.note is not None and "terpapar sebelum" in r.note

    def test_ambang_disebut_di_pesan(self) -> None:
        r = difference_in_differences(
            treated_pre=_cell(50, n=1),
            treated_post=_cell(58, n=1),
            control_pre=_cell(50, n=1),
            control_post=_cell(53, n=1),
        )
        assert r.note is not None and str(MIN_CELL_N) in r.note


class TestTrenParalel:
    def test_tren_sejajar_lolos(self) -> None:
        ok, gap = check_parallel_trends([50, 51, 52], [40, 41, 42])
        assert ok and gap == 0.0

    def test_tren_menyimpang_gagal(self) -> None:
        ok, gap = check_parallel_trends([50, 52, 54], [40, 40, 40])
        assert not ok and gap == 2.0

    def test_deret_terlalu_pendek_ditolak(self) -> None:
        with pytest.raises(ValueError, match="dua pengamatan"):
            check_parallel_trends([50], [40, 41])

    def test_tanpa_deret_pra_ditandai_tidak_diperiksa(self) -> None:
        r = difference_in_differences(
            treated_pre=_cell(50),
            treated_post=_cell(58),
            control_pre=_cell(50),
            control_post=_cell(53),
        )
        assert r.parallel_trends_checked is False
        assert any("TIDAK diperiksa" in x for x in r.limitations)

    def test_tren_gagal_membatalkan_pembacaan_sebagai_efek(self) -> None:
        r = difference_in_differences(
            treated_pre=_cell(50),
            treated_post=_cell(58),
            control_pre=_cell(50),
            control_post=_cell(53),
            treated_pre_series=[44, 47, 50],
            control_pre_series=[50, 50, 50],
        )
        assert r.parallel_trends_ok is False
        assert r.distinguishable_from_zero is False, "efek diklaim padahal asumsinya jatuh"
        assert r.note is not None and "tren paralel gagal" in r.note.lower()

    def test_tren_lolos_membolehkan_pembacaan_sebagai_efek(self) -> None:
        r = difference_in_differences(
            treated_pre=_cell(50, sd=5),
            treated_post=_cell(58, sd=5),
            control_pre=_cell(50, sd=5),
            control_post=_cell(51, sd=5),
            treated_pre_series=[48, 49, 50],
            control_pre_series=[48, 49, 50],
        )
        assert r.parallel_trends_ok is True
        assert r.distinguishable_from_zero is True


class TestKontrak:
    def test_metode_menyebut_did_agar_envelope_mengizinkan_klaim_kausal(self) -> None:
        """app/ai/envelope.py:_has_causal_design() mencari kata ini di method."""
        r = difference_in_differences(
            treated_pre=_cell(50),
            treated_post=_cell(58),
            control_pre=_cell(50),
            control_post=_cell(53),
        )
        assert "difference-in-differences" in r.method

    def test_batasan_selalu_menyebut_efek_rata_rata(self) -> None:
        r = difference_in_differences(
            treated_pre=_cell(50),
            treated_post=_cell(58),
            control_pre=_cell(50),
            control_post=_cell(53),
        )
        assert any("rata-rata" in x for x in r.limitations)
        assert any("peristiwa lain" in x for x in r.limitations)

    def test_ci_level_asing_ditolak(self) -> None:
        with pytest.raises(ValueError, match="ci_level"):
            difference_in_differences(
                treated_pre=_cell(50),
                treated_post=_cell(58),
                control_pre=_cell(50),
                control_post=_cell(53),
                ci_level=0.77,
            )

    def test_sel_dengan_nilai_tidak_masuk_akal_ditolak(self) -> None:
        with pytest.raises(ValueError, match="negatif"):
            Cell(mean=50, sd=-1, n=100)
