"""Tes fungsi murni Kinerja Komunikasi Pemerintah (services/comm_performance.py)."""

from datetime import UTC, datetime

import pytest

from app.services import comm_performance as cp


def _all(value: int) -> dict[str, int | None]:
    return {i.code: value for i in cp.INDICATORS}


class TestKatalog:
    def test_kode_unik_dan_28_indikator(self) -> None:
        assert len(cp.INDICATORS) == 28
        assert len(cp.INDICATOR_BY_CODE) == 28

    def test_jumlah_per_dimensi_sesuai_dokumen_kerangka(self) -> None:
        counts = {d: sum(1 for i in cp.INDICATORS if i.dimension == d) for d in cp.DIMENSIONS}
        assert counts == {"INPUT": 6, "PROCESS": 7, "OUTPUT": 9, "OUTCOME": 6}

    def test_awalan_kode_cocok_dengan_dimensi(self) -> None:
        prefix = {"INPUT": "I", "PROCESS": "P", "OUTPUT": "O", "OUTCOME": "C"}
        assert all(i.code.startswith(prefix[i.dimension]) for i in cp.INDICATORS)

    def test_output_dan_outcome_tidak_tertukar(self) -> None:
        # Engagement dan response rate = output; pemahaman dan keselarasan = outcome.
        assert cp.INDICATOR_BY_CODE["O5"].dimension == "OUTPUT"
        assert cp.INDICATOR_BY_CODE["O8"].dimension == "OUTPUT"
        assert cp.INDICATOR_BY_CODE["C1"].dimension == "OUTCOME"
        assert cp.INDICATOR_BY_CODE["C3"].dimension == "OUTCOME"

    def test_bobot_usulan_berjumlah_100(self) -> None:
        assert sum(cp.DEFAULT_WEIGHTS.values()) == 100


class TestSkorDimensi:
    def test_contoh_di_dokumen_cakupan_56_persen_tidak_terbit(self) -> None:
        scores = {"O1": 3, "O4": 4, "O5": 2, "O8": 2, "O9": 4}
        d = cp.score_dimension("OUTPUT", scores)
        assert d.published is False
        assert d.score is None
        assert d.coverage == pytest.approx(0.556, abs=0.001)
        assert (d.n_available, d.n_total) == (5, 9)

    def test_contoh_di_dokumen_cakupan_67_persen_terbit_3_0(self) -> None:
        scores = {"O1": 3, "O4": 4, "O5": 2, "O8": 2, "O9": 4, "O6": 3}
        d = cp.score_dimension("OUTPUT", scores)
        assert d.published is True
        assert d.score == 3.0

    def test_none_tidak_ikut_rata_rata(self) -> None:
        scores: dict[str, int | None] = {c: 5 for c in ("I1", "I2", "I3", "I4")}
        scores["I5"] = None
        d = cp.score_dimension("INPUT", scores)
        assert d.score == 5.0
        assert d.n_available == 4


class TestKartuSkor:
    def test_total_tidak_terbit_bila_satu_dimensi_kurang_cakupan(self) -> None:
        scores = _all(4)
        for code in ("C1", "C2", "C5", "C6"):
            scores[code] = None
        card = cp.build_scorecard(scores)
        assert card.total is None
        assert card.total_equal_weights is None
        assert card.label is None
        assert [d.published for d in card.dimensions] == [True, True, True, False]

    def test_total_memakai_bobot_dan_pembanding_bobot_rata(self) -> None:
        scores = {
            **{i.code: 2 for i in cp.INDICATORS if i.dimension == "INPUT"},
            **{i.code: 3 for i in cp.INDICATORS if i.dimension == "PROCESS"},
            **{i.code: 4 for i in cp.INDICATORS if i.dimension == "OUTPUT"},
            **{i.code: 5 for i in cp.INDICATORS if i.dimension == "OUTCOME"},
        }
        card = cp.build_scorecard(scores)
        # (15*2 + 30*3 + 20*4 + 35*5) / 100
        assert card.total == 3.75
        assert card.total_equal_weights == 3.5
        assert card.label == "Tertata"

    def test_kartu_kosong_tidak_menghasilkan_angka(self) -> None:
        card = cp.build_scorecard({})
        assert card.total is None
        assert all(d.score is None and d.coverage == 0 for d in card.dimensions)

    def test_indikator_tidak_dikenal_ditolak(self) -> None:
        with pytest.raises(ValueError, match="tidak dikenal"):
            cp.build_scorecard({"X9": 3})

    @pytest.mark.parametrize("bad", [0, 6, -1])
    def test_skor_di_luar_rentang_ditolak(self, bad: int) -> None:
        with pytest.raises(ValueError, match="harus 1 sampai 5"):
            cp.build_scorecard({"I1": bad})

    def test_bobot_tidak_lengkap_ditolak(self) -> None:
        with pytest.raises(ValueError, match="Bobot"):
            cp.build_scorecard(_all(3), {"INPUT": 50, "PROCESS": 50})  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("total", "label"),
        [(1.0, "Belum tertata"), (1.9, "Dasar"), (2.7, "Berkembang"), (3.5, "Tertata"),
         (4.3, "Terpadu"), (5.0, "Terpadu")],
    )
    def test_sebutan(self, total: float, label: str) -> None:
        assert cp.label_for(total) == label


