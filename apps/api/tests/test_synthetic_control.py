"""Tes synthetic control — fungsi murni, tanpa database.

Sama seperti test_impact.py untuk DiD, yang terpenting bukan yang
memverifikasi aritmetikanya, melainkan yang memverifikasi PENOLAKANNYA:
donor kurang, periode pra-perlakuan tidak cukup melebihi jumlah donor, dan
kecocokan pra-perlakuan yang buruk.
"""

from __future__ import annotations

import pytest

from app.services.impact import MIN_DONORS, synthetic_control


def _donor_pool(
    n: int, n_pre: int, *, base: float = 10.0, step: float = 0.5
) -> dict[str, list[float]]:
    return {f"d{i}": [base + i * step] * n_pre for i in range(n)}


class TestGating:
    def test_donor_kurang_dari_minimum_ditolak(self) -> None:
        donors = _donor_pool(MIN_DONORS - 1, n_pre=10)
        r = synthetic_control(
            treated_pre=[10.0] * 10,
            treated_post=12.0,
            donors_pre=donors,
            donors_post=dict.fromkeys(donors, 10.0),
        )
        assert r.insufficient_data
        assert r.effect is None
        assert str(MIN_DONORS - 1) in r.note

    def test_periode_pra_tidak_lebih_banyak_dari_donor_ditolak(self) -> None:
        """Donor >= periode -> optimasi bisa overfit sempurna tanpa berarti apa-apa."""
        n_donors = 6
        donors = _donor_pool(n_donors, n_pre=n_donors)  # persis sama, bukan lebih
        r = synthetic_control(
            treated_pre=[10.0] * n_donors,
            treated_post=12.0,
            donors_pre=donors,
            donors_post=dict.fromkeys(donors, 10.0),
        )
        assert r.insufficient_data
        assert "overfit" in r.note.lower()

    def test_tepat_di_atas_ambang_diterima(self) -> None:
        n_donors = MIN_DONORS
        donors = _donor_pool(n_donors, n_pre=n_donors + 1)
        r = synthetic_control(
            treated_pre=[10.0] * (n_donors + 1),
            treated_post=12.0,
            donors_pre=donors,
            donors_post=dict.fromkeys(donors, 10.0),
        )
        assert not r.insufficient_data

    def test_donor_pre_dan_post_harus_unit_yang_sama(self) -> None:
        donors_pre = _donor_pool(MIN_DONORS, n_pre=10)
        donors_post = {f"beda{i}": 10.0 for i in range(MIN_DONORS)}
        with pytest.raises(ValueError, match="sama persis"):
            synthetic_control(
                treated_pre=[10.0] * 10,
                treated_post=12.0,
                donors_pre=donors_pre,
                donors_post=donors_post,
            )

    def test_panjang_deret_donor_tidak_konsisten_ditolak(self) -> None:
        donors_pre = _donor_pool(MIN_DONORS, n_pre=10)
        donors_pre["d0"] = donors_pre["d0"][:-1]  # satu donor lebih pendek
        with pytest.raises(ValueError, match="jumlah periode"):
            synthetic_control(
                treated_pre=[10.0] * 10,
                treated_post=12.0,
                donors_pre=donors_pre,
                donors_post=dict.fromkeys(donors_pre, 10.0),
            )


