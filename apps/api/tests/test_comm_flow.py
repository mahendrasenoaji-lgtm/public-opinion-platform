"""Arus informasi (T1-T4), waktu tanggap (C4), keselarasan (C3), tingkat jawab (O8)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.services import comm_flow as cf


def _t(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, tzinfo=UTC)


class TestSelang:
    def test_jam_per_selang(self) -> None:
        r = cf.FlowRecord(
            requested_at=_t(1, 8), received_at=_t(1, 14), verified_at=_t(2, 14),
            drafted_at=_t(2, 15), approved_at=_t(2, 18), published_at=_t(2, 19),
        )
        assert cf.interval_hours(r) == {"T1": 6.0, "T2": 24.0, "T3": 3.0, "T4": 1.0}

    def test_cap_waktu_kosong_tidak_ditebak(self) -> None:
        r = cf.FlowRecord(requested_at=_t(1), approved_at=_t(3), published_at=_t(3, 2))
        assert cf.interval_hours(r) == {"T1": None, "T2": None, "T3": None, "T4": 2.0}

    def test_cap_waktu_mundur_ditolak(self) -> None:
        with pytest.raises(ValueError, match="lebih awal"):
            cf.check_order(cf.FlowRecord(requested_at=_t(2), received_at=_t(1)))

    def test_urutan_diperiksa_melewati_yang_kosong(self) -> None:
        with pytest.raises(ValueError, match="published_at lebih awal daripada requested_at"):
            cf.check_order(cf.FlowRecord(requested_at=_t(5), published_at=_t(4)))

    def test_tanpa_cap_waktu_ditolak(self) -> None:
        with pytest.raises(ValueError, match="paling sedikit"):
            cf.check_order(cf.FlowRecord())

    def test_tahap_hambatan_di_luar_model_ditolak(self) -> None:
        with pytest.raises(ValueError, match="1 sampai 11"):
            cf.check_order(cf.FlowRecord(requested_at=_t(1), bottleneck_stage=12))


class TestRingkasanArus:
    def test_median_ditahan_di_bawah_ambang(self) -> None:
        records = [cf.FlowRecord(approved_at=_t(1), published_at=_t(1, 2))] * (cf.MIN_RECORDS - 1)
        s = cf.summarize_flow(records)
        t4 = next(i for i in s.intervals if i.code == "T4")
        assert t4.n == cf.MIN_RECORDS - 1 and t4.median_hours is None
        assert s.slowest is None

    def test_selang_terlambat_dan_hambatan(self) -> None:
        records = [
            cf.FlowRecord(
                requested_at=_t(1), received_at=_t(1, 2 + i), drafted_at=_t(2),
                approved_at=_t(4), published_at=_t(4, 1), bottleneck_stage=6,
            )
            for i in range(5)
        ]
        s = cf.summarize_flow(records)
        by = {i.code: i for i in s.intervals}
        assert by["T1"].median_hours == 4.0 and by["T1"].max_hours == 6.0
        assert by["T3"].median_hours == 48.0
        assert by["T2"].n == 0 and by["T2"].median_hours is None
        assert s.slowest == "T3"
        assert (6, "Persetujuan", 5) in s.bottlenecks
        assert len(s.bottlenecks) == 11


class TestWaktuTanggap:
    volume = {date(2026, 10, d): v for d, v in [(11, 40), (12, 50), (13, 60), (14, 400), (15, 45)]}

    def test_lonjakan_dijawab(self) -> None:
        # 14 Okt 00.00 WIB = 13 Okt 17.00 UTC; unggahan 14 Okt 03.00 UTC = 10 jam kemudian.
        r = cf.response_time(self.volume, [_t(12, 1), _t(14, 3)])
        assert [s.day for s in r.spikes] == [date(2026, 10, 14)]
        assert r.spikes[0].hours == 10.0 and r.spikes[0].ratio == 8.0
        assert r.median_hours == 10.0 and r.suggested_score == 4

    def test_unggahan_sebelum_lonjakan_tidak_dihitung(self) -> None:
        r = cf.response_time(self.volume, [_t(13, 10)])
        assert r.spikes[0].hours is None and r.n_unanswered == 1
        assert r.suggested_score == 1

    def test_di_luar_72_jam_dianggap_tidak_dijawab(self) -> None:
        r = cf.response_time(self.volume, [_t(17, 0)])
        assert r.spikes[0].hours is None

    def test_tanpa_lonjakan_tidak_ada_saran(self) -> None:
        flat = {date(2026, 10, d): 50 for d in range(11, 16)}
        r = cf.response_time(flat, [_t(12)])
        assert r.spikes == () and r.suggested_score is None

    def test_kurang_dari_tiga_hari_tidak_ada_lonjakan(self) -> None:
        r = cf.response_time({date(2026, 10, 11): 5, date(2026, 10, 12): 500}, [])
        assert r.spikes == ()

    def test_zona_menggeser_awal_hari(self) -> None:
        wib = cf.response_time(self.volume, [_t(14, 3)], tz_offset_hours=7)
        wit = cf.response_time(self.volume, [_t(14, 3)], tz_offset_hours=9)
        assert wit.spikes[0].hours == wib.spikes[0].hours + 2

    def test_cap_waktu_tanpa_zona_dianggap_utc(self) -> None:
        naive = datetime(2026, 10, 14, 3)
        assert cf.response_time(self.volume, [naive]).spikes[0].hours == 10.0


class TestKeselarasan:
    def test_di_bawah_ambang_tanpa_saran(self) -> None:
        s = cf.summarize_alignment([("selaras", False)] * (cf.MIN_PAIRS - 1))
        assert s.suggested_score is None and s.n_pairs == cf.MIN_PAIRS - 1

    def test_semua_selaras_lima(self) -> None:
        assert cf.summarize_alignment([("selaras", False)] * 6).suggested_score == 5

    def test_beda_penekanan_tiga(self) -> None:
        pairs = [("selaras", False)] * 5 + [("beda_penekanan", False)]
        assert cf.summarize_alignment(pairs).suggested_score == 3

    def test_bertentangan_tidak_diralat_satu(self) -> None:
        pairs = [("selaras", False)] * 5 + [("bertentangan", False)]
        s = cf.summarize_alignment(pairs)
        assert s.suggested_score == 1 and s.n_contradiction_open == 1

    def test_bertentangan_tetapi_diralat_tiga(self) -> None:
        pairs = [("selaras", False)] * 5 + [("bertentangan", True)]
        s = cf.summarize_alignment(pairs)
        assert s.suggested_score == 3 and s.counts["bertentangan"] == 1


class TestTingkatJawab:
    @pytest.mark.parametrize(
        "text",
        ["Kapan cair pak", "syaratnya apa saja?", "  gimana cara daftar", "Mohon info jadwalnya",
         "dimana kantornya"],
    )
    def test_pertanyaan(self, text: str) -> None:
        assert cf.is_question(text)

    @pytest.mark.parametrize("text", ["Mantap pak", "", "   ", "semoga lancar", "apalagi ini"])
    def test_bukan_pertanyaan(self, text: str) -> None:
        assert not cf.is_question(text)

    def test_di_bawah_ambang_tanpa_angka(self) -> None:
        r = cf.response_rate([("kapan?", True)] * (cf.MIN_QUESTIONS - 1) + [("bagus", False)])
        assert r.n_questions == cf.MIN_QUESTIONS - 1 and r.n_comments == cf.MIN_QUESTIONS
        assert r.rate_pct is None and r.suggested_score is None

    def test_porsi_dan_saran_skor(self) -> None:
        threads = [("kapan?", True)] * 5 + [("kapan?", False)] * 15 + [("mantap", True)] * 30
        r = cf.response_rate(threads)
        assert (r.n_questions, r.n_answered) == (20, 5)
        assert r.rate_pct == 25.0 and r.suggested_score == 3

    def test_balasan_pada_bukan_pertanyaan_tidak_dihitung(self) -> None:
        r = cf.response_rate([("kapan?", False)] * 20 + [("bagus", True)] * 100)
        assert r.rate_pct == 0.0 and r.suggested_score == 1
