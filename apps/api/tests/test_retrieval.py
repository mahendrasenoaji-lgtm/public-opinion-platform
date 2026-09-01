"""Tes pemilihan kartu fakta untuk Copilot — fungsi murni, tanpa LLM."""

from __future__ import annotations

from app.ai.envelope import EvidenceRef
from app.ai.retrieval import FactCard, question_terms, select_relevant


def _card(key: str, label: str, keywords: set[str], *, core: bool = False) -> FactCard:
    return FactCard(
        key=key,
        label=label,
        payload={"nilai": 1},
        evidence=EvidenceRef(kind="metric_snapshot", label=label, source="SURVEY"),
        keywords=frozenset(keywords),
        is_core=core,
    )


def _kartu() -> list[FactCard]:
    return [
        _card("metric:poi", "Metrik poi", {"poi", "index", "survey"}, core=True),
        _card("metric:trust", "Metrik trust", {"trust", "kepercayaan"}, core=True),
        _card("segment:Skeptis Kota", "Segmen Skeptis Kota", {"segmen", "skeptis", "kota"}),
        _card("topic:harga", "Tema harga pangan", {"harga", "pangan", "beras"}),
        _card("signal:summary", "Ringkasan percakapan media sosial", {"sosial", "medsos"}),
    ]


class TestQuestionTerms:
    def test_stopword_dibuang(self) -> None:
        terms = question_terms("Bagaimana kondisi kepercayaan publik saat ini?")
        assert "bagaimana" not in terms
        assert "kepercayaan" in terms

    def test_kata_terlalu_pendek_dibuang(self) -> None:
        assert "di" not in question_terms("apa di sana ada data")

    def test_pertanyaan_kosong(self) -> None:
        assert question_terms("   ") == set()


class TestSelectRelevant:
    def test_kartu_yang_cocok_dipilih(self) -> None:
        r = select_relevant("bagaimana tema harga pangan berkembang?", _kartu())
        assert not r.fell_back_to_core
        assert "topic:harga" in {c.key for c in r.cards}

    def test_kata_yang_cocok_dilaporkan_supaya_bisa_diaudit(self) -> None:
        r = select_relevant("bagaimana harga pangan?", _kartu())
        assert set(r.matched_terms["topic:harga"]) >= {"harga", "pangan"}

    def test_kartu_dengan_lebih_banyak_kecocokan_didahulukan(self) -> None:
        r = select_relevant("harga pangan beras", _kartu())
        assert r.cards[0].key == "topic:harga"

    def test_pertanyaan_umum_jatuh_ke_kartu_inti(self) -> None:
        """Pertanyaan tanpa kata kunci spesifik tetap sah dan harus terjawab."""
        r = select_relevant("bagaimana kondisinya sekarang?", _kartu())
        assert r.fell_back_to_core
        assert {c.key for c in r.cards} == {"metric:poi", "metric:trust"}

    def test_fallback_ditandai_supaya_keyakinan_bisa_diturunkan(self) -> None:
        r = select_relevant("zzz qqq wwwww", _kartu())
        assert r.fell_back_to_core is True
        assert r.matched_terms == {}

    def test_tanpa_kartu_inti_fallback_mengembalikan_kosong(self) -> None:
        """Lebih baik router menolak menjawab daripada envelope tanpa bukti."""
        kartu = [_card("topic:x", "Tema x", {"x"})]
        r = select_relevant("pertanyaan tanpa kecocokan sama sekali", kartu)
        assert r.cards == []

    def test_hasil_stabil_untuk_pertanyaan_yang_sama(self) -> None:
        """Jawaban yang berubah tanpa datanya berubah menghancurkan kepercayaan."""
        a = select_relevant("harga pangan dan kepercayaan", _kartu())
        b = select_relevant("harga pangan dan kepercayaan", _kartu())
        assert [c.key for c in a.cards] == [c.key for c in b.cards]

    def test_batas_jumlah_kartu_dihormati(self) -> None:
        kartu = [_card(f"k{i}", f"Kartu harga {i}", {"harga"}) for i in range(20)]
        assert len(select_relevant("harga", kartu, limit=3).cards) == 3

    def test_metode_dilaporkan_apa_adanya(self) -> None:
        """R1: jangan menyebut ini semantic search kalau cuma cocok kata."""
        r = select_relevant("harga", _kartu())
        assert "kata kunci" in r.method
        assert "semantic" not in r.method.lower()
