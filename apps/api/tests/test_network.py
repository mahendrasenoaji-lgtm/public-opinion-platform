"""Tes graf interaksi balasan/kutipan — fungsi murni, tanpa database."""

from __future__ import annotations

from app.services.network import MIN_ACCOUNTS, MIN_EDGES, EdgeKind, InteractionEdge, build


def _rantai(n_sumber: int, target: str, *, kind: EdgeKind = "reply") -> list[InteractionEdge]:
    """n_sumber akun BERBEDA masing-masing sekali membalas/mengutip `target`."""
    return [InteractionEdge(f"src{i:03d}", target, kind) for i in range(n_sumber)]


class TestGating:
    def test_tanpa_edge_menolak(self) -> None:
        r = build([])
        assert r.insufficient_data
        assert r.top == []
        assert r.total_accounts == 0

    def test_akun_kurang_dari_minimum_menolak(self) -> None:
        """3 akun (2 sumber + 1 target) jauh di bawah MIN_ACCOUNTS."""
        edges = _rantai(2, "target")
        r = build(edges)
        assert r.insufficient_data
        assert str(MIN_ACCOUNTS) in (r.note or "")

    def test_edge_kurang_dari_minimum_menolak(self) -> None:
        """Cukup akun tapi tiap akun cuma sekali -> edge < MIN_EDGES."""
        # MIN_ACCOUNTS akun sumber berbeda, tapi jumlah edge < MIN_EDGES.
        n = min(MIN_ACCOUNTS + 1, MIN_EDGES - 1)
        edges = _rantai(n, "target")
        assert len(edges) < MIN_EDGES
        r = build(edges)
        assert r.insufficient_data
        assert str(MIN_EDGES) in (r.note or "")

    def test_self_loop_dibuang_dari_hitungan(self) -> None:
        """Akun membalas dirinya sendiri (thread) bukan interaksi antar akun."""
        edges = _rantai(MIN_EDGES + 5, "target")
        edges.append(InteractionEdge("target", "target", "reply"))
        r = build(edges)
        assert r.total_edges == MIN_EDGES + 5  # self-loop tidak ikut terhitung
        assert all(p.author_hash != p.author_hash or True for p in r.top)  # tak crash


class TestPeringkat:
    def test_akun_paling_banyak_dibalas_naik_ke_atas(self) -> None:
        edges = _rantai(MIN_EDGES + 5, "populer")
        r = build(edges)
        assert not r.insufficient_data
        assert r.top[0].author_hash == "populer"
        assert r.top[0].replies_received == MIN_EDGES + 5
        assert r.top[0].distinct_sources == MIN_EDGES + 5

    def test_reply_dan_quote_dihitung_terpisah_tapi_masuk_in_degree(self) -> None:
        edges = _rantai(10, "campuran", kind="reply") + _rantai(10, "campuran", kind="quote")
        # cukupkan akun & edge lain supaya lolos gating
        edges += _rantai(MIN_ACCOUNTS, "lain")
        r = build(edges)
        campuran = next(p for p in r.top if p.author_hash == "campuran")
        assert campuran.replies_received == 10
        assert campuran.quotes_received == 10
        assert campuran.in_degree == 20

    def test_satu_sumber_membalas_berkali_kali_beda_dari_banyak_sumber(self) -> None:
        """1 akun membalas 20x vs 20 akun masing-masing 1x -- in_degree sama,
        distinct_sources beda. Itu yang membedakan spam satu akun dari
        perhatian luas."""
        satu_sumber = [InteractionEdge("spammer", "korban_a", "reply") for _ in range(20)]
        banyak_sumber = _rantai(20, "korban_b")
        edges = satu_sumber + banyak_sumber + _rantai(MIN_ACCOUNTS, "pengisi")
        r = build(edges)
        a = next(p for p in r.top if p.author_hash == "korban_a")
        b = next(p for p in r.top if p.author_hash == "korban_b")
        assert a.in_degree == b.in_degree == 20
        assert a.distinct_sources == 1
        assert b.distinct_sources == 20

    def test_akun_yang_cuma_jadi_sumber_tidak_masuk_peringkat(self) -> None:
        """Akun yang cuma membalas orang lain, tidak pernah dibalas, tidak
        punya posisi untuk diperingkat sebagai TUJUAN."""
        edges = _rantai(MIN_EDGES + 5, "target")
        r = build(edges)
        assert not any(p.author_hash.startswith("src") for p in r.top)

    def test_urutan_stabil_saat_seri(self) -> None:
        edges = _rantai(MIN_EDGES + 5, "a") + [
            InteractionEdge(f"srcx{i}", "b", "reply") for i in range(MIN_EDGES + 5)
        ]
        r1 = build(edges)
        r2 = build(list(reversed(edges)))
        assert [p.author_hash for p in r1.top] == [p.author_hash for p in r2.top]


class TestKontrak:
    def test_metode_dan_batasan_tidak_kosong(self) -> None:
        r = build(_rantai(MIN_EDGES + 5, "target"))
        assert r.method
        assert r.limitations
        assert any("terambil" in x for x in r.limitations)
        assert any("bukan bukti pengaruh kausal" in x for x in r.limitations)
