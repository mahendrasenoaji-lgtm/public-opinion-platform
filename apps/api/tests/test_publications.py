"""Tes fungsi murni publikasi (services/publications.py)."""

import pytest

from app.services import publications as pub


def _report() -> dict:
    return {
        "period_start": "2026-10-11",
        "period_end": "2026-10-20",
        "sources": [
            {
                "source": "SOCIAL",
                "n": 10,
                "peaks": [
                    {
                        "day": "2026-10-12",
                        "top_content": [
                            {
                                "text": "komentar warga",
                                "engagement": 9,
                                "published_at": "2026-10-12T01:00:00Z",
                                "source_url": "https://youtube.com/watch?v=x&lc=abc",
                            }
                        ],
                        "same_day_media": [
                            {
                                "text": "Judul berita",
                                "engagement": 0,
                                "published_at": "2026-10-12T02:00:00Z",
                                "source_url": "https://media.example/berita",
                            }
                        ],
                    }
                ],
            },
            {
                "source": "MEDIA",
                "n": 2,
                "peaks": [
                    {
                        "day": "2026-10-12",
                        "top_content": [
                            {
                                "text": "Judul berita",
                                "engagement": 0,
                                "published_at": "2026-10-12T02:00:00Z",
                                "source_url": "https://media.example/berita",
                            }
                        ],
                        "same_day_media": [],
                    }
                ],
            },
        ],
    }


class TestSlug:
    def test_slugify(self) -> None:
        assert (
            pub.slugify("Sentimen Publik: BBM Bali (11–20 Okt)!")
            == "sentimen-publik-bbm-bali-11-20-okt"
        )
        assert pub.slugify("Kelangkaan Énergi") == "kelangkaan-energi"
        assert pub.slugify("???") == "artikel"

    def test_slug_baru_berakhiran_acak_dan_sah(self) -> None:
        a, b = pub.new_slug("Judul Sama"), pub.new_slug("Judul Sama")
        assert a != b
        assert a.startswith("judul-sama-")
        import re

        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", a)

    def test_judul_panjang_dipotong(self) -> None:
        assert len(pub.slugify("kata " * 100)) <= pub.MAX_SLUG_BASE


class TestStatus:
    def test_alur_yang_sah(self) -> None:
        pub.check_transition("draft", "review", "RESEARCHER")
        pub.check_transition("review", "draft", "RESEARCHER")
        pub.check_transition("review", "published", "RESEARCH_DIRECTOR")
        pub.check_transition("review", "published", "SUPER_ADMIN")

    def test_peneliti_tidak_boleh_menerbitkan(self) -> None:
        with pytest.raises(PermissionError):
            pub.check_transition("review", "published", "RESEARCHER")

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            ("draft", "published"),
            ("published", "draft"),
            ("published", "review"),
            ("draft", "draft"),
        ],
    )
    def test_lompatan_dan_mundur_dari_terbit_ditolak(self, current: str, target: str) -> None:
        with pytest.raises(ValueError):
            pub.check_transition(current, target, "SUPER_ADMIN")  # type: ignore[arg-type]


class TestTag:
    def test_normalisasi(self) -> None:
        assert pub.normalize_tags(["Kebijakan", " kebijakan ", "Energi & BBM", ""]) == [
            "kebijakan",
            "energi-bbm",
        ]

    def test_maksimal_delapan(self) -> None:
        assert len(pub.normalize_tags([f"tag{i}" for i in range(20)])) == 8


class TestSnapshot:
    def test_teks_dan_tautan_konten_warga_dibuang(self) -> None:
        snap = pub.build_snapshot(
            report=_report(),
            project_name="P",
            frozen_at="2026-11-13T00:00:00+00:00",
            timezone="WITA",
        )
        social = snap["report"]["sources"][0]["peaks"][0]
        assert social["top_content"] == [{"engagement": 9, "published_at": "2026-10-12T01:00:00Z"}]
        assert pub.snapshot_has_social_text(snap) is False
        assert "komentar warga" not in str(snap)
        assert "lc=abc" not in str(snap)

    def test_berita_tetap_utuh(self) -> None:
        snap = pub.build_snapshot(report=_report(), project_name="P", frozen_at="x", timezone="WIB")
        assert (
            snap["report"]["sources"][0]["peaks"][0]["same_day_media"][0]["text"] == "Judul berita"
        )
        assert snap["report"]["sources"][1]["peaks"][0]["top_content"][0]["source_url"]

    def test_laporan_asal_tidak_diubah(self) -> None:
        report = _report()
        pub.sanitize_report(report)
        assert report["sources"][0]["peaks"][0]["top_content"][0]["text"] == "komentar warga"

    def test_penjaga_mengenali_snapshot_kotor(self) -> None:
        assert pub.snapshot_has_social_text({"report": _report()}) is True

    def test_keterangan_pembekuan(self) -> None:
        snap = pub.build_snapshot(
            report=_report(),
            project_name="BBM",
            frozen_at="2026-11-13T00:00:00+00:00",
            timezone="WITA",
        )
        assert snap["period_start"] == "2026-10-11"
        assert snap["project_name"] == "BBM"
        assert snap["snapshot_version"] == 1
        assert "dibekukan" in snap["note"]
