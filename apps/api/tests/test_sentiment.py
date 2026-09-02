"""Tes sentiment Indonesia — fungsi murni, tanpa database.

Ambang di kelas TestEvaluasi sengaja ditulis sebagai LANTAI, bukan nilai
persis: menambah satu kata ke leksikon tidak boleh memerahkan suite, tapi
penurunan mutu yang sesungguhnya harus tertangkap.
"""

from __future__ import annotations

import pytest

from app.services.sentiment import (
    aggregate,
    emotions,
    evaluate,
    label_for,
    score,
)
from app.services.sentiment_eval import LABELED


class TestSkorDasar:
    def test_kalimat_positif(self) -> None:
        r = score("Programnya sangat membantu dan bermanfaat")
        assert r.score is not None and r.score > 0
        assert r.label == "positif"

    def test_kalimat_negatif(self) -> None:
        r = score("Pelayanannya buruk dan mengecewakan")
        assert r.score is not None and r.score < 0
        assert r.label == "negatif"

    def test_tanpa_kata_leksikon_abstain_bukan_netral(self) -> None:
        r = score("Rapat dijadwalkan hari Kamis pukul sembilan")
        assert r.score is None
        assert r.abstained
        assert r.label == "tidak dinilai"

    def test_matched_bisa_ditelusuri(self) -> None:
        r = score("Programnya bagus")
        assert [w for w, _ in r.matched] == ["bagus"]


class TestKataAmbigu:
    """Regresi dari verifikasi terhadap feed RSS media sungguhan (2026-09-02).

    "asal" sempat ada di leksikon negatif (arti "asal-asalan", ceroboh), tapi
    di 215 artikel media nyata yang ditarik lewat RSSConnector, satu-satunya
    kemunculan token itu (2 dari 2) adalah arti "berasal dari"/"asal negara-X"
    yang netral — bukan arti "ceroboh". Dihapus dari leksikon karena itu.
    """

    def test_asal_negara_tidak_lagi_dianggap_negatif(self) -> None:
        r = score("Aktor asal Inggris Raya bergabung dalam film itu")
        assert r.abstained, "'asal' (arti 'dari') tidak boleh memicu skor apa pun"


class TestNegasi:
    def test_negasi_membalik_polaritas(self) -> None:
        positif = score("pelayanannya bagus")
        negasi = score("pelayanannya tidak bagus")
        assert positif.score is not None and negasi.score is not None
        assert positif.score > 0 > negasi.score

    def test_negasi_lebih_lemah_dari_lawan_katanya(self) -> None:
        """"tidak bagus" adalah keluhan yang diperhalus, bukan "buruk"."""
        negasi = score("pelayanannya tidak bagus")
        langsung = score("pelayanannya buruk")
        assert negasi.score is not None and langsung.score is not None
        assert langsung.score < negasi.score < 0

    def test_negasi_berhenti_di_batas_klausa(self) -> None:
        """Regresi: "tidak" di klausa pertama tidak boleh membalik klausa kedua."""
        r = score("sistemnya tidak ribet malah cepat")
        assert r.score is not None and r.score > 0

    def test_bentuk_tidak_baku_dikenali(self) -> None:
        r = score("sistem barunya nggak membantu")
        assert r.score is not None and r.score < 0


class TestPenguat:
    def test_penguat_sebelum_kata(self) -> None:
        biasa = score("hasilnya bagus")
        kuat = score("hasilnya sangat bagus")
        assert biasa.score is not None and kuat.score is not None
        assert kuat.score > biasa.score

    def test_penguat_sesudah_kata(self) -> None:
        biasa = score("hasilnya bagus")
        kuat = score("hasilnya bagus sekali")
        assert biasa.score is not None and kuat.score is not None
        assert kuat.score > biasa.score

    def test_pelemah_menurunkan(self) -> None:
        biasa = score("hasilnya bagus")
        lemah = score("hasilnya agak bagus")
        assert biasa.score is not None and lemah.score is not None
        assert 0 < lemah.score < biasa.score


