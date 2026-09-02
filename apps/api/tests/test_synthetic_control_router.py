"""Tes end-to-end endpoint synthetic control.

Sama seperti test_influence_impact_router.py untuk DiD: yang paling penting
bukan tes yang memverifikasi aritmetikanya (itu sudah ditutupi
test_synthetic_control.py tanpa database), melainkan tes yang memverifikasi
PENOLAKANNYA -- donor kurang, periode pra-perlakuan tidak sejajar/cukup,
segmen donor tidak valid, dan isolasi tenant.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

import pytest

DSN = os.getenv("TEST_DATABASE_URL_APP")

if DSN:
    os.environ["DATABASE_URL"] = DSN
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")

pytestmark = pytest.mark.asyncio(loop_scope="session")

# 6 periode bulanan pra-perlakuan (lebih banyak dari MIN_DONORS=5) + 1 pasca.
PRE_PERIODS = [date(2025, 11, 30), date(2025, 12, 31), date(2026, 1, 31),
               date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]
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
    slug = f"sc-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Synthetic Control",
            "org_slug": slug,
            "full_name": "Penguji SC",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek SC"}, headers=headers)
    body = proj.json()
    return headers, body["org_id"], body["id"]


async def _snapshot(
    org_id: str,
    project_id: str,
    *,
    segment: str,
    period_end: date,
    value: float,
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
                       :v, :lo, :hi, 400, :seg)
                    """
                ),
                {
                    "o": org_id,
                    "p": project_id,
                    "m": metric,
                    "ps": period_end - timedelta(days=30),
                    "pe": period_end,
                    "v": value,
                    "lo": value - 2,
                    "hi": value + 2,
                    "seg": segment,
                },
            )
    finally:
        await engine.dispose()


DONOR_NAMES = ["D1", "D2", "D3", "D4", "D5"]


async def _isi_desain_lengkap(
    org_id: str,
    pid: str,
    *,
    treated_post: float = 55.0,
    donor_posts: dict[str, float] | None = None,
) -> None:
    """Terpapar + 5 donor, tiap-tiap punya deret pra-perlakuan sejajar (6
    periode) dan satu nilai pasca-perlakuan."""
    donor_posts = donor_posts or dict.fromkeys(DONOR_NAMES, 50.0)
    for i, p in enumerate(PRE_PERIODS):
        # Terpapar dan donor semua naik pelan-pelan supaya bukan deret datar.
        await _snapshot(org_id, pid, segment="Terpapar", period_end=p, value=50.0 + i * 0.5)
        for d in DONOR_NAMES:
            await _snapshot(org_id, pid, segment=d, period_end=p, value=50.0 + i * 0.5)
    await _snapshot(org_id, pid, segment="Terpapar", period_end=POST, value=treated_post)
    for d in DONOR_NAMES:
        await _snapshot(org_id, pid, segment=d, period_end=POST, value=donor_posts[d])


def _body(**overrides) -> dict:
    return {
        "metric": "approval",
        "treated_segment": "Terpapar",
        "donor_segments": DONOR_NAMES,
        "pre_period_end": PRE_PERIODS[-1].isoformat(),
        "post_period_end": POST.isoformat(),
        **overrides,
    }


