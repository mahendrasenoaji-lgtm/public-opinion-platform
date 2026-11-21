"""Panggilan YouTube Data API v3 untuk "Tarik tema" (lihat services/theme_pull.py).

Bukan konektor terdaftar: ia tidak muncul di formulir "Tambah sumber" dan tidak
ikut `collect-all`. Pekerja di routers/theme_pulls.py memanggil fungsi-fungsi
di sini satu langkah sekali jalan.

Hanya API resmi dengan kunci organisasi (batas legal di base.py). Yang bisa
dites tanpa jaringan — membaca respons — ada di fungsi `parse_*` murni.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import get_settings
from app.connectors.base import ConnectorError, CredentialMissing, RawItem
from app.connectors.theme_common import CommentPage, ItemUnavailable, QuotaExceeded
from app.connectors.youtube import API_ROOT, REQUEST_TIMEOUT

#: Nama lama dipertahankan: tes dan pemanggil memakai `yt.VideoUnavailable`.
VideoUnavailable = ItemUnavailable

__all__ = ["CommentPage", "QuotaExceeded", "VideoUnavailable"]


def _key() -> str:
    key = get_settings().youtube_api_key
    if not key:
        raise CredentialMissing(
            "Tarik tema butuh YOUTUBE_API_KEY di environment backend. "
            "Belum diset di deployment ini."
        )
    return key


def classify_error(status: int, body: str) -> ConnectorError:
    """Bedakan kuota habis / video tak tersedia / galat lain. Fungsi murni."""
    low = body.lower()
    if status == 403 and ("quotaexceeded" in low or "dailylimitexceeded" in low or "quota" in low):
        return QuotaExceeded("Kuota harian YouTube API habis.")
    if status == 403 and "commentsdisabled" in low:
        return VideoUnavailable("komentar dimatikan pemilik video")
    if status == 404 or "videonotfound" in low:
        return VideoUnavailable("video tidak ditemukan (dihapus atau privat)")
    if status == 403 and "forbidden" in low:
        return VideoUnavailable("komentar tidak bisa dibuka (dibatasi pemilik video)")
    return ConnectorError(f"YouTube API membalas {status}.")


async def _get(client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> dict[str, Any]:
    params = {**params, "key": _key()}
    try:
        response = await client.get(f"{API_ROOT}/{path}", params=params)
    except httpx.HTTPError as e:
        raise ConnectorError(f"YouTube API tidak bisa dihubungi: {type(e).__name__}") from e
    if response.status_code >= 400:
        raise classify_error(response.status_code, response.text[:2000])
    data: dict[str, Any] = response.json()
    return data


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=REQUEST_TIMEOUT)


def parse_search_ids(payload: dict[str, Any]) -> tuple[list[str], str | None]:
    ids = [
        str(item.get("id", {}).get("videoId") or "")
        for item in payload.get("items", [])
        if item.get("id", {}).get("videoId")
    ]
    return ids, payload.get("nextPageToken")


async def search_page(
    http: httpx.AsyncClient,
    *,
    query: str,
    published_after: str,
    published_before: str,
    page_token: str | None,
    max_results: int,
) -> tuple[list[str], str | None]:
    params: dict[str, Any] = {
        "part": "snippet",
        "type": "video",
        "q": query,
        "order": "relevance",
        "maxResults": max_results,
        "publishedAfter": published_after,
        "publishedBefore": published_before,
        "regionCode": "ID",
        "relevanceLanguage": "id",
    }
    if page_token:
        params["pageToken"] = page_token
    return parse_search_ids(await _get(http, "search", params))


def parse_videos(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        if not item.get("id") or not snippet.get("title"):
            continue
        out.append(
            {
                "id": str(item["id"]),
                "title": str(snippet.get("title") or ""),
                "description": str(snippet.get("description") or ""),
                "channel": str(snippet.get("channelTitle") or ""),
                "published_at": snippet.get("publishedAt"),
                "comment_count": int(stats.get("commentCount") or 0),
            }
        )
    return out


async def video_details(http: httpx.AsyncClient, ids: list[str]) -> list[dict[str, Any]]:
    payload = await _get(
        http,
        "videos",
        {"part": "snippet,statistics", "id": ",".join(ids), "maxResults": len(ids)},
    )
    return parse_videos(payload)


def _ts(raw: object) -> datetime | None:
    try:
        moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def comment_item(
    comment: dict[str, Any],
    video_id: str,
    *,
    replies: int = 0,
    parent_id: str | None = None,
    parent_author: str | None = None,
) -> RawItem | None:
    """Satu komentar atau balasan → RawItem. Fungsi murni.

    Nama tampilan dipakai sebagai handle mentah di sini dan LANGSUNG di-hash di
    lapisan ingest (CLAUDE.md §3). Relasi balasan diisi karena API-nya sendiri
    menyatakannya (`parentId`), bukan ditebak dari teks.
    """
    snippet = comment.get("snippet", {})
    text = (snippet.get("textOriginal") or snippet.get("textDisplay") or "").strip()
    cid = str(comment.get("id") or "").strip()
    published = _ts(snippet.get("publishedAt"))
    if not text or not cid or published is None:
        return None
    likes = int(snippet.get("likeCount") or 0)
    return RawItem(
        external_id=cid,
        text=text,
        published_at=published,
        author_handle=(snippet.get("authorDisplayName") or "").strip() or None,
        engagement=likes + replies,
        url=f"https://www.youtube.com/watch?v={video_id}&lc={cid}",
        reply_to_handle=parent_author if parent_id else None,
        conversation_id=parent_id,
        extra={"likes": str(likes), "replies": str(replies), "video_id": video_id},
    )


def parse_threads(
    payload: dict[str, Any], video_id: str
) -> tuple[list[RawItem], list[tuple[str, str | None, int]]]:
    """Utas → (komentar utama + balasan yang ikut, utas yang balasannya belum lengkap).

    Elemen kedua: (id komentar utama, nama penulisnya, jumlah balasan total)
    untuk utas yang balasannya lebih banyak dari yang dikirim inline.
    """
    items: list[RawItem] = []
    incomplete: list[tuple[str, str | None, int]] = []
    for thread in payload.get("items", []):
        snip = thread.get("snippet", {})
        top = snip.get("topLevelComment", {})
        total = int(snip.get("totalReplyCount") or 0)
        top_item = comment_item(top, video_id, replies=total)
        if top_item is None:
            continue
        items.append(top_item)
        inline = thread.get("replies", {}).get("comments", [])
        if total > len(inline):
            incomplete.append((top_item.external_id, top_item.author_handle, total))
            continue
        for reply in inline:
            r = comment_item(
                reply,
                video_id,
                parent_id=top_item.external_id,
                parent_author=top_item.author_handle,
            )
            if r is not None:
                items.append(r)
    return items, incomplete


async def comment_page(
    http: httpx.AsyncClient,
    *,
    video_id: str,
    page_token: str | None,
    include_replies: bool,
) -> CommentPage:
    params: dict[str, Any] = {
        "part": "snippet,replies" if include_replies else "snippet",
        "videoId": video_id,
        "maxResults": 100,
        "order": "time",
        "textFormat": "plainText",
    }
    if page_token:
        params["pageToken"] = page_token
    payload = await _get(http, "commentThreads", params)
    units = 1
    items, incomplete = parse_threads(payload, video_id)
    if not include_replies:
        items = [i for i in items if i.conversation_id is None]
    else:
        for parent_id, parent_author, _total in incomplete:
            token: str | None = None
            while True:
                rp: dict[str, Any] = {
                    "part": "snippet",
                    "parentId": parent_id,
                    "maxResults": 100,
                    "textFormat": "plainText",
                }
                if token:
                    rp["pageToken"] = token
                try:
                    data = await _get(http, "comments", rp)
                except VideoUnavailable:
                    break
                units += 1
                for reply in data.get("items", []):
                    r = comment_item(
                        reply, video_id, parent_id=parent_id, parent_author=parent_author
                    )
                    if r is not None:
                        items.append(r)
                token = data.get("nextPageToken")
                if not token:
                    break
    return CommentPage(items=items, next_token=payload.get("nextPageToken"), units=units)
