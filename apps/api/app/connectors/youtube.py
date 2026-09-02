"""Percakapan publik dari YouTube Data API v3.

Memakai endpoint `commentThreads` resmi dengan kunci API yang diberikan Google
kepada organisasi pengguna. Tidak ada pengambilan halaman, tidak ada
pembongkaran API internal.

Batasan yang melekat pada sumber ini dan wajib ikut ditampilkan:

- Komentar YouTube adalah **self-selected**. Orang yang berkomentar bukan
  sampel dari populasi mana pun; mereka adalah orang yang kebetulan menonton
  DAN cukup terdorong untuk mengetik. Warna `--social` di frontend ada persis
  untuk menandai ini (CLAUDE.md R1).
- Komentar yang dihapus pemilik kanal atau moderator tidak akan pernah terlihat
  di sini. Ketiadaan kritik di suatu kanal bukan bukti tidak ada kritik.
- Kuota API harian terbatas; `limit` yang besar akan menghabiskannya.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx

from app.config import get_settings
from app.connectors.base import (
    Connector,
    ConnectorError,
    CredentialMissing,
    RawItem,
    register,
)
from app.models.measurement import SignalSource

API_ROOT = "https://www.googleapis.com/youtube/v3"
REQUEST_TIMEOUT = 20.0
#: Batas per halaman yang ditetapkan API-nya sendiri.
PAGE_SIZE = 100


def parse_comment_threads(payload: dict[str, Any]) -> list[RawItem]:
    """Ubah respons commentThreads jadi RawItem. Fungsi murni — inti yang dites.

    Komentar tanpa teks atau tanpa tanggal dilewati, bukan diberi nilai
    pengganti.
    """
    items: list[RawItem] = []
    for thread in payload.get("items", []):
        top = thread.get("snippet", {}).get("topLevelComment", {})
        snippet = top.get("snippet", {})
        text = (snippet.get("textOriginal") or snippet.get("textDisplay") or "").strip()
        external_id = str(top.get("id") or thread.get("id") or "").strip()
        published_raw = snippet.get("publishedAt")
        if not text or not external_id or not published_raw:
            continue
        try:
            published = datetime.fromisoformat(str(published_raw).replace("Z", "+00:00"))
        except ValueError:
            continue

        # Balasan ikut dihitung sebagai keterlibatan: sebuah komentar yang
        # memancing 40 balasan lebih menggerakkan percakapan daripada yang
        # hanya disukai 40 kali tanpa jawaban.
        likes = int(snippet.get("likeCount") or 0)
        replies = int(thread.get("snippet", {}).get("totalReplyCount") or 0)

        items.append(
            RawItem(
                external_id=external_id,
                text=text,
                published_at=published if published.tzinfo else published.replace(tzinfo=UTC),
                # Nama tampilan dipakai sebagai handle mentah di sini; ia
                # LANGSUNG di-hash di lapisan ingest dan tidak pernah disimpan
                # apa adanya (CLAUDE.md §3).
                author_handle=(snippet.get("authorDisplayName") or "").strip() or None,
                engagement=likes + replies,
                url=(
                    f"https://www.youtube.com/watch?v={snippet['videoId']}"
                    if snippet.get("videoId")
                    else None
                ),
                extra={"replies": str(replies), "likes": str(likes)},
            )
        )
    return items


@register
class YouTubeConnector(Connector):
    """Komentar publik pada video atau kanal tertentu."""

    key: ClassVar[str] = "youtube_api"
    label: ClassVar[str] = "YouTube Data API v3 (komentar)"
    source: ClassVar[SignalSource] = SignalSource.SOCIAL
    requires_credential: ClassVar[str | None] = "YOUTUBE_API_KEY"
    config_fields: ClassVar[tuple[str, ...]] = ("video_id",)
    notes: ClassVar[str] = (
        "Komentar bersifat self-selected dan tunduk moderasi kanal — bukan "
        "sampel populasi. Isi 'video_id', atau 'channel_id' untuk seluruh "
        "kanal. Kuota API harian terbatas."
    )

    async def fetch(
        self,
        config: dict[str, object],
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[RawItem]:
        settings = get_settings()
        if not settings.youtube_api_key:
            raise CredentialMissing(
                "Konektor YouTube butuh YOUTUBE_API_KEY di environment backend. "
                "Belum diset di deployment ini."
            )

        video_id = str(config.get("video_id", "")).strip()
        channel_id = str(config.get("channel_id", "")).strip()
        if not video_id and not channel_id:
            raise ConnectorError("konfigurasi konektor kurang: video_id atau channel_id")

        params: dict[str, str | int] = {
            "part": "snippet",
            "maxResults": min(PAGE_SIZE, max(1, limit)),
            "order": "time",
            "textFormat": "plainText",
            "key": settings.youtube_api_key,
        }
        if video_id:
            params["videoId"] = video_id
        else:
            params["allThreadsRelatedToChannelId"] = channel_id

        collected: list[RawItem] = []
        page_token: str | None = None
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                while len(collected) < limit:
                    if page_token:
                        params["pageToken"] = page_token
                    response = await client.get(f"{API_ROOT}/commentThreads", params=params)
                    response.raise_for_status()
                    payload = response.json()
                    batch = parse_comment_threads(payload)
                    if not batch:
                        break
                    collected.extend(batch)
                    page_token = payload.get("nextPageToken")
                    if not page_token:
                        break
        except httpx.HTTPStatusError as e:
            # 403 di API ini hampir selalu berarti kuota habis atau komentar
            # dimatikan — dua hal yang perlu dibedakan pengguna dari "gagal".
            raise ConnectorError(
                f"YouTube API menolak permintaan ({e.response.status_code}). "
                "Periksa kuota harian, status kunci API, dan apakah komentar "
                "diaktifkan pada video/kanal itu."
            ) from e
        except httpx.HTTPError as e:
            raise ConnectorError(f"YouTube API tidak bisa dihubungi: {e}") from e

        if since is not None:
            cutoff = since if since.tzinfo else since.replace(tzinfo=UTC)
            collected = [i for i in collected if i.published_at >= cutoff]
        return collected[:limit]
