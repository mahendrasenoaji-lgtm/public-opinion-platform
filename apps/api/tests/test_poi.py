import pytest

from app.services.poi import Dimension, SignalSource, compute_index, compute_change, publishable


def survey_dims():
    return [
        Dimension("approval", "Approval", 74, 25, SignalSource.SURVEY, 8940),
        Dimension("trust", "Trust", 68, 25, SignalSource.SURVEY, 8940),
        Dimension("satisfaction", "Satisfaction", 71, 12, SignalSource.SURVEY, 8940),
    ]


def test_bobot_dinormalisasi_meski_tidak_berjumlah_seratus():
    dims = [
        Dimension("a", "A", 80, 3, SignalSource.SURVEY, 1000),
        Dimension("b", "B", 60, 1, SignalSource.SURVEY, 1000),
    ]
    assert compute_index(dims).value == pytest.approx(75.0)


def test_ci_hanya_dari_komponen_probabilistik():
    dims = survey_dims() + [
        Dimension("sentiment", "Sentiment", 61, 20, SignalSource.SOCIAL),
    ]
    r = compute_index(dims)
    assert r.ci_low is not None
    # margin dipersempit sesuai porsi bobot survei
    assert r.ci_high - r.ci_low < 2.5


def test_tanpa_survei_tidak_ada_interval_kepercayaan():
    dims = [Dimension("sentiment", "Sentiment", 61, 100, SignalSource.SOCIAL)]
    r = compute_index(dims)
    assert r.ci_low is None
    assert any("non-probabilistik" in x for x in r.limitations)


def test_source_mix_menjumlah_satu():
    r = compute_index(survey_dims() + [Dimension("s", "S", 50, 30, SignalSource.SOCIAL)])
    assert sum(r.source_mix.values()) == pytest.approx(1.0, abs=1e-3)
    assert r.generalisable_share < 1.0


def test_sampel_kecil_tidak_layak_terbit():
    dims = [Dimension("trust", "Trust", 68, 100, SignalSource.SURVEY, 120)]
    assert publishable(compute_index(dims)) is False


def test_skor_di_luar_rentang_ditolak():
    with pytest.raises(ValueError):
        Dimension("x", "X", 140, 10, SignalSource.SURVEY)


def test_perubahan_menandai_interval_bertumpang_tindih():
    cur = compute_index(survey_dims())
    prev = compute_index(
        [Dimension(d.key, d.label, d.score - 0.2, d.weight, d.source, d.effective_n) for d in survey_dims()]
    )
    change = compute_change(cur, prev)
    assert change["intervals_separated"] is False
    assert "belum tentu berarti" in change["note"]
