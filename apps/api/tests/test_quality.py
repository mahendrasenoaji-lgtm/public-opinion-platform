import pytest

from app.services.quality import QualityFlag, assess, dataset_quality


def test_speeding_terdeteksi_dan_skor_turun():
    r = assess(duration_sec=50, median_duration_sec=300, scale_answers=[])
    assert QualityFlag.SPEEDING in r.flags
    assert r.score == 70
    assert r.needs_review is True


def test_median_nol_tidak_memicu_speeding():
    # Median durasi 0 berarti belum ada data lapangan untuk dibandingkan —
    # jangan menuduh speeding dari pembagi yang tidak berarti.
    r = assess(duration_sec=1, median_duration_sec=0, scale_answers=[])
    assert QualityFlag.SPEEDING not in r.flags
    assert r.score == 100


def test_straight_lining_terdeteksi_saat_variasi_nol():
    r = assess(
        duration_sec=300,
        median_duration_sec=300,
        scale_answers=[3, 3, 3, 3, 3, 3],
    )
    assert QualityFlag.STRAIGHT_LINING in r.flags
    assert r.score == 65


def test_variasi_sangat_rendah_menurunkan_skor_tanpa_flag():
    # sd kecil tapi tidak nol: peringatan lunak, bukan flag straight-lining.
    r = assess(
        duration_sec=300,
        median_duration_sec=300,
        scale_answers=[3, 3, 3, 3, 3, 3, 3, 3, 3, 3.5],
    )
    assert QualityFlag.STRAIGHT_LINING not in r.flags
    assert r.score == 90
    assert any("variasi" in reason for reason in r.reasons)


def test_kurang_dari_enam_item_skala_tidak_dievaluasi():
    r = assess(duration_sec=300, median_duration_sec=300, scale_answers=[1, 1, 1, 1, 1])
    assert r.flags == []
    assert r.score == 100


def test_trap_pairs_konsisten_tidak_memicu_flag():
    r = assess(
        duration_sec=300,
        median_duration_sec=300,
        scale_answers=[],
        trap_pairs=[(2, 4)],
        scale_points=5,
    )
    assert QualityFlag.INCONSISTENT not in r.flags
    assert r.score == 100


def test_trap_pairs_tidak_konsisten_memicu_flag():
    r = assess(
        duration_sec=300,
        median_duration_sec=300,
        scale_answers=[],
        trap_pairs=[(5, 5)],
        scale_points=5,
    )
    assert QualityFlag.INCONSISTENT in r.flags
    assert r.score == 80


def test_hanya_pasangan_pertama_yang_tidak_konsisten_yang_dilaporkan():
    # Loop berhenti begitu satu pasangan bermasalah ditemukan.
    r = assess(
        duration_sec=300,
        median_duration_sec=300,
        scale_answers=[],
        trap_pairs=[(5, 5), (5, 5)],
        scale_points=5,
    )
    assert r.flags.count(QualityFlag.INCONSISTENT) == 1
    assert r.score == 80


def test_semua_flag_sekaligus_skor_turun_gabungan_dan_tetap_positif():
    r = assess(
        duration_sec=50,
        median_duration_sec=300,
        scale_answers=[3, 3, 3, 3, 3, 3],
        trap_pairs=[(5, 5)],
        scale_points=5,
    )
    assert set(r.flags) == {
        QualityFlag.SPEEDING,
        QualityFlag.STRAIGHT_LINING,
        QualityFlag.INCONSISTENT,
    }
    assert r.score == 15
    assert r.score >= 0


def test_needs_review_false_ketika_bersih():
    r = assess(duration_sec=300, median_duration_sec=300, scale_answers=[1, 2, 3, 4, 5, 1])
    assert r.flags == []
    assert r.needs_review is False


def test_dataset_quality_sempurna_menghasilkan_seratus():
    r = dataset_quality(
        total=100,
        complete=100,
        duplicates=0,
        flagged=0,
        inconsistent=0,
        max_stratum_deviation_pp=0,
        metadata_fields_filled=1.0,
    )
    assert r["overall"] == 100


def test_dataset_quality_total_nol_tidak_membagi_nol():
    r = dataset_quality(
        total=0,
        complete=0,
        duplicates=0,
        flagged=0,
        inconsistent=0,
        max_stratum_deviation_pp=0,
        metadata_fields_filled=0,
    )
    assert r["completeness"] == 0
    assert r["duplicate"] == 100  # pct(0, 0) == 0 -> 100 - 0


def test_dataset_quality_deviasi_strata_besar_menekan_balance_ke_nol():
    r = dataset_quality(
        total=100,
        complete=100,
        duplicates=0,
        flagged=0,
        inconsistent=0,
        max_stratum_deviation_pp=25,
        metadata_fields_filled=1.0,
    )
    assert r["sample_balance"] == 0
    assert r["overall"] < 100


def test_dataset_quality_sample_balance_dibobot_lebih_berat_dari_metadata():
    turun_balance = dataset_quality(
        total=100, complete=100, duplicates=0, flagged=0, inconsistent=0,
        max_stratum_deviation_pp=10, metadata_fields_filled=1.0,
    )
    turun_metadata = dataset_quality(
        total=100, complete=100, duplicates=0, flagged=0, inconsistent=0,
        max_stratum_deviation_pp=0, metadata_fields_filled=0.5,
    )
    assert turun_balance["overall"] < turun_metadata["overall"]