class TestSyntheticControlMenolakDesainTidakMemadai:
    async def test_donor_kurang_dari_minimum_ditolak_422(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _isi_desain_lengkap(org_id, pid)
        r = await client.post(
            f"/v1/projects/{pid}/impact/synthetic-control",
            json=_body(donor_segments=DONOR_NAMES[:3]),
            headers=headers,
        )
        assert r.status_code == 422, r.text

    async def test_terpapar_ikut_jadi_donor_ditolak(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _isi_desain_lengkap(org_id, pid)
        r = await client.post(
            f"/v1/projects/{pid}/impact/synthetic-control",
            json=_body(donor_segments=[*DONOR_NAMES, "Terpapar"]),
            headers=headers,
        )
        assert r.status_code == 422
        assert "donornya sendiri" in r.json()["detail"]

    async def test_donor_duplikat_ditolak(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _isi_desain_lengkap(org_id, pid)
        r = await client.post(
            f"/v1/projects/{pid}/impact/synthetic-control",
            json=_body(donor_segments=[*DONOR_NAMES[:4], DONOR_NAMES[0]]),
            headers=headers,
        )
        assert r.status_code == 422
        assert "duplikat" in r.json()["detail"]

    async def test_pra_perlakuan_tidak_lebih_banyak_dari_donor_insufficient(
        self, client
    ) -> None:
        """5 donor tapi cuma 1 periode pra-perlakuan yang sejajar -> tidak
        cukup derajat kebebasan, harus insufficient_data bukan angka."""
        headers, org_id, pid = await _new_project(client)
        satu_periode = PRE_PERIODS[-1]
        await _snapshot(org_id, pid, segment="Terpapar", period_end=satu_periode, value=50.0)
        for d in DONOR_NAMES:
            await _snapshot(org_id, pid, segment=d, period_end=satu_periode, value=50.0)
        await _snapshot(org_id, pid, segment="Terpapar", period_end=POST, value=55.0)
        for d in DONOR_NAMES:
            await _snapshot(org_id, pid, segment=d, period_end=POST, value=50.0)

        r = await client.post(
            f"/v1/projects/{pid}/impact/synthetic-control",
            json=_body(pre_period_end=satu_periode.isoformat()),
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["insufficient_data"] is True
        assert body["effect"] is None

    async def test_snapshot_pasca_hilang_untuk_satu_donor_404(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        for p in PRE_PERIODS:
            await _snapshot(org_id, pid, segment="Terpapar", period_end=p, value=50.0)
            for d in DONOR_NAMES:
                await _snapshot(org_id, pid, segment=d, period_end=p, value=50.0)
        await _snapshot(org_id, pid, segment="Terpapar", period_end=POST, value=55.0)
        # D5 sengaja tidak diberi nilai pasca-perlakuan.
        for d in DONOR_NAMES[:-1]:
            await _snapshot(org_id, pid, segment=d, period_end=POST, value=50.0)

        r = await client.post(
            f"/v1/projects/{pid}/impact/synthetic-control", json=_body(), headers=headers
        )
        assert r.status_code == 404, r.text
        assert "D5" in r.json()["detail"]


class TestSyntheticControlPerhitungan:
    async def test_efek_dari_data_asli_dan_bobot_ikut_dikembalikan(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _isi_desain_lengkap(org_id, pid, treated_post=60.0)
        r = await client.post(
            f"/v1/projects/{pid}/impact/synthetic-control", json=_body(), headers=headers
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["insufficient_data"] is False
        assert body["donors_used"] == 5
        assert body["n_pre_periods"] == len(PRE_PERIODS)
        # Semua donor identik satu sama lain dan dengan terpapar pra-perlakuan
        # -> unit sintetis pasca-perlakuan seharusnya persis 50.0 (rata-rata
        # donor, yang semuanya 50.0), efek = 60 - 50 = 10.
        assert body["synthetic_post"] == pytest.approx(50.0, abs=0.05)
        assert body["effect"] == pytest.approx(10.0, abs=0.05)
        assert sum(body["weights"].values()) == pytest.approx(1.0, abs=1e-3)
        assert body["fit_quality_ok"] is True

    async def test_metode_menyebut_synthetic_control(self, client) -> None:
        """Kunci yang membuat AIEnvelope mengizinkan bahasa kausal."""
        headers, org_id, pid = await _new_project(client)
        await _isi_desain_lengkap(org_id, pid)
        body = (
            await client.post(
                f"/v1/projects/{pid}/impact/synthetic-control", json=_body(), headers=headers
            )
        ).json()
        assert "synthetic control" in body["method"]

    async def test_batasan_menyebut_unit_sintetis_dan_permutasi(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _isi_desain_lengkap(org_id, pid)
        body = (
            await client.post(
                f"/v1/projects/{pid}/impact/synthetic-control", json=_body(), headers=headers
            )
        ).json()
        assert any("permutasi" in x for x in body["limitations"])

    async def test_rank_p_value_dari_placebo(self, client) -> None:
        headers, org_id, pid = await _new_project(client)
        await _isi_desain_lengkap(org_id, pid, treated_post=60.0)
        body = (
            await client.post(
                f"/v1/projects/{pid}/impact/synthetic-control", json=_body(), headers=headers
            )
        ).json()
        assert body["rank_p_value"] is not None
        assert 0.0 <= body["rank_p_value"] <= 1.0

    async def test_isolasi_tenant(self, client) -> None:
        headers_a, org_a, pid_a = await _new_project(client)
        headers_b, _org_b, _pid_b = await _new_project(client)
        await _isi_desain_lengkap(org_a, pid_a)
        r = await client.post(
            f"/v1/projects/{pid_a}/impact/synthetic-control", json=_body(), headers=headers_b
        )
        assert r.status_code == 404, "RLS bocor: org lain melihat snapshot"
