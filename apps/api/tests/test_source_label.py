"""Tes label sumber di ringkasan collect-all — fungsi murni, tanpa database."""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/z")
os.environ.setdefault("JWT_SECRET", "x" * 40)

from app.models.signal import DataSource  # noqa: E402
from app.routers.signals import _source_label  # noqa: E402


def _source(connector: str, config: dict[str, str]) -> DataSource:
    return DataSource(connector=connector, config=config)


def test_label_eksplisit_menang() -> None:
    src = _source("rss", {"label": "Antara", "feed_url": "https://contoh.id/rss"})
    assert _source_label(src) == "Antara"


def test_rss_tanpa_label_memakai_url_feed() -> None:
    assert _source_label(_source("rss", {"feed_url": "https://contoh.id/rss"})) == (
        "https://contoh.id/rss"
    )


def test_youtube_menyebut_videonya_bukan_none() -> None:
    src = _source("youtube_api", {"video_id": "lrqC8RB9QS4"})
    assert _source_label(src) == "youtube_api video_id=lrqC8RB9QS4"


def test_konfigurasi_kosong_jatuh_ke_nama_konektor() -> None:
    assert _source_label(_source("manual", {})) == "manual"
