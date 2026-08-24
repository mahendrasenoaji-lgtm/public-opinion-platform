"""Unit tests for services/weighting.py — raking (post-stratification)."""

import pytest

from app.services.weighting import rake_weights


def _respondents(gender_counts: dict[str, int]) -> dict[str, dict[str, str | None]]:
    """Bangun dict responden sintetis: {"r0": {"gender": "L"}, ...}."""
    out: dict[str, dict[str, str | None]] = {}
    i = 0
    for gender, count in gender_counts.items():
        for _ in range(count):
            out[f"r{i}"] = {"gender": gender}
            i += 1
    return out


def test_respondents_kosong_ditolak():
    with pytest.raises(ValueError, match="respondents tidak boleh kosong"):
        rake_weights({}, {"gender": {"L": 0.5, "P": 0.5}})


def test_targets_kosong_ditolak():
    with pytest.raises(ValueError, match="targets tidak boleh kosong"):
        rake_weights({"r0": {"gender": "L"}}, {})


def test_variabel_tidak_dikenal_ditolak():
    with pytest.raises(ValueError, match="tidak dikenal"):
        rake_weights({"r0": {"agama": "X"}}, {"agama": {"X": 1.0}})


def test_target_tidak_berjumlah_satu_ditolak():
    with pytest.raises(ValueError, match="berjumlah"):
        rake_weights({"r0": {"gender": "L"}}, {"gender": {"L": 0.3, "P": 0.3}})


def test_sampel_seimbang_bobot_mendekati_satu():
    respondents = _respondents({"L": 50, "P": 50})
    result = rake_weights(respondents, {"gender": {"L": 0.5, "P": 0.5}})
    assert result.converged is True
    assert result.iterations == 1
    for w in result.weights.values():
        assert abs(w - 1.0) < 0.01


def test_sampel_timpang_bobot_menyesuaikan():
    # 80 laki-laki, 20 perempuan di sampel; target populasi 50/50.
    respondents = _respondents({"L": 80, "P": 20})
    result = rake_weights(respondents, {"gender": {"L": 0.5, "P": 0.5}})

    l_weight = next(w for rid, w in result.weights.items() if respondents[rid]["gender"] == "L")
    p_weight = next(w for rid, w in result.weights.items() if respondents[rid]["gender"] == "P")

    # Kelompok under-represented (P) harus dapat bobot lebih besar dari yang
    # over-represented (L).
    assert p_weight > 1.0
    assert l_weight < 1.0
    assert p_weight > l_weight


def test_dua_variabel_konvergen():
    respondents: dict[str, dict[str, str | None]] = {}
    i = 0
    # Sampel dengan korelasi antara gender dan age_band supaya raking dua
    # variabel benar-benar diuji, bukan cuma satu variabel dominan.
    for gender, age, count in [
        ("L", "muda", 60),
        ("L", "tua", 10),
        ("P", "muda", 10),
        ("P", "tua", 20),
    ]:
        for _ in range(count):
            respondents[f"r{i}"] = {"gender": gender, "age_band": age}
            i += 1

    result = rake_weights(
        respondents,
        {"gender": {"L": 0.5, "P": 0.5}, "age_band": {"muda": 0.5, "tua": 0.5}},
        max_iterations=50,
    )
    assert result.converged is True

    total_w = sum(result.weights.values())
    gender_l_share = (
        sum(w for rid, w in result.weights.items() if respondents[rid]["gender"] == "L") / total_w
    )
    age_muda_share = (
        sum(w for rid, w in result.weights.items() if respondents[rid]["age_band"] == "muda")
        / total_w
    )

    assert abs(gender_l_share - 0.5) < 0.01
    assert abs(age_muda_share - 0.5) < 0.01


def test_kategori_tanpa_target_diabaikan_dengan_peringatan():
    respondents = {"r0": {"gender": "L"}, "r1": {"gender": "P"}, "r2": {"gender": "X"}}
    result = rake_weights(respondents, {"gender": {"L": 0.5, "P": 0.5}})
    assert any("diabaikan dari raking" in w for w in result.warnings)


def test_kategori_target_tanpa_responden_diberi_peringatan():
    respondents = {"r0": {"gender": "L"}, "r1": {"gender": "L"}}
    result = rake_weights(respondents, {"gender": {"L": 0.9, "P": 0.1}})
    assert any("tanpa responden sama sekali" in w for w in result.warnings)


def test_pemangkasan_bobot_ekstrem():
    # 1 responden perempuan dari 100 harus mewakili 50% populasi tertimbang —
    # bobot mentahnya akan meledak jauh di atas 3x median dan wajib dipangkas.
    respondents = _respondents({"L": 99, "P": 1})
    result = rake_weights(respondents, {"gender": {"L": 0.5, "P": 0.5}}, trim_ratio=3.0)
    assert result.trimmed_count > 0
    assert any("dipangkas" in w for w in result.warnings)


def test_bobot_rata_rata_selalu_satu():
    respondents = _respondents({"L": 80, "P": 20})
    result = rake_weights(respondents, {"gender": {"L": 0.5, "P": 0.5}})
    mean_w = sum(result.weights.values()) / len(result.weights)
    assert abs(mean_w - 1.0) < 1e-6


def test_tidak_konvergen_masih_mengembalikan_hasil():
    respondents: dict[str, dict[str, str | None]] = {}
    i = 0
    for gender, age, count in [
        ("L", "muda", 70),
        ("L", "tua", 5),
        ("P", "muda", 5),
        ("P", "tua", 20),
    ]:
        for _ in range(count):
            respondents[f"r{i}"] = {"gender": gender, "age_band": age}
            i += 1

    result = rake_weights(
        respondents,
        {"gender": {"L": 0.5, "P": 0.5}, "age_band": {"muda": 0.5, "tua": 0.5}},
        max_iterations=1,
    )
    assert result.converged is False
    assert len(result.weights) == len(respondents)
    assert any("tidak konvergen" in w for w in result.warnings)


def test_nilai_kategori_none_tidak_meledak():
    respondents = {"r0": {"gender": "L"}, "r1": {"gender": None}, "r2": {"gender": "P"}}
    result = rake_weights(respondents, {"gender": {"L": 0.5, "P": 0.5}})
    assert len(result.weights) == 3
