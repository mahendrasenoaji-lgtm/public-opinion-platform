"""Tes end-to-end Phase 3: forecast baseline dari model yang di-fit, dan
Opinion Risk Score dari komponen yang benar-benar punya data.

Pola sama dengan test_dashboard_reads.py: Postgres nyata, role pop_app, RLS
aktif. Riwayat metrik di-INSERT langsung lewat SQL karena metric_snapshots
memang diisi pipeline survei/seed, bukan dibuat pengguna lewat HTTP.
"""

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
    slug = f"p3-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Phase3",
            "org_slug": slug,
            "full_name": "Penguji Phase3",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek P3"}, headers=headers)
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


async def _seed_history(
    org_id: str, project_id: str, metric: str, values: list[float], *, step_days: int = 7
) -> None:
    """Riwayat nasional sebuah metrik, satu snapshot per periode."""
    start = date(2026, 1, 5)
    for i, value in enumerate(values):
        period_end = start + timedelta(days=i * step_days)
        await _insert_as_org(
            org_id,
            """
            INSERT INTO metric_snapshots
              (org_id, project_id, metric, source, method, period_start,
               period_end, value, effective_n)
            VALUES
              (:o, :p, :m, 'SURVEY', 'survei probabilistik', :ps, :pe, :v, 1200)
            """,
            {
                "o": org_id,
                "p": project_id,
                "m": metric,
                "ps": period_end - timedelta(days=step_days),
                "pe": period_end,
                "v": value,
            },
        )


def _tren_naik(n: int) -> list[float]:
    derau = [0.0, 0.4, -0.3, 0.2, -0.4, 0.3, -0.2, 0.1]
    return [60 + 0.8 * i + derau[i % len(derau)] for i in range(n)]


