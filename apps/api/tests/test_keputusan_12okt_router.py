"""Tes end-to-end keputusan 12 Oktober 2026 terhadap Postgres nyata (role
pop_app, RLS aktif): versi penilai saat ingest, penilaian ulang, ringkasan
ragam berita, penemuan video di collect-all, dan sumber SENSOR.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.connectors import youtube_search
from app.connectors.youtube import YouTubeConnector
from app.connectors.youtube_search import DiscoveredVideo
from app.services import sentiment

DSN = os.getenv("TEST_DATABASE_URL_APP")

if DSN:
    os.environ["DATABASE_URL"] = DSN
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")

pytestmark = pytest.mark.asyncio(loop_scope="session")

OLD = sentiment.MODEL_VERSION
INFORMAL = sentiment.INFORMAL_MODEL_VERSION
NEWS = sentiment.NEWS_MODEL_VERSION


@pytest.fixture
async def client():
    if not DSN:
        pytest.skip("TEST_DATABASE_URL_APP tidak diset")

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _new_project(client) -> tuple[dict[str, str], str, str]:
    slug = f"k12-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Keputusan",
            "org_slug": slug,
            "full_name": "Penguji Keputusan",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Keputusan"}, headers=headers)
    assert proj.status_code == 201, proj.text
    body = proj.json()
    return headers, body["org_id"], body["id"]


async def _sql(org_id: str, sql: str, params: dict | None = None) -> list:
    """Jalankan SQL sebagai pop_app dengan konteks tenant — RLS tetap berlaku."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(DSN)
    try:
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s, s.begin():
            await s.execute(
                text("SELECT set_config('app.current_org', :o, true)"), {"o": org_id}
            )
            result = await s.execute(text(sql), params or {})
            return list(result.all()) if result.returns_rows else []
    finally:
        await engine.dispose()


def _items(texts: list[str]) -> list[dict]:
    return [
        {
            "external_id": f"ext-{uuid.uuid4().hex}",
            "text": t,
            "published_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "author_handle": f"akun{i}",
        }
        for i, t in enumerate(texts)
    ]


async def _ingest(client, headers, pid, source: str, texts: list[str]) -> None:
    r = await client.post(
        f"/v1/projects/{pid}/signals/ingest",
        json={"source": source, "connector": f"manual_{source.lower()}", "items": _items(texts)},
        headers=headers,
    )
    assert r.status_code == 200, r.text


_ROWS = (
    "SELECT text, sentiment, sentiment_model, sentiment_alt, sentiment_alt_model "
    "FROM mentions WHERE project_id = :p ORDER BY text"
)


class TestVersiPenilaiSaatIngest:
    async def test_percakapan_dicatat_ragam_informal_tanpa_pendamping(self, client) -> None:
        headers, org, pid = await _new_project(client)
        await _ingest(client, headers, pid, "SOCIAL", ["program ini parah bgt"])
        ((_, _, model, alt, alt_model),) = await _sql(org, _ROWS, {"p": pid})
        assert (model, alt, alt_model) == (INFORMAL, None, None)

    async def test_liputan_dicatat_baku_dengan_skor_ragam_berita_di_pendamping(
        self, client
    ) -> None:
        headers, org, pid = await _new_project(client)
        await _ingest(
            client,
            headers,
            pid,
            "MEDIA",
            ["Pertamina mendukung ajang balap", "Program gagal dan mengecewakan warga"],
        )
        rows = {r[0]: r[1:] for r in await _sql(org, _ROWS, {"p": pid})}
        korporat = rows["Pertamina mendukung ajang balap"]
        assert float(korporat[0]) > 0 and korporat[1] == OLD  # skor utama: leksikon baku
        assert korporat[2] is None and korporat[3] == NEWS  # ragam berita abstain
        gagal = rows["Program gagal dan mengecewakan warga"]
        assert gagal[0] == gagal[2] and gagal[3] == NEWS


