"""Percakapan publik dari X API v2 (endpoint recent search).

Memakai `GET /2/tweets/search/recent` resmi dengan bearer token dari paket
akses berbayar yang dimiliki organisasi pengguna. Tidak ada pengambilan
halaman dan tidak ada pemakaian endpoint internal.

Batasan yang melekat dan wajib ikut ditampilkan:

- Endpoint `recent` hanya menjangkau **7 hari terakhir**. Analisis tren yang
  lebih panjang dari itu tidak boleh disusun dari satu panggilan konektor ini;
  ia harus dikumpulkan bertahap dan disimpan.
- Pengguna X di Indonesia sangat tidak mewakili populasi (timpang secara umur,
  kota, dan pendidikan). Warna `--social` menandai itu di frontend.
- Apa yang masuk hasil pencarian dipengaruhi kebijakan platform yang tidak
  transparan. Volume yang turun bisa berarti percakapan turun, atau kebijakan
  berubah — kedua penjelasan itu tidak bisa dipisahkan dari data ini saja.
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
    require,
)
from app.models.measurement import SignalSource

API_URL = "https://api.x.com/2/tweets/search/recent"
REQUEST_TIMEOUT = 20.0
MAX_PAGE = 100
#: Jangkauan endpoint recent search, ditetapkan oleh platformnya.
LOOKBACK_DAYS = 7


def parse_search(payload: dict[str, Any]) -> list[RawItem]:
    """Ubah respons recent search jadi RawItem. Fungsi murni — inti yang dites."""
    users = {
        str(u.get("id")): str(u.get("username", ""))
        for u in payload.get("includes", {}).get("users", [])
    }
    # `includes.tweets` berisi tweet yang DIRUJUK (dibalas/dikutip) tapi tidak
    # sendiri lolos kueri pencarian -- expansions `referenced_tweets.id` dan
    # `referenced_tweets.id.author_id` di fetch() yang membuatnya ada di sini.
    # Dipetakan ke author_id-nya supaya bisa dicari usernamenya di `users`.
    referenced_author_by_id = {
        str(t.get("id")): str(t.get("author_id"))
        for t in payload.get("includes", {}).get("tweets", [])
        if t.get("id") and t.get("author_id")
    }

    items: list[RawItem] = []
    for row in payload.get("data", []):
        text = (row.get("text") or "").strip()
        external_id = str(row.get("id") or "").strip()
        created = row.get("created_at")
        if not text or not external_id or not created:
            continue
        try:
            published = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        except ValueError:
            continue

        metrics = row.get("public_metrics") or {}
        # Repost dan kutipan dihitung sebagai keterlibatan karena keduanya
        # menyebarkan pesan; suka tidak menyebarkan tapi tetap sinyal minat.
        engagement = sum(
            int(metrics.get(k) or 0)
            for k in ("retweet_count", "reply_count", "like_count", "quote_count")
        )

        # Relasi balasan/kutipan -- dari field `referenced_tweets` X sendiri,
        # bukan ditebak dari teks. "retweeted" sengaja tidak diambil: repost
        # bukan balasan atau kutipan, itu penyebaran ulang tanpa komentar.
        reply_to_handle: str | None = None
        quote_of_handle: str | None = None
        for ref in row.get("referenced_tweets") or []:
            author_id = referenced_author_by_id.get(str(ref.get("id")))
            handle = users.get(author_id) if author_id else None
            if not handle:
                continue
            if ref.get("type") == "replied_to":
                reply_to_handle = handle
            elif ref.get("type") == "quoted":
                quote_of_handle = handle

        items.append(
            RawItem(
                external_id=external_id,
                text=text,
                published_at=published if published.tzinfo else published.replace(tzinfo=UTC),
                author_handle=users.get(str(row.get("author_id"))) or None,
                engagement=engagement,
                url=f"https://x.com/i/status/{external_id}",
                reply_to_handle=reply_to_handle,
                quote_of_handle=quote_of_handle,
                conversation_id=str(row.get("conversation_id") or "") or None,
                extra={"lang_reported": str(row.get("lang") or "")},
            )
        )
    return items


@register
class XConnector(Connector):
    """Pencarian percakapan publik 7 hari terakhir."""

    key: ClassVar[str] = "x_api"
    label: ClassVar[str] = "X API v2 (recent search)"
    source: ClassVar[SignalSource] = SignalSource.SOCIAL
    requires_credential: ClassVar[str | None] = "X_BEARER_TOKEN"
    config_fields: ClassVar[tuple[str, ...]] = ("query",)
    notes: ClassVar[str] = (
        "Hanya menjangkau 7 hari terakhir — tren lebih panjang harus dikumpulkan "
        "bertahap. Pengguna X tidak mewakili populasi Indonesia. Sintaks 'query' "
        "mengikuti operator pencarian resmi X."
    )

    async def fetch(
        self,
        config: dict[str, object],
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[RawItem]:
        settings = get_settings()
        if not settings.x_bearer_token:
            raise CredentialMissing(
                "Konektor X butuh X_BEARER_TOKEN di environment backend. "
                "Belum diset di deployment ini."
            )

        cfg = require(config, self.config_fields)
        params: dict[str, str | int] = {
            "query": cfg["query"],
            "max_results": min(MAX_PAGE, max(10, limit)),
            "tweet.fields": "created_at,public_metrics,lang,conversation_id,referenced_tweets",
            # `referenced_tweets.id.author_id` membuat X mengembalikan
            # tweet yang dirujuk (dibalas/dikutip) di `includes.tweets` --
            # DAN username penulisnya di `includes.users` -- walau tweet
            # itu sendiri tidak lolos kueri pencarian `query`. Tanpa ini,
            # relasi balasan/kutipan cuma bisa ditelusuri ke tweet yang
            # kebetulan ikut lolos kueri yang sama.
            "expansions": "author_id,referenced_tweets.id,referenced_tweets.id.author_id",
            "user.fields": "username",
        }
        if since is not None:
            aware = since if since.tzinfo else since.replace(tzinfo=UTC)
            params["start_time"] = aware.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                headers={"Authorization": f"Bearer {settings.x_bearer_token}"},
            ) as client:
                response = await client.get(API_URL, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 429:
                # Rate limit dilaporkan apa adanya dan TIDAK diakali dengan
                # coba-lagi cepat — melewati rate limit dilarang di paket ini.
                raise ConnectorError(
                    "Rate limit X tercapai. Tunggu jendela berikutnya; jangan "
                    "menaikkan frekuensi pengambilan."
                ) from e
            raise ConnectorError(
                f"X API menolak permintaan ({status}). Periksa bearer token dan "
                "paket akses yang mencakup endpoint recent search."
            ) from e
        except httpx.HTTPError as e:
            raise ConnectorError(f"X API tidak bisa dihubungi: {e}") from e

        return parse_search(payload)[:limit]
