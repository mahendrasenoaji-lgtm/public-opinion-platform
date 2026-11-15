"""Jendela waktu bersama untuk endpoint agregat di luar `routers/signals.py`.

Jendela relatif (`days`) atau mutlak (`start` + `end`, keduanya inklusif, UTC).
Jendela mutlak dibutuhkan untuk data historis: data Oktober tidak boleh hilang
dari Tema, Jaringan, atau Pengaruh hanya karena hari ini sudah lewat 30 hari.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import HTTPException, Query

from app.services import signal_stats

StartDate = Query(default=None, description="Tanggal awal (UTC, inklusif), bersama `end`")
EndDate = Query(default=None, description="Tanggal akhir (UTC, inklusif), bersama `start`")


def window(days: int, start: date | None, end: date | None) -> tuple[datetime, datetime]:
    try:
        return signal_stats.resolve_window(days=days, start=start, end=end, now=datetime.now(UTC))
    except signal_stats.WindowError as e:
        raise HTTPException(422, str(e)) from e
