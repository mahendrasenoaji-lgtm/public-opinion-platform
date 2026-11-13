"""Tes end-to-end router Kinerja Komunikasi terhadap Postgres dengan RLS aktif."""

import os
import uuid

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


async def _org_with_project(client) -> tuple[dict[str, str], str]:
    slug = f"test-kinerja-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Kinerja",
            "org_slug": slug,
            "full_name": "Penguji Kinerja",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Kinerja"}, headers=headers)
    assert proj.status_code == 201, proj.text
    return headers, proj.json()["id"]


def _posts(n: int, platform: str = "instagram", account: str = "kemenko_contoh") -> list[dict]:
    return [
        {
            "platform": platform,
            "account": account,
            "external_id": f"{platform}-{i}",
            "posted_at": f"2026-10-{i + 1:02d}T03:00:00Z",
            "kind": "foto",
            "likes": 100 + i,
            "comments": 10,
            "followers": 10000,
        }
        for i in range(n)
    ]


def _base(project_id: str) -> str:
    return f"/v1/projects/{project_id}/comm-performance"


async def test_framework_memuat_28_indikator_dan_penafian(client) -> None:
    headers, pid = await _org_with_project(client)
    r = await client.get(f"{_base(pid)}/framework", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["indicators"]) == 28
    assert "bukan standar resmi" in body["disclaimer"]
    assert body["weights"] == {"INPUT": 15, "PROCESS": 30, "OUTPUT": 20, "OUTCOME": 35}


async def test_tanpa_token_ditolak(client) -> None:
    r = await client.get(f"{_base(str(uuid.uuid4()))}/framework")
    assert r.status_code in (401, 403)


async def test_unggah_lalu_ringkasan_per_akun_per_platform(client) -> None:
    headers, pid = await _org_with_project(client)
    items = _posts(6) + _posts(3, platform="x")
    r = await client.post(f"{_base(pid)}/posts", json={"items": items}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"received": 9, "stored": 9, "updated": 0, "duplicates_dropped": 0}

    s = await client.get(f"{_base(pid)}/posts/summary", headers=headers)
    assert s.status_code == 200, s.text
    body = s.json()
    assert body["n_posts"] == 9
    assert body["source"] == "OFFICIAL_ACCOUNT"
    assert body["limitations"]
    by = {(a["account"], a["platform"]): a for a in body["accounts"]}
    ig = by[("kemenko_contoh", "instagram")]
    assert ig["n_posts"] == 6
    assert ig["median_likes"] == 102.5
    assert ig["median_views"] is None
    assert ig["median_engagement_rate"] == pytest.approx(1.125)
    x = by[("kemenko_contoh", "x")]
    assert x["insufficient_data"] is True
    assert x["median_likes"] is None


async def test_unggah_ulang_memperbarui_tidak_menggandakan(client) -> None:
    headers, pid = await _org_with_project(client)
    await client.post(f"{_base(pid)}/posts", json={"items": _posts(5)}, headers=headers)
    again = _posts(5)
    again[0]["likes"] = 999
    again.append(dict(again[1]))
    r = await client.post(f"{_base(pid)}/posts", json={"items": again}, headers=headers)
    assert r.json() == {"received": 6, "stored": 0, "updated": 5, "duplicates_dropped": 1}
    s = await client.get(f"{_base(pid)}/posts/summary", headers=headers)
    assert s.json()["n_posts"] == 5


async def test_ringkasan_menurut_rentang_tanggal(client) -> None:
    headers, pid = await _org_with_project(client)
    await client.post(f"{_base(pid)}/posts", json={"items": _posts(10)}, headers=headers)
    s = await client.get(
        f"{_base(pid)}/posts/summary",
        params={"start": "2026-10-01T00:00:00Z", "end": "2026-10-06T00:00:00Z"},
        headers=headers,
    )
    assert s.json()["n_posts"] == 5


async def test_platform_tidak_dikenal_dan_angka_negatif_ditolak(client) -> None:
    headers, pid = await _org_with_project(client)
    bad = _posts(1)
    bad[0]["platform"] = "facebook"
    assert (
        await client.post(f"{_base(pid)}/posts", json={"items": bad}, headers=headers)
    ).status_code == 422
    neg = _posts(1)
    neg[0]["likes"] = -1
    assert (
        await client.post(f"{_base(pid)}/posts", json={"items": neg}, headers=headers)
    ).status_code == 422


