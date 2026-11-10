"""Tes services/conversation_report.py."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.services import conversation_report as cr

D0 = datetime(2026, 10, 10, 3, 0, tzinfo=UTC)


def _row(
    text: str = "antre bbm",
    *,
    source: str = "SOCIAL",
    day: int = 0,
    hour: int = 0,
    sentiment: float | None = None,
    engagement: int = 0,
    url: str | None = None,
    topic_id: str | None = None,
) -> cr.Row:
    return cr.Row(
        source=source,
        text=text,
        sentiment=sentiment,
        published_at=D0 + timedelta(days=day, hours=hour),
        engagement=engagement,
        url=url,
        topic_id=topic_id,
    )


class TestPotongan:
    def test_kata_tanpa_kata_umum_angka_dan_kata_pendek(self) -> None:
        assert cr.words_in("Yang antre BBM di SPBU itu 3 jam, gak ada solusi") == {
            "antre",
            "bbm",
            "spbu",
            "jam",
            "solusi",
        }

    def test_tagar_dan_emoji_sekali_per_konten(self) -> None:
        assert cr.hashtags_in("#BBM langka #bbm #Bali") == ["#bbm", "#bali"]
        assert cr.emoji_in("parah 😡😡 👍 ok") == ["😡", "👍"]
        assert cr.emoji_in("tanpa emoji © 2026") == []

    def test_domain(self) -> None:
        assert cr.domain_of("https://www.Kompas.com/a/b") == "kompas.com"
        assert cr.domain_of(None) is None
        assert cr.domain_of("bukan-url") is None


class TestBuild:
    def test_sumber_tidak_digabung(self) -> None:
        report = cr.build([_row("bbm langka"), _row("bbm aman", source="MEDIA")])
        assert [(s.source, s.n) for s in report.sources] == [("SOCIAL", 1), ("MEDIA", 1)]
        assert report.sources[0].words == [("bbm", 1), ("langka", 1)]

    def test_sumber_lain_diabaikan(self) -> None:
        assert cr.build([_row(source="SURVEY")]).sources == []

    def test_kata_dihitung_per_konten(self) -> None:
        report = cr.build([_row("bbm bbm bbm"), _row("bbm langka")])
        assert report.sources[0].words[0] == ("bbm", 2)

    def test_tanggal_mengikuti_zona(self) -> None:
        late = _row(hour=14)  # 17.00 UTC = 01.00 WITA esok harinya
        assert cr.build([late], tz="WITA").sources[0].days[0].day == date(2026, 10, 11)
        assert cr.build([late], tz="WIB").sources[0].days[0].day == date(2026, 10, 11)
        early = _row(hour=12)  # 15.00 UTC = 22.00 WIB, 23.00 WITA, 00.00 WIT
        assert cr.build([early], tz="WITA").sources[0].days[0].day == date(2026, 10, 10)
        assert cr.build([early], tz="WIT").sources[0].days[0].day == date(2026, 10, 11)

    def test_zona_tak_dikenal_ditolak(self) -> None:
        with pytest.raises(ValueError):
            cr.build([], tz="GMT")

    def test_sentimen_harian_ditahan_di_bawah_ambang(self) -> None:
        few = [_row(sentiment=-0.5) for _ in range(cr.MIN_SCORED - 1)]
        day = cr.build(few).sources[0].days[0]
        assert (day.scored, day.mean, day.negative_share) == (cr.MIN_SCORED - 1, None, None)

        enough = [_row(sentiment=-0.5) for _ in range(cr.MIN_SCORED)] + [_row()]
        src = cr.build(enough).sources[0]
        assert src.days[0].mean == -0.5
        assert src.days[0].negative_share == 1.0
        assert src.labels == {"negatif": cr.MIN_SCORED, "tidak dinilai": 1}
        assert src.scored == cr.MIN_SCORED

    def test_lonjakan_membawa_konten_dan_liputan_hari_yang_sama(self) -> None:
        rows = [_row(day=d) for d in (0, 1, 3, 4)]
        rows += [_row(f"ramai {i}", day=2, engagement=i) for i in range(6)]
        rows += [
            _row("Gubernur sidak SPBU", source="MEDIA", day=2, url="https://kompas.com/x"),
            _row("Berita hari lain", source="MEDIA", day=0, url="https://www.kompas.com/y"),
            _row("Antara", source="MEDIA", day=1, url="https://antaranews.com/z"),
        ]
        report = cr.build(rows)
        social = report.sources[0]
        (peak,) = social.peaks
        assert (peak.day, peak.volume, peak.ratio, peak.is_spike) == (
            date(2026, 10, 12),
            6,
            6.0,
            True,
        )
        assert [i.engagement for i in peak.top_content] == [5, 4, 3]
        assert [i.text for i in peak.same_day_media] == ["Gubernur sidak SPBU"]
        assert report.outlets == [cr.Outlet("kompas.com", 2), cr.Outlet("antaranews.com", 1)]
        assert report.outlets_total == 2
        # Liputan tidak menjadi "liputan hari yang sama" bagi dirinya sendiri.
        assert all(p.same_day_media == [] for p in report.sources[1].peaks)

    def test_volume_rata_hanya_hari_teramai_tanpa_tanda_lonjakan(self) -> None:
        rows = [_row(day=d) for d in range(5) for _ in range(3)]
        (peak,) = cr.build(rows).sources[0].peaks
        assert peak.is_spike is False and peak.ratio == 1.0

    def test_kurang_dari_tiga_hari_bukan_lonjakan(self) -> None:
        rows = [_row(day=0)] + [_row(day=1) for _ in range(9)]
        (peak,) = cr.build(rows).sources[0].peaks
        assert peak.volume == 9 and peak.is_spike is False

    def test_tema_per_sumber_dengan_engagement(self) -> None:
        rows = [_row(topic_id="t1", engagement=5, sentiment=0.5) for _ in range(30)]
        rows += [_row(topic_id="t2", engagement=100), _row()]
        topics = cr.build(rows).topics
        assert [(t.topic_id, t.n, t.engagement, t.mean) for t in topics] == [
            ("t1", 30, 150, 0.5),
            ("t2", 1, 100, None),
        ]

    def test_kosong(self) -> None:
        report = cr.build([])
        assert report.sources == [] and report.outlets == [] and report.topics == []
