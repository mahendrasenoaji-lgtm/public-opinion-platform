"""Tes topic discovery — fungsi murni, tanpa database dan tanpa LLM."""

from __future__ import annotations

import pytest

from app.services.topics import (
    MIN_DOCUMENTS,
    TopicCluster,
    discover,
    limitations_for,
    momentum,
    share_of_voice,
)


def _korpus_dua_tema() -> list[str]:
    """Dua tema yang jelas berbeda kosakatanya, masing-masing 12 teks.

    Ditulis dengan variasi kata supaya bukan sekadar kalimat identik yang
    diulang — klasterisasi yang hanya bisa mengelompokkan duplikat persis
    tidak membuktikan apa pun.
    """
    harga = [
        "harga beras di pasar terus naik minggu ini",
        "beras mahal sekali sekarang di pasar tradisional",
        "kenaikan harga pangan memberatkan warga",
        "harga cabai dan beras melonjak tajam",
        "pasar tradisional harga sembako naik lagi",
        "sembako mahal warga mengeluh harga beras",
        "harga pangan naik terus tiap minggu",
        "beras dan minyak goreng makin mahal di pasar",
        "kenaikan sembako bikin belanja dapur membengkak",
        "harga beras premium naik di sejumlah pasar",
        "pangan mahal daya beli warga turun",
        "minyak goreng dan beras harga naik terus",
    ]
    transportasi = [
        "jalan rusak parah di jalur utama kecamatan",
        "perbaikan jalan belum selesai sudah berbulan bulan",
        "jalan berlubang bikin kendaraan rusak",
        "infrastruktur jalan di daerah kami terbengkalai",
        "aspal jalan mengelupas setelah hujan deras",
        "jalan provinsi rusak belum diperbaiki juga",
        "kendaraan sulit lewat karena jalan berlubang",
        "perbaikan infrastruktur jalan lambat sekali",
        "jalur transportasi rusak mengganggu distribusi",
        "jalan utama kecamatan rusak berat sejak lama",
        "aspal berlubang membahayakan pengendara motor",
        "infrastruktur jalan daerah butuh perbaikan segera",
    ]
    return harga + transportasi


class TestGating:
    def test_di_bawah_ambang_menolak_bukan_mengarang_tema(self) -> None:
        r = discover(["harga naik"] * 5)
        assert r.insufficient_data
        assert r.clusters == []
        assert r.note is not None and str(MIN_DOCUMENTS) in r.note

    def test_korpus_kosong_aman(self) -> None:
        r = discover([])
        assert r.insufficient_data and r.n == 0 and r.unclustered_pct == 0.0

    def test_teks_kosong_semua_ditolak(self) -> None:
        r = discover(["   "] * (MIN_DOCUMENTS + 5))
        assert r.insufficient_data


