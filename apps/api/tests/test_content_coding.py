"""Pengodean isi: validasi kode dan Krippendorff alpha.

Dua set acuan untuk alpha berasal dari literatur, bukan dari implementasi ini:
contoh 4 pengode x 12 unit di Krippendorff (2011), "Computing Krippendorff's
Alpha-Reliability" (nominal 0,743; ordinal 0,815), dan contoh 3 pengode x 15
unit yang umum dikutip (nominal 0,691).
"""

from __future__ import annotations

import pytest

from app.services import content_coding as cc

_ = None
KRIPPENDORFF_4X12 = [
    [1, 2, 3, 3, 2, 1, 4, 1, 2, _, _, _],
    [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, _, 3],
    [_, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, _],
    [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, _],
]
THREE_BY_15 = [
    [_, _, _, _, _, 3, 4, 1, 2, 1, 1, 3, 3, _, 3],
    [1, _, 2, 1, 3, 3, 4, 3, _, _, _, _, _, _, _],
    [_, _, 2, 1, 3, 4, 4, _, 2, 1, 1, 3, 3, _, 4],
]


def _units(matrix: list[list[int | None]]) -> list[list[int]]:
    return [[v for v in column if v is not None] for column in zip(*matrix, strict=True)]


class TestAlpha:
    def test_acuan_krippendorff_nominal(self) -> None:
        assert cc.krippendorff_alpha(_units(KRIPPENDORFF_4X12)) == pytest.approx(0.743, abs=0.001)

    def test_acuan_krippendorff_ordinal(self) -> None:
        alpha = cc.krippendorff_alpha(_units(KRIPPENDORFF_4X12), level="ordinal")
        assert alpha == pytest.approx(0.815, abs=0.001)

    def test_acuan_tiga_pengode_nominal(self) -> None:
        assert cc.krippendorff_alpha(_units(THREE_BY_15)) == pytest.approx(0.691, abs=0.001)

    def test_sepakat_penuh_satu(self) -> None:
        assert cc.krippendorff_alpha([[1, 1], [2, 2], [3, 3]]) == 1.0

    def test_berlawanan_sistematis_negatif(self) -> None:
        alpha = cc.krippendorff_alpha([[0, 1], [1, 0], [0, 1], [1, 0]])
        assert alpha is not None and alpha < 0

    def test_tanpa_variasi_tidak_bisa_dihitung(self) -> None:
        assert cc.krippendorff_alpha([[1, 1], [1, 1]]) is None

    def test_tanpa_pasangan_tidak_bisa_dihitung(self) -> None:
        assert cc.krippendorff_alpha([[1], [2], []]) is None

    def test_ordinal_menghukum_selisih_jauh_lebih_berat(self) -> None:
        near = cc.krippendorff_alpha([[1, 2], [3, 3], [5, 5], [2, 2]], level="ordinal")
        far = cc.krippendorff_alpha([[1, 5], [3, 3], [5, 5], [2, 2]], level="ordinal")
        assert near is not None and far is not None and near > far

    def test_label_mengikuti_ambang(self) -> None:
        assert cc.reliability_label(0.8) == "dapat diandalkan"
        assert cc.reliability_label(0.7) == "hanya untuk kesimpulan sementara"
        assert cc.reliability_label(0.666) == "kategori perlu diperbaiki"
        assert cc.reliability_label(None) == "tidak bisa dihitung"


class TestValidasi:
    def test_kosong_dibuang_yang_sah_lolos(self) -> None:
        assert cc.validate_codes({"A9": 3, "A12": None, "A14": 0}) == {"A9": 3, "A14": 0}

    def test_variabel_tidak_dikenal_ditolak(self) -> None:
        with pytest.raises(ValueError, match="tidak dikenal"):
            cc.validate_codes({"A99": 1})

    def test_nilai_di_luar_daftar_ditolak(self) -> None:
        with pytest.raises(ValueError, match="tidak sah"):
            cc.validate_codes({"A9": 8})

    def test_semua_kosong_ditolak(self) -> None:
        with pytest.raises(ValueError, match="paling sedikit"):
            cc.validate_codes({"A9": None})


class TestReliabilitas:
    def test_di_bawah_ambang_alpha_ditahan(self) -> None:
        codings = {i: {"a": {"A9": 1}, "b": {"A9": 2}} for i in range(cc.MIN_DOUBLE_CODED - 1)}
        r = cc.reliability(codings, n_posts=100)
        a9 = next(v for v in r.variables if v.code == "A9")
        assert a9.alpha is None and a9.percent_agreement is None
        assert "data tidak cukup" in a9.label
        assert r.meets_target is False

    def test_cukup_dan_sepakat(self) -> None:
        codings = {
            i: {"a": {"A9": 1 + i % 3, "A14": i % 6}, "b": {"A9": 1 + i % 3, "A14": i % 6}}
            for i in range(30)
        }
        r = cc.reliability(codings, n_posts=200)
        a9 = next(v for v in r.variables if v.code == "A9")
        assert a9.alpha == 1.0 and a9.percent_agreement == 1.0
        assert r.n_double_coded == 30 and r.n_coders == 2
        assert r.double_share == 0.15 and r.meets_target is True

    def test_variabel_yang_hanya_diisi_satu_pengode_tidak_dihitung(self) -> None:
        codings = {i: {"a": {"A9": 1, "A15": 2}, "b": {"A9": 1}} for i in range(25)}
        r = cc.reliability(codings, n_posts=25)
        assert next(v for v in r.variables if v.code == "A15").n_double_coded == 0

    def test_target_sepuluh_persen(self) -> None:
        codings = {i: {"a": {"A9": 1}, "b": {"A9": 1}} for i in range(20)}
        assert cc.reliability(codings, n_posts=1000).meets_target is False


class TestSebaran:
    def test_hitung_per_nilai_termasuk_yang_nol(self) -> None:
        d = cc.distributions([{"A9": 1}, {"A9": 1, "A12": 0}, {"A9": 3}])
        a9 = next(x for x in d if x.code == "A9")
        assert a9.n == 3
        assert [(v, n) for v, _, n in a9.counts][:3] == [(1, 2), (2, 0), (3, 1)]
        assert next(x for x in d if x.code == "A12").n == 1
