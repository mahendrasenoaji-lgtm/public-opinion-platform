"""Tarik tema TikTok + Instagram: fungsi murni (tanpa jaringan, tanpa DB) dan
alur pekerja terhadap Postgres nyata dengan API platform diganti palsu.

Kunci TikTok/Instagram belum ada (21 Nov 2026), jadi parsing diuji terhadap
bentuk respons menurut dokumentasi publik masing-masing platform.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.connectors import instagram_theme as ig
from app.connectors import tiktok_theme as tt
from app.connectors.base import RawItem
from app.connectors.theme_common import ItemUnavailable, PullRejected, QuotaExceeded, SearchPage
from app.services import theme_pull as tp

TODAY = date(2026, 11, 21)
LO = datetime(2026, 11, 9, 17, tzinfo=UTC)  # 10 Nov 00.00 WIB
HI = datetime(2026, 11, 17, 17, tzinfo=UTC)  # 18 Nov 00.00 WIB


def _req(platform: str, queries: str = "gibran mundur", start: date = date(2026, 11, 10),
         end: date = date(2026, 11, 17)) -> tp.ThemeRequest:
    return tp.parse_request(
        queries=queries, start=start, end=end, max_videos=5, include_replies=True,
        comments_until_now=False, keyword_filter=True, today=TODAY, platform=platform,
    )


# ------------------------------------------------------------ murni ----


class TestParseRequest:
    def test_platform_tidak_dikenal(self) -> None:
        with pytest.raises(tp.ThemeError):
            _req("facebook")

    def test_tiktok_periode_panjang_boleh(self) -> None:
        r = _req("tiktok", start=date(2026, 1, 1), end=date(2026, 11, 20))
        assert r.platform == "tiktok" and r.keyword_filter

    def test_instagram_tagar_dinormalkan_dan_penyaring_mati(self) -> None:
        r = _req("instagram", queries="#Gibran Mundur, gibranmundur, BBM",
                 start=date(2026, 11, 20), end=date(2026, 11, 21))
        assert r.queries == ("gibranmundur", "bbm")
        assert r.keyword_filter is False

    def test_instagram_menolak_periode_lampau(self) -> None:
        with pytest.raises(tp.ThemeError, match="24 jam"):
            _req("instagram", queries="bbm")

    def test_instagram_menolak_tagar_tidak_sah(self) -> None:
        with pytest.raises(tp.ThemeError, match="tagar"):
            _req("instagram", queries="bbm-bali!", start=date(2026, 11, 20),
                 end=date(2026, 11, 21))

    def test_state_lama_tanpa_platform_dianggap_youtube(self) -> None:
        assert tp.info({}).key == "youtube"
        state = tp.initial_state(_req("tiktok"), label="x", now=datetime.now(UTC))
        assert state["platform"] == "tiktok" and state["prefetched"] == {}


class TestQuotaReset:
    def test_per_platform(self) -> None:
        now = datetime(2026, 11, 21, 3, 0, tzinfo=UTC)
        assert tp.next_quota_reset(now) == datetime(2026, 11, 21, 8, 5, tzinfo=UTC)
        assert tp.next_quota_reset(now, "tiktok") == datetime(2026, 11, 22, 0, 5, tzinfo=UTC)
        assert tp.next_quota_reset(now, "instagram") == datetime(2026, 11, 21, 4, 0, tzinfo=UTC)


class TestInstagramSelesaiTanpaKomentar:
    def test_sesudah_pencarian_langsung_selesai(self) -> None:
        req = _req("instagram", queries="bbm", start=date(2026, 11, 20), end=date(2026, 11, 21))
        state = tp.initial_state(req, label="bbm", now=datetime.now(UTC))
        tp.add_prefetched(state, [{"id": "m1", "title": "a", "comment_count": 3}])
        state["received"] = 1
        tp.advance_search(state, next_token=None)
        assert state["status"] == tp.STATUS_DONE
        assert state["candidates"] == [] and state["prefetched"] == {}


class TestTikTokParsing:
    def test_jendela_maks_27_hari(self) -> None:
        wins = tt.windows(date(2026, 1, 1), date(2026, 3, 1))
        assert wins[0] == (date(2026, 1, 1), date(2026, 1, 27))
        assert wins[-1][1] == date(2026, 3, 1)
        assert all((b - a).days + 1 <= tt.WINDOW_DAYS for a, b in wins)

    def test_badan_permintaan_melebar_satu_hari(self) -> None:
        body = tt.request_body("bbm", (date(2026, 11, 10), date(2026, 11, 17)), 0, None, 500)
        assert body["start_date"] == "20261109" and body["end_date"] == "20261118"
        assert body["max_count"] == 100 and "search_id" not in body
        assert body["query"]["and"][0]["field_values"] == ["bbm"]
        # rentang yang diminta tetap ≤ 30 hari untuk jendela terpanjang
        b = tt.request_body("x", (date(2026, 1, 1), date(2026, 1, 27)), 0, "s", 10)
        span = (datetime.strptime(b["end_date"], "%Y%m%d")
                - datetime.strptime(b["start_date"], "%Y%m%d")).days
        assert span <= 30 and b["search_id"] == "s"

    def test_token_bolak_balik(self) -> None:
        assert tt.decode_token(tt.encode_token(2, 100, "abc")) == (2, 100, "abc")
        assert tt.decode_token(None) == (0, 0, None)
        assert tt.decode_token("rusak") == (0, 0, None)

    def test_parse_videos_membuang_di_luar_periode(self) -> None:
        inside = int(datetime(2026, 11, 12, tzinfo=UTC).timestamp())
        outside = int(datetime(2026, 11, 25, tzinfo=UTC).timestamp())
        payload = {
            "data": {
                "videos": [
                    {"id": 111, "create_time": inside, "username": "budi",
                     "video_description": "gibran mundur?", "comment_count": 40,
                     "hashtag_names": ["gibran"]},
                    {"id": 222, "create_time": outside, "video_description": "x"},
                    {"id": None, "create_time": inside},
                ],
                "cursor": 100, "has_more": True, "search_id": "sid",
            },
            "error": {"code": "ok"},
        }
        details, cursor, more, sid = tt.parse_videos(payload, LO, HI)
        assert [d["id"] for d in details] == ["111"]
        d = details[0]
        assert d["channel"] == "@budi" and d["comment_count"] == 40
        assert d["description"] == "gibran mundur? #gibran"
        assert d["url"] == "https://www.tiktok.com/@budi/video/111"
        assert (cursor, more, sid) == (100, True, "sid")

    def test_parse_comments_relasi_balasan(self) -> None:
        ts = int(datetime(2026, 11, 12, tzinfo=UTC).timestamp())
        payload = {
            "data": {
                "comments": [
                    {"id": 1, "video_id": 111, "text": "setuju", "like_count": 2,
                     "reply_count": 1, "parent_comment_id": 111, "create_time": ts},
                    {"id": 2, "video_id": 111, "text": "tidak", "parent_comment_id": 1,
                     "create_time": ts},
                    {"id": 3, "text": "", "create_time": ts},
                ],
                "cursor": 100, "has_more": True,
            }
        }
        items, nxt = tt.parse_comments(payload, "111", "https://t/v")
        assert [i.external_id for i in items] == ["1", "2"]
        assert items[0].conversation_id is None and items[0].engagement == 3
        assert items[1].conversation_id == "1"
        assert all(i.author_handle is None for i in items)
        assert nxt == "100"
        _, end = tt.parse_comments({"data": {"comments": [], "has_more": False}}, "1", "u")
        assert end is None

    def test_klasifikasi_galat(self) -> None:
        assert isinstance(tt.classify_error(429, ""), QuotaExceeded)
        assert isinstance(tt.classify_error(200, "scope_not_authorized"), PullRejected)
        assert isinstance(tt.classify_error(404, ""), ItemUnavailable)
        assert type(tt.classify_error(500, "")).__name__ == "ConnectorError"


class TestInstagramParsing:
    def test_to_hashtag(self) -> None:
        assert ig.to_hashtag("#BBM Bali") == "bbmbali"
        assert ig.to_hashtag("bbm-bali") is None

    def test_parse_media(self) -> None:
        payload = {
            "data": [
                {"id": "m1", "caption": "Antre BBM lagi #bbm", "like_count": 10,
                 "comments_count": 4, "permalink": "https://instagram.com/p/m1",
                 "timestamp": "2026-11-12T03:00:00+0000", "media_type": "IMAGE"},
                {"id": "m2", "caption": "", "timestamp": "2026-11-12T03:00:00+0000"},
                {"id": "m3", "caption": "lama", "timestamp": "2026-10-01T03:00:00+0000"},
            ],
            "paging": {"cursors": {"after": "AFT"}, "next": "https://graph..."},
        }
        details, items, after = ig.parse_media(payload, "bbm", LO, HI)
        assert [d["id"] for d in details] == ["m1", "m2"]
        assert [i.external_id for i in items] == ["m1"]  # tanpa keterangan tidak disimpan
        assert items[0].engagement == 14 and items[0].url == "https://instagram.com/p/m1"
        assert after == "AFT"
        _, _, none = ig.parse_media({"data": [], "paging": {"cursors": {"after": "X"}}},
                                    "bbm", LO, HI)
        assert none is None

    def test_klasifikasi_galat(self) -> None:
        assert isinstance(ig.classify_error(400, '{"error":{"code":4}}'), QuotaExceeded)
        assert isinstance(
            ig.classify_error(400, '{"error":{"code":24,"message":"Hashtag limit reached: 30"}}'),
            PullRejected,
        )
        assert isinstance(ig.classify_error(400, '{"error":{"code":190}}'), PullRejected)
        assert type(ig.classify_error(500, "bukan json")).__name__ == "ConnectorError"


# ------------------------------------------------------ alur + DB ----

DSN = os.getenv("TEST_DATABASE_URL_APP")
if DSN:
    os.environ["DATABASE_URL"] = DSN
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")


@pytest.fixture
async def client(monkeypatch):
    if not DSN:
        pytest.skip("TEST_DATABASE_URL_APP tidak diset")
    from httpx import ASGITransport, AsyncClient

    from app.config import get_settings
    from app.main import app
    from app.routers import theme_pulls

    monkeypatch.setattr(theme_pulls, "AUTOSTART", False)
    s = get_settings()
    monkeypatch.setattr(s, "youtube_api_key", None)
    monkeypatch.setattr(s, "tiktok_client_key", "kunci-palsu")
    monkeypatch.setattr(s, "tiktok_client_secret", "rahasia-palsu")
    monkeypatch.setattr(s, "instagram_access_token", None)
    monkeypatch.setattr(s, "instagram_user_id", None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _project(client) -> tuple[dict[str, str], str, str]:
    import jwt

    slug = f"plat-{uuid.uuid4().hex[:10]}"
    reg = await client.post("/v1/auth/register", json={
        "org_name": "Org Platform", "org_slug": slug, "full_name": "Penguji",
        "email": f"{slug}@example.com", "password": "PasswordAsli123",
    })
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek"}, headers=headers)
    org = jwt.decode(token, options={"verify_signature": False})["org"]
    return headers, proj.json()["id"], org


async def _drain(job_id: str, org: str, limit: int = 30) -> None:
    from app.routers.theme_pulls import run_step

    for _ in range(limit):
        delay = await run_step(uuid.UUID(job_id), uuid.UUID(org), None)  # type: ignore[arg-type]
        if delay is None or delay > 1:
            return


def _c(cid: str, parent: str | None = None, day: int = 12) -> RawItem:
    return RawItem(external_id=cid, text=f"komentar gibran mundur {cid}",
                   published_at=datetime(2026, 11, day, 5, tzinfo=UTC),
                   url="https://www.tiktok.com/@a/video/t1", conversation_id=parent)


@pytest.fixture
def fake_tiktok(monkeypatch) -> list[str]:
    from app.connectors.theme_common import CommentPage

    calls: list[str] = []

    async def search_page(http: Any, **kw: Any) -> SearchPage:
        calls.append(f"search:{kw['query']}:{kw['page_token']}")
        base = {"channel": "@a", "published_at": "2026-11-12T00:00:00+00:00"}
        if kw["page_token"] is None:
            return SearchPage(details=[
                {**base, "id": "t1", "title": "Gibran mundur", "description": "gibran mundur",
                 "comment_count": 50, "url": "https://www.tiktok.com/@a/video/t1"},
                {**base, "id": "t2", "title": "masak", "description": "resep soto",
                 "comment_count": 999},
            ], next_token=tt.encode_token(1, 0, None), units=1)
        return SearchPage(details=[
            {**base, "id": "t3", "title": "reaksi", "description": "gibran mundur hari ini",
             "comment_count": 2},
        ], next_token=None, units=1)

    async def comment_page(http: Any, *, video_id: str, video_url_: str,
                           page_token: str | None, include_replies: bool) -> CommentPage:
        calls.append(f"comments:{video_id}:{page_token}")
        if video_id == "t1" and page_token is None:
            return CommentPage([_c("k1"), _c("k2", "k1"), _c("k3", day=25)], "100", 1)
        if video_id == "t1":
            return CommentPage([_c("k4")], None, 1)
        raise ItemUnavailable("video tidak ditemukan atau komentarnya tidak tersedia")

    monkeypatch.setattr(tt, "search_page", search_page)
    monkeypatch.setattr(tt, "comment_page", comment_page)
    return calls


BODY = {"platform": "tiktok", "queries": "gibran mundur", "start": "2026-11-10",
        "end": "2026-11-17", "max_videos": 5}


@pytest.mark.asyncio(loop_scope="session")
class TestAlurPlatform:
    async def test_daftar_platform_tanpa_nilai_kunci(self, client) -> None:
        h, _pid, _org = await _project(client)
        r = await client.get("/v1/signals/theme-platforms", headers=h)
        assert r.status_code == 200, r.text
        got = {p["key"]: p for p in r.json()}
        assert set(got) == {"youtube", "tiktok", "instagram"}
        assert got["tiktok"]["configured"] is True
        assert got["instagram"]["configured"] is False
        assert got["instagram"]["env_vars"] == ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID"]
        assert got["instagram"]["collects_comments"] is False
        assert "kunci-palsu" not in r.text

    async def test_platform_tanpa_kunci_503(self, client) -> None:
        h, pid, _org = await _project(client)
        r = await client.post(f"/v1/projects/{pid}/signals/theme-pulls", headers=h,
                              json={**BODY, "platform": "instagram", "queries": "bbm",
                                    "start": "2026-11-20", "end": "2026-11-21"})
        assert r.status_code == 503 and "INSTAGRAM_ACCESS_TOKEN" in r.text
        r = await client.post(f"/v1/projects/{pid}/signals/theme-pulls", headers=h,
                              json={**BODY, "platform": "youtube"})
        assert r.status_code == 503 and "YOUTUBE_API_KEY" in r.text

    async def test_tiktok_alur_lengkap(self, client, fake_tiktok) -> None:
        h, pid, org = await _project(client)
        r = await client.post(f"/v1/projects/{pid}/signals/theme-pulls", json=BODY, headers=h)
        assert r.status_code == 201, r.text
        assert r.json()["platform"] == "tiktok"
        await _drain(r.json()["id"], org)

        j = (await client.get(f"/v1/projects/{pid}/signals/theme-pulls", headers=h)).json()[0]
        assert j["status"] == "done", j
        assert j["dropped_by_filter"] == 1  # resep soto
        assert [v["id"] for v in j["videos"]] == ["t1", "t3"]
        assert j["videos"][0]["url"] == "https://www.tiktok.com/@a/video/t1"
        assert j["videos"][1]["state"] == "skipped"
        assert j["received"] == 3 and j["stored"] == 3 and j["outside_window"] == 1
        assert j["units"] == 2 + 2  # 2 halaman cari + 2 halaman komentar; detail gratis
        assert "TikTok Research API" in j["method"]
        assert not any(c.startswith("videos") for c in fake_tiktok)

        m = (await client.get(f"/v1/projects/{pid}/mentions?start=2026-11-10&end=2026-11-17",
                              headers=h)).json()
        assert {x["connector"] for x in m} == {"tiktok_api"}
        assert {x["external_id"] for x in m} == {"k1", "k2", "k4"}

    async def test_instagram_menyimpan_keterangan(self, client, monkeypatch) -> None:
        from app.config import get_settings

        s = get_settings()
        monkeypatch.setattr(s, "instagram_access_token", "token-palsu")
        monkeypatch.setattr(s, "instagram_user_id", "1784")

        async def search_page(http: Any, **kw: Any) -> SearchPage:
            ts = datetime.now(UTC)
            return SearchPage(
                details=[{"id": "m1", "title": "Antre BBM", "description": "",
                          "channel": "#bbm", "published_at": ts.isoformat(),
                          "comment_count": 4}],
                items=[RawItem(external_id="m1", text="Antre BBM lagi hari ini #bbm",
                               published_at=ts, url="https://instagram.com/p/m1")],
                next_token=None, units=2,
            )

        monkeypatch.setattr(ig, "search_page", search_page)
        h, pid, org = await _project(client)
        today = (datetime.now(UTC)).date().isoformat()
        r = await client.post(f"/v1/projects/{pid}/signals/theme-pulls", headers=h,
                              json={"platform": "instagram", "queries": "#BBM",
                                    "start": today, "end": today, "max_videos": 10})
        assert r.status_code == 201, r.text
        assert r.json()["queries"] == ["bbm"]
        await _drain(r.json()["id"], org)
        j = (await client.get(f"/v1/projects/{pid}/signals/theme-pulls", headers=h)).json()[0]
        assert j["status"] == "done", j
        assert j["received"] == 1 and j["stored"] == 1 and j["units"] == 2
        assert j["videos"] == []
        m = (await client.get(f"/v1/projects/{pid}/mentions?days=2", headers=h)).json()
        assert [x["connector"] for x in m] == ["instagram_api"]

    async def test_izin_ditolak_langsung_gagal(self, client, monkeypatch) -> None:
        async def search_page(http: Any, **kw: Any) -> SearchPage:
            raise PullRejected("TikTok menolak akses Research API.")

        monkeypatch.setattr(tt, "search_page", search_page)
        h, pid, org = await _project(client)
        r = await client.post(f"/v1/projects/{pid}/signals/theme-pulls", json=BODY, headers=h)
        await _drain(r.json()["id"], org)
        j = (await client.get(f"/v1/projects/{pid}/signals/theme-pulls", headers=h)).json()[0]
        assert j["status"] == "failed" and "menolak" in j["error"]
