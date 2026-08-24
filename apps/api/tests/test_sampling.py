import pytest

from app.services.sampling import (
    SamplingMethod,
    margin_from_n,
    sample_size,
    stratum_balance,
)


def test_srs_385_untuk_margin_lima_persen():
    r = sample_size(population=None, margin_of_error=0.05, method=SamplingMethod.SRS)
    assert r.recommended_n == 385


def test_srs_1068_untuk_margin_tiga_persen():
    r = sample_size(population=None, margin_of_error=0.03, method=SamplingMethod.SRS)
    assert r.recommended_n == 1068


def test_koreksi_populasi_terbatas_mengurangi_sampel():
    besar = sample_size(population=None, method=SamplingMethod.SRS).recommended_n
    kecil = sample_size(population=2000, method=SamplingMethod.SRS).recommended_n
    assert kecil < besar
    assert sample_size(population=2000, method=SamplingMethod.SRS).finite_population_correction


def test_multistage_butuh_sampel_lebih_besar():
    srs = sample_size(population=None, method=SamplingMethod.SRS).recommended_n
    ms = sample_size(population=None, method=SamplingMethod.MULTISTAGE).recommended_n
    assert ms > srs


def test_metode_nonprobabilistik_memberi_peringatan():
    r = sample_size(population=None, method=SamplingMethod.QUOTA)
    assert any("non-probabilistik" in w for w in r.warnings)


def test_response_rate_rendah_menaikkan_target_dan_memperingatkan():
    r = sample_size(population=None, expected_response_rate=0.4, method=SamplingMethod.SRS)
    assert r.recommended_n > 1068
    assert any("bias non-respons" in w for w in r.warnings)


def test_margin_dan_n_saling_konsisten():
    n = sample_size(population=None, margin_of_error=0.03, method=SamplingMethod.SRS).base_n
    assert margin_from_n(n) == pytest.approx(0.03, abs=0.001)


def test_strata_kosong_dilaporkan():
    rep = stratum_balance({"jawa": 500}, {"jawa": 0.6, "luar_jawa": 0.4}, target_n=800)
    assert any("tanpa responden" in w for w in rep.warnings)
    assert rep.achieved_n == 500