class TestPenilaianUlang:
    async def _proyek_lama(self, client) -> tuple[dict[str, str], str, str]:
        """Proyek yang isinya seperti data sebelum 10 Okt: tanpa versi, semua leksikon baku."""
        headers, org, pid = await _new_project(client)
        await _ingest(client, headers, pid, "SOCIAL", ["gk becus bgt programnya", "ok saja"])
        await _ingest(client, headers, pid, "MEDIA", ["Pertamina mendukung ajang balap"])
        await _sql(
            org,
            "UPDATE mentions SET sentiment_model = NULL, sentiment_alt = NULL, "
            "sentiment_alt_model = NULL WHERE project_id = :p",
            {"p": pid},
        )
        # Leksikon baku abstain pada komentar ragam cakap.
        await _sql(
            org,
            "UPDATE mentions SET sentiment = NULL WHERE project_id = :p AND source = 'SOCIAL'",
            {"p": pid},
        )
        return headers, org, pid

    async def test_komentar_dinilai_ulang_liputan_tidak_bergeser(self, client) -> None:
        headers, org, pid = await self._proyek_lama(client)
        media_before = (
            await _sql(
                org,
                "SELECT sentiment FROM mentions WHERE project_id = :p AND source = 'MEDIA'",
                {"p": pid},
            )
        )[0][0]

        r = await client.post(f"/v1/projects/{pid}/signals/rescore", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["examined"] == 3 and body["remaining"] == 0
        assert body["alt_written"] == 1
        assert body["primary_changed"] == 1  # "ok saja" tetap tidak dinilai

        rows = {row[0]: row[1:] for row in await _sql(org, _ROWS, {"p": pid})}
        becus = rows["gk becus bgt programnya"]
        assert float(becus[0]) < 0 and becus[1] == INFORMAL
        assert becus[2] is None and becus[3] == OLD  # skor lama (abstain) diarsipkan
        assert rows["ok saja"][1] == INFORMAL and rows["ok saja"][3] is None
        media = rows["Pertamina mendukung ajang balap"]
        assert media[0] == media_before and media[1] == OLD and media[3] == NEWS

    async def test_idempoten_dan_bertahap(self, client) -> None:
        headers, _, pid = await self._proyek_lama(client)
        url = f"/v1/projects/{pid}/signals/rescore"
        first = (await client.post(url, params={"limit": 2}, headers=headers)).json()
        assert first["examined"] == 2 and first["remaining"] == 1
        second = (await client.post(url, params={"limit": 2}, headers=headers)).json()
        assert second["examined"] == 1 and second["remaining"] == 0
        third = (await client.post(url, headers=headers)).json()
        assert (third["examined"], third["primary_changed"], third["remaining"]) == (0, 0, 0)

    async def test_hanya_research_director_ke_atas(self, client) -> None:
        import jwt

        from app.services.auth import create_access_token

        headers, _, pid = await self._proyek_lama(client)
        claims = jwt.decode(
            headers["Authorization"].split()[1],
            "test-secret-for-unit-tests",
            algorithms=["HS256"],
        )
        token = create_access_token(
            user_id=uuid.UUID(claims["sub"]),
            org_id=uuid.UUID(claims["org"]),
            role="RESEARCHER",
            email=claims["email"],
        )
        r = await client.post(
            f"/v1/projects/{pid}/signals/rescore",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    async def test_org_lain_tidak_bisa_menilai_ulang_proyek_ini(self, client) -> None:
        headers_a, org_a, pid_a = await self._proyek_lama(client)
        headers_b, _, _ = await _new_project(client)
        r = await client.post(f"/v1/projects/{pid_a}/signals/rescore", headers=headers_b)
        assert r.status_code == 200
        assert r.json()["examined"] == 0  # RLS: baris org A tidak terlihat
        untouched = await _sql(
            org_a,
            "SELECT count(*) FROM mentions WHERE project_id = :p AND sentiment_model IS NULL",
            {"p": pid_a},
        )
        assert untouched[0][0] == 3


class TestRingkasanRagamBerita:
    async def test_dua_angka_berdampingan_dan_yang_lama_tidak_berubah(self, client) -> None:
        headers, _, pid = await _new_project(client)
        korporat = [f"Perusahaan mendukung ajang olahraga nomor {i}" for i in range(20)]
        kritik = [f"Program gagal dan mengecewakan warga nomor {i}" for i in range(32)]
        await _ingest(client, headers, pid, "MEDIA", korporat + kritik)

        body = (
            await client.get(
                f"/v1/projects/{pid}/signals/summary",
                params={"source": "MEDIA"},
                headers=headers,
            )
        ).json()
        utama, berita = body["sentiment"], body["sentiment_revised"]
        assert utama["effective_n"] == 52 and OLD in utama["method"]
        assert berita["effective_n"] == 32 and NEWS in berita["method"]
        assert berita["source"] == "MEDIA"
        # 20 judul "mendukung" menarik angka lama ke atas; ragam berita tidak.
        assert berita["value"] < utama["value"]

    async def test_tidak_ada_untuk_percakapan_sosial(self, client) -> None:
        headers, _, pid = await _new_project(client)
        await _ingest(client, headers, pid, "SOCIAL", ["program ini parah"])
        body = (
            await client.get(
                f"/v1/projects/{pid}/signals/summary",
                params={"source": "SOCIAL"},
                headers=headers,
            )
        ).json()
        assert body["sentiment_revised"] is None

    async def test_liputan_lama_yang_belum_dinilai_ulang_dilaporkan_apa_adanya(
        self, client
    ) -> None:
        headers, org, pid = await _new_project(client)
        await _ingest(
            client, headers, pid, "MEDIA", [f"Program gagal total nomor {i}" for i in range(40)]
        )
        await _sql(
            org,
            "UPDATE mentions SET sentiment_alt = NULL, sentiment_alt_model = NULL "
            "WHERE project_id = :p AND external_id IN "
            "(SELECT external_id FROM mentions WHERE project_id = :p LIMIT 5)",
            {"p": pid},
        )
        url = f"/v1/projects/{pid}/signals/summary"
        berita = (await client.get(url, params={"source": "MEDIA"}, headers=headers)).json()[
            "sentiment_revised"
        ]
        assert berita["effective_n"] == 35
        assert "35 dari 40" in berita["note"]


class TestPenemuanVideo:
    @pytest.fixture
    def tanpa_jaringan(self, monkeypatch):
        """Pencarian mengembalikan dua video; pengambilan komentar tidak menyentuh API."""
        calls: list[dict] = []

        async def discover(self, config):
            calls.append(dict(config))
            return [
                DiscoveredVideo("vidA", "Keracunan MBG", "Kanal Satu", None),
                DiscoveredVideo("vidB", "Evaluasi MBG", "Kanal Dua", None),
            ]

        async def fetch(self, config, *, since=None, limit=100):
            return []

        monkeypatch.setattr(youtube_search.YouTubeSearchConnector, "discover", discover)
        monkeypatch.setattr(YouTubeConnector, "fetch", fetch)
        return calls

    async def _add(self, client, headers, pid, connector: str, **config: str) -> str:
        r = await client.post(
            f"/v1/projects/{pid}/signals/sources",
            json={"connector": connector, "config": config},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        return str(r.json()["id"])

    async def test_video_baru_didaftarkan_dan_ditarik_di_run_yang_sama(
        self, client, tanpa_jaringan
    ) -> None:
        headers, org, pid = await _new_project(client)
        await self._add(client, headers, pid, "youtube_api", video_id="vidA")
        search_id = await self._add(client, headers, pid, "youtube_search", query="mbg")

        r = await client.post(f"/v1/projects/{pid}/signals/collect-all", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        found = next(s for s in body["results"] if s["connector"] == "youtube_search")
        assert found["ok"] and found["offered"] == 2 and found["matched"] == 1
        assert "1 baru" in found["note"]
        # vidA (lama) + vidB (temuan) ditarik; sumber pencarian sendiri tidak.
        fetched = [s for s in body["results"] if s["connector"] == "youtube_api"]
        assert len(fetched) == 2 and all(s["ok"] for s in fetched)
        assert body["sources_total"] == 3 and body["sources_failed"] == 0

        sources = (
            await client.get(f"/v1/projects/{pid}/signals/sources", headers=headers)
        ).json()
        new = next(s for s in sources if s["config"].get("video_id") == "vidB")
        assert new["config"]["label"] == "Evaluasi MBG — Kanal Dua"
        assert new["config"]["discovered_by"] == search_id
        assert new["source"] == "SOCIAL"

        audit = await _sql(
            org,
            "SELECT metadata FROM audit_logs WHERE action = 'discover' AND entity_id = :s",
            {"s": search_id},
        )
        assert audit and audit[0][0]["video_ids"] == ["vidB"]

    async def test_run_berikutnya_tidak_mencari_lagi(self, client, tanpa_jaringan) -> None:
        """Yang menjaga kuota: 100 unit per pencarian, sekali per interval."""
        headers, _, pid = await _new_project(client)
        await self._add(client, headers, pid, "youtube_search", query="mbg")
        url = f"/v1/projects/{pid}/signals/collect-all"
        await client.post(url, headers=headers)
        again = (await client.post(url, headers=headers)).json()
        assert len(tanpa_jaringan) == 1
        row = next(s for s in again["results"] if s["connector"] == "youtube_search")
        assert row["ok"] and row["offered"] is None and "belum waktunya" in row["note"]
        assert again["sources_total"] == 3  # tidak ada sumber ganda

    async def test_batas_jumlah_sumber_video(self, client, tanpa_jaringan, monkeypatch) -> None:
        from app.routers import signals

        monkeypatch.setattr(signals, "MAX_YOUTUBE_SOURCES", 1)
        headers, _, pid = await _new_project(client)
        await self._add(client, headers, pid, "youtube_search", query="mbg")
        body = (
            await client.post(f"/v1/projects/{pid}/signals/collect-all", headers=headers)
        ).json()
        row = next(s for s in body["results"] if s["connector"] == "youtube_search")
        assert row["matched"] == 1 and "batas 1 sumber video" in row["note"]

    async def test_tanpa_kunci_api_dilaporkan_sebagai_sumber_gagal(self, client) -> None:
        headers, _, pid = await _new_project(client)
        await self._add(client, headers, pid, "youtube_search", query="mbg")
        body = (
            await client.post(f"/v1/projects/{pid}/signals/collect-all", headers=headers)
        ).json()
        assert body["sources_failed"] == 1
        assert "YOUTUBE_API_KEY" in body["results"][0]["error"]

    async def test_konfigurasi_keliru_ditolak_saat_didaftarkan(self, client) -> None:
        headers, _, pid = await _new_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/signals/sources",
            json={"connector": "youtube_search", "config": {"query": "mbg", "max_videos": "999"}},
            headers=headers,
        )
        assert r.status_code == 422


class TestKesepakatanDiApi:
    async def test_sentiment_quality_membawa_kesepakatan_antarpenilai(self, client) -> None:
        headers, _, pid = await _new_project(client)
        body = (
            await client.get(f"/v1/projects/{pid}/signals/sentiment-quality", headers=headers)
        ).json()
        agreement = body["field"]["agreement"]
        assert agreement["n"] == 440
        assert 0 < agreement["kappa"] < agreement["observed_agreement"] <= 1
        assert "AI" in agreement["caveat"]


class TestSumberSensor:
    async def test_enum_database_menerima_sensor(self, client) -> None:
        """Menjaga db/schema.sql dan enum Python tetap seiring."""
        headers, org, pid = await _new_project(client)
        await _sql(
            org,
            """INSERT INTO metric_snapshots
                 (org_id, project_id, metric, source, method, period_start, period_end, value)
               VALUES (:o, :p, 'airquality_pm25', 'SENSOR', 'estimasi model', :d, :d, 30.0)""",
            {"o": org, "p": pid, "d": datetime.now(UTC).date()},
        )
        rows = await _sql(
            org, "SELECT source::text FROM metric_snapshots WHERE project_id = :p", {"p": pid}
        )
        assert rows[0][0] == "SENSOR"
