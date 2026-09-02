"""Tes estimasi keterpaparan akun — fungsi murni, tanpa database."""

from __future__ import annotations

from app.services.influence import (
    MIN_AUTHORS,
    MIN_POSTS_FOR_RANKING,
    AuthorActivity,
    estimate,
)


def _akun(n: int, *, posts: int = 5, engagement: int = 50) -> list[AuthorActivity]:
    return [AuthorActivity(f"hash{i:03d}", posts, engagement) for i in range(n)]


class TestGating:
    def test_tanpa_akun_menolak(self) -> None:
        r = estimate([])
        assert r.insufficient_data and r.top == []

    def test_terlalu_sedikit_akun_menolak_memeringkat(self) -> None:
        """Dari 4 akun, yang teratas otomatis terlihat dominan tanpa arti."""
        r = estimate(_akun(4))
        assert r.insufficient_data
        assert r.top == []
        assert r.note is not None and str(MIN_AUTHORS) in r.note

    def test_satu_unggahan_viral_tidak_diperingkat(self) -> None:
        akun = _akun(MIN_AUTHORS, posts=1, engagement=10)
        akun[0] = AuthorActivity("viral", posts=1, engagement=99999)
        r = estimate(akun)
        assert r.insufficient_data
        assert r.note is not None and str(MIN_POSTS_FOR_RANKING) in r.note

    def test_akun_di_bawah_ambang_tetap_masuk_penyebut(self) -> None:
        """Porsi harus dihitung dari SELURUH percakapan, bukan yang diperingkat."""
        akun = _akun(MIN_AUTHORS, posts=5, engagement=50)
        akun.append(AuthorActivity("kecil", posts=1, engagement=10))
        r = estimate(akun)
        assert r.total_posts == MIN_AUTHORS * 5 + 1
        assert r.total_authors == MIN_AUTHORS + 1
        assert r.ranked_authors == MIN_AUTHORS


class TestPeringkat:
    def test_akun_dengan_keterlibatan_lebih_besar_naik(self) -> None:
        akun = _akun(MIN_AUTHORS)
        akun[3] = AuthorActivity("dominan", posts=20, engagement=800)
        r = estimate(akun)
        assert r.top[0].author_hash == "dominan"

    def test_amplifikasi_relatif_terhadap_median(self) -> None:
        akun = _akun(MIN_AUTHORS, posts=5, engagement=50)  # 10 per unggahan
        akun.append(AuthorActivity("kuat", posts=5, engagement=150))  # 30 per unggahan
        r = estimate(akun)
        kuat = next(e for e in r.top if e.author_hash == "kuat")
        assert kuat.amplification == 3.0

    def test_porsi_dilaporkan_terpisah_dari_skor_gabungan(self) -> None:
        """Pembaca harus bisa menilai sendiri pembobotannya."""
        r = estimate(_akun(MIN_AUTHORS))
        e = r.top[0]
        assert e.post_share_pct > 0
        assert e.engagement_share_pct > 0
        assert e.influence_estimate > 0

    def test_hasil_stabil_saat_skor_seri(self) -> None:
        a = estimate(_akun(MIN_AUTHORS))
        b = estimate(_akun(MIN_AUTHORS))
        assert [e.author_hash for e in a.top] == [e.author_hash for e in b.top]

    def test_batas_jumlah_dihormati(self) -> None:
        assert len(estimate(_akun(30), limit=5).top) == 5

    def test_konsentrasi_dilaporkan(self) -> None:
        akun = _akun(20, posts=1, engagement=10)
        akun = [AuthorActivity(f"h{i}", posts=5 if i < 10 else 1, engagement=10) for i in range(20)]
        r = estimate(akun)
        # 10 akun teratas menyumbang 50 dari 60 unggahan
        assert r.concentration_top10_pct == round(100 * 50 / 60, 2)


class TestBahasa:
    def test_tidak_pernah_menyebut_mengendalikan(self) -> None:
        """CLAUDE.md §3 dan OVERCLAIM_TERMS di AIEnvelope."""
        r = estimate(_akun(MIN_AUTHORS))
        teks = " ".join(r.limitations) + r.method
        assert "mengendalikan" not in teks.lower()
        assert "menyebabkan" not in teks.lower()

    def test_batasan_menyatakan_ini_keterpaparan_bukan_pengaruh_kausal(self) -> None:
        r = estimate(_akun(MIN_AUTHORS))
        gabung = " ".join(r.limitations)
        assert "keterpaparan" in gabung
        assert "bukan pengaruh kausal" in gabung

    def test_batasan_menyebut_mediasi_algoritma(self) -> None:
        r = estimate(_akun(MIN_AUTHORS))
        assert "algoritma" in " ".join(r.limitations)

    def test_metode_selalu_disertakan(self) -> None:
        assert "porsi unggahan" in estimate(_akun(MIN_AUTHORS)).method


class TestKasusTepi:
    def test_keterlibatan_nol_tidak_membagi_nol(self) -> None:
        r = estimate(_akun(MIN_AUTHORS, posts=5, engagement=0))
        assert all(e.amplification == 0.0 for e in r.top)

    def test_identitas_tidak_pernah_selain_hash_masukan(self) -> None:
        r = estimate(_akun(MIN_AUTHORS))
        assert all(e.author_hash.startswith("hash") for e in r.top)
