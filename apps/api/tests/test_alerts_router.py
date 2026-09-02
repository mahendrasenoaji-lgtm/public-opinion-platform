"""Tes end-to-end endpoint /alerts — Postgres nyata, role pop_app, RLS aktif."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

DSN = os.getenv("TEST_DATABASE_URL_APP")

if DSN:
    os.environ["DATABASE_URL"] = DSN
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")

pytestmark = pytest.mark.asyncio(loop_scope="session")


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
    slug = f"alr-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Alerts",
            "org_slug": slug,
            "full_name": "Penguji Alerts",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Alerts"}, headers=headers)
    body = proj.json()
    return headers, body["org_id"], body["id"]


async def _insert_as_org(org_id: str, sql: str, params: dict) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(DSN)
    try:
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s, s.begin():
            await s.execute(
                text("SELECT set_config('app.current_org', :o, true)"), {"o": org_id}
            )
            await s.execute(text(sql), params)
    finally:
        await engine.dispose()


async def _seed_metric(org_id: str, pid: str, metric: str, values: list[float]) -> None:
    start = date(2026, 1, 5)
    for i, value in enumerate(values):
        period_end = start + timedelta(days=i * 14)
        await _insert_as_org(
            org_id,
            """INSERT INTO metric_snapshots
                 (org_id, project_id, metric, source, method, period_start,
                  period_end, value, effective_n)
               VALUES (:o, :p, :m, 'SURVEY', 'survei probabilistik', :ps, :pe, :v, 1200)""",
            {
                "o": org_id, "p": pid, "m": metric,
                "ps": period_end - timedelta(days=14), "pe": period_end, "v": value,
            },
        )


def _mention(i: int, text: str, *, days_ago: int, engagement: int = 0) -> dict:
    return {
        "external_id": f"alr-{uuid.uuid4().hex[:8]}-{i}",
        "text": text,
        "published_at": (datetime.now(UTC) - timedelta(days=days_ago, hours=1)).isoformat(),
        "engagement": engagement,
    }


class TestGatingKosong:
    async def test_proyek_kosong_semua_insufficient(self, client) -> None:
        headers, _org, pid = await _new_project(client)
        r = await client.get(f"/v1/projects/{pid}/alerts", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["alerts"] == []
        assert "signal_volume" in body["insufficient"]
        assert "signal_sentiment" in body["insufficient"]

    async def test_metrik_dengan_riwayat_pendek_insufficient(self, client) -> None:
        headers, org, pid = await _new_project(client)
        await _seed_metric(org, pid, "poi", [60.0, 61.0])  # cuma 2 titik
        body = (await client.get(f"/v1/projects/{pid}/alerts", headers=headers)).json()
        assert "metric:poi" in body["insufficient"]


class TestDeteksiMetrik:
    async def test_metrik_stabil_tidak_menghasilkan_alert(self, client) -> None:
        headers, org, pid = await _new_project(client)
        await _seed_metric(org, pid, "poi", [60.0, 61.0, 59.5, 60.2, 60.4])
        body = (await client.get(f"/v1/projects/{pid}/alerts", headers=headers)).json()
        assert "metric:poi" in body["checked"]
        assert not any(a["key"] == "metric:poi" for a in body["alerts"])

    async def test_lonjakan_metrik_terdeteksi(self, client) -> None:
        headers, org, pid = await _new_project(client)
        await _seed_metric(org, pid, "trust", [60.0, 61.0, 59.5, 60.2, 95.0])
        body = (await client.get(f"/v1/projects/{pid}/alerts", headers=headers)).json()
        trust_alert = next((a for a in body["alerts"] if a["key"] == "metric:trust"), None)
        assert trust_alert is not None, body["alerts"]
        assert trust_alert["direction"] == "naik"
        # "krisis" cuma boleh muncul sebagai negasi eksplisit ("bukan
        # penilaian krisis"), bukan klaim positif bahwa ini krisis.
        assert "bukan penilaian krisis" in trust_alert["limitations"].lower()
        assert "disebabkan" not in trust_alert["limitations"].lower()

    async def test_isolasi_tenant(self, client) -> None:
        """RLS harus membuat metrik org A tidak terlihat SAMA SEKALI dari org
        B -- bukan cuma "tidak cukup data", tapi tidak pernah muncul di
        checked maupun insufficient, karena org B memang tidak pernah
        mencatat metrik bernama itu."""
        headers_a, org_a, pid_a = await _new_project(client)
        headers_b, _org_b, _pid_b = await _new_project(client)
        await _seed_metric(org_a, pid_a, "trust", [60.0, 61.0, 59.5, 60.2, 95.0])
        body = (await client.get(f"/v1/projects/{pid_a}/alerts", headers=headers_b)).json()
        assert body["alerts"] == []
        assert "metric:trust" not in body["insufficient"]
        assert "metric:trust" not in body["checked"]


class TestDeteksiSinyal:
    async def test_lonjakan_volume_terdeteksi_dari_ingest_asli(self, client) -> None:
        headers, _org, pid = await _new_project(client)
        items = []
        # 10 hari baseline dengan volume kecil dan stabil (2/hari)
        for d in range(10, 0, -1):
            for i in range(2):
                items.append(_mention(i, f"komentar biasa hari ke-{d} nomor {i}", days_ago=d))
        # hari terakhir (kemarin): lonjakan besar
        for i in range(40):
            items.append(_mention(i, f"lonjakan percakapan mendadak nomor {i}", days_ago=1))

        ing = await client.post(
            f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
        )
        assert ing.status_code == 200, ing.text

        body = (await client.get(f"/v1/projects/{pid}/alerts", headers=headers)).json()
        assert "signal_volume" in body["checked"]
        vol_alert = next((a for a in body["alerts"] if a["key"] == "signal_volume"), None)
        assert vol_alert is not None, body["alerts"]
        assert vol_alert["direction"] == "naik"

    async def test_batasan_selalu_disebut_bukan_klaim_penyebab(self, client) -> None:
        headers, org, pid = await _new_project(client)
        await _seed_metric(org, pid, "approval", [60.0, 61.0, 59.5, 60.2, 10.0])
        body = (await client.get(f"/v1/projects/{pid}/alerts", headers=headers)).json()
        assert any("bukan penilaian krisis" in x for x in body["limitations"])
