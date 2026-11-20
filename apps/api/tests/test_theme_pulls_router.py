"""Tes end-to-end "Tarik tema": endpoint + langkah pekerja terhadap Postgres nyata (RLS aktif).

Jaringan tidak disentuh: fungsi YouTube di `app.connectors.youtube_theme`
diganti palsu, dan pekerja latar belakang dimatikan (`AUTOSTART=False`) —
langkahnya dijalankan langsung lewat `run_step` supaya urutannya pasti.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest

from app.connectors.base import RawItem

DSN = os.getenv("TEST_DATABASE_URL_APP")

if DSN:
    os.environ["DATABASE_URL"] = DSN
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
async def client(monkeypatch):
    if not DSN:
        pytest.skip("TEST_DATABASE_URL_APP tidak diset")

    from httpx import ASGITransport, AsyncClient

    from app.config import get_settings
    from app.main import app
    from app.routers import theme_pulls

    monkeypatch.setattr(theme_pulls, "AUTOSTART", False)
    monkeypatch.setattr(get_settings(), "youtube_api_key", "kunci-palsu")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _new_project(client) -> tuple[dict[str, str], str, str]:
    slug = f"tema-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Tema",
            "org_slug": slug,
            "full_name": "Penguji Tema",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Tema"}, headers=headers)
    assert proj.status_code == 201, proj.text
    import jwt

    org = jwt.decode(token, options={"verify_signature": False})["org"]
    return headers, proj.json()["id"], org


def _item(cid: str, day: int, parent: str | None = None) -> RawItem:
    from datetime import UTC, datetime

    return RawItem(
        external_id=cid,
        text=f"Komentar uji tentang gibran mundur nomor {cid}",
        published_at=datetime(2026, 11, day, 5, tzinfo=UTC),
        author_handle=f"akun-{cid}",
        url=f"https://www.youtube.com/watch?v=v&lc={cid}",
        conversation_id=parent,
        reply_to_handle="akun-induk" if parent else None,
    )


class FakeYouTube:
    """Dua video relevan + satu di luar tema; video v1 dua halaman komentar."""

    def __init__(self) -> None:
        self.quota_once = False
        self.calls: list[str] = []

    async def search_page(self, http: Any, **kw: Any) -> tuple[list[str], str | None]:
        self.calls.append(f"search:{kw['query']}")
        return ["v1", "v2", "v3"], None

    async def video_details(self, http: Any, ids: list[str]) -> list[dict[str, Any]]:
        self.calls.append("videos")
        data = {
            "v1": {"title": "Gibran mundur hari ini", "comment_count": 300},
            "v2": {"title": "Reaksi gibran mundur", "comment_count": 3},
            "v3": {"title": "Resep soto lamongan", "comment_count": 900},
        }
        return [{"id": i, "channel": "Kanal", "description": "", **data[i]} for i in ids]

    async def comment_page(self, http: Any, *, video_id: str, page_token: str | None,
                           include_replies: bool) -> Any:
        from app.connectors import youtube_theme as yt

        if self.quota_once:
            self.quota_once = False
            raise yt.QuotaExceeded("Kuota harian YouTube API habis.")
        self.calls.append(f"comments:{video_id}:{page_token}")
        if video_id == "v1" and page_token is None:
            # c3 ditulis 25 Nov — di luar periode 10–17 Nov, tidak disimpan.
            return yt.CommentPage([_item("c1", 12), _item("c2", 12, "c1"), _item("c3", 25)],
                                  "P2", 2)
        if video_id == "v1":
            return yt.CommentPage([_item("c4", 11)], None, 1)
        raise yt.VideoUnavailable("komentar dimatikan pemilik video")


@pytest.fixture
def fake(monkeypatch) -> FakeYouTube:
    from app.connectors import youtube_theme as yt

    f = FakeYouTube()
    monkeypatch.setattr(yt, "search_page", f.search_page)
    monkeypatch.setattr(yt, "video_details", f.video_details)
    monkeypatch.setattr(yt, "comment_page", f.comment_page)
    return f


BODY = {
    "queries": "gibran mundur",
    "start": "2026-11-10",
    "end": "2026-11-17",
    "max_videos": 5,
}


async def _drain(job_id: str, org: str, limit: int = 30) -> int:
    from app.routers.theme_pulls import run_step

    steps = 0
    while steps < limit:
        delay = await run_step(uuid.UUID(job_id), uuid.UUID(org), None)  # type: ignore[arg-type]
        steps += 1
        if delay is None or delay > 1:
            break
    return steps


class TestThemePull:
    async def test_alur_lengkap_sampai_selesai(self, client, fake) -> None:
        headers, pid, org = await _new_project(client)
        r = await client.post(f"/v1/projects/{pid}/signals/theme-pulls", json=BODY,
                              headers=headers)
        assert r.status_code == 201, r.text
        job = r.json()
        assert job["status"] == "searching" and job["label"] == "gibran mundur"

        await _drain(job["id"], org)

        jobs = (await client.get(f"/v1/projects/{pid}/signals/theme-pulls",
                                 headers=headers)).json()
        assert len(jobs) == 1
        j = jobs[0]
        assert j["status"] == "done", j
        assert j["dropped_by_filter"] == 1  # resep soto dibuang
        assert [v["id"] for v in j["videos"]] == ["v1", "v2"]  # yang paling ramai dulu
        assert j["videos"][1]["state"] == "skipped"
        assert j["received"] == 3 and j["stored"] == 3 and j["outside_window"] == 1
        assert j["units"] == 100 + 1 + 2 + 1
        assert j["limitations"] and j["method"]

        # Komentar masuk sebagai konten YouTube biasa proyek ini.
        m = await client.get(
            f"/v1/projects/{pid}/signals/summary?start=2026-11-10&end=2026-11-17",
            headers=headers,
        )
        assert m.status_code == 200, m.text

        # Pekerjaan tidak ikut ditarik collect-all.
        ca = (await client.post(f"/v1/projects/{pid}/signals/collect-all",
                                headers=headers)).json()
        assert all(s["connector"] != "youtube_theme" for s in ca["results"])

    async def test_kuota_habis_lalu_menunggu(self, client, fake) -> None:
        headers, pid, org = await _new_project(client)
        job = (await client.post(f"/v1/projects/{pid}/signals/theme-pulls", json=BODY,
                                 headers=headers)).json()
        fake.quota_once = True
        await _drain(job["id"], org)
        j = (await client.get(f"/v1/projects/{pid}/signals/theme-pulls",
                              headers=headers)).json()[0]
        assert j["status"] == "waiting_quota"
        assert j["resume_at"] is not None
        assert any("Kuota habis" in n for n in j["notes"])

    async def test_hentikan_lalu_lanjutkan(self, client, fake) -> None:
        headers, pid, org = await _new_project(client)
        job = (await client.post(f"/v1/projects/{pid}/signals/theme-pulls", json=BODY,
                                 headers=headers)).json()
        from app.routers.theme_pulls import run_step

        await run_step(uuid.UUID(job["id"]), uuid.UUID(org), None)  # type: ignore[arg-type]
        stop = await client.post(
            f"/v1/projects/{pid}/signals/theme-pulls/{job['id']}/stop", headers=headers
        )
        assert stop.status_code == 200 and stop.json()["status"] == "stopped"
        # Pekerja yang masih memegang pekerjaan berhenti sendiri.
        assert await run_step(uuid.UUID(job["id"]), uuid.UUID(org), None) is None  # type: ignore[arg-type]

        res = await client.post(
            f"/v1/projects/{pid}/signals/theme-pulls/{job['id']}/resume", headers=headers
        )
        assert res.json()["status"] == "details"
        await _drain(job["id"], org)
        j = (await client.get(f"/v1/projects/{pid}/signals/theme-pulls",
                              headers=headers)).json()[0]
        assert j["status"] == "done" and j["stored"] == 3

    async def test_validasi_dan_peran(self, client, fake) -> None:
        headers, pid, _ = await _new_project(client)
        bad = await client.post(
            f"/v1/projects/{pid}/signals/theme-pulls",
            json={**BODY, "start": "2026-11-17", "end": "2026-11-10"},
            headers=headers,
        )
        assert bad.status_code == 422
        assert "sebelum" in bad.json()["detail"]

        import jwt

        from app.services.auth import create_access_token

        claims = jwt.decode(headers["Authorization"].removeprefix("Bearer "),
                            options={"verify_signature": False})
        viewer = {
            "Authorization": "Bearer "
            + create_access_token(
                user_id=uuid.UUID(claims["sub"]),
                org_id=uuid.UUID(claims["org"]),
                role="VIEWER",
                email=claims["email"],
            )
        }
        r = await client.post(f"/v1/projects/{pid}/signals/theme-pulls", json=BODY,
                              headers=viewer)
        assert r.status_code == 403

    async def test_organisasi_lain_tidak_melihat(self, client, fake) -> None:
        headers, pid, _ = await _new_project(client)
        job = (await client.post(f"/v1/projects/{pid}/signals/theme-pulls", json=BODY,
                                 headers=headers)).json()
        other, _, _ = await _new_project(client)
        listed = await client.get(f"/v1/projects/{pid}/signals/theme-pulls", headers=other)
        assert listed.status_code in (200, 404)
        if listed.status_code == 200:
            assert listed.json() == []
        stop = await client.post(
            f"/v1/projects/{pid}/signals/theme-pulls/{job['id']}/stop", headers=other
        )
        assert stop.status_code == 404

    async def test_batas_pekerjaan_aktif_per_proyek(self, client, fake) -> None:
        headers, pid, _ = await _new_project(client)
        for _ in range(3):
            r = await client.post(f"/v1/projects/{pid}/signals/theme-pulls", json=BODY,
                                  headers=headers)
            assert r.status_code == 201
        r = await client.post(f"/v1/projects/{pid}/signals/theme-pulls", json=BODY,
                              headers=headers)
        assert r.status_code == 409

