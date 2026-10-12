"""Penemuan video YouTube per kata kunci (`search.list`).

Menjawab satu kelemahan daftar video yang didaftarkan tangan: video baru
tentang tema proyek tidak pernah terjaring sendiri. Sumber jenis ini TIDAK
menyimpan konten apa pun. Tugasnya hanya menemukan video, lalu `collect-all`
mendaftarkan tiap video baru sebagai sumber `youtube_api` biasa — sehingga
komentarnya dikumpulkan lewat jalur yang sama, terlihat di `/sinyal`, dan bisa
dihapus satu per satu oleh peneliti.

## Kuota — alasan sumber ini dibatasi ketat

`search.list` memakan **100 unit** per panggilan, seratus kali `commentThreads`
(1 unit). Kuota bawaan 10.000 unit per hari. Karena itu:

- pencarian hanya dijalankan bila sudah lewat `interval_hours` sejak pencarian
  terakhir (bawaan 24 jam, minimum 6) — bukan di setiap run terjadwal;
- satu panggilan per pencarian, tanpa membalik halaman;
- jumlah video yang didaftarkan per pencarian dibatasi `max_videos`.

Satu sumber pencarian dengan nilai bawaan memakai 100 unit per hari.

## Batas yang melekat dan wajib ikut dibaca

- Hasil pencarian diurutkan YouTube, bukan sampel. Video yang ditemukan adalah
  yang dipilih algoritma peringkat untuk kata kunci itu; menambahkannya
  otomatis memperbesar korpus, TIDAK membuatnya lebih representatif.
- Kata kunci yang longgar menjaring video di luar tema. Judul video ikut
  disimpan sebagai label sumber supaya peneliti bisa memeriksa dan membuang
  yang tidak relevan.
- Hanya API resmi dengan kunci organisasi; lihat batas legal di `base.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import httpx

from app.config import get_settings
from app.connectors.base import (
    Connector,
    ConnectorError,
    CredentialMissing,
    RawItem,
    register,
    require,
)
from app.connectors.youtube import API_ROOT, REQUEST_TIMEOUT
from app.models.measurement import SignalSource

KEY = "youtube_search"

#: Biaya kuota satu panggilan `search.list`, menurut dokumentasi API-nya.
SEARCH_QUOTA_UNITS = 100

DEFAULT_MAX_VIDEOS = 5
MAX_MAX_VIDEOS = 25
DEFAULT_INTERVAL_HOURS = 24
MIN_INTERVAL_HOURS = 6
DEFAULT_PUBLISHED_WITHIN_DAYS = 14
MAX_PUBLISHED_WITHIN_DAYS = 90
MAX_QUERY_LENGTH = 120


@dataclass(frozen=True, slots=True)
class DiscoveredVideo:
    video_id: str
    title: str
    channel: str
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class SearchConfig:
    query: str
    max_videos: int
    interval_hours: int
    published_within_days: int


def _int_field(config: dict[str, Any], name: str, default: int, low: int, high: int) -> int:
    raw = str(config.get(name, "")).strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as e:
        raise ConnectorError(f"{name} harus bilangan bulat") from e
    if not low <= value <= high:
        raise ConnectorError(f"{name} harus di antara {low} dan {high}")
    return value


def parse_config(config: dict[str, Any]) -> SearchConfig:
    """Baca dan batasi konfigurasi. Fungsi murni; melempar ConnectorError."""
    query = require(config, ("query",))["query"]
    if len(query) > MAX_QUERY_LENGTH:
        raise ConnectorError(f"query maksimal {MAX_QUERY_LENGTH} karakter")
    return SearchConfig(
        query=query,
        max_videos=_int_field(config, "max_videos", DEFAULT_MAX_VIDEOS, 1, MAX_MAX_VIDEOS),
        interval_hours=_int_field(
            config, "interval_hours", DEFAULT_INTERVAL_HOURS, MIN_INTERVAL_HOURS, 24 * 30
        ),
        published_within_days=_int_field(
            config,
            "published_within_days",
            DEFAULT_PUBLISHED_WITHIN_DAYS,
            1,
            MAX_PUBLISHED_WITHIN_DAYS,
        ),
    )


def is_due(config: SearchConfig, *, last_run: datetime | None, now: datetime) -> bool:
    """Apakah pencarian boleh dijalankan lagi. Fungsi murni.

    Inilah yang menjaga kuota: run terjadwal bisa datang tiap 30 menit, tapi
    pencarian hanya jalan sekali per `interval_hours`.
    """
    if last_run is None:
        return True
    return now - last_run >= timedelta(hours=config.interval_hours)


def parse_search(payload: dict[str, Any]) -> list[DiscoveredVideo]:
    """Ubah respons `search.list` jadi daftar video. Fungsi murni — inti yang dites.

    Hasil yang bukan video (kanal, playlist) dan yang tanpa ID dilewati.
    Urutan dipertahankan dan ID ganda dibuang.
    """
    videos: list[DiscoveredVideo] = []
    seen: set[str] = set()
    for item in payload.get("items", []):
        video_id = str((item.get("id") or {}).get("videoId") or "").strip()
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        snippet = item.get("snippet") or {}
        published: datetime | None = None
        raw = snippet.get("publishedAt")
        if raw:
            try:
                published = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                published = None
        videos.append(
            DiscoveredVideo(
                video_id=video_id,
                title=str(snippet.get("title") or "").strip(),
                channel=str(snippet.get("channelTitle") or "").strip(),
                published_at=published,
            )
        )
    return videos


def video_label(video: DiscoveredVideo) -> str:
    """Label sumber untuk video temuan: judul dan kanalnya, dipotong wajar."""
    title = video.title or video.video_id
    label = f"{title} — {video.channel}" if video.channel else title
    return label if len(label) <= 140 else label[:139] + "…"


@register
class YouTubeSearchConnector(Connector):
    """Menemukan video baru per kata kunci; tidak menyimpan konten sendiri."""

    key: ClassVar[str] = KEY
    label: ClassVar[str] = "YouTube — temukan video per kata kunci"
    source: ClassVar[SignalSource] = SignalSource.SOCIAL
    requires_credential: ClassVar[str | None] = "YOUTUBE_API_KEY"
    config_fields: ClassVar[tuple[str, ...]] = ("query",)
    optional_fields: ClassVar[tuple[str, ...]] = (
        "max_videos",
        "interval_hours",
        "published_within_days",
        "label",
    )
    notes: ClassVar[str] = (
        "Mencari video baru untuk kata kunci dan mendaftarkannya otomatis "
        "sebagai sumber komentar. Tiap pencarian memakai 100 unit kuota API "
        f"(bawaan sekali per {DEFAULT_INTERVAL_HOURS} jam, {DEFAULT_MAX_VIDEOS} "
        "video). Hasilnya urutan peringkat YouTube, bukan sampel: korpus "
        "membesar, tidak menjadi lebih representatif. Periksa judul video "
        "temuan dan hapus yang di luar tema."
    )

    def validate_config(self, config: dict[str, str]) -> None:
        parse_config(dict(config))

    async def fetch(
        self,
        config: dict[str, object],
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[RawItem]:
        # Sumber ini tidak punya konten sendiri; komentar dikumpulkan sumber
        # `youtube_api` yang didaftarkannya. `collect-all` memanggil
        # `discover`, bukan `fetch`.
        return []

    async def discover(self, config: dict[str, object]) -> list[DiscoveredVideo]:
        """Satu panggilan `search.list`. Memakai 100 unit kuota."""
        settings = get_settings()
        if not settings.youtube_api_key:
            raise CredentialMissing(
                "Penemuan video YouTube butuh YOUTUBE_API_KEY di environment backend. "
                "Belum diset di deployment ini."
            )
        cfg = parse_config(dict(config))
        published_after = datetime.now(UTC) - timedelta(days=cfg.published_within_days)
        params: dict[str, str | int] = {
            "part": "snippet",
            "type": "video",
            "q": cfg.query,
            "order": "relevance",
            "maxResults": cfg.max_videos,
            "publishedAfter": published_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "regionCode": "ID",
            "relevanceLanguage": "id",
            "key": settings.youtube_api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(f"{API_ROOT}/search", params=params)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ConnectorError(
                f"YouTube API menolak pencarian ({e.response.status_code}). "
                "Periksa kuota harian (pencarian memakai 100 unit) dan status kunci API."
            ) from e
        except httpx.HTTPError as e:
            raise ConnectorError(f"YouTube API tidak bisa dihubungi: {e}") from e
        return parse_search(response.json())[: cfg.max_videos]