class TestConfidence:
    def test_penanda_bertentangan_menurunkan_keyakinan(self) -> None:
        searah = score("bagus baik mantap")
        campur = score("bagus tapi buruk")
        assert searah.confidence > campur.confidence

    def test_lebih_banyak_bukti_lebih_yakin(self) -> None:
        satu = score("programnya bagus")
        tiga = score("programnya bagus bermanfaat dan adil")
        assert tiga.confidence > satu.confidence


class TestLabelFor:
    @pytest.mark.parametrize(
        ("nilai", "harapan"),
        [(0.9, "positif"), (0.16, "positif"), (0.0, "netral"), (-0.1, "netral"), (-0.9, "negatif")],
    )
    def test_ambang(self, nilai: float, harapan: str) -> None:
        assert label_for(nilai) == harapan


class TestEmosi:
    def test_penanda_ditemukan(self) -> None:
        e = emotions("saya marah dan kesal dengan layanan ini")
        assert e.get("anger", 0) > 0

    def test_tanpa_penanda_kosong_bukan_nol_semua(self) -> None:
        assert emotions("rapat dijadwalkan hari kamis") == {}

    def test_proporsi_berjumlah_satu(self) -> None:
        e = emotions("saya marah dan juga takut")
        assert sum(e.values()) == pytest.approx(1.0, abs=1e-3)


class TestAggregate:
    def test_abstain_tidak_dihitung_sebagai_netral(self) -> None:
        hasil = aggregate([score("bagus sekali"), score("rapat hari kamis")])
        assert hasil["n"] == 2
        assert hasil["n_scored"] == 1
        assert hasil["abstain_rate"] == 0.5

    def test_semua_abstain_mean_none(self) -> None:
        hasil = aggregate([score("rapat hari kamis"), score("formulirnya diunduh")])
        assert hasil["mean"] is None
        assert hasil["abstain_rate"] == 1.0

    def test_kosong_aman(self) -> None:
        hasil = aggregate([])
        assert hasil["n"] == 0 and hasil["mean"] is None


class TestEvaluasi:
    """Roadmap mewajibkan set evaluasi berlabel sebelum fitur ini dipakai."""

    def test_set_evaluasi_punya_ketiga_kelas(self) -> None:
        labels = {lbl for _, lbl in LABELED}
        assert labels == {"positif", "netral", "negatif"}

    def test_mutu_di_atas_lantai_yang_ditetapkan(self) -> None:
        r = evaluate(LABELED)
        # Lantai, bukan nilai persis — lihat docstring modul.
        assert r.macro_f1 >= 0.80, f"macro F1 turun ke {r.macro_f1}"
        assert r.accuracy_scored_only >= 0.80, f"akurasi turun ke {r.accuracy_scored_only}"

    def test_abstain_terutama_pada_kalimat_netral(self) -> None:
        """Abstain di kalimat bermuatan adalah kebutaan; di kalimat faktual bukan."""
        r = evaluate(LABELED)
        bermuatan = r.abstain_by_class["positif"] + r.abstain_by_class["negatif"]
        assert bermuatan <= 2, f"terlalu banyak abstain di kalimat bermuatan: {bermuatan}"

    def test_abstain_dihitung_salah_pada_akurasi_ketat(self) -> None:
        """Akurasi ketat tidak boleh bisa dinaikkan dengan lebih sering menyerah."""
        r = evaluate(LABELED)
        assert r.accuracy < r.accuracy_scored_only
        assert r.n_scored < r.n

    def test_caveat_ikut_dilaporkan(self) -> None:
        r = evaluate(LABELED)
        assert "bukan sampel acak" in r.caveat

    def test_label_asing_ditolak(self) -> None:
        with pytest.raises(ValueError, match="label tidak dikenal"):
            evaluate([("apa saja", "campuran")])