class TestEstimasi:
    def _kasus_bobot_diketahui(self) -> dict:
        """Treated_pre adalah kombinasi PERSIS 0.5*d0 + 0.3*d1 + 0.2*d2, plus
        tiga donor lain yang tidak relevan -- solver harus menemukan bobot
        itu kembali dan mengabaikan yang tidak relevan."""
        n_pre = 8
        donors_pre = {
            "d0": [10.0, 10.5, 10.2, 10.8, 10.3, 10.6, 10.1, 10.7],
            "d1": [11.0, 11.3, 11.1, 11.4, 11.2, 11.5, 11.0, 11.3],
            "d2": [9.0, 9.2, 9.1, 9.4, 9.3, 9.5, 9.2, 9.4],
            "d3": [20.0] * n_pre,  # jelas tidak relevan
            "d4": [5.0] * n_pre,  # jelas tidak relevan
        }
        weights = {"d0": 0.5, "d1": 0.3, "d2": 0.2, "d3": 0.0, "d4": 0.0}
        treated_pre = [
            sum(weights[k] * donors_pre[k][t] for k in donors_pre) for t in range(n_pre)
        ]
        donors_post = {"d0": 12.0, "d1": 13.0, "d2": 11.0, "d3": 20.0, "d4": 5.0}
        synthetic_post = sum(weights[k] * donors_post[k] for k in donors_post)
        return {
            "donors_pre": donors_pre,
            "treated_pre": treated_pre,
            "donors_post": donors_post,
            "synthetic_post_true": synthetic_post,
        }

    def test_bobot_pulih_dengan_benar(self) -> None:
        kasus = self._kasus_bobot_diketahui()
        r = synthetic_control(
            treated_pre=kasus["treated_pre"],
            treated_post=kasus["synthetic_post_true"] + 5.0,
            donors_pre=kasus["donors_pre"],
            donors_post=kasus["donors_post"],
        )
        assert r.weights.get("d0", 0) == pytest.approx(0.5, abs=0.02)
        assert r.weights.get("d1", 0) == pytest.approx(0.3, abs=0.02)
        assert r.weights.get("d2", 0) == pytest.approx(0.2, abs=0.02)
        # donor yang jelas tidak relevan tidak boleh dapat bobot berarti
        assert r.weights.get("d3", 0) < 0.02
        assert r.weights.get("d4", 0) < 0.02

    def test_efek_terdeteksi_akurat_saat_fit_sempurna(self) -> None:
        kasus = self._kasus_bobot_diketahui()
        r = synthetic_control(
            treated_pre=kasus["treated_pre"],
            treated_post=kasus["synthetic_post_true"] + 5.0,
            donors_pre=kasus["donors_pre"],
            donors_post=kasus["donors_post"],
        )
        assert r.effect == pytest.approx(5.0, abs=0.05)
        assert r.fit_quality_ok is True

    def test_tanpa_efek_menghasilkan_dekat_nol(self) -> None:
        kasus = self._kasus_bobot_diketahui()
        r = synthetic_control(
            treated_pre=kasus["treated_pre"],
            treated_post=kasus["synthetic_post_true"],
            donors_pre=kasus["donors_pre"],
            donors_post=kasus["donors_post"],
        )
        assert r.effect == pytest.approx(0.0, abs=0.05)

    def test_bobot_hanya_menyertakan_yang_lebih_dari_nol(self) -> None:
        kasus = self._kasus_bobot_diketahui()
        r = synthetic_control(
            treated_pre=kasus["treated_pre"],
            treated_post=kasus["synthetic_post_true"],
            donors_pre=kasus["donors_pre"],
            donors_post=kasus["donors_post"],
        )
        assert set(r.weights) <= {"d0", "d1", "d2"}

    def test_bobot_berjumlah_satu(self) -> None:
        kasus = self._kasus_bobot_diketahui()
        r = synthetic_control(
            treated_pre=kasus["treated_pre"],
            treated_post=kasus["synthetic_post_true"],
            donors_pre=kasus["donors_pre"],
            donors_post=kasus["donors_post"],
        )
        # bobot yang tersimpan sudah dibulatkan & disaring (>1e-4) -- jumlahnya
        # boleh sedikit meleset dari 1.0 karena pembulatan, bukan karena solver
        assert sum(r.weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_deterministik(self) -> None:
        kasus = self._kasus_bobot_diketahui()
        a = synthetic_control(
            treated_pre=kasus["treated_pre"], treated_post=100.0,
            donors_pre=kasus["donors_pre"], donors_post=kasus["donors_post"],
        )
        b = synthetic_control(
            treated_pre=kasus["treated_pre"], treated_post=100.0,
            donors_pre=kasus["donors_pre"], donors_post=kasus["donors_post"],
        )
        assert a.weights == b.weights
        assert a.effect == b.effect


class TestKecocokanBuruk:
    def test_fit_buruk_menurunkan_fit_quality_ok(self) -> None:
        """Donor yang sama sekali tidak mirip -> RMSPE besar -> fit_quality_ok False."""
        donors_pre = {
            "d0": [1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0],
            "d1": [3.0, 1.0, 3.0, 1.0, 3.0, 1.0, 3.0, 1.0],
            "d2": [2.0, 3.0, 2.0, 3.0, 2.0, 3.0, 2.0, 3.0],
            "d3": [1.0, 3.0, 1.0, 3.0, 1.0, 3.0, 1.0, 3.0],
            "d4": [3.0, 2.0, 3.0, 2.0, 3.0, 2.0, 3.0, 2.0],
        }
        # treated_pre jauh berbeda pola dan skalanya dari semua donor
        treated_pre = [100.0, 5.0, 95.0, 10.0, 90.0, 15.0, 85.0, 20.0]
        r = synthetic_control(
            treated_pre=treated_pre,
            treated_post=50.0,
            donors_pre=donors_pre,
            donors_post=dict.fromkeys(donors_pre, 2.0),
        )
        assert r.fit_quality_ok is False
        assert any("tidak boleh ditafsirkan" in x for x in r.limitations)

    def test_note_menyebut_kecocokan_buruk(self) -> None:
        donors_pre = {f"d{i}": [float(i)] * 8 for i in range(5)}
        r = synthetic_control(
            treated_pre=[100.0, 0.0, 100.0, 0.0, 100.0, 0.0, 100.0, 0.0],
            treated_post=50.0,
            donors_pre=donors_pre,
            donors_post=dict.fromkeys(donors_pre, 2.0),
        )
        if not r.fit_quality_ok:
            assert r.note is not None and "buruk" in r.note.lower()


class TestPlacebo:
    def test_placebo_dihitung_untuk_tiap_donor(self) -> None:
        n_donors = 6
        donors_pre = _donor_pool(n_donors, n_pre=8)
        r = synthetic_control(
            treated_pre=[10.0] * 8,
            treated_post=10.0,
            donors_pre=donors_pre,
            donors_post=dict.fromkeys(donors_pre, 10.0),
        )
        assert len(r.placebo_effects) == n_donors

    def test_rank_p_value_berada_di_rentang_valid(self) -> None:
        kasus = TestEstimasi()._kasus_bobot_diketahui()
        r = synthetic_control(
            treated_pre=kasus["treated_pre"],
            treated_post=kasus["synthetic_post_true"] + 5.0,
            donors_pre=kasus["donors_pre"],
            donors_post=kasus["donors_post"],
        )
        assert r.rank_p_value is not None
        assert 0.0 < r.rank_p_value <= 1.0

    def test_efek_besar_menghasilkan_rank_p_kecil(self) -> None:
        """Efek yang jauh lebih besar dari semua placebo -> rank_p rendah,
        efek yang sepadan dengan variasi placebo -> rank_p lebih besar."""
        kasus = TestEstimasi()._kasus_bobot_diketahui()
        efek_besar = synthetic_control(
            treated_pre=kasus["treated_pre"],
            treated_post=kasus["synthetic_post_true"] + 50.0,
            donors_pre=kasus["donors_pre"],
            donors_post=kasus["donors_post"],
        )
        efek_kecil = synthetic_control(
            treated_pre=kasus["treated_pre"],
            treated_post=kasus["synthetic_post_true"] + 0.01,
            donors_pre=kasus["donors_pre"],
            donors_post=kasus["donors_post"],
        )
        assert efek_besar.rank_p_value <= efek_kecil.rank_p_value


class TestKontrak:
    def test_metode_menyebut_synthetic_control_untuk_envelope(self) -> None:
        """app/ai/envelope.py:_has_causal_design() mencari kata ini di method."""
        donors_pre = _donor_pool(MIN_DONORS, n_pre=8)
        r = synthetic_control(
            treated_pre=[10.0] * 8,
            treated_post=10.0,
            donors_pre=donors_pre,
            donors_post=dict.fromkeys(donors_pre, 10.0),
        )
        assert "synthetic control" in r.method.lower()

    def test_batasan_selalu_disertakan(self) -> None:
        donors_pre = _donor_pool(MIN_DONORS, n_pre=8)
        r = synthetic_control(
            treated_pre=[10.0] * 8,
            treated_post=10.0,
            donors_pre=donors_pre,
            donors_post=dict.fromkeys(donors_pre, 10.0),
        )
        assert any("unit sintetis" in x.lower() for x in r.limitations)
        assert any("permutasi" in x.lower() for x in r.limitations)
