"""Unggahan kanal YouTube RESMI lembaga, untuk modul Kinerja Komunikasi.

Berbeda dari `youtube.py` (komentar warga, sumber SOCIAL), modul ini membaca
daftar video yang diunggah kanal lembaga beserta angka publiknya. Hasilnya
masuk ke `official_posts`, BUKAN ke `mentions`: pernyataan lembaga tidak boleh
ikut terhitung sebagai percakapan publik (CLAUDE.md R1). Karena itu modul ini
sengaja tidak didaftarkan sebagai `Connector` sumber sinyal.

Hanya API resmi (YouTube Data API v3) dengan kunci organisasi pengguna; lihat
batas legal di `base.py`.

## Kuota

Tiga endpoint, masing-masing 1 unit per panggilan (kuota bawaan 10.000/hari):
`channels.list` sekali, `playlistItems.list` per 50 video, `videos.list` per 50
video. Mengambil 200 video memakai sekitar 9 unit.

## Batas yang melekat dan wajib ikut dibaca

- Yang tampil publik hanya tayangan, suka, dan jumlah komentar. Share, reach,
  impressions, dan durasi tonton hanya ada di YouTube Studio pemilik kanal.
- Suka bisa disembunyikan pemilik kanal dan komentar bisa dimatikan; angkanya
  lalu dicatat kosong, tidak nol.
- Jumlah pelanggan dibulatkan YouTube (tiga angka penting) dan bisa
  disembunyikan. Angka yang dipakai adalah angka SAAT pengambilan, bukan saat
  video diunggah.
- Video yang dihapus atau dijadikan privat tidak terlihat.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.config import get_settings
from app.connectors.base import ConnectorError, CredentialMissing
from app.connectors.youtube import API_ROOT, REQUEST_TIMEOUT

#: Batas per halaman `playlistItems.list` dan jumlah id per `videos.list`.
PAGE_SIZE = 50
DEFAULT_MAX_VIDEOS = 50
MAX_MAX_VIDEOS = 200
DEFAULT_SINCE_DAYS = 90
MAX_SINCE_DAYS = 365

PLATFORM = "youtube"

_CHANNEL_ID = re.compile(r"^UC[0-9A-Za-z_-]{22}$")
_HANDLE = re.compile(r"^@?[0-9A-Za-z._-]{3,30}$")
_URL = re.compile(
    r"youtube\.com/(?:channel/(UC[0-9A-Za-z_-]{22})|(@[0-9A-Za-z._-]{3,30}))", re.IGNORECASE
)
_DURATION = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


@dataclass(frozen=True, slots=True)
class ChannelRef:
    """Kanal yang diketik pengguna, sudah dinormalkan. Tepat satu terisi."""

    channel_id: str | None
    handle: str | None


@dataclass(frozen=True, slots=True)
class ChannelInfo:
    channel_id: str
    title: str
    #: `customUrl` dari API, mis. "@kanalresmi". None bila kanal tidak punya.
    handle: str | None
    uploads_playlist: str
    #: None bila pemilik kanal menyembunyikannya.
    subscribers: int | None


@dataclass(frozen=True, slots=True)
class VideoStats:
    video_id: str
    title: str
    published_at: datetime
    kind: str
    views: int | None
    likes: int | None
    comments: int | None


@dataclass(frozen=True, slots=True)
class ChannelFetch:
    channel: ChannelInfo
    videos: list[VideoStats]
    quota_units: int
    #: True bila pengambilan berhenti karena `max_videos`, bukan karena batas tanggal.
    truncated: bool


# ------------------------------------------------------ fungsi murni ----


def parse_channel_input(raw: str) -> ChannelRef:
    """Terima ID kanal (UC…), handle (@nama atau nama), atau URL kanal.

    Nama kanal bebas (judul) sengaja tidak diterima: pencarian judul memakan
    100 unit kuota dan bisa salah kanal. Akun resmi harus disebut pasti.
    """
    s = raw.strip()
    m = _URL.search(s)
    if m:
        s = m.group(1) or m.group(2)
    if _CHANNEL_ID.match(s):
        return ChannelRef(channel_id=s, handle=None)
    if _HANDLE.match(s):
        return ChannelRef(channel_id=None, handle=s if s.startswith("@") else f"@{s}")
    raise ConnectorError(
        "Kanal harus ditulis sebagai handle (@namakanal), ID kanal (UC…), atau URL kanal YouTube."
    )


def _count(value: Any) -> int | None:
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def _ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def parse_channel(payload: dict[str, Any]) -> ChannelInfo | None:
    """Respons `channels.list` (part snippet,statistics,contentDetails)."""
    items = payload.get("items") or []
    if not items:
        return None
    it = items[0]
    snippet = it.get("snippet", {})
    stats = it.get("statistics", {})
    uploads = it.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    channel_id = it.get("id")
    if not channel_id or not uploads:
        return None
    custom = (snippet.get("customUrl") or "").strip() or None
    if custom and not custom.startswith("@"):
        custom = f"@{custom}"
    hidden = bool(stats.get("hiddenSubscriberCount"))
    return ChannelInfo(
        channel_id=str(channel_id),
        title=(snippet.get("title") or "").strip() or str(channel_id),
        handle=custom,
        uploads_playlist=str(uploads),
        subscribers=None if hidden else _count(stats.get("subscriberCount")),
    )


def parse_playlist_items(payload: dict[str, Any]) -> list[tuple[str, datetime]]:
    """Respons `playlistItems.list` (part contentDetails): (video_id, tanggal unggah).

    Video privat atau terhapus tidak punya `videoPublishedAt` dan dilewati.
    """
    out: list[tuple[str, datetime]] = []
    for it in payload.get("items", []):
        cd = it.get("contentDetails", {})
        vid = cd.get("videoId")
        published = _ts(cd.get("videoPublishedAt"))
        if vid and published:
            out.append((str(vid), published))
    return out


def parse_duration(iso: str | None) -> int | None:
    """Durasi ISO 8601 (mis. PT1H2M3S) menjadi detik."""
    if not iso:
        return None
    m = _DURATION.match(iso)
    if not m or not any(m.groups()):
        return None
    d, h, mi, s = (int(g) if g else 0 for g in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def parse_videos(payload: dict[str, Any]) -> list[VideoStats]:
    """Respons `videos.list` (part snippet,statistics,liveStreamingDetails).

    `kind` hanya membedakan siaran langsung dari video biasa. Shorts tidak
    ditebak dari durasi: API tidak menyatakannya dan batas durasinya berubah.
    """
    out: list[VideoStats] = []
    for it in payload.get("items", []):
        vid = it.get("id")
        snippet = it.get("snippet", {})
        published = _ts(snippet.get("publishedAt"))
        if not vid or not published:
            continue
        stats = it.get("statistics", {})
        live = "liveStreamingDetails" in it or snippet.get("liveBroadcastContent") in (
            "live",
            "upcoming",
        )
        out.append(
            VideoStats(
                video_id=str(vid),
                title=(snippet.get("title") or "").strip(),
                published_at=published,
                kind="siaran langsung" if live else "video",
                views=_count(stats.get("viewCount")),
                # Tidak ada kunci = disembunyikan atau dimatikan; dicatat kosong.
                likes=_count(stats.get("likeCount")),
                comments=_count(stats.get("commentCount")),
            )
        )
    return out


def select_recent(
    items: list[tuple[str, datetime]], cutoff: datetime, room: int
) -> tuple[list[str], bool, bool]:
    """Ambil id yang tidak lebih tua dari `cutoff`, paling banyak `room`.

    Kembalian: (id terpilih, halaman sudah memuat video yang lebih tua dari
    batas sehingga tidak perlu membalik halaman lagi, ada video dalam batas
    tanggal yang tidak terambil karena `room` habis). Daftar unggahan kanal
    diurutkan dari yang terbaru.
    """
    fresh = [vid for vid, ts in items if ts >= cutoff]
    reached = any(ts < cutoff for _, ts in items)
    return fresh[:room], reached, len(fresh) > room


def to_post_rows(fetch: ChannelFetch, captured_at: datetime) -> list[dict[str, Any]]:
    """Baris siap simpan untuk `official_posts`. Share tidak tampil publik: kosong."""
    ch = fetch.channel
    account = ch.handle or ch.channel_id
    return [
        {
            "platform": PLATFORM,
            "account": account,
            "external_id": v.video_id,
            "url": f"https://www.youtube.com/watch?v={v.video_id}",
            "posted_at": v.published_at,
            "kind": v.kind,
            "caption": v.title or None,
            "likes": v.likes,
            "comments": v.comments,
            "shares": None,
            "views": v.views,
            "followers": ch.subscribers,
            "captured_at": captured_at,
        }
        for v in fetch.videos
    ]


# ------------------------------------------- balasan akun resmi (O8) ----

#: Utas komentar per video dan video per panggilan untuk ukuran tingkat jawab.
THREADS_PER_VIDEO = 100
DEFAULT_RESPONSE_VIDEOS = 20
MAX_RESPONSE_VIDEOS = 50


@dataclass(frozen=True, slots=True)
class Thread:
    """Satu komentar tingkat atas pada video kanal resmi.

    Hanya hidup di memori selama hitungan: teks komentar warga TIDAK disimpan
    oleh modul Kinerja, dan penulisnya tidak dibaca sama sekali.
    """

    text: str
    owner_replied: bool
    #: Balasan lebih banyak daripada yang disertakan API (maksimal 5), dan di
    #: antara yang disertakan tidak ada balasan pemilik kanal: belum pasti.
    replies_truncated: bool


def parse_threads(payload: dict[str, Any]) -> list[Thread]:
    """Utas dari `commentThreads.list` (part=snippet,replies).

    Komentar tingkat atas yang ditulis pemilik kanal sendiri dilewati: itu
    bukan pertanyaan publik. Pemilik kanal dikenali dari `authorChannelId`
    yang sama dengan `channelId` video, bukan dari nama tampilan.
    """
    out: list[Thread] = []
    for item in payload.get("items", []):
        snippet = item.get("snippet") or {}
        owner = snippet.get("channelId")
        top = (snippet.get("topLevelComment") or {}).get("snippet") or {}
        if not owner or (top.get("authorChannelId") or {}).get("value") == owner:
            continue
        text = top.get("textOriginal") or top.get("textDisplay") or ""
        replies = (item.get("replies") or {}).get("comments") or []
        replied = any(
            ((r.get("snippet") or {}).get("authorChannelId") or {}).get("value") == owner
            for r in replies
        )
        total = _count(snippet.get("totalReplyCount")) or 0
        out.append(
            Thread(
                text=str(text),
                owner_replied=replied,
                replies_truncated=not replied and total > len(replies),
            )
        )
    return out


@dataclass(frozen=True, slots=True)
class ThreadFetch:
    threads: list[Thread]
    n_videos: int
    #: Video yang komentarnya dimatikan atau tidak bisa dibaca.
    n_videos_skipped: int
    quota_units: int


async def fetch_threads(
    video_ids: list[str], *, client: httpx.AsyncClient | None = None
) -> ThreadFetch:
    """Satu halaman utas terbaru (maksimal 100) per video; 1 unit kuota per video."""
    settings = get_settings()
    if not settings.youtube_api_key:
        raise CredentialMissing(
            "Pengambilan komentar YouTube butuh YOUTUBE_API_KEY di environment backend."
        )
    ids = video_ids[:MAX_RESPONSE_VIDEOS]
    threads: list[Thread] = []
    skipped = units = 0
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
    try:
        for video_id in ids:
            r = await http.get(
                f"{API_ROOT}/commentThreads",
                params={
                    "part": "snippet,replies",
                    "videoId": video_id,
                    "maxResults": THREADS_PER_VIDEO,
                    "order": "time",
                    "textFormat": "plainText",
                    "key": settings.youtube_api_key,
                },
            )
            units += 1
            if r.status_code in (403, 404):
                # 403 commentsDisabled / 404 video hilang: lewati video ini.
                # 403 kuota habis juga jatuh ke sini; bila SEMUA video
                # terlewat, pemanggil melaporkannya sebagai kegagalan.
                skipped += 1
                continue
            r.raise_for_status()
            threads.extend(parse_threads(r.json()))
    except httpx.HTTPStatusError as e:
        raise ConnectorError(
            f"YouTube API menolak permintaan ({e.response.status_code}). "
            "Periksa kuota harian dan status kunci API."
        ) from e
    except httpx.HTTPError as e:
        raise ConnectorError(f"YouTube API tidak bisa dihubungi: {e}") from e
    finally:
        if owns_client:
            await http.aclose()
    if ids and skipped == len(ids):
        raise ConnectorError(
            "Tidak ada video yang komentarnya bisa dibaca (komentar dimatikan, video hilang, "
            "atau kuota harian habis)."
        )
    return ThreadFetch(
        threads=threads, n_videos=len(ids) - skipped, n_videos_skipped=skipped, quota_units=units
    )


# ---------------------------------------------------------------- I/O ----


async def fetch_channel_uploads(
    raw_channel: str,
    *,
    since_days: int = DEFAULT_SINCE_DAYS,
    max_videos: int = DEFAULT_MAX_VIDEOS,
    now: datetime | None = None,
    client: httpx.AsyncClient | None = None,
) -> ChannelFetch:
    """Ambil video kanal dalam `since_days` terakhir, paling banyak `max_videos`."""
    settings = get_settings()
    if not settings.youtube_api_key:
        raise CredentialMissing(
            "Pengambilan kanal YouTube butuh YOUTUBE_API_KEY di environment backend."
        )
    ref = parse_channel_input(raw_channel)
    max_videos = max(1, min(max_videos, MAX_MAX_VIDEOS))
    since_days = max(1, min(since_days, MAX_SINCE_DAYS))
    cutoff = (now or datetime.now(UTC)) - timedelta(days=since_days)
    key = settings.youtube_api_key
    units = 0

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
    try:
        params: dict[str, str | int] = {
            "part": "snippet,statistics,contentDetails",
            "key": key,
        }
        if ref.channel_id:
            params["id"] = ref.channel_id
        else:
            params["forHandle"] = ref.handle or ""
        r = await http.get(f"{API_ROOT}/channels", params=params)
        units += 1
        r.raise_for_status()
        channel = parse_channel(r.json())
        if channel is None:
            raise ConnectorError(
                f"Kanal {ref.channel_id or ref.handle} tidak ditemukan di YouTube. "
                "Periksa ejaan handle atau ID kanalnya."
            )

        ids: list[str] = []
        page_token: str | None = None
        truncated = False
        while True:
            pparams: dict[str, str | int] = {
                "part": "contentDetails",
                "playlistId": channel.uploads_playlist,
                "maxResults": PAGE_SIZE,
                "key": key,
            }
            if page_token:
                pparams["pageToken"] = page_token
            r = await http.get(f"{API_ROOT}/playlistItems", params=pparams)
            units += 1
            if r.status_code == 404:
                # Kanal tanpa video sama sekali: playlist unggahannya tidak ada.
                break
            r.raise_for_status()
            payload = r.json()
            chosen, reached, left_out = select_recent(
                parse_playlist_items(payload), cutoff, max_videos - len(ids)
            )
            ids.extend(chosen)
            page_token = payload.get("nextPageToken")
            if len(ids) >= max_videos:
                truncated = left_out or (bool(page_token) and not reached)
                break
            if reached or not page_token:
                break

        videos: list[VideoStats] = []
        for start in range(0, len(ids), PAGE_SIZE):
            r = await http.get(
                f"{API_ROOT}/videos",
                params={
                    "part": "snippet,statistics,liveStreamingDetails",
                    "id": ",".join(ids[start : start + PAGE_SIZE]),
                    "maxResults": PAGE_SIZE,
                    "key": key,
                },
            )
            units += 1
            r.raise_for_status()
            videos.extend(parse_videos(r.json()))
    except httpx.HTTPStatusError as e:
        raise ConnectorError(
            f"YouTube API menolak permintaan ({e.response.status_code}). "
            "Periksa kuota harian dan status kunci API."
        ) from e
    except httpx.HTTPError as e:
        raise ConnectorError(f"YouTube API tidak bisa dihubungi: {e}") from e
    finally:
        if owns_client:
            await http.aclose()

    videos.sort(key=lambda v: v.published_at, reverse=True)
    return ChannelFetch(channel=channel, videos=videos, quota_units=units, truncated=truncated)
