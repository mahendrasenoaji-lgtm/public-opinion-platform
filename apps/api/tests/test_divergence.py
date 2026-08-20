import pytest

from app.services.divergence import SignalReading, analyse, NOTABLE_GAP
from app.services.poi import SignalSource


def reading(source, value, n=5000, method="synthetic", bias="none"):
    return SignalReading(source=source, value=value, n=n, method=method, known_bias=bias)


def test_selisih_besar_ditandai_notable():
    readings = [
        reading(SignalSource.SURVEY, 68),
        reading(SignalSource.SOCIAL, 41),
    ]
    r = analyse(readings)
    assert r.is_notable is True
    assert r.gap == 27
    assert r.highest is SignalSource.SURVEY
    assert r.lowest is SignalSource.SOCIAL


def test_selisih_kecil_bukan_notable():
    readings = [
        reading(SignalSource.SURVEY, 68),
        reading(SignalSource.MEDIA, 60),
    ]
    r = analyse(readings)
    assert r.is_notable is False
    assert r.gap == 8


def test_tepat_di_batas_notable():
    readings = [
        reading(SignalSource.SURVEY, NOTABLE_GAP),
        reading(SignalSource.SOCIAL, 0),
    ]
    r = analyse(readings)
    assert r.is_notable is True
    assert r.gap == NOTABLE_GAP


def test_satu_sumber_ditolak():
    with pytest.raises(ValueError, match="minimal dua"):
        analyse([reading(SignalSource.SURVEY, 68)])


def test_tiga_sumber_menghasilkan_penjelasan_lengkap():
    readings = [
        reading(SignalSource.SURVEY, 72),
        reading(SignalSource.SOCIAL, 48),
        reading(SignalSource.MEDIA, 60),
    ]
    r = analyse(readings)
    assert r.gap == 24
    factors = [e["factor"] for e in r.explanations]
    assert "Self-selection" in factors
    assert "Framing media" in factors


def test_sampel_kecil_survei_menambah_limitations():
    readings = [
        reading(SignalSource.SURVEY, 68, n=300),
        reading(SignalSource.SOCIAL, 55),
    ]
    r = analyse(readings)
    assert any("galat sampling" in lim for lim in r.limitations)


def test_sampel_besar_tidak_menambah_limitations_tambahan():
    readings = [
        reading(SignalSource.SURVEY, 68, n=5000),
        reading(SignalSource.SOCIAL, 55),
    ]
    r = analyse(readings)
    assert not any("galat sampling" in lim for lim in r.limitations)


def test_limitations_selalu_berisi_peringatan_dasar():
    readings = [
        reading(SignalSource.SURVEY, 50),
        reading(SignalSource.SOCIAL, 50),
    ]
    r = analyse(readings)
    assert len(r.limitations) >= 2
    assert any("self-selected" in lim.lower() or "populasi" in lim.lower() for lim in r.limitations)
