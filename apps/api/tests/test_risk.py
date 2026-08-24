import pytest

from app.services.risk import (
    DEFAULT_RISK_WEIGHTS,
    band_for,
    polarization,
    risk_score,
)


def full_components(value: float = 50) -> dict[str, float]:
    return {k: value for k in DEFAULT_RISK_WEIGHTS}


def test_semua_nol_menghasilkan_low():
    r = risk_score(full_components(0))
    assert r.score == 0
    assert r.band == "Low"


def test_semua_seratus_menghasilkan_critical():
    r = risk_score(full_components(100))
    assert r.score == 100
    assert r.band == "Critical"


def test_semua_lima_puluh_menghasilkan_moderate_atau_elevated():
    r = risk_score(full_components(50))
    assert r.band in ("Moderate", "Elevated")


def test_komponen_kurang_ditolak():
    incomplete = {"negative_sentiment": 80, "sentiment_velocity": 60}
    with pytest.raises(ValueError, match="komponen risiko belum lengkap"):
        risk_score(incomplete)


def test_top_contributors_maksimal_tiga():
    r = risk_score(full_components(50))
    assert len(r.top_contributors) <= 3


def test_top_contributors_terurut_menurun():
    comps = full_components(0)
    comps["negative_sentiment"] = 100
    comps["sentiment_velocity"] = 80
    comps["issue_growth"] = 60
    r = risk_score(comps)
    values = [v for _, v in r.top_contributors]
    assert values == sorted(values, reverse=True)


def test_bobot_custom_diterima():
    custom_w = {"a": 0.5, "b": 0.5}
    comps = {"a": 80, "b": 20}
    r = risk_score(comps, weights=custom_w)
    assert r.score == 50
    assert r.weights == custom_w


def test_band_for_semua_rentang():
    assert band_for(0) == "Low"
    assert band_for(20) == "Low"
    assert band_for(21) == "Moderate"
    assert band_for(40) == "Moderate"
    assert band_for(41) == "Elevated"
    assert band_for(60) == "Elevated"
    assert band_for(61) == "High"
    assert band_for(80) == "High"
    assert band_for(81) == "Critical"
    assert band_for(100) == "Critical"


def test_band_for_di_atas_seratus_fallback_critical():
    assert band_for(150) == "Critical"


# === Polarization ===


def test_konsensus_kuat():
    segments = [
        ("muda", 5, 0.3),
        ("tengah", 3, 0.4),
        ("tua", 8, 0.3),
    ]
    r = polarization(segments)
    assert r["state"] == "menuju konsensus"
    assert r["polarization_score"] < 30


def test_terpolarisasi_dua_kutub():
    segments = [
        ("pro", 70, 0.45),
        ("kontra", -60, 0.45),
        ("netral", 0, 0.10),
    ]
    r = polarization(segments)
    assert r["state"] == "terpolarisasi"
    assert r["polarization_score"] > 50


def test_terfragmentasi():
    segments = [
        ("a", 50, 0.25),
        ("b", -30, 0.25),
        ("c", 10, 0.25),
        ("d", -5, 0.25),
    ]
    r = polarization(segments)
    assert r["state"] == "terfragmentasi"


def test_kurang_dari_dua_segmen_ditolak():
    with pytest.raises(ValueError, match="minimal dua"):
        polarization([("a", 10, 1.0)])


def test_metode_dan_limitations_selalu_ada():
    r = polarization([("a", 50, 0.5), ("b", -50, 0.5)])
    assert r["method"] != ""
    assert r["limitations"] != ""


def test_pole_mass_dan_middle_mass_masuk_akal():
    segments = [
        ("pro", 70, 0.5),
        ("kontra", -60, 0.3),
        ("netral", 0, 0.2),
    ]
    r = polarization(segments)
    assert 0 <= r["pole_mass"] <= 1
    assert 0 <= r["middle_mass"] <= 1
    # Segmen "netral" (posisi 0, abs<=20) termasuk middle
    assert r["middle_mass"] == 0.2