class TestAmbang:
    @pytest.mark.parametrize(
        ("answered", "questions", "expected"),
        [(0, 50, 1), (2, 50, 1), (3, 50, 2), (10, 50, 3), (20, 50, 4), (30, 50, 5), (50, 50, 5)],
    )
    def test_response_rate(self, answered: int, questions: int, expected: int) -> None:
        assert cp.score_response_rate(answered, questions) == expected

    def test_response_rate_tanpa_pertanyaan_tidak_dinilai(self) -> None:
        assert cp.score_response_rate(0, 0) is None

    def test_response_rate_melebihi_pertanyaan_ditolak(self) -> None:
        with pytest.raises(ValueError):
            cp.score_response_rate(5, 4)

    @pytest.mark.parametrize(
        ("hours", "expected"),
        [(0, 5), (5.9, 5), (6, 4), (23.9, 4), (24, 3), (48, 2), (72, 1), (200, 1), (None, 1)],
    )
    def test_kecepatan_respons(self, hours: float | None, expected: int) -> None:
        assert cp.score_response_hours(hours) == expected


def _post(
    account: str = "kemenko",
    platform: cp.Platform = "instagram",
    day: int = 1,
    **kw: int | None,
) -> cp.PostRow:
    base: dict[str, int | None] = {
        "likes": 100, "comments": 10, "shares": None, "views": None, "followers": 10_000,
    }
    base.update(kw)
    return cp.PostRow(
        account=account,
        platform=platform,
        posted_at=datetime(2026, 10, day, 3, 0, tzinfo=UTC),
        kind="foto",
        likes=base["likes"],
        comments=base["comments"],
        shares=base["shares"],
        views=base["views"],
        followers=base["followers"],
    )


class TestRingkasanUnggahan:
    def test_engagement_rate_terhadap_pengikut(self) -> None:
        assert cp.engagement_rate(_post(likes=90, comments=10)) == pytest.approx(1.0)

    def test_engagement_rate_none_tanpa_pengikut_atau_tanpa_interaksi(self) -> None:
        assert cp.engagement_rate(_post(followers=None)) is None
        assert cp.engagement_rate(_post(followers=0)) is None
        assert cp.engagement_rate(_post(likes=None, comments=None)) is None

    def test_median_ditahan_di_bawah_lima_unggahan(self) -> None:
        [s] = cp.summarize_posts(_post(day=d) for d in range(1, 5))
        assert s.n_posts == 4
        assert s.insufficient_data is True
        assert s.median_likes is None
        assert s.median_engagement_rate is None

    def test_median_bukan_rata_rata_satu_viral_tidak_menentukan(self) -> None:
        rows = [_post(day=d, likes=100) for d in range(1, 6)] + [_post(day=6, likes=1_000_000)]
        [s] = cp.summarize_posts(rows)
        assert s.median_likes == 100

    def test_platform_dan_akun_tidak_digabung(self) -> None:
        rows = [_post(day=d) for d in range(1, 6)]
        rows += [_post(platform="x", day=d) for d in range(1, 6)]
        rows += [_post(account="kemendagri", day=d) for d in range(1, 6)]
        out = cp.summarize_posts(rows)
        assert [(s.account, s.platform, s.n_posts) for s in out] == [
            ("kemendagri", "instagram", 5),
            ("kemenko", "instagram", 5),
            ("kemenko", "x", 5),
        ]

    def test_angka_yang_tidak_tampil_tetap_none_bukan_nol(self) -> None:
        [s] = cp.summarize_posts(_post(day=d) for d in range(1, 8))
        assert s.median_views is None
        assert s.median_shares is None
        assert s.median_likes == 100

    def test_per_bulan_dan_per_jenis(self) -> None:
        [s] = cp.summarize_posts(_post(day=d) for d in range(1, 6))
        assert s.posts_by_month == {"2026-10": 5}
        assert s.by_kind == {"foto": 5}

    def test_tanpa_unggahan_daftar_kosong(self) -> None:
        assert cp.summarize_posts([]) == []
