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
from app.services.sentiment_eval_field import FIELD, evaluate_field, labeled


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

    def test_hebat_penguat_keparahan_tidak_lagi_dianggap_positif(self) -> None:
        """Regresi dari verifikasi production 2026-09-11 (445 item, 7 feed).

        "hebat" sempat ada di leksikon positif (arti pujian), tapi 3/3
        kemunculannya di media nyata adalah penguat keparahan di depan kata
        negatif ("kebakaran hebat", "muntah hebat") — 0/3 arti pujian.
        Dihapus dari leksikon karena itu, pola sama seperti "asal".
        """
        r = score("Kebakaran hebat melanda sekolah itu, beberapa korban tewas")
        assert r.abstained or (r.score is not None and r.score <= 0), (
            "'hebat' sebagai penguat keparahan tidak boleh mendorong skor positif"
        )


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


class TestRagamInformal:
    """Komentar media sosial. Contoh di sini diambil dari data lapangan."""

    def test_singkatan_dan_pemanjangan_tidak_lagi_abstain(self) -> None:
        for teks in ("Betuuuul sekaliiii bu", "Mksh Bu sdh mewakili kami", "GK becus"):
            assert score(teks).abstained, teks
            assert not score(teks, register="informal").abstained, teks

    def test_negator_singkat_membalik(self) -> None:
        r = score("pemerintah gk peduli", register="informal")
        assert r.label == "negatif"
        assert ("peduli", -0.525) in r.matched

    def test_tuntutan_penolakan_negatif(self) -> None:
        assert score("Bubarkan mbg.", register="informal").label == "negatif"
        assert score("Stop MBG", register="informal").label == "negatif"

    def test_larangan_tidak_membalik_kata_negatif(self) -> None:
        """"jangan ngeyel" menegur — bukan pujian."""
        assert score("prabowo dengarkan, jangan ngeyel aja", register="informal").label == "negatif"

    def test_negasi_berhenti_di_tanda_baca(self) -> None:
        """Negasi klausa pertama tidak boleh membalik tuntutan di klausa kedua."""
        r = score("GK becus, bubarkan aja", register="informal")
        assert ("bubarkan", -0.7) in r.matched
        assert r.label == "negatif"

    def test_label_konsisten_dengan_skor_yang_disimpan(self) -> None:
        """(0.9 - 0.6) / 2 adalah 0.15000000000000002 — tepat di ambang, bukan di atasnya."""
        r = score("Mantap Bu, tiap hari keracunan dimana mana", register="informal")
        assert r.score == 0.15
        assert r.label == label_for(r.score) == "netral"

    def test_penyangkalan_tetap_membalik(self) -> None:
        assert score("gak bodoh kok", register="informal").label == "positif"

    def test_emoji_dihitung_sekali_per_jenis(self) -> None:
        r = score("😡😡😡😡", register="informal")
        assert r.matched == [("😡", -0.8)]
        assert score("👍", register="informal").label == "positif"

    def test_emoji_ambigu_tetap_abstain(self) -> None:
        assert score("😂😂😂", register="informal").abstained

    def test_method_menyebut_ragamnya(self) -> None:
        assert "informal" in score("mantap", register="informal").method
        assert "informal" not in score("mantap").method


class TestRagamBakuTidakBergeser:
    """Deret sentimen MEDIA harus tetap sinambung dengan lexicon-id-1."""

    def test_kosakata_informal_tidak_bocor_ke_baku(self) -> None:
        # "hebat" dihapus dari leksikon baku 2026-09-11 (penguat keparahan di
        # judul berita); ia hanya boleh hidup di ragam informal.
        assert score("Kebakaran hebat melanda kantor").abstained
        assert score("Polisi hentikan pencarian").abstained
        assert score("Anjing pelacak dikerahkan").abstained

    def test_normalisasi_tidak_dipakai_di_baku(self) -> None:
        assert score("gk becus").abstained
        assert score("terima kasih").abstained

    def test_cakupan_set_internal_tidak_berubah(self) -> None:
        """Angka set internal untuk ragam baku tidak berubah oleh pekerjaan ini."""
        r = evaluate(LABELED)
        assert (r.n, r.n_scored) == (52, 39)


class TestSetLapangan:
    """Integritas set komentar nyata — lihat sentiment_eval_field.py."""

    def test_kedua_belahan_punya_ketiga_kelas(self) -> None:
        for split in ("kembang", "uji"):
            assert {lbl for _, lbl in labeled(split)} == {"positif", "netral", "negatif"}

    def test_belahan_ditentukan_hash_teks_bukan_dipilih(self) -> None:
        """Memindahkan satu komentar dari `uji` ke `kembang` harus memerahkan tes ini."""
        import hashlib

        for item in FIELD:
            first = int(hashlib.sha256(item.text.encode()).hexdigest()[0], 16)
            assert item.split == ("uji" if first < 8 else "kembang"), item.text[:40]

    def test_tidak_ada_identitas_akun(self) -> None:
        assert not any("@" in item.text for item in FIELD)
        assert len({item.text for item in FIELD}) == len(FIELD)

    def test_penanda_hanya_yang_didokumentasikan(self) -> None:
        assert all(set(item.flags) <= set("sdc") for item in FIELD)


class TestMutuLapangan:
    """Lantai pada belahan UJI. Angka persisnya ada di docs/progress.md."""

    def test_informal_jauh_di_atas_baku_pada_komentar_yang_sama(self) -> None:
        r = evaluate_field()
        assert r.informal.abstain_rate <= 0.35, r.informal.abstain_rate
        assert r.baseline.abstain_rate >= 0.65
        assert r.informal.macro_f1 >= 0.55, r.informal.macro_f1
        assert r.informal.macro_f1 >= r.baseline.macro_f1 + 0.20
        assert r.informal.accuracy >= 0.50, r.informal.accuracy

    def test_cakupan_naik_tanpa_mengorbankan_ketepatan(self) -> None:
        """Lebih sering bersuara tidak boleh dibayar dengan lebih sering salah."""
        r = evaluate_field()
        assert r.informal.accuracy_scored_only >= 0.72, r.informal.accuracy_scored_only
        assert r.informal.accuracy_scored_only >= r.baseline.accuracy_scored_only

    def test_nada_bukan_sikap_masih_berlaku(self) -> None:
        """Mengunci kalimat `_TONE_NOT_STANCE_LIMITATION` di routers/signals.py.

        Kalimat itu menyebut "hampir separuh". Kalau proporsinya keluar dari
        rentang ini, kalimatnya harus ikut disunting — bukan tesnya dilonggarkan.
        """
        r = evaluate_field()
        share = r.predicted_positive_supporting_critic / r.predicted_positive
        assert 0.40 <= share <= 0.55, share

    def test_sarkasme_tetap_batas_yang_diakui(self) -> None:
        """Bukan lantai mutu: mencatat bahwa leksikon TIDAK mengenali sarkasme.

        Sebagian komentar sarkastis tetap dinilai benar karena kata lain di
        kalimatnya ("program beracun"), bukan karena sarkasmenya terbaca. Kalau
        suatu hari SEMUANYA benar, peringatan di UI perlu ditinjau ulang.
        """
        r = evaluate_field()
        assert r.sarcasm_n >= 5
        assert r.sarcasm_correct < r.sarcasm_n
        sindiran = "Sukses pak dengan program beracunnya, bangga saya"
        assert score(sindiran, register="informal").label == "positif"

    def test_caveat_lapangan_menyebut_nada(self) -> None:
        assert "NADA" in evaluate_field().informal.caveat
