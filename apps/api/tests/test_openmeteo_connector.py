"""Tes konektor Open-Meteo — parsing dan agregasi murni, tanpa jaringan.

Yang dijaga tes ini bukan cuma "parsing tidak error". Tiga hal yang kalau
rusak akan merusak arti datanya tanpa ada yang sadar:

1. Rata-rata harian dihitung dari jam yang BENAR-BENAR terukur, bukan dengan
   menganggap jam kosong sebagai nol.
2. Hari yang jamnya terlalu sedikit dibuang, bukan dimasukkan dengan bobot
   yang tidak dia punya.
3. Setiap baris membawa `province_code` asli dari koordinat yang diminta —
   bukan ditebak.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.connectors.base import ConnectorError
from app.connectors.openmeteo import (
    METHOD_NOTE,
    METRIC,
    PROVINCE_CAPITALS,
    daily_means,
    parse_air_quality,
)
from app.models.measurement import SignalSource

METHOD = f"Open-Meteo Air Quality API · PM2.5 µg/m³ · Kalimantan Tengah · {METHOD_NOTE}"


def _hours(day: str, values: list[float | None]) -> tuple[list[str], list[float | None]]:
    times = [f"{day}T{h:02d}:00" for h in range(len(values))]
    return times, values


def _payload(times: list[str], values: list[float | None]) -> bytes:
    return json.dumps(
        {
            "latitude": -2.21,
            "longitude": 113.92,
            "hourly_units": {"pm2_5": "μg/m³"},
            "hourly": {"time": times, "pm2_5": values},
        }
    ).encode()


def _full_day(day: str, value: float) -> tuple[list[str], list[float | None]]:
    return _hours(day, [value] * 24)


class TestRataRataHarian:
    def test_hari_penuh_dirata_ratakan(self) -> None:
        times, values = _hours("2026-09-10", [10.0] * 12 + [20.0] * 12)

        result = daily_means(times, values)

        assert result == [(date(2026, 9, 10), 15.0, 24)]

    def test_jam_null_dilewati_bukan_dianggap_nol(self) -> None:
        """Menganggap jam kosong sebagai nol akan menurunkan rata-rata hari
        berkabut asap justru ketika sensornya paling sering gagal."""
        times, values = _hours("2026-09-10", [100.0, None, 100.0, None])

        result = daily_means(times, values)

        assert result == [(date(2026, 9, 10), 100.0, 2)]

    def test_jumlah_jam_terpakai_ikut_dikembalikan(self) -> None:
        times, values = _hours("2026-09-10", [50.0, 50.0, None])

        [(_, _, hours)] = daily_means(times, values)

        assert hours == 2

    def test_beberapa_hari_terpisah_dan_terurut(self) -> None:
        t1, v1 = _full_day("2026-09-11", 30.0)
        t2, v2 = _full_day("2026-09-10", 10.0)

        result = daily_means(t2 + t1, v2 + v1)

        assert [d for d, _, _ in result] == [date(2026, 9, 10), date(2026, 9, 11)]

    def test_timestamp_cacat_dilewati(self) -> None:
        result = daily_means(["bukan-waktu", "2026-09-10T00:00"], [99.0, 10.0])

        assert result == [(date(2026, 9, 10), 10.0, 1)]

    def test_deret_kosong_bukan_error(self) -> None:
        assert daily_means([], []) == []


class TestParsing:
    def test_hari_penuh_jadi_satu_pengamatan(self) -> None:
        times, values = _full_day("2026-09-10", 42.5)

        obs = parse_air_quality(
            _payload(times, values), province_code="62", method=METHOD, min_hours=18
        )

        assert len(obs) == 1
        assert obs[0].value == 42.5
        assert obs[0].metric == METRIC
        assert obs[0].period_start == obs[0].period_end == date(2026, 9, 10)

    def test_hari_dengan_jam_kurang_dibuang(self) -> None:
        """Hari dengan 6 jam data bukan hari yang setara dengan hari penuh.
        Pola gating yang sama dengan MIN_EFFECTIVE_N di services/poi.py."""
        times, values = _hours("2026-09-10", [40.0] * 6)

        obs = parse_air_quality(
            _payload(times, values), province_code="62", method=METHOD, min_hours=18
        )

        assert obs == []

    def test_tepat_di_ambang_jam_diterima(self) -> None:
        times, values = _hours("2026-09-10", [40.0] * 18)

        obs = parse_air_quality(
            _payload(times, values), province_code="62", method=METHOD, min_hours=18
        )

        assert len(obs) == 1

    def test_province_code_terbawa_apa_adanya(self) -> None:
        """Georeferensi berasal dari koordinat yang DIMINTA, bukan ditebak
        dari isi apa pun — larangan yang sama seperti di ingestion.py."""
        times, values = _full_day("2026-09-10", 30.0)

        obs = parse_air_quality(
            _payload(times, values), province_code="62", method=METHOD, min_hours=18
        )

        assert obs[0].province_code == "62"
        assert obs[0].breakdown["province_name"] == "Kalimantan Tengah"

    def test_satuan_tercatat_di_breakdown(self) -> None:
        times, values = _full_day("2026-09-10", 30.0)

        obs = parse_air_quality(
            _payload(times, values), province_code="62", method=METHOD, min_hours=18
        )

        assert obs[0].breakdown["unit"] == "ug/m3"
        assert obs[0].breakdown["hours_used"] == "24"

    def test_sumber_digital_bukan_survey(self) -> None:
        times, values = _full_day("2026-09-10", 30.0)

        obs = parse_air_quality(
            _payload(times, values), province_code="62", method=METHOD, min_hours=18
        )

        assert obs[0].source is SignalSource.DIGITAL

    def test_method_membawa_peringatan_bukan_opini(self) -> None:
        """Peringatan ini ikut tersimpan ke metric_snapshots.method dan dari
        sana tampil di UI. Ia bagian dari data, bukan komentar kode."""
        times, values = _full_day("2026-09-10", 30.0)

        obs = parse_air_quality(
            _payload(times, values), province_code="62", method=METHOD, min_hours=18
        )

        assert METHOD_NOTE in obs[0].method

    def test_nama_metrik_tidak_bertabrakan_dengan_poi(self) -> None:
        assert METRIC.startswith("airquality_")
        assert METRIC not in {"poi", "trust", "approval"}


class TestRespondsGagal:
    def test_bukan_json(self) -> None:
        with pytest.raises(ConnectorError, match="bukan JSON"):
            parse_air_quality(b"<html>", province_code="62", method=METHOD, min_hours=18)

    def test_error_eksplisit_dari_api_diteruskan(self) -> None:
        payload = json.dumps({"error": True, "reason": "rentang di luar cakupan"}).encode()

        with pytest.raises(ConnectorError, match="rentang di luar cakupan"):
            parse_air_quality(payload, province_code="62", method=METHOD, min_hours=18)

    def test_tanpa_blok_hourly(self) -> None:
        with pytest.raises(ConnectorError, match="hourly"):
            parse_air_quality(b'{"latitude": 1}', province_code="62", method=METHOD, min_hours=18)

    def test_tanpa_deret_pm25(self) -> None:
        payload = json.dumps({"hourly": {"time": ["2026-09-10T00:00"]}}).encode()

        with pytest.raises(ConnectorError, match="pm2_5"):
            parse_air_quality(payload, province_code="62", method=METHOD, min_hours=18)


class TestKoordinatProvinsi:
    def test_provinsi_seed_semuanya_punya_koordinat(self) -> None:
        """16 provinsi di db/seed.py harus ada, kalau tidak lapisan kualitas
        udara tidak bisa disandingkan dengan data POI yang sudah ada."""
        dari_seed = {
            "31", "32", "33", "34", "35", "36", "51",
            "12", "16", "14", "64", "73", "52", "53", "94", "81",
        }

        assert dari_seed <= set(PROVINCE_CAPITALS)

    def test_provinsi_inti_karhutla_tersedia(self) -> None:
        """Riau, Jambi, Sumsel, Kalbar, Kalteng, Kalsel — provinsi yang
        studi karhutla-nya memang berjalan."""
        karhutla = {"14", "15", "16", "61", "62", "63"}

        assert karhutla <= set(PROVINCE_CAPITALS)

    def test_koordinat_berada_di_kotak_indonesia(self) -> None:
        """Penjagaan kasar terhadap salah ketik lintang/bujur tertukar —
        koordinat yang salah akan tersimpan sebagai georeferensi 'asli'."""
        for code, (name, lat, lon) in PROVINCE_CAPITALS.items():
            assert -11.5 <= lat <= 6.5, f"{code} {name}: lintang {lat} di luar Indonesia"
            assert 94.0 <= lon <= 141.5, f"{code} {name}: bujur {lon} di luar Indonesia"

    def test_tidak_ada_koordinat_ganda(self) -> None:
        titik = [(lat, lon) for _, lat, lon in PROVINCE_CAPITALS.values()]

        assert len(titik) == len(set(titik))


class TestRegistry:
    def test_terdaftar_tanpa_kredensial(self) -> None:
        from app.connectors.metrics import get_metric_connector

        c = get_metric_connector("openmeteo_air_quality")

        assert c.requires_credential is None

    def test_notes_menolak_klaim_geographic_spread(self) -> None:
        """Komponen risiko itu mengukur sebaran PERCAKAPAN. Kalau catatan ini
        hilang, orang akan mengisinya dari sini dan mengubah arti skornya."""
        from app.connectors.metrics import get_metric_connector

        notes = get_metric_connector("openmeteo_air_quality").notes

        assert "geographic_spread" in notes
        assert "bukan opini" in notes.lower()