class TestForecastBaseline:
    async def test_riwayat_pendek_menolak_bukan_menebak(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _seed_history(org_id, pid, "poi", [60, 61, 62])
        r = await client.get(f"/v1/projects/{pid}/forecast/baseline", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["insufficient_data"] is True
        assert body["baseline"] is None
        assert body["note"] is not None

    async def test_riwayat_cukup_menghasilkan_model_terpasang(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _seed_history(org_id, pid, "poi", _tren_naik(20))
        r = await client.get(f"/v1/projects/{pid}/forecast/baseline", headers=headers)
        body = r.json()
        assert body["insufficient_data"] is False
        assert "state-space" in body["model"]
        assert body["n_observations"] == 20
        assert set(body["spread"]) == {"1", "3", "7", "14", "30", "90"}

    async def test_batasan_asumsi_selalu_ikut(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _seed_history(org_id, pid, "poi", _tren_naik(20))
        body = (
            await client.get(f"/v1/projects/{pid}/forecast/baseline", headers=headers)
        ).json()
        assert any("berjarak sama" in x for x in body["limitations"])


class TestWhatIf:
    async def test_tanpa_riwayat_ditandai_belum_ada_model(self, client) -> None:
        """Jangan diam-diam memakai angka tetap seolah hasil estimasi."""
        headers, _org_id, pid = await _new_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/forecast/what-if",
            json={"baseline": 67.3, "scenario": {"food_price": 6}},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["fitted"] is False
        assert "belum ada model" in body["model"]
        assert any("bukan hasil perhitungan dari data proyek" in x for x in body["limitations"])

    async def test_dengan_riwayat_memakai_model_terpasang(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _seed_history(org_id, pid, "poi", _tren_naik(20))
        r = await client.post(
            f"/v1/projects/{pid}/forecast/what-if",
            json={"scenario": {"food_price": 6}},
            headers=headers,
        )
        body = r.json()
        assert body["fitted"] is True
        assert "state-space" in body["model"]

    async def test_baseline_diambil_dari_riwayat_bila_tidak_disebut(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        nilai = _tren_naik(20)
        await _seed_history(org_id, pid, "poi", nilai)
        body = (
            await client.post(
                f"/v1/projects/{pid}/forecast/what-if", json={}, headers=headers
            )
        ).json()
        # tanpa skenario, horizon terpendek harus dekat nilai terakhir
        assert body["points"][0]["expected"] == pytest.approx(nilai[-1], abs=1.0)

    async def test_tanpa_riwayat_dan_tanpa_baseline_ditolak_jelas(self, client) -> None:
        headers, _org_id, pid = await _new_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/forecast/what-if", json={}, headers=headers
        )
        assert r.status_code == 422
        assert "baseline" in r.json()["detail"]

    async def test_skenario_menandai_hasil_sebagai_simulasi(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _seed_history(org_id, pid, "poi", _tren_naik(20))
        body = (
            await client.post(
                f"/v1/projects/{pid}/forecast/what-if",
                json={"scenario": {"food_price": 6}},
                headers=headers,
            )
        ).json()
        assert body["is_simulation"] is True
        assert any("simulasi" in x.lower() for x in body["limitations"])

    async def test_driver_asing_ditolak(self, client) -> None:
        headers, _org_id, pid = await _new_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/forecast/what-if",
            json={"baseline": 60, "scenario": {"cuaca": 3}},
            headers=headers,
        )
        assert r.status_code == 422
        assert "tidak dikenal" in r.json()["detail"]


class TestRiskScore:
    async def test_proyek_kosong_menolak_memberi_skor(self, client) -> None:
        headers, _org_id, pid = await _new_project(client)
        r = await client.get(f"/v1/projects/{pid}/risk/score", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["insufficient_data"] is True
        assert body["score"] is None
        assert body["coverage"] == 0.0

    async def test_setiap_komponen_dilaporkan_termasuk_yang_hilang(self, client) -> None:
        headers, _org_id, pid = await _new_project(client)
        body = (await client.get(f"/v1/projects/{pid}/risk/score", headers=headers)).json()
        assert len(body["components"]) == 9
        for komponen in body["components"]:
            if not komponen["available"]:
                assert komponen["reason_missing"], komponen["key"]
                assert komponen["value"] is None

    async def test_geografis_menjelaskan_kenapa_tidak_diinferensi(self, client) -> None:
        """CLAUDE.md: provinsi tidak boleh ditebak dari isi teks."""
        headers, _org_id, pid = await _new_project(client)
        body = (await client.get(f"/v1/projects/{pid}/risk/score", headers=headers)).json()
        geo = next(c for c in body["components"] if c["key"] == "geographic_spread")
        assert "TIDAK diinferensi" in geo["reason_missing"]

    async def test_skor_terbit_setelah_cukup_komponen(self, client) -> None:
        headers, org_id, pid = await _new_project(client)

        # segmen -> narrative_polarization
        for nama, sentimen, ukuran in (
            ("Pendukung", 55.0, 40.0),
            ("Penentang", -60.0, 35.0),
            ("Mengambang", 5.0, 25.0),
        ):
            await _insert_as_org(
                org_id,
                """INSERT INTO segments (org_id, project_id, name, size_pct, sentiment)
                   VALUES (:o, :p, :n, :s, :sen)""",
                {"o": org_id, "p": pid, "n": nama, "s": ukuran, "sen": sentimen},
            )

        # deret trust & approval -> dua komponen penurunan
        await _seed_history(org_id, pid, "trust", [66.0, 61.0])
        await _seed_history(org_id, pid, "approval", [70.0, 64.0])

        # percakapan di dua periode -> negatif, kecepatan, pertumbuhan, amplifikasi
        now = datetime.now(UTC)
        items = []
        for i in range(40):
            items.append(
                {
                    "external_id": f"r-{uuid.uuid4().hex[:8]}-{i}",
                    "text": f"kebijakan ini memberatkan dan mengecewakan warga nomor {i}",
                    "published_at": (now - timedelta(days=2)).isoformat(),
                    "author_handle": f"akun{i % 4}",
                }
            )
        for i in range(20):
            items.append(
                {
                    "external_id": f"o-{uuid.uuid4().hex[:8]}-{i}",
                    "text": f"program bantuan ini bagus dan membantu warga nomor {i}",
                    "published_at": (now - timedelta(days=20)).isoformat(),
                    "author_handle": f"lama{i}",
                }
            )
        ingest = await client.post(
            f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
        )
        assert ingest.status_code == 200, ingest.text

        r = await client.get(f"/v1/projects/{pid}/risk/score", headers=headers)
        body = r.json()
        assert body["insufficient_data"] is False, body["note"]
        assert body["score"] is not None
        assert body["band"] in {"Low", "Moderate", "Elevated", "High", "Critical"}
        assert body["coverage"] >= 0.6
        # geographic_spread tetap hilang: tidak ada geotag
        assert "geographic_spread" in body["missing"]

    async def test_batasan_kalibrasi_selalu_disebut(self, client) -> None:
        headers, _org_id, pid = await _new_project(client)
        body = (await client.get(f"/v1/projects/{pid}/risk/score", headers=headers)).json()
        assert any("belum dikalibrasi" in x for x in body["limitations"])

    async def test_isolasi_tenant(self, client) -> None:
        headers_a, org_a, pid_a = await _new_project(client)
        headers_b, _org_b, _pid_b = await _new_project(client)
        await _seed_history(org_a, pid_a, "trust", [66.0, 61.0])
        body = (
            await client.get(f"/v1/projects/{pid_a}/risk/score", headers=headers_b)
        ).json()
        assert body["insufficient_data"] is True
        assert body["coverage"] == 0.0
