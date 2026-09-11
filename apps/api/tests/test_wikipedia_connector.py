"""Tes konektor Wikipedia Pageviews — parsing murni, tanpa jaringan.

Sesuai CLAUDE.md §4: konektor seluruhnya I/O, jadi yang dites adalah bagian
yang sudah dipisah jadi fungsi murni (`parse_pageviews`, `metric_name`) plus
validasi `RawObservation`. Pengambilan HTTP-nya sendiri tidak dites di sini.

Payload di bawah bentuknya persis seperti respons Wikimedia sungguhan yang
diverifikasi pada 2026-09-11 untuk artikel "Badan Gizi Nasional" di
id.wikipedia — termasuk angkanya (94, 81, 106, 120, 142, 84).
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.connectors.base import ConnectorError
from app.connectors.metrics import MAX_METRIC_VALUE, RawObservation
from app.connectors.wikipedia import metric_name, parse_pageviews
from app.models.measurement import SignalSource

METRIC = "pageviews_badan_gizi_nasional"
METHOD = "Wikimedia Pageviews API · id.wikipedia · agen user · harian"


def _payload(items: list[dict]) -> bytes:
    return json.dumps({"items": items}).encode()


def _day(stamp: str, views: int) -> dict:
    return {
        "project": "id.wikipedia",
        "article": "Badan_Gizi_Nasional",
        "granularity": "daily",
        "timestamp": stamp,
        "access": "all-access",
        "agent": "user",
        "views": views,
    }


REAL_SERIES = [
    _day("2026090500", 94),
    _day("2026090600", 81),
    _day("2026090700", 106),
    _day("2026090800", 120),
    _day("2026090900", 142),
    _day("2026091000", 84),
]


class TestParsing:
    def test_deret_nyata_terbaca_utuh(self) -> None:
        obs = parse_pageviews(_payload(REAL_SERIES), metric=METRIC, method=METHOD)

        assert [o.value for o in obs] == [94.0, 81.0, 106.0, 120.0, 142.0, 84.0]
        assert obs[0].period_end == date(2026, 9, 5)
        assert obs[-1].period_end == date(2026, 9, 10)

    def test_setiap_pengamatan_berdurasi_satu_hari(self) -> None:
        obs = parse_pageviews(_payload(REAL_SERIES), metric=METRIC, method=METHOD)

        assert all(o.period_start == o.period_end for o in obs)

    def test_sumbernya_digital_bukan_survey(self) -> None:
        """Perhatian terukur, bukan pernyataan responden. Lihat CLAUDE.md R1."""
        obs = parse_pageviews(_payload(REAL_SERIES), metric=METRIC, method=METHOD)

        assert all(o.source is SignalSource.DIGITAL for o in obs)

    def test_method_menyebut_sumbernya(self) -> None:
        """`method` sampai ke layar. Ia harus cukup untuk tahu angka ini dari mana."""
        obs = parse_pageviews(_payload(REAL_SERIES), metric=METRIC, method=METHOD)

        assert all("Wikimedia Pageviews" in o.method for o in obs)
        assert all("id.wikipedia" in o.method for o in obs)

    def test_hasil_selalu_terurut_naik(self) -> None:
        acak = [REAL_SERIES[4], REAL_SERIES[0], REAL_SERIES[2]]

        obs = parse_pageviews(_payload(acak), metric=METRIC, method=METHOD)

        assert [o.period_end for o in obs] == [
            date(2026, 9, 5),
            date(2026, 9, 7),
            date(2026, 9, 9),
        ]

    def test_timestamp_cacat_dibuang_bukan_ditebak(self) -> None:
        """Menempatkan tampilan halaman di tanggal salah menggeser hubungannya
        dengan kejadian yang mau dijelaskan — lebih baik hilang satu hari."""
        rusak = [*REAL_SERIES[:2], _day("bukan-tanggal", 999), _day("", 5)]

        obs = parse_pageviews(_payload(rusak), metric=METRIC, method=METHOD)

        assert len(obs) == 2
        assert 999.0 not in [o.value for o in obs]

    def test_views_bukan_angka_dibuang(self) -> None:
        rusak = [*REAL_SERIES[:1], {**_day("2026090600", 0), "views": None}]

        obs = parse_pageviews(_payload(rusak), metric=METRIC, method=METHOD)

        assert len(obs) == 1

    def test_views_boolean_dibuang(self) -> None:
        """`True` adalah `int` di Python; tanpa penjagaan eksplisit ia akan
        tersimpan sebagai 1 tampilan halaman yang tidak pernah terjadi."""
        rusak = [{**_day("2026090600", 0), "views": True}]

        obs = parse_pageviews(_payload(rusak), metric=METRIC, method=METHOD)

        assert obs == []

    def test_hari_kosong_hilang_bukan_jadi_nol(self) -> None:
        """Nol berarti "diukur, hasilnya nol". Hari yang tidak dilaporkan
        Wikimedia tidak pernah diukur — dua hal yang berbeda."""
        berlubang = [REAL_SERIES[0], REAL_SERIES[3]]

        obs = parse_pageviews(_payload(berlubang), metric=METRIC, method=METHOD)

        assert len(obs) == 2
        assert 0.0 not in [o.value for o in obs]

    def test_nol_sungguhan_tetap_disimpan(self) -> None:
        obs = parse_pageviews(_payload([_day("2026090500", 0)]), metric=METRIC, method=METHOD)

        assert len(obs) == 1
        assert obs[0].value == 0.0

    def test_breakdown_menyimpan_artikel_dan_proyek(self) -> None:
        obs = parse_pageviews(_payload(REAL_SERIES[:1]), metric=METRIC, method=METHOD)

        assert obs[0].breakdown["article"] == "Badan_Gizi_Nasional"
        assert obs[0].breakdown["project"] == "id.wikipedia"
        assert obs[0].breakdown["agent"] == "user"


class TestRespondsGagal:
    def test_bukan_json(self) -> None:
        with pytest.raises(ConnectorError, match="bukan JSON"):
            parse_pageviews(b"<html>502</html>", metric=METRIC, method=METHOD)

    def test_json_tapi_bukan_objek(self) -> None:
        with pytest.raises(ConnectorError, match="bukan objek JSON"):
            parse_pageviews(b"[1, 2, 3]", metric=METRIC, method=METHOD)

    def test_tanpa_daftar_items(self) -> None:
        with pytest.raises(ConnectorError, match="items"):
            parse_pageviews(b'{"detail": "not found"}', metric=METRIC, method=METHOD)

    def test_items_kosong_bukan_error(self) -> None:
        """Artikel yang memang belum pernah dibuka bukan kegagalan."""
        assert parse_pageviews(b'{"items": []}', metric=METRIC, method=METHOD) == []


class TestNamaMetrik:
    def test_diawali_pageviews_supaya_tidak_bertabrakan_dengan_poi(self) -> None:
        """Kalau bertabrakan, /forecast/baseline?metric=poi akan mencampur
        tampilan halaman ke riwayat Public Opinion Index (pelanggaran R1)."""
        assert metric_name("poi") == "pageviews_poi"
        assert metric_name("Badan Gizi Nasional").startswith("pageviews_")

    def test_spasi_jadi_garis_bawah_dan_huruf_kecil(self) -> None:
        assert metric_name("Badan Gizi Nasional") == "pageviews_badan_gizi_nasional"

    def test_stabil_untuk_ejaan_yang_sama(self) -> None:
        """Nama deret yang berubah antar pengambilan memecah riwayatnya jadi
        dua deret pendek, dan model tidak akan pernah punya cukup pengamatan."""
        assert metric_name(" Badan Gizi Nasional ") == metric_name("Badan_Gizi_Nasional")


class TestBatasNilai:
    def test_nilai_di_atas_kapasitas_kolom_ditolak_bukan_dipotong(self) -> None:
        """metric_snapshots.value = NUMERIC(8,3). Memotong diam-diam akan
        membuat puncak deret terbaca sebagai plateau yang tidak pernah ada."""
        with pytest.raises(ConnectorError, match="batas kolom"):
            RawObservation(
                metric=METRIC,
                period_start=date(2026, 9, 5),
                period_end=date(2026, 9, 5),
                value=float(MAX_METRIC_VALUE + 1),
                source=SignalSource.DIGITAL,
                method=METHOD,
            )

    def test_tepat_di_batas_masih_diterima(self) -> None:
        obs = RawObservation(
            metric=METRIC,
            period_start=date(2026, 9, 5),
            period_end=date(2026, 9, 5),
            value=float(MAX_METRIC_VALUE),
            source=SignalSource.DIGITAL,
            method=METHOD,
        )

        assert obs.value == float(MAX_METRIC_VALUE)

    def test_nilai_negatif_ditolak(self) -> None:
        with pytest.raises(ConnectorError, match="negatif"):
            RawObservation(
                metric=METRIC,
                period_start=date(2026, 9, 5),
                period_end=date(2026, 9, 5),
                value=-1.0,
                source=SignalSource.DIGITAL,
                method=METHOD,
            )

    def test_rentang_terbalik_ditolak(self) -> None:
        with pytest.raises(ConnectorError, match="sebelum"):
            RawObservation(
                metric=METRIC,
                period_start=date(2026, 9, 10),
                period_end=date(2026, 9, 5),
                value=10.0,
                source=SignalSource.DIGITAL,
                method=METHOD,
            )


class TestRegistry:
    def test_konektor_terdaftar_dan_bisa_diambil(self) -> None:
        from app.connectors.metrics import get_metric_connector

        connector = get_metric_connector("wikipedia_pageviews")

        assert connector.source is SignalSource.DIGITAL
        assert connector.requires_credential is None

    def test_notes_menyebut_batas_perhatian_bukan_sikap(self) -> None:
        """Batas ini wajib ikut ke UI — lihat docstring connectors/metrics.py."""
        from app.connectors.metrics import get_metric_connector

        notes = get_metric_connector("wikipedia_pageviews").notes.lower()

        assert "perhatian" in notes
        assert "sikap" in notes

    def test_kunci_tak_dikenal_menyebut_yang_tersedia(self) -> None:
        from app.connectors.metrics import get_metric_connector

        with pytest.raises(ConnectorError, match="wikipedia_pageviews"):
            get_metric_connector("salah_ketik")
