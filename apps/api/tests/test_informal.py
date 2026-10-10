"""Tes normalisasi ragam informal — fungsi murni, tanpa database."""

from __future__ import annotations

from app.services.informal import (
    CLAUSE_BOUNDARY,
    SLANG,
    canonical,
    canonical_tokens,
    emoji_marks,
    split_informal,
)

VOCAB = frozenset(
    ["tidak", "betul", "mantap", "sekali", "parah", "maaf", "terimakasih"]
    + ["omongkosong", "dukung", "terima", "kasih"]
)


class TestSplit:
    def test_huruf_berulang_dipangkas_jadi_dua_bukan_satu(self) -> None:
        # "maaaf" harus masih bisa jadi "maaf"; pemangkasan ke satu huruf
        # baru dicoba di canonical(), dan hanya kalau hasilnya dikenali.
        assert split_informal("maaaaf betuuuul") == ["maaf", "betuul"]

    def test_angka_dua_sebagai_tanda_ulang(self) -> None:
        assert split_informal("anak2 gara² anak2nya") == ["anak", "gara", "anak"]

    def test_angka_biasa_tidak_disentuh(self) -> None:
        assert split_informal("tahun 2026 rp15rb b2") == ["tahun", "2026", "rp15rb", "b2"]


class TestCanonical:
    def test_singkatan_lewat_kamus(self) -> None:
        assert canonical("gk", VOCAB) == "tidak"
        assert canonical("tdk", VOCAB) == "tidak"

    def test_huruf_ganda_dipangkas_kalau_hasilnya_dikenali(self) -> None:
        assert canonical("betuul", VOCAB) == "betul"
        assert canonical("mantapp", VOCAB) == "mantap"

    def test_huruf_ganda_sah_tidak_dirusak(self) -> None:
        assert canonical("maaf", VOCAB) == "maaf"

    def test_klitik_ekor_dilepas(self) -> None:
        assert canonical("parahnya", VOCAB) == "parah"
        assert canonical("dukungmu", VOCAB) == "dukung"

    def test_kata_tak_dikenal_dikembalikan_apa_adanya(self) -> None:
        """Modul ini tidak menebak: tanpa aturan yang cocok, token tidak berubah."""
        assert canonical("maataap", VOCAB) == "maataap"
        assert canonical("nggedabrus", VOCAB) == "nggedabrus"

    def test_kamus_tidak_memetakan_ke_dirinya_sendiri(self) -> None:
        assert all(variant != canon for variant, canon in SLANG.items())


class TestFrasa:
    def test_frasa_dua_kata_digabung(self) -> None:
        assert canonical_tokens("terima kasih bu", VOCAB) == ["terimakasih", "bu"]
        assert canonical_tokens("cuma omong kosong", VOCAB) == ["cuma", "omongkosong"]

    def test_frasa_tidak_digabung_melewati_batas_klausa(self) -> None:
        assert canonical_tokens("saya terima. kasih tahu ya", VOCAB) == [
            "saya", "terima", CLAUSE_BOUNDARY, "kasih", "tahu", "ya",
        ]

    def test_gabungan_singkatan_pemanjangan_dan_tanda_baca(self) -> None:
        assert canonical_tokens("GK betuuuul..mantapp sekaliiii!!!", VOCAB) == [
            "tidak", "betul", CLAUSE_BOUNDARY, "mantap", "sekali",
        ]

    def test_titik_di_dalam_url_bukan_batas_klausa(self) -> None:
        assert canonical_tokens("lihat https://contoh.id/a.b mantap", VOCAB) == ["lihat", "mantap"]


class TestEmoji:
    KNOWN = frozenset("😡👍❤")

    def test_sekali_per_jenis(self) -> None:
        assert emoji_marks("parah 😡😡😡 👍", self.KNOWN) == ["😡", "👍"]

    def test_emoji_tak_dikenal_diabaikan(self) -> None:
        assert emoji_marks("lucu 😂😂", self.KNOWN) == []

    def test_variation_selector_tidak_mengganggu(self) -> None:
        assert emoji_marks("makasih ❤️", self.KNOWN) == ["❤"]