async def test_skor_tanpa_bukti_ditolak(client) -> None:
    headers, pid = await _org_with_project(client)
    r = await client.put(
        f"{_base(pid)}/scores",
        json={"subject": "Lembaga Contoh", "period": "2026-10",
              "items": [{"indicator": "I5", "score": 4}]},
        headers=headers,
    )
    assert r.status_code == 422
    assert "bukti" in r.text


async def test_skor_dan_alasan_bersamaan_atau_kosong_keduanya_ditolak(client) -> None:
    headers, pid = await _org_with_project(client)
    for item in (
        {"indicator": "I5", "score": 4, "evidence": "SOP", "unavailable_reason": "tidak ada"},
        {"indicator": "I5"},
        {"indicator": "Z1", "score": 3, "evidence": "x"},
    ):
        r = await client.put(
            f"{_base(pid)}/scores",
            json={"subject": "Lembaga Contoh", "period": "2026-10", "items": [item]},
            headers=headers,
        )
        assert r.status_code == 422, item


async def test_kartu_skor_cakupan_dan_total(client) -> None:
    headers, pid = await _org_with_project(client)
    fw = (await client.get(f"{_base(pid)}/framework", headers=headers)).json()
    value = {"INPUT": 2, "PROCESS": 3, "OUTPUT": 4, "OUTCOME": 5}

    # Tahap 1: hanya Input dan Process terisi; Output diisi "tidak tersedia".
    items = [
        {"indicator": i["code"], "score": value[i["dimension"]], "evidence": "dokumen contoh"}
        for i in fw["indicators"]
        if i["dimension"] in ("INPUT", "PROCESS")
    ] + [
        {"indicator": c, "unavailable_reason": "tidak ada akses insight akun"}
        for c in ("O2", "O3", "O7")
    ]
    r = await client.put(
        f"{_base(pid)}/scores",
        json={"subject": "Lembaga Contoh", "period": "2026-10", "items": items},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    card = r.json()
    dims = {d["dimension"]: d for d in card["dimensions"]}
    assert dims["INPUT"]["score"] == 2.0 and dims["INPUT"]["published"] is True
    assert dims["PROCESS"]["score"] == 3.0
    assert dims["OUTPUT"]["published"] is False and dims["OUTPUT"]["score"] is None
    assert card["total"] is None and card["label"] is None
    assert (card["n_scored"], card["n_unavailable"], card["n_empty"]) == (13, 3, 12)
    assert any("tidak terbit" in s for s in card["limitations"])
    assert "bukan standar resmi" in card["disclaimer"]

    # Tahap 2: sisanya diisi; total terbit.
    rest = [
        {"indicator": i["code"], "score": value[i["dimension"]], "evidence": "data contoh"}
        for i in fw["indicators"]
        if i["dimension"] in ("OUTPUT", "OUTCOME") and i["code"] not in ("O2", "O3", "O7")
    ]
    r = await client.put(
        f"{_base(pid)}/scores",
        json={"subject": "Lembaga Contoh", "period": "2026-10", "items": rest},
        headers=headers,
    )
    card = r.json()
    assert card["total"] == 3.75
    assert card["total_equal_weights"] == 3.5
    assert card["label"] == "Tertata"

    got = await client.get(
        f"{_base(pid)}/scores",
        params={"subject": "Lembaga Contoh", "period": "2026-10"},
        headers=headers,
    )
    assert got.json()["total"] == 3.75
    o2 = next(i for i in got.json()["items"] if i["indicator"] == "O2")
    assert o2["score"] is None and o2["unavailable_reason"] == "tidak ada akses insight akun"

    refs = (await client.get(f"{_base(pid)}/assessments", headers=headers)).json()
    assert refs == [
        {"subject": "Lembaga Contoh", "period": "2026-10", "n_scored": 25, "n_unavailable": 3}
    ]


async def test_skor_bisa_diganti_menjadi_tidak_tersedia(client) -> None:
    headers, pid = await _org_with_project(client)
    body = {"subject": "L", "period": "2026-09",
            "items": [{"indicator": "I1", "score": 3, "evidence": "SK tim"}]}
    assert (await client.put(f"{_base(pid)}/scores", json=body, headers=headers)).status_code == 200
    body["items"] = [{"indicator": "I1", "unavailable_reason": "dokumen ditarik"}]
    r = await client.put(f"{_base(pid)}/scores", json=body, headers=headers)
    assert r.status_code == 200, r.text
    i1 = next(i for i in r.json()["items"] if i["indicator"] == "I1")
    assert i1["score"] is None and i1["unavailable_reason"] == "dokumen ditarik"


async def test_isolasi_tenant_unggahan_dan_skor(client) -> None:
    """Organisasi B tidak bisa membaca atau menulis data proyek organisasi A."""
    headers_a, pid_a = await _org_with_project(client)
    headers_b, _ = await _org_with_project(client)

    await client.post(f"{_base(pid_a)}/posts", json={"items": _posts(6)}, headers=headers_a)
    await client.put(
        f"{_base(pid_a)}/scores",
        json={"subject": "L", "period": "2026-10",
              "items": [{"indicator": "I1", "score": 3, "evidence": "SK"}]},
        headers=headers_a,
    )

    assert (
        await client.get(f"{_base(pid_a)}/posts/summary", headers=headers_b)
    ).status_code == 404
    assert (
        await client.get(
            f"{_base(pid_a)}/scores", params={"subject": "L", "period": "2026-10"},
            headers=headers_b,
        )
    ).status_code == 404
    assert (await client.get(f"{_base(pid_a)}/assessments", headers=headers_b)).status_code == 404
    assert (
        await client.post(f"{_base(pid_a)}/posts", json={"items": _posts(1)}, headers=headers_b)
    ).status_code == 404
    assert (
        await client.put(
            f"{_base(pid_a)}/scores",
            json={"subject": "L", "period": "2026-10",
                  "items": [{"indicator": "I1", "score": 5, "evidence": "selundupan"}]},
            headers=headers_b,
        )
    ).status_code == 404

    # Data A tidak berubah.
    s = await client.get(f"{_base(pid_a)}/posts/summary", headers=headers_a)
    assert s.json()["n_posts"] == 6


async def test_rls_menolak_baris_lintas_tenant_di_lapisan_basis_data() -> None:
    """Bukan lewat API: langsung ke Postgres sebagai pop_app (R3)."""
    if not DSN:
        pytest.skip("TEST_DATABASE_URL_APP tidak diset")
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(DSN)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    a, b, pa = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        for org in (a, b):
            async with sm() as s, s.begin():
                await s.execute(
                    text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org)}
                )
                await s.execute(
                    text("INSERT INTO organizations (id, name, slug) VALUES (:i, 'X', :s)"),
                    {"i": str(org), "s": f"rls-{org.hex[:8]}"},
                )
        async with sm() as s, s.begin():
            await s.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(a)})
            await s.execute(
                text("INSERT INTO projects (id, org_id, name) VALUES (:p, :o, 'PA')"),
                {"p": str(pa), "o": str(a)},
            )
            await s.execute(
                text(
                    "INSERT INTO official_posts (org_id, project_id, platform, account, "
                    "external_id, posted_at) VALUES (:o, :p, 'x', 'akun', 'e1', now())"
                ),
                {"o": str(a), "p": str(pa)},
            )
            await s.execute(
                text(
                    "INSERT INTO comm_indicator_scores (org_id, project_id, subject, period, "
                    "indicator, score, evidence) VALUES (:o, :p, 'L', '2026-10', 'I1', 3, 'b')"
                ),
                {"o": str(a), "p": str(pa)},
            )
        for table in ("official_posts", "comm_indicator_scores"):
            async with sm() as s, s.begin():
                await s.execute(
                    text("SELECT set_config('app.current_org', :o, true)"), {"o": str(b)}
                )
                assert (await s.execute(text(f"SELECT count(*) FROM {table}"))).scalar() == 0
            async with sm() as s, s.begin():
                assert (await s.execute(text(f"SELECT count(*) FROM {table}"))).scalar() == 0
        with pytest.raises(Exception):  # noqa: B017
            async with sm() as s, s.begin():
                await s.execute(
                    text("SELECT set_config('app.current_org', :o, true)"), {"o": str(b)}
                )
                await s.execute(
                    text(
                        "INSERT INTO official_posts (org_id, project_id, platform, account, "
                        "external_id, posted_at) VALUES (:o, :p, 'x', 'akun', 'e2', now())"
                    ),
                    {"o": str(a), "p": str(pa)},
                )
    finally:
        await engine.dispose()
