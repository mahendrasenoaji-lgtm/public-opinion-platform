"""Tes pipeline ingestion — fungsi murni, tanpa database."""

from __future__ import annotations

import pytest

from app.services.ingestion import (
    concentration_ratio,
    content_fingerprint,
    dedupe,
    detect_language,
    hash_author,
    jaccard,
    normalize_text,
    shingles,
)


class TestNormalize:
    def test_membuang_url_dan_handle(self) -> None:
        out = normalize_text("Setuju banget @budi lihat https://contoh.id/x #KebijakanBaru")
        assert "http" not in out
        assert "budi" not in out
        # tanda pagar dibuang, katanya dipertahankan — hashtag membawa makna
        assert "kebijakanbaru" in out

    def test_dua_penulisan_sama_jadi_satu_bentuk(self) -> None:
        assert normalize_text("Harga  BBM  naik!!!") == normalize_text("harga bbm naik")

    def test_teks_kosong_aman(self) -> None:
        assert normalize_text("   \n\t ") == ""


class TestFingerprint:
    def test_stabil_lintas_variasi_kosmetik(self) -> None:
        a = content_fingerprint("Program bantuan ini membantu, menurut saya.")
        b = content_fingerprint("program bantuan ini membantu menurut saya")
        assert a == b

    def test_beda_isi_beda_sidik_jari(self) -> None:
        assert content_fingerprint("harga naik") != content_fingerprint("harga turun")


class TestHashAuthor:
    def test_deterministik_dengan_salt_sama(self) -> None:
        assert hash_author("@Budi", salt="s") == hash_author("budi", salt="s")

    def test_salt_berbeda_menghasilkan_hash_berbeda(self) -> None:
        assert hash_author("budi", salt="a") != hash_author("budi", salt="b")

    def test_handle_kosong_ditolak(self) -> None:
        with pytest.raises(ValueError, match="kosong"):
            hash_author("  ", salt="s")

    def test_tidak_menyimpan_handle_asli(self) -> None:
        assert "budi" not in hash_author("budi", salt="rahasia")


class TestShingles:
    def test_teks_pendek_jadi_satu_shingle(self) -> None:
        assert len(shingles("harga bbm naik")) == 1

    def test_jaccard_identik_satu(self) -> None:
        s = shingles("pemerintah mengumumkan program bantuan pangan untuk warga terdampak")
        assert jaccard(s, s) == 1.0

    def test_jaccard_kosong_nol(self) -> None:
        assert jaccard(frozenset(), shingles("apa saja")) == 0.0


class TestDedupe:
    def test_duplikat_persis_dibuang_yang_pertama_bertahan(self) -> None:
        r = dedupe(
            ["Harga pangan naik lagi", "harga pangan naik lagi!", "Kebijakan baru diumumkan"]
        )
        assert r.kept_indexes == [0, 2]
        assert r.duplicate_of == {1: 0}
        assert r.exact_duplicates == 1

    def test_nyaris_sama_terdeteksi(self) -> None:
        base = (
            "pemerintah mengumumkan program bantuan pangan untuk warga terdampak "
            "kenaikan harga di sejumlah provinsi tahun ini"
        )
        r = dedupe([base, base + " silakan dibagikan"])
        assert r.kept_indexes == [0]
        assert r.near_duplicates == 1
        assert r.duplicate_of == {1: 0}

    def test_topik_sama_kalimat_beda_bukan_duplikat(self) -> None:
        r = dedupe(
            [
                "menurut saya program bantuan pangan ini sangat membantu keluarga kami",
                "harga beras di pasar masih tinggi walaupun sudah ada operasi pasar",
            ]
        )
        assert r.kept_indexes == [0, 1]
        assert r.duplicate_of == {}

    def test_duplicate_rate_dilaporkan(self) -> None:
        r = dedupe(["a b c d", "a b c d", "e f g h"])
        assert r.duplicate_rate == pytest.approx(1 / 3, abs=1e-4)

    def test_batch_kosong(self) -> None:
        r = dedupe([])
        assert r.kept_indexes == [] and r.duplicate_rate == 0.0

    def test_threshold_tidak_valid_ditolak(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            dedupe(["a"], threshold=0)


class TestDetectLanguage:
    def test_indonesia_terdeteksi(self) -> None:
        g = detect_language(
            "saya rasa kebijakan ini tidak adil untuk warga yang sudah lama menunggu"
        )
        assert g.lang == "id" and g.confidence > 0

    def test_inggris_terdeteksi(self) -> None:
        g = detect_language("this is the kind of policy that will not work for the people here")
        assert g.lang == "en"

    def test_teks_pendek_menyerah_bukan_menebak(self) -> None:
        g = detect_language("harga naik")
        assert g.lang is None and g.confidence == 0.0

    def test_tanpa_stopword_dikenal_menyerah(self) -> None:
        g = detect_language("kwitansi bakpia kurma jengkol semangka rambutan salak")
        assert g.lang is None

    def test_seimbang_menyerah(self) -> None:
        # jumlah petunjuk sama banyak untuk kedua bahasa -> tidak memihak
        g = detect_language("yang dan the and satu dua tiga empat lima enam")
        assert g.lang is None

    def test_confidence_naik_bersama_bukti(self) -> None:
        tipis = detect_language("kucing berlari yang cepat sekali melintasi jalan")
        tebal = detect_language(
            "saya dan kami tidak akan pergi ke sana karena ini sudah dari dulu begitu"
        )
        assert tebal.confidence > tipis.confidence


class TestConcentration:
    def test_terpusat_penuh(self) -> None:
        assert concentration_ratio(["a"] * 10, top=1) == 1.0

    def test_tersebar(self) -> None:
        assert concentration_ratio([f"akun{i}" for i in range(100)], top=10) == 0.1

    def test_none_diabaikan_bukan_dihitung_sebagai_akun(self) -> None:
        assert concentration_ratio(["a", "a", None, None], top=1) == 1.0

    def test_kosong_nol(self) -> None:
        assert concentration_ratio([]) == 0.0