class TestDiscover:
    def test_dua_tema_terpisah(self) -> None:
        r = discover(_korpus_dua_tema())
        assert not r.insufficient_data
        assert len(r.clusters) >= 2, f"hanya menemukan {len(r.clusters)} tema"

    def test_tema_terurut_dari_yang_terbesar(self) -> None:
        r = discover(_korpus_dua_tema())
        sizes = [c.size for c in r.clusters]
        assert sizes == sorted(sizes, reverse=True)

    def test_kata_kunci_mencerminkan_isi_tema(self) -> None:
        r = discover(_korpus_dua_tema())
        semua_kata = " ".join(k for c in r.clusters for k in c.keywords)
        assert "harga" in semua_kata or "beras" in semua_kata
        assert "jalan" in semua_kata

    def test_indeks_anggota_menunjuk_ke_input_asli(self) -> None:
        korpus = _korpus_dua_tema()
        r = discover(korpus)
        for c in r.clusters:
            for i in c.member_indexes:
                assert 0 <= i < len(korpus)

    def test_setiap_teks_masuk_tepat_satu_tempat(self) -> None:
        """Tidak boleh ada teks yang hilang atau dihitung dua kali."""
        korpus = _korpus_dua_tema()
        r = discover(korpus)
        terpetakan = [i for c in r.clusters for i in c.member_indexes]
        semua = sorted(terpetakan + r.unclustered_indexes)
        assert semua == list(range(len(korpus)))

    def test_unclustered_pct_konsisten_dengan_daftarnya(self) -> None:
        korpus = _korpus_dua_tema()
        r = discover(korpus)
        assert r.unclustered_pct == pytest.approx(
            100 * len(r.unclustered_indexes) / len(korpus), abs=0.1
        )

    def test_deterministik(self) -> None:
        """Laporan minggu ini harus bisa dibandingkan dengan minggu lalu."""
        korpus = _korpus_dua_tema()
        a, b = discover(korpus), discover(korpus)
        assert [c.member_indexes for c in a.clusters] == [c.member_indexes for c in b.clusters]
        assert [c.keywords for c in a.clusters] == [c.keywords for c in b.clusters]

    def test_metode_dilaporkan_apa_adanya_bukan_klaim_embedding(self) -> None:
        """R1: metadata metode tidak boleh mengklaim embedding untuk TF-IDF."""
        r = discover(_korpus_dua_tema())
        assert "TF-IDF" in r.method
        assert "embedding" not in r.method.lower()

    def test_batasan_selalu_disertakan(self) -> None:
        r = discover(_korpus_dua_tema())
        assert r.limitations
        assert any("makna" in x for x in r.limitations)

    def test_koherensi_dilaporkan_per_tema(self) -> None:
        r = discover(_korpus_dua_tema())
        assert all(0.0 <= c.coherence <= 1.0 for c in r.clusters)
        assert any(c.coherence > 0.5 for c in r.clusters)

    def test_label_dari_kata_kunci_bukan_kalimat_interpretatif(self) -> None:
        cluster = TopicCluster(
            keywords=["harga", "beras", "pasar", "naik"], size=9, member_indexes=[], coherence=0.9
        )
        assert cluster.label == "harga / beras / pasar"

    def test_label_tanpa_kata_kunci_jujur(self) -> None:
        assert TopicCluster([], 0, [], 0.0).label == "(tanpa kata kunci)"

    def test_kosakata_habis_tersaring_ditolak_bukan_dipaksakan(self) -> None:
        """Teks yang tak berbagi satu kata pun tidak punya tema untuk ditemukan."""
        acak = [f"kata{i} lain{i} beda{i} unik{i} sendiri{i}" for i in range(30)]
        r = discover(acak)
        assert r.insufficient_data
        assert r.note is not None and "membedakan" in r.note


class TestLimitations:
    def test_selalu_menyebut_keterbatasan_makna(self) -> None:
        assert any("makna" in x for x in limitations_for(0.0))

    def test_cakupan_rendah_memicu_peringatan_tambahan(self) -> None:
        assert any("tidak masuk tema" in x for x in limitations_for(41.0))

    def test_cakupan_baik_tidak_memicu_peringatan_itu(self) -> None:
        assert not any("tidak masuk tema" in x for x in limitations_for(12.0))

    def test_ambang_peringatan_di_tiga_puluh_persen(self) -> None:
        assert len(limitations_for(30.0)) > len(limitations_for(29.9))


class TestMomentum:
    def test_pertumbuhan_positif(self) -> None:
        assert momentum(150, 100) == 50.0

    def test_penurunan(self) -> None:
        assert momentum(80, 100) == -20.0

    def test_dari_nol_none_bukan_seratus_persen(self) -> None:
        assert momentum(25, 0) is None

    def test_dua_duanya_nol(self) -> None:
        assert momentum(0, 0) is None

    def test_volume_negatif_ditolak(self) -> None:
        with pytest.raises(ValueError, match="negatif"):
            momentum(-1, 10)


class TestShareOfVoice:
    def test_porsi_berjumlah_seratus(self) -> None:
        s = share_of_voice({"a": 60, "b": 40})
        assert s == {"a": 60.0, "b": 40.0}

    def test_total_nol_kosong(self) -> None:
        assert share_of_voice({"a": 0}) == {}

    def test_dict_kosong(self) -> None:
        assert share_of_voice({}) == {}
