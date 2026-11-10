"""Tes unit services/signal_stats.py: emosi, engagement/jam ramai, jendela."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.services import signal_stats as st

# ------------------------------------------------------------------ emosi ----


def test_emosi_kosong_tidak_membagi_nol():
    out = st.summarize_emotions([])
    assert out.n_total == 0 and out.n_with_emotion == 0
    assert out.coverage == 0.0
    assert set(out.share) == set(st.EMOTION_KEYS)
    assert all(v == 0.0 for v in out.share.values())


def test_baris_tanpa_penanda_masuk_total_bukan_penyebut():
    out = st.summarize_emotions([None, {}, {"anger": 1.0}, {"anger": 0.5, "fear": 0.5}])
    assert out.n_total == 4
    assert out.n_with_emotion == 2
    assert out.coverage == 0.5
    # (1.0 + 0.5) / 2 dan 0.5 / 2
    assert out.share["anger"] == 0.75
    assert out.share["fear"] == 0.25
    assert abs(sum(out.share.values()) - 1.0) < 1e-9


def test_dominan_seri_dihitung_ke_keduanya():
    out = st.summarize_emotions([{"anger": 0.5, "fear": 0.5}, {"joy": 1.0}])
    assert out.dominant["anger"] == 1
    assert out.dominant["fear"] == 1
    assert out.dominant["joy"] == 1


def test_kunci_asing_dan_nilai_nol_diabaikan():
    out = st.summarize_emotions([{"bosan": 1.0}, {"anger": 0.0}, {"joy": 0.4, "bosan": 0.6}])
    assert out.n_total == 3
    assert out.n_with_emotion == 1
    assert out.share["joy"] == 1.0


# -------------------------------------------------------------- aktivitas ----


def test_jam_dan_hari_mengikuti_zona_yang_diminta():
    # Minggu 11 Okt 2026 16.30 UTC = Minggu 23.30 WIB = Senin 00.30 WITA.
    moment = datetime(2026, 10, 11, 16, 30, tzinfo=UTC)
    wib = st.summarize_activity([(moment, 3)], tz="WIB")
    wita = st.summarize_activity([(moment, 3)], tz="WITA")
    assert wib.heatmap[6][23] == 1 and wib.by_day[0].day == date(2026, 10, 11)
    assert wita.heatmap[0][0] == 1 and wita.by_day[0].day == date(2026, 10, 12)
    assert wib.peak == (6, 23, 1)
    assert wita.timezone == "WITA"


def test_engagement_dijumlah_per_hari_dan_negatif_dianggap_nol():
    base = datetime(2026, 10, 12, 2, 0, tzinfo=UTC)
    out = st.summarize_activity(
        [(base, 5), (base + timedelta(hours=1), 0), (base + timedelta(days=1), 7), (base, -4)]
    )
    assert out.n == 4
    assert out.engagement_total == 12
    assert out.n_with_engagement == 2
    assert [(d.volume, d.engagement) for d in out.by_day] == [(3, 5), (1, 7)]
    assert sum(st.hourly_totals(out.heatmap)) == 4
    assert out.peak is not None and out.peak[2] == 2


def test_waktu_tanpa_zona_dianggap_utc():
    naive = datetime(2026, 10, 12, 0, 0)
    out = st.summarize_activity([(naive, 0)], tz="WIB")
    assert out.heatmap[0][7] == 1


def test_aktivitas_kosong_dan_zona_tak_dikenal():
    out = st.summarize_activity([])
    assert out.n == 0 and out.peak is None and out.by_day == []
    with pytest.raises(ValueError):
        st.summarize_activity([], tz="GMT")


# ---------------------------------------------------------------- jendela ----

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def test_jendela_relatif_sama_dengan_perilaku_lama():
    since, until = st.resolve_window(days=30, start=None, end=None, now=NOW)
    assert until == NOW and since == NOW - timedelta(days=30)


def test_jendela_mutlak_mencakup_kedua_tanggal_penuh():
    since, until = st.resolve_window(
        days=30, start=date(2026, 10, 11), end=date(2026, 10, 20), now=NOW
    )
    assert since == datetime(2026, 10, 11, tzinfo=UTC)
    assert until.date() == date(2026, 10, 20)
    assert until < datetime(2026, 10, 21, tzinfo=UTC)
    assert datetime(2026, 10, 20, 23, 59, 59, tzinfo=UTC) <= until


def test_satu_hari_sah():
    since, until = st.resolve_window(
        days=30, start=date(2026, 10, 11), end=date(2026, 10, 11), now=NOW
    )
    assert since.date() == until.date() == date(2026, 10, 11)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 10, 11), None),
        (None, date(2026, 10, 20)),
        (date(2026, 10, 20), date(2026, 10, 11)),
        (date(2025, 1, 1), date(2026, 10, 11)),
    ],
)
def test_jendela_tidak_sah_ditolak(start, end):
    with pytest.raises(st.WindowError):
        st.resolve_window(days=30, start=start, end=end, now=NOW)
