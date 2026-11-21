"""Panggilan Instagram Graph API untuk "Tarik tema" (lihat services/theme_pull.py).

API resmi Meta, lewat akun Instagram Business/Creator milik organisasi
(``INSTAGRAM_USER_ID``) dan token aplikasi yang sudah lolos App Review untuk
fitur *Instagram Public Content Access* (``INSTAGRAM_ACCESS_TOKEN``).

Yang bisa diambil jauh lebih sempit daripada YouTube, dan itu batas API, bukan
pilihan kode ini:

- pencarian hanya per TAGAR (``ig_hashtag_search``), bukan kata kunci bebas;
- paling banyak 30 tagar unik per 7 hari bergulir per akun;
- ``recent_media`` hanya memuat unggahan sekitar 24 jam terakhir;
- komentar unggahan akun lain TIDAK bisa diambil; yang disimpan adalah
  keterangan (caption) unggahannya, sebagai konten SOCIAL biasa;
- nama akun pengunggah tidak dikirim oleh edge tagar, jadi ``author_handle``
  kosong.

Belum pernah dijalankan terhadap API sungguhan karena token belum ada; cek
ulang ``parse_*`` begitu token diisi.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

import httpx

from app.config import get_settings
from app.connectors.base import ConnectorError, CredentialMissing, RawItem
from app.connectors.theme_common import PullRejected, QuotaExceeded, SearchPage

REQUEST_TIMEOUT = 30.0
PAGE_SIZE = 50
MEDIA_FIELDS = "id,caption,media_type,comments_count,like_count,permalink,timestamp"

#: Kode galat Graph API untuk batas laju aplikasi/akun.
RATE_LIMIT_CODES = frozenset({4, 17, 32, 613})

_TAG = re.compile(r"^\w{1,100}$", re.UNICODE)


def configured() -> bool:
    s = get_settings()
    return bool(s.instagram_access_token and s.instagram_user_id)


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=REQUEST_TIMEOUT)


def to_hashtag(query: str) -> str | None:
    """"#Gibran Mundur" → "gibranmundur"; None bila bukan tagar yang sah."""
    tag = re.sub(r"\s+", "", query.strip().lstrip("#")).lower()
    return tag if _TAG.match(tag) else None


def classify_error(status: int, body: str) -> ConnectorError:
    """Bedakan batas laju / batas tagar / izin / galat lain. Fungsi murni."""
    try:
        err = (json.loads(body) or {}).get("error") or {}
    except ValueError:
        err = {}
    code = int(err.get("code") or 0)
    msg = str(err.get("message") or "").lower()
    if code in RATE_LIMIT_CODES or "rate limit" in msg or "request limit" in msg:
        return QuotaExceeded("Batas laju Instagram Graph API tercapai.")
    if "hashtag" in msg and ("limit" in msg or "30" in msg):
        return PullRejected(
            "Batas 30 tagar unik per 7 hari untuk akun Instagram ini sudah habis."
        )
    if code == 190 or status in (401, 403) or code == 10 or code == 200:
        return PullRejected(
            "Instagram menolak akses (token kedaluwarsa, atau izin Instagram Public "
            "Content Access belum disetujui Meta)."
        )
    return ConnectorError(f"Instagram Graph API membalas {status}.")


def _creds() -> tuple[str, str, str]:
    s = get_settings()
    if not (s.instagram_access_token and s.instagram_user_id):
        raise CredentialMissing(
            "Tarik tema Instagram butuh INSTAGRAM_ACCESS_TOKEN dan INSTAGRAM_USER_ID di "
            "environment backend. Belum diset di deployment ini."
        )
    return s.instagram_access_token, s.instagram_user_id, s.instagram_graph_version


async def _get(http: httpx.AsyncClient, path: str, params: dict[str, Any]) -> dict[str, Any]:
    token, _uid, version = _creds()
    try:
        r = await http.get(
            f"https://graph.facebook.com/{version}/{path}",
            params={**params, "access_token": token},
        )
    except httpx.HTTPError as e:
        raise ConnectorError(f"Instagram tidak bisa dihubungi: {type(e).__name__}") from e
    if r.status_code >= 400:
        raise classify_error(r.status_code, r.text[:2000])
    data: dict[str, Any] = r.json()
    return data


def encode_token(hashtag_id: str, after: str | None) -> str:
    return json.dumps({"h": hashtag_id, "a": after}, separators=(",", ":"))


def decode_token(raw: str | None) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    try:
        d = json.loads(raw)
        return d.get("h"), d.get("a")
    except (ValueError, TypeError, AttributeError):
        return None, None


def _ts(raw: object) -> datetime | None:
    try:
        return datetime.strptime(str(raw), "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None


def parse_media(
    payload: dict[str, Any], tag: str, lo: datetime, hi: datetime
) -> tuple[list[dict[str, Any]], list[RawItem], str | None]:
    """Respons recent_media → (detail, konten keterangan dalam periode, cursor berikut)."""
    details: list[dict[str, Any]] = []
    items: list[RawItem] = []
    for m in payload.get("data") or []:
        mid = str(m.get("id") or "").strip()
        caption = str(m.get("caption") or "").strip()
        ts = _ts(m.get("timestamp"))
        if not mid or ts is None or not (lo <= ts < hi):
            continue
        comments = int(m.get("comments_count") or 0)
        likes = int(m.get("like_count") or 0)
        details.append(
            {
                "id": mid,
                "title": (caption or f"Unggahan #{tag}")[:200],
                "description": caption,
                "channel": f"#{tag}",
                "published_at": ts.isoformat(),
                "comment_count": comments,
            }
        )
        if caption:
            items.append(
                RawItem(
                    external_id=mid,
                    text=caption,
                    published_at=ts,
                    author_handle=None,
                    engagement=likes + comments,
                    url=m.get("permalink"),
                    extra={
                        "likes": str(likes),
                        "comments": str(comments),
                        "hashtag": tag,
                        "media_type": str(m.get("media_type") or ""),
                    },
                )
            )
    after = None
    paging = payload.get("paging") or {}
    if paging.get("next"):
        after = (paging.get("cursors") or {}).get("after")
    return details, items, after


async def search_page(
    http: httpx.AsyncClient,
    *,
    query: str,
    lo: datetime,
    hi: datetime,
    page_token: str | None,
    max_results: int,
) -> SearchPage:
    _token, uid, _v = _creds()
    tag = to_hashtag(query)
    if tag is None:
        raise PullRejected(f"'{query}' bukan tagar Instagram yang sah.")
    hashtag_id, after = decode_token(page_token)
    units = 0
    if not hashtag_id:
        found = await _get(http, "ig_hashtag_search", {"user_id": uid, "q": tag})
        units += 1
        ids = [str(d["id"]) for d in found.get("data") or [] if d.get("id")]
        if not ids:
            return SearchPage(details=[], next_token=None, units=units)
        hashtag_id = ids[0]
    params: dict[str, Any] = {
        "user_id": uid,
        "fields": MEDIA_FIELDS,
        "limit": max(1, min(PAGE_SIZE, max_results)),
    }
    if after:
        params["after"] = after
    payload = await _get(http, f"{hashtag_id}/recent_media", params)
    units += 1
    details, items, nxt = parse_media(payload, tag, lo, hi)
    return SearchPage(
        details=details,
        items=items,
        next_token=encode_token(hashtag_id, nxt) if nxt else None,
        units=units,
    )
