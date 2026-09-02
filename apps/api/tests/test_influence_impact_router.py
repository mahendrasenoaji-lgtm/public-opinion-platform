"""Tes end-to-end influence dan Communication Impact.

Yang paling penting di file ini adalah tes yang memverifikasi endpoint impact
MENOLAK bekerja tanpa desain pembanding lengkap. Itu satu-satunya penjaga
antara platform ini dan klaim kausal yang tidak bisa dipertanggungjawabkan.
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

PRE = date(2026, 3, 31)
POST = date(2026, 5, 31)


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
    slug = f"imp-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Impact",
            "org_slug": slug,
            "full_name": "Penguji Impact",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Impact"}, headers=headers)
    body = proj.json()
    return headers, body["org_id"], body["id"]


async def _snapshot(
    org_id: str,
    project_id: str,
    *,
    segment: str,
    period_end: date,
    value: float,
    ci_half: float | None = 2.0,
    n: int | None = 400,
    metric: str = "approval",
) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(DSN)
    try:
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s, s.begin():
            await s.execute(
                text("SELECT set_config('app.current_org', :o, true)"), {"o": org_id}
            )
            await s.execute(
                text(
                    """
                    INSERT INTO metric_snapshots
                      (org_id, project_id, metric, source, method, period_start,
                       period_end, value, ci_low, ci_high, effective_n, segment)
                    VALUES
                      (:o, :p, :m, 'SURVEY', 'survei probabilistik', :ps, :pe,
                       :v, :lo, :hi, :n, :seg)
                    """
                ),
                {
                    "o": org_id,
                    "p": project_id,
                    "m": metric,
                    "ps": period_end - timedelta(days=30),
                    "pe": period_end,
                    "v": value,
                    "lo": None if ci_half is None else value - ci_half,
                    "hi": None if ci_half is None else value + ci_half,
                    "n": n,
                    "seg": segment,
                },
            )
    finally:
        await engine.dispose()


async def _desain_lengkap(
    org_id: str,
    pid: str,
    *,
    treated_post: float = 58.0,
    control_post: float = 51.0,
) -> None:
    """Empat sel: terpapar dan pembanding, sebelum dan sesudah."""
    await _snapshot(org_id, pid, segment="Terpapar", period_end=PRE, value=50.0)
    await _snapshot(org_id, pid, segment="Terpapar", period_end=POST, value=treated_post)
    await _snapshot(org_id, pid, segment="Pembanding", period_end=PRE, value=50.0)
    await _snapshot(org_id, pid, segment="Pembanding", period_end=POST, value=control_post)


def _body(**overrides) -> dict:
    return {
        "metric": "approval",
        "treated_segment": "Terpapar",
        "control_segment": "Pembanding",
        "pre_period_end": PRE.isoformat(),
        "post_period_end": POST.isoformat(),
        **overrides,
    }


class TestImpactMenolakDesainTidakMemadai:
    async def test_tanpa_sel_pembanding_ditolak_404_dengan_alasan(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _snapshot(org_id, pid, segment="Terpapar", period_end=PRE, value=50.0)
        await _snapshot(org_id, pid, segment="Terpapar", period_end=POST, value=58.0)

        r = await client.post(f"/v1/projects/{pid}/impact/analyze", json=_body(), headers=headers)
        assert r.status_code == 404, r.text
        assert "esain pembanding" in r.json()["detail"]

    async def test_segmen_sama_ditolak(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _desain_lengkap(org_id, pid)
        r = await client.post(
            f"/v1/projects/{pid}/impact/analyze",
            json=_body(control_segment="Terpapar"),
            headers=headers,
        )
        assert r.status_code == 422
        assert "tidak boleh sama" in r.json()["detail"]

    async def test_snapshot_tanpa_interval_ditolak(self, client) -> None:
        """Efek tanpa ketidakpastian menyembunyikan apa yang tidak diketahui."""
        headers, org_id, pid = await _new_project(client)
        await _desain_lengkap(org_id, pid)
        await _snapshot(
            org_id, pid, segment="Pembanding", period_end=date(2026, 6, 30),
            value=52.0, ci_half=None,
        )
        await _snapshot(
            org_id, pid, segment="Terpapar", period_end=date(2026, 6, 30),
            value=60.0, ci_half=None,
        )
        r = await client.post(
            f"/v1/projects/{pid}/impact/analyze",
            json=_body(post_period_end="2026-06-30"),
            headers=headers,
        )
        assert r.status_code == 422
        assert "ketidakpastian" in r.json()["detail"]

    async def test_sel_terlalu_kecil_menolak_memberi_angka(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        for seg in ("Terpapar", "Pembanding"):
            for periode, nilai in ((PRE, 50.0), (POST, 55.0)):
                await _snapshot(org_id, pid, segment=seg, period_end=periode, value=nilai, n=5)
        r = await client.post(f"/v1/projects/{pid}/impact/analyze", json=_body(), headers=headers)
        assert r.status_code == 200
        assert r.json()["insufficient_data"] is True
        assert r.json()["effect"] is None


class TestImpactPerhitungan:
    async def test_efek_selisih_dari_selisih(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _desain_lengkap(org_id, pid, treated_post=58.0, control_post=51.0)
        r = await client.post(f"/v1/projects/{pid}/impact/analyze", json=_body(), headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["treated_change"] == 8.0
        assert body["control_change"] == 1.0
        assert body["effect"] == 7.0

    async def test_tren_bersama_menghasilkan_efek_nol(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _desain_lengkap(org_id, pid, treated_post=58.0, control_post=58.0)
        body = (
            await client.post(
                f"/v1/projects/{pid}/impact/analyze", json=_body(), headers=headers
            )
        ).json()
        assert body["effect"] == 0.0
        assert body["distinguishable_from_zero"] is False

    async def test_metode_menyebut_did(self, client) -> None:
        """Kunci yang membuat AIEnvelope mengizinkan bahasa kausal."""
        headers, org_id, pid = await _new_project(client)
        await _desain_lengkap(org_id, pid)
        body = (
            await client.post(
                f"/v1/projects/{pid}/impact/analyze", json=_body(), headers=headers
            )
        ).json()
        assert "difference-in-differences" in body["method"]

    async def test_batasan_selalu_ikut(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _desain_lengkap(org_id, pid)
        body = (
            await client.post(
                f"/v1/projects/{pid}/impact/analyze", json=_body(), headers=headers
            )
        ).json()
        assert any("rata-rata" in x for x in body["limitations"])
        assert any("peristiwa lain" in x for x in body["limitations"])

    async def test_tren_paralel_diperiksa_bila_ada_deret_pra(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _desain_lengkap(org_id, pid)
        # tambah titik pra kedua supaya kemiringan bisa dihitung
        awal = date(2026, 2, 28)
        await _snapshot(org_id, pid, segment="Terpapar", period_end=awal, value=44.0)
        await _snapshot(org_id, pid, segment="Pembanding", period_end=awal, value=50.0)

        body = (
            await client.post(
                f"/v1/projects/{pid}/impact/analyze", json=_body(), headers=headers
            )
        ).json()
        assert body["parallel_trends_checked"] is True
        # Terpapar naik 6, pembanding datar -> asumsi paralel gagal
        assert body["parallel_trends_ok"] is False
        assert body["distinguishable_from_zero"] is False

    async def test_isolasi_tenant(self, client) -> None:
        headers_a, org_a, pid_a = await _new_project(client)
        headers_b, _org_b, _pid_b = await _new_project(client)
        await _desain_lengkap(org_a, pid_a)
        r = await client.post(
            f"/v1/projects/{pid_a}/impact/analyze", json=_body(), headers=headers_b
        )
        assert r.status_code == 404, "RLS bocor: org lain melihat snapshot"


class TestInfluence:
    async def test_proyek_kosong_menolak_memeringkat(self, client) -> None:
        headers, _org, pid = await _new_project(client)
        r = await client.get(f"/v1/projects/{pid}/influence", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["insufficient_data"] is True
        assert r.json()["top"] == []

    async def test_peringkat_dari_data_asli(self, client) -> None:
        headers, _org, pid = await _new_project(client)
        now = datetime.now(UTC)
        items = []
        for akun in range(12):
            jumlah = 10 if akun == 0 else 3
            for i in range(jumlah):
                items.append(
                    {
                        "external_id": f"inf-{uuid.uuid4().hex[:8]}-{akun}-{i}",
                        "text": f"pendapat warga tentang kebijakan nomor {akun}-{i}",
                        "published_at": (now - timedelta(days=1)).isoformat(),
                        "author_handle": f"akun{akun}",
                        "engagement": 100 if akun == 0 else 5,
                    }
                )
        ing = await client.post(
            f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
        )
        assert ing.status_code == 200, ing.text

        r = await client.get(f"/v1/projects/{pid}/influence", headers=headers)
        body = r.json()
        assert body["insufficient_data"] is False
        assert body["total_authors"] == 12
        assert body["top"][0]["engagement_share_pct"] > 50

    async def test_hanya_hash_yang_keluar_bukan_handle(self, client) -> None:
        headers, _org, pid = await _new_project(client)
        now = datetime.now(UTC)
        items = [
            {
                "external_id": f"h-{uuid.uuid4().hex[:8]}-{a}-{i}",
                "text": f"pendapat warga nomor {a}-{i}",
                "published_at": (now - timedelta(days=1)).isoformat(),
                "author_handle": f"nama_asli_{a}",
                "engagement": 5,
            }
            for a in range(12)
            for i in range(3)
        ]
        await client.post(
            f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
        )
        body = (await client.get(f"/v1/projects/{pid}/influence", headers=headers)).json()
        assert body["top"]
        assert all("nama_asli" not in e["author_hash"] for e in body["top"])

    async def test_batasan_menyatakan_bukan_pengaruh_kausal(self, client) -> None:
        headers, _org, pid = await _new_project(client)
        body = (await client.get(f"/v1/projects/{pid}/influence", headers=headers)).json()
        assert any("bukan pengaruh kausal" in x for x in body["limitations"])

    async def test_isolasi_tenant(self, client) -> None:
        headers_a, _org_a, pid_a = await _new_project(client)
        headers_b, _org_b, _pid_b = await _new_project(client)
        now = datetime.now(UTC)
        items = [
            {
                "external_id": f"t-{uuid.uuid4().hex[:8]}-{a}-{i}",
                "text": f"pendapat nomor {a}-{i}",
                "published_at": (now - timedelta(days=1)).isoformat(),
                "author_handle": f"akun{a}",
            }
            for a in range(12)
            for i in range(3)
        ]
        await client.post(
            f"/v1/projects/{pid_a}/signals/ingest", json={"items": items}, headers=headers_a
        )
        body = (await client.get(f"/v1/projects/{pid_a}/influence", headers=headers_b)).json()
        assert body["total_authors"] == 0
