import pytest

from app.services.forecast import (
    DEFAULT_SPREAD,
    Driver,
    project,
)

SPREAD = DEFAULT_SPREAD


def test_baseline_tanpa_skenario_tidak_bergerak():
    r = project(baseline=70, base_spread=SPREAD)
    assert r.is_simulation is False
    assert r.scenario == {}
    for pt in r.points:
        assert pt.expected == 70


def test_skenario_positif_menaikkan_expected():
    r = project(baseline=70, base_spread=SPREAD, scenario={"food_price": -3})
    # food_price coeff = -0.72, jadi -3 × -0.72 = +2.16 efek positif
    last = r.points[-1]
    assert last.expected > 70
    assert r.is_simulation is True
    assert "simulasi" in r.limitations[0].lower()


def test_skenario_negatif_menurunkan_expected():
    r = project(baseline=70, base_spread=SPREAD, scenario={"food_price": 5})
    last = r.points[-1]
    assert last.expected < 70


def test_interval_melebar_dengan_skenario():
    tanpa = project(baseline=70, base_spread=SPREAD)
    dengan = project(baseline=70, base_spread=SPREAD, scenario={"food_price": 5})
    # Pada horizon terjauh, interval harus lebih lebar
    last_tanpa = tanpa.points[-1]
    last_dengan = dengan.points[-1]
    width_tanpa = last_tanpa.pi_high - last_tanpa.pi_low
    width_dengan = last_dengan.pi_high - last_dengan.pi_low
    assert width_dengan > width_tanpa


def test_interval_tidak_menyempit_dengan_skenario_ekstrem():
    # Prinsip kunci: skenario lebih ekstrem → tahu lebih sedikit.
    mild = project(baseline=70, base_spread=SPREAD, scenario={"food_price": 2})
    extreme = project(baseline=70, base_spread=SPREAD, scenario={"food_price": 10})
    last_mild = mild.points[-1]
    last_extreme = extreme.points[-1]
    assert (last_extreme.pi_high - last_extreme.pi_low) >= (last_mild.pi_high - last_mild.pi_low)


def test_driver_tidak_dikenal_ditolak():
    with pytest.raises(ValueError, match="driver tidak dikenal"):
        project(baseline=70, base_spread=SPREAD, scenario={"nonexistent": 5})


def test_expected_terklem_ke_0_100():
    # Driver besar ke arah negatif → pi_low tidak boleh di bawah 0
    r = project(baseline=5, base_spread=SPREAD, scenario={"food_price": 30})
    for pt in r.points:
        assert pt.pi_low >= 0
        assert pt.pi_high <= 100


def test_ramp_efek_bertahap():
    r = project(baseline=70, base_spread=SPREAD, scenario={"food_price": 5})
    # Pada horizon pertama efek lebih kecil dari horizon terakhir
    assert abs(r.points[0].expected - 70) <= abs(r.points[-1].expected - 70)


def test_skenario_nol_sama_dengan_tanpa_skenario():
    tanpa = project(baseline=70, base_spread=SPREAD)
    dengan = project(baseline=70, base_spread=SPREAD, scenario={"food_price": 0})
    for a, b in zip(tanpa.points, dengan.points, strict=True):
        assert a.expected == b.expected


def test_driver_contributions_dilaporkan():
    r = project(baseline=70, base_spread=SPREAD, scenario={"food_price": 5})
    assert len(r.driver_contributions) == 1
    assert r.driver_contributions[0]["driver"] == "Kenaikan harga pangan"
    assert r.driver_contributions[0]["effect_at_max_horizon"] == round(-0.72 * 5, 2)


def test_custom_drivers():
    custom = [Driver("x", "X factor", 1.0, "unit", 0.1)]
    r = project(
        baseline=50,
        base_spread={1: 1, 7: 3},
        scenario={"x": 10},
        drivers=custom,
    )
    last = r.points[-1]
    assert last.expected == 60
    assert r.is_simulation is True


def test_limitations_selalu_ada():
    r = project(baseline=70, base_spread=SPREAD)
    assert len(r.limitations) >= 2
