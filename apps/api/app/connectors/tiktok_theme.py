"""Panggilan TikTok Research API untuk "Tarik tema" (lihat services/theme_pull.py).

API resmi untuk peneliti nirlaba yang proyeknya disetujui TikTok. Kunci aplikasi
(``TIKTOK_CLIENT_KEY``/``TIKTOK_CLIENT_SECRET``) ditukar dengan token
*client credentials*; tidak ada akun pribadi yang dipakai (batas di base.py).

Alur yang dipetakan ke mesin tarik tema:

- ``search``   — ``POST /v2/research/video/query/``: video berkata kunci dalam
  rentang tanggal (paling panjang 30 hari per permintaan, jadi periode dipecah
  per jendela), ``region_code = ID``. Hasilnya sudah membawa deskripsi dan
  jumlah komentar, sehingga tahap detail tidak memanggil API lagi;
- ``comments`` — ``POST /v2/research/video/comment/list/`` per video.

Komentar Research API tidak membawa nama akun. Karena itu ``author_handle``
kosong dan konten TikTok tidak ikut hitungan akun berbeda maupun graf balasan
antar-akun; relasi balasan tetap tercatat lewat ``parent_comment_id``.

Endpoint, nama field, dan batasnya mengikuti dokumentasi publik TikTok for
Developers (Research API) per November 2026. Belum pernah dijalankan terhadap
API sungguhan karena akses belum disetujui; cek ulang ``parse_*`` begitu kunci
diisi.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from app.config import get_settings
from app.connectors.base import ConnectorError, CredentialMissing, RawItem
from app.connectors.theme_common import (
    CommentPage,
    ItemUnavailable,
    PullRejected,
    QuotaExceeded,
    SearchPage,
)

API_ROOT = "https://open.tiktokapis.com/v2"
TOKEN_URL = f"{API_ROOT}/oauth/token/"
REQUEST_TIMEOUT = 30.0
#: Rentang tanggal yang diminta per jendela. API membatasi 30 hari; jendela
#: diperlebar satu hari di tiap sisi supaya batas WIB tidak terpotong, lalu
#: video di luar periode dibuang di sini.
WINDOW_DAYS = 27
MAX_COUNT = 100

VIDEO_FIELDS = (
    "id,create_time,username,region_code,video_description,"
    "like_count,comment_count,share_count,view_count,hashtag_names"
)
COMMENT_FIELDS = "id,video_id,text,like_count,reply_count,parent_comment_id,create_time"

_token: dict[str, Any] = {"value": None, "expires": 0.0}


def configured() -> bool:
    s = get_settings()
    return bool(s.tiktok_client_key and s.tiktok_client_secret)


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=REQUEST_TIMEOUT)


def classify_error(status: int, body: str) -> ConnectorError:
    """Bedakan batas laju / izin / video tak tersedia / galat lain. Fungsi murni."""
    low = body.lower()
    if status == 429 or "rate_limit" in low or "quota" in low:
        return QuotaExceeded("Batas permintaan harian TikTok Research API habis.")
    if "scope_not_authorized" in low or "access_token_invalid" in low or status in (401, 403):
        return PullRejected(
            "TikTok menolak akses Research API (kunci salah, atau proyek riset belum "
            "disetujui TikTok)."
        )
    if status == 404 or "not_found" in low or "video_not" in low:
        return ItemUnavailable("video tidak ditemukan atau komentarnya tidak tersedia")
    return ConnectorError(f"TikTok Research API membalas {status}.")


async def _access_token(http: httpx.AsyncClient) -> str:
    now = time.time()
    if _token["value"] and _token["expires"] - 60 > now:
        return str(_token["value"])
    s = get_settings()
    if not (s.tiktok_client_key and s.tiktok_client_secret):
        raise CredentialMissing(
            "Tarik tema TikTok butuh TIKTOK_CLIENT_KEY dan TIKTOK_CLIENT_SECRET di "
            "environment backend. Belum diset di deployment ini."
        )
    try:
        r = await http.post(
            TOKEN_URL,
            data={
                "client_key": s.tiktok_client_key,
                "client_secret": s.tiktok_client_secret,
                "grant_type": "client_credentials",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    except httpx.HTTPError as e:
        raise ConnectorError(f"TikTok tidak bisa dihubungi: {type(e).__name__}") from e
    if r.status_code >= 400 or "access_token" not in r.text:
        raise PullRejected(
            "Token TikTok Research API ditolak; periksa TIKTOK_CLIENT_KEY/SECRET dan "
            "status persetujuan proyek riset."
        )
    data = r.json()
    _token["value"] = data["access_token"]
    _token["expires"] = now + float(data.get("expires_in") or 7200)
    return str(data["access_token"])


async def _post(
    http: httpx.AsyncClient, path: str, fields: str, body: dict[str, Any]
) -> dict[str, Any]:
    token = await _access_token(http)
    try:
        r = await http.post(
            f"{API_ROOT}/{path}",
            params={"fields": fields},
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
    except httpx.HTTPError as e:
        raise ConnectorError(f"TikTok tidak bisa dihubungi: {type(e).__name__}") from e
    text = r.text[:2000]
    if r.status_code >= 400:
        raise classify_error(r.status_code, text)
    payload: dict[str, Any] = r.json()
    code = str((payload.get("error") or {}).get("code") or "ok").lower()
    if code != "ok":
        raise classify_error(r.status_code, code)
    return payload


# ------------------------------------------------------------ jendela ----


def windows(start: date, end: date) -> list[tuple[date, date]]:
    """Periode WIB inklusif → jendela [mulai, akhir] inklusif ≤ WINDOW_DAYS hari."""
    out: list[tuple[date, date]] = []
    d = start
    while d <= end:
        last = min(end, d + timedelta(days=WINDOW_DAYS - 1))
        out.append((d, last))
        d = last + timedelta(days=1)
    return out


def encode_token(window: int, cursor: int, search_id: str | None) -> str:
    return json.dumps({"w": window, "c": cursor, "s": search_id}, separators=(",", ":"))


def decode_token(raw: str | None) -> tuple[int, int, str | None]:
    if not raw:
        return 0, 0, None
    try:
        d = json.loads(raw)
        return int(d.get("w") or 0), int(d.get("c") or 0), d.get("s")
    except (ValueError, TypeError, AttributeError):
        return 0, 0, None


def request_body(
    query: str, win: tuple[date, date], cursor: int, search_id: str | None, size: int
) -> dict[str, Any]:
    """Badan permintaan video/query untuk satu jendela. Fungsi murni."""
    lo, hi = win
    body: dict[str, Any] = {
        "query": {
            "and": [
                {"operation": "IN", "field_name": "keyword", "field_values": [query]},
                {"operation": "IN", "field_name": "region_code", "field_values": ["ID"]},
            ]
        },
        # Satu hari ekstra di tiap sisi: 00.00 WIB = 17.00 UTC hari sebelumnya.
        "start_date": (lo - timedelta(days=1)).strftime("%Y%m%d"),
        "end_date": (hi + timedelta(days=1)).strftime("%Y%m%d"),
        "max_count": max(1, min(MAX_COUNT, size)),
        "cursor": cursor,
    }
    if search_id:
        body["search_id"] = search_id
    return body


def _epoch(raw: object) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(str(raw)), tz=UTC)
    except (ValueError, OverflowError, OSError):
        return None


def video_url(username: str | None, video_id: str) -> str:
    if username:
        return f"https://www.tiktok.com/@{username}/video/{video_id}"
    return f"https://www.tiktok.com/video/{video_id}"


def parse_videos(
    payload: dict[str, Any], lo: datetime, hi: datetime
) -> tuple[list[dict[str, Any]], int, bool, str | None]:
    """Respons video/query → (detail video dalam periode, cursor, has_more, search_id)."""
    data = payload.get("data") or {}
    out: list[dict[str, Any]] = []
    for v in data.get("videos") or []:
        vid = str(v.get("id") or "").strip()
        created = _epoch(v.get("create_time"))
        if not vid or created is None or not (lo <= created < hi):
            continue
        desc = str(v.get("video_description") or "")
        tags = " ".join(f"#{t}" for t in v.get("hashtag_names") or [] if t)
        user = str(v.get("username") or "")
        out.append(
            {
                "id": vid,
                "title": (desc or tags or f"Video TikTok {vid}")[:200],
                "description": f"{desc} {tags}".strip(),
                "channel": f"@{user}" if user else "",
                "published_at": created.isoformat(),
                "comment_count": int(v.get("comment_count") or 0),
                "url": video_url(user or None, vid),
            }
        )
    return (
        out,
        int(data.get("cursor") or 0),
        bool(data.get("has_more")),
        data.get("search_id"),
    )


async def search_page(
    http: httpx.AsyncClient,
    *,
    query: str,
    start: date,
    end: date,
    lo: datetime,
    hi: datetime,
    page_token: str | None,
    max_results: int,
) -> SearchPage:
    wins = windows(start, end)
    w, cursor, search_id = decode_token(page_token)
    if w >= len(wins):
        return SearchPage(details=[], next_token=None, units=0)
    payload = await _post(
        http, "research/video/query/", VIDEO_FIELDS,
        request_body(query, wins[w], cursor, search_id, max_results),
    )
    details, next_cursor, has_more, sid = parse_videos(payload, lo, hi)
    if has_more:
        token: str | None = encode_token(w, next_cursor, sid)
    elif w + 1 < len(wins):
        token = encode_token(w + 1, 0, None)
    else:
        token = None
    return SearchPage(details=details, next_token=token, units=1)


def parse_comments(
    payload: dict[str, Any], video_id: str, video_url_: str
) -> tuple[list[RawItem], str | None]:
    """Respons comment/list → (komentar, token halaman berikut). Fungsi murni."""
    data = payload.get("data") or {}
    items: list[RawItem] = []
    for c in data.get("comments") or []:
        cid = str(c.get("id") or "").strip()
        text = str(c.get("text") or "").strip()
        created = _epoch(c.get("create_time"))
        if not cid or not text or created is None:
            continue
        likes = int(c.get("like_count") or 0)
        replies = int(c.get("reply_count") or 0)
        parent = str(c.get("parent_comment_id") or "").strip()
        # Komentar utama di Research API ber-parent = id videonya sendiri.
        parent_id = parent if parent and parent != video_id else None
        items.append(
            RawItem(
                external_id=cid,
                text=text,
                published_at=created,
                author_handle=None,
                engagement=likes + replies,
                url=video_url_,
                conversation_id=parent_id,
                extra={"likes": str(likes), "replies": str(replies), "video_id": video_id},
            )
        )
    nxt = str(int(data.get("cursor") or 0)) if data.get("has_more") else None
    return items, nxt


async def comment_page(
    http: httpx.AsyncClient,
    *,
    video_id: str,
    video_url_: str,
    page_token: str | None,
    include_replies: bool,
) -> CommentPage:
    try:
        vid: int | str = int(video_id)
    except ValueError:
        vid = video_id
    payload = await _post(
        http, "research/video/comment/list/", COMMENT_FIELDS,
        {"video_id": vid, "max_count": MAX_COUNT, "cursor": int(page_token or 0)},
    )
    items, nxt = parse_comments(payload, video_id, video_url_)
    if not include_replies:
        items = [i for i in items if i.conversation_id is None]
    return CommentPage(items=items, next_token=nxt, units=1)
