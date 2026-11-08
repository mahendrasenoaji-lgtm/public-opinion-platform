"""Tes kamus bahasa daerah (informal-3) — fungsi murni, tanpa database.

Contoh kalimat diambil dari komentar YouTube BBM Bali (proyek/bbm-bali-youtube)
kecuali yang ditandai buatan. Tes menjaga tiga hal: kata daerah tertangkap,
kata yang artinya berbeda antarbahasa TIDAK ikut masuk, dan ragam baku (media)
tidak bergeser.
"""

from __future__ import annotations

import pytest

from app.services import regional
from app.services.informal import PHRASES, SLANG
from app.services.sentiment import (
    INFORMAL_LEXICON,
    INFORMAL_MODEL_VERSION,
    LEXICON,
    MODEL_VERSION,
    score,
)


class TestStrukturKamus:
    def test_versi_dinaikkan(self) -> None:
        assert INFORMAL_MODEL_VERSION.startswith("lexicon-id-1+informal-")
        assert MODEL_VERSION == "lexicon-id-1"  # ragam baku tidak bergeser

    def test_kata_tidak_tercatat_di_dua_bahasa(self) -> None:
        """Satu kata satu asal: kalau dua bahasa memakainya, artinya harus diputuskan dulu."""
        seen: dict[str, str] = {}
        for language, words in regional.REGIONAL_LEXICON.items():
            for word in words:
                assert word not in seen, (word, seen.get(word), language)
                seen[word] = language

    def test_bobot_dalam_rentang_dan_tidak_nol(self) -> None:
        for words in regional.REGIONAL_LEXICON.values():
            for word, (weight, meaning) in words.items():
                assert 0 < abs(weight) <= 1, word
                assert meaning, word

    def test_tidak_membalik_tanda_kata_yang_sudah_ada(self) -> None:
        for word, weight in regional.lexicon().items():
            if word in LEXICON:
                assert (LEXICON[word] > 0) == (weight > 0), word

    def test_kata_yang_dikecualikan_tidak_masuk_lewat_jalur_mana_pun(self) -> None:
        for word in regional.EXCLUDED:
            assert word not in regional.lexicon(), word
            assert word not in regional.REGIONAL_MODIFIERS, word

    def test_pengubah_daerah_sampai_ke_normalisasi(self) -> None:
        for word, (target, _language) in regional.REGIONAL_MODIFIERS.items():
            assert SLANG[word] == target, word
            assert word not in regional.lexicon(), word
        for pair, joined in regional.REGIONAL_PHRASES.items():
            assert PHRASES[pair] == joined

    def test_asal_kata(self) -> None:
        assert regional.origin("naskleng") == "Bali"
        assert regional.origin("pekok") == "Jawa"
        assert regional.origin("bagus") is None


class TestKataDaerahTerbaca:
    @pytest.mark.parametrize(
        "teks",
        [
            "Gubernur NASKLENG",  # Bali
            "GUBERNUR BALI CICING",  # Bali
            "jeg keweh saan meli bensin jani.. WTF !!",  # Bali
            "Gubernur Koster Pekok dan Arogan.",  # Jawa
            "Dapuranmu ra tau melu antri kok sok tau kondisi di lapangan",  # Jawa
            "Pemerintah taek",  # Jawa, ejaan lain dari "tai"
            "gubernur gelo",  # Sunda
            "Gubernur dongo",  # Makassar
            "Sudah nyusahin rakyat pak",  # Betawi
            "Gubernur g pecus",  # ejaan "becus" + negasi
        ],
    )
    def test_terbaca_negatif(self, teks: str) -> None:
        r = score(teks, register="informal")
        assert not r.abstained, teks
        assert r.label == "negatif", (teks, r.score, r.matched)

    def test_komentar_contoh_pengguna(self) -> None:
        r = score(
            "heran.. makhluk rendahan ber-IQ primata model begitu kok bisa jadi gubernur. "
            "cuih menjijikan.",
            register="informal",
        )
        assert r.label == "negatif"
        assert [w for w, _ in r.matched] == ["cuih", "jijik"]

    @pytest.mark.parametrize(
        "teks",
        [
            "Gubernur ora becus",  # Jawa
            "pejabat teu becus",  # Sunda (buatan)
            "Pemerintah sudah dak becus kerja",  # Palembang/Melayu (buatan dari pola di data)
        ],
    )
    def test_negator_daerah_dikenali(self, teks: str) -> None:
        assert score(teks, register="informal").label == "negatif", teks

    def test_negator_daerah_membalik_seperti_tidak(self) -> None:
        assert score("pejabate tusing becus", register="informal").label == "negatif"
        assert score("pejabate tusing arogan", register="informal").label == "positif"

    def test_larangan_jawa_tidak_membalik_kata_negatif(self) -> None:
        assert score("ojo korupsi", register="informal").label == "negatif"

    def test_penguat_daerah(self) -> None:
        biasa = score("parah", register="informal").score
        medan = score("parah kali", register="informal").score
        jawa = score("ruwet tenan", register="informal").score
        assert biasa is not None and medan is not None and jawa is not None
        assert medan < biasa
        assert jawa < (score("ruwet", register="informal").score or 0)

    def test_frasa_terima_kasih_daerah(self) -> None:
        assert score("matur nuwun pak", register="informal").label == "positif"
        assert score("hatur nuhun", register="informal").label == "positif"


class TestKataBentrokTetapAbstain:
    @pytest.mark.parametrize(
        "teks",
        [
            "pejabat seng ngarai kisuruh",  # Jawa Timur "yang"
            "harga digoreng terus",  # buatan: "goreng" bukan "jelek"
            "orang lain juga antri",  # "lain" bukan "bukan"
            "antri aja dulu",  # "aja" = "saja"
            "pegawai rendahan",  # simpati, bukan cela
            "Kalo gubernur kdm merakyat",  # tuntutan/pembanding, dikecualikan
        ],
    )
    def test_abstain(self, teks: str) -> None:
        r = score(teks, register="informal")
        assert r.abstained, (teks, r.matched)

    def test_sing_tidak_membalik_pujian(self) -> None:
        # Buatan. Jawa: "yang penting tetap semangat".
        assert score("sing penting tetep semangat", register="informal").label == "positif"

    def test_sing_tidak_membalik_makian(self) -> None:
        # Buatan. Jawa: "yang bodoh itu". Kalau "sing" dibaca "tidak", ini jadi pujian.
        assert score("sing goblok iku", register="informal").label == "negatif"


class TestRagamBakuTidakTersentuh:
    @pytest.mark.parametrize("teks", ["Gubernur pekok", "ora becus", "parah kali", "naskleng"])
    def test_kata_daerah_hanya_untuk_ragam_informal(self, teks: str) -> None:
        baku = score(teks)
        assert "naskleng" not in LEXICON and "pekok" not in LEXICON
        assert all(w not in regional.lexicon() for w, _ in baku.matched), baku.matched

    def test_kamus_informal_memuat_semua_kata_daerah(self) -> None:
        for word in regional.lexicon():
            assert word in INFORMAL_LEXICON, word
