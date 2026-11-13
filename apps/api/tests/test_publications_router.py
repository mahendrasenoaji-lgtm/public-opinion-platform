"""Tes end-to-end publikasi: alur status, ralat, baca publik, isolasi tenant."""

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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _org(client) -> tuple[dict[str, str], str]:
    slug = f"test-pub-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Publikasi",
            "org_slug": slug,
            "full_name": "Penulis Uji",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Publikasi"}, headers=headers)
    assert proj.status_code == 201, proj.text
    pid = proj.json()["id"]
    marker = uuid.uuid4().hex
    ingest = await client.post(
        f"/v1/projects/{pid}/signals/ingest",
        json={
            "connector": "manual",
            "source": "SOCIAL",
            "items": [
                {
                    "external_id": f"c{i}-{marker}",
                    "text": f"antre bbm lama sekali kecewa nomor {i}",
                    "published_at": f"2026-10-1{i % 5 + 1}T03:00:00Z",
                    "engagement": i,
                    "url": f"https://www.youtube.com/watch?v=abc&lc={marker}{i}",
                }
                for i in range(12)
            ],
        },
        headers=headers,
    )
    assert ingest.status_code == 200, ingest.text
    return headers, pid


def _base(pid: str) -> str:
    return f"/v1/projects/{pid}/publications"


DRAFT = {
    "title": "Sentimen Publik terhadap Antrean BBM",
    "start": "2026-10-11",
    "end": "2026-10-20",
    "tz": "WITA",
}


async def _draft(client, headers, pid) -> dict:
    r = await client.post(_base(pid), json=DRAFT, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _publish(client, headers, pid, pub_id) -> dict:
    r = await client.patch(
        f"{_base(pid)}/{pub_id}",
        json={"summary": "Ringkasan uji.", "body": "## Temuan\n\nIsi uji.", "tags": ["Energi"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    for target in ("review", "published"):
        r = await client.post(
            f"{_base(pid)}/{pub_id}/status", json={"status": target}, headers=headers
        )
        assert r.status_code == 200, r.text
    return r.json()


async def test_draf_memuat_snapshot_beku_tanpa_teks_warga(client) -> None:
    headers, pid = await _org(client)
    d = await _draft(client, headers, pid)
    assert d["status"] == "draft" and d["version"] == 1
    assert d["author_name"] == "Penulis Uji"
    assert d["slug"].startswith("sentimen-publik-terhadap-antrean-bbm-")
    snap = d["snapshot"]
    assert snap["period_start"] == "2026-10-11" and snap["timezone"] == "WITA"
    social = next(s for s in snap["report"]["sources"] if s["source"] == "SOCIAL")
    assert social["n"] == 12
    dumped = str(snap)
    # Kata teratas adalah agregat dan boleh tampil; kalimat utuh dan tautan tidak.
    assert "antre bbm lama sekali" not in dumped and "lc=" not in dumped


async def test_snapshot_tidak_berubah_saat_data_bertambah(client) -> None:
    headers, pid = await _org(client)
    d = await _draft(client, headers, pid)
    await client.post(
        f"/v1/projects/{pid}/signals/ingest",
        json={
            "connector": "manual",
            "source": "SOCIAL",
            "items": [
                {
                    "external_id": f"baru-{uuid.uuid4().hex}",
                    "text": "komentar baru sesudah draf dibuat soal bbm",
                    "published_at": "2026-10-12T05:00:00Z",
                }
            ],
        },
        headers=headers,
    )
    again = (await client.get(f"{_base(pid)}/{d['id']}", headers=headers)).json()
    social = next(s for s in again["snapshot"]["report"]["sources"] if s["source"] == "SOCIAL")
    assert social["n"] == 12


async def test_draf_tidak_terbaca_publik(client) -> None:
    headers, pid = await _org(client)
    d = await _draft(client, headers, pid)
    assert (await client.get(f"/v1/public/publications/{d['slug']}")).status_code == 404
    listed = (await client.get("/v1/public/publications", params={"limit": 100})).json()
    assert d["slug"] not in [i["slug"] for i in listed["items"]]


async def test_tidak_bisa_terbit_tanpa_tinjau_atau_tanpa_isi(client) -> None:
    headers, pid = await _org(client)
    d = await _draft(client, headers, pid)
    url = f"{_base(pid)}/{d['id']}/status"
    assert (
        await client.post(url, json={"status": "published"}, headers=headers)
    ).status_code == 409
    assert (await client.post(url, json={"status": "review"}, headers=headers)).status_code == 200
    r = await client.post(url, json={"status": "published"}, headers=headers)
    assert r.status_code == 422 and "Ringkasan" in r.text


async def test_terbit_lalu_terbaca_publik_tanpa_login(client) -> None:
    headers, pid = await _org(client)
    d = await _draft(client, headers, pid)
    p = await _publish(client, headers, pid, d["id"])
    assert p["status"] == "published" and p["published_at"]

    r = await client.get(f"/v1/public/publications/{d['slug']}")
    assert r.status_code == 200, r.text
    art = r.json()
    assert art["title"] == DRAFT["title"] and art["tags"] == ["energi"]
    assert art["snapshot"]["report"]["sources"]
    assert "org_id" not in art and "project_id" not in art and "id" not in art

    listed = (
        await client.get("/v1/public/publications", params={"tag": "energi", "limit": 100})
    ).json()
    assert d["slug"] in [i["slug"] for i in listed["items"]]
    assert listed["total"] >= 1
    none = (
        await client.get("/v1/public/publications", params={"tag": f"x{uuid.uuid4().hex}"})
    ).json()
    assert none == {"total": 0, "items": []}


async def test_ralat_wajib_catatan_versi_naik_dan_isi_lama_tidak_dibuka(client) -> None:
    headers, pid = await _org(client)
    d = await _draft(client, headers, pid)
    await _publish(client, headers, pid, d["id"])
    url = f"{_base(pid)}/{d['id']}"

    r = await client.patch(url, json={"body": "Isi baru."}, headers=headers)
    assert r.status_code == 422 and "ralat" in r.text

    r = await client.patch(
        url, json={"body": "Isi baru.", "correction_note": "Angka n diperbaiki."}, headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 2
    assert r.json()["corrections"][0]["previous"]["body"] == "## Temuan\n\nIsi uji."

    art = (await client.get(f"/v1/public/publications/{d['slug']}")).json()
    assert art["version"] == 2 and art["body"] == "Isi baru."
    assert art["corrections"] == [
        {"version": 1, "at": art["corrections"][0]["at"], "note": "Angka n diperbaiki."}
    ]


async def test_artikel_terbit_tidak_bisa_dihapus_atau_ditarik(client) -> None:
    headers, pid = await _org(client)
    d = await _draft(client, headers, pid)
    await _publish(client, headers, pid, d["id"])
    url = f"{_base(pid)}/{d['id']}"
    assert (await client.delete(url, headers=headers)).status_code == 409
    r = await client.post(f"{url}/status", json={"status": "draft"}, headers=headers)
    assert r.status_code == 409


async def test_draf_bisa_dihapus(client) -> None:
    headers, pid = await _org(client)
    d = await _draft(client, headers, pid)
    assert (await client.delete(f"{_base(pid)}/{d['id']}", headers=headers)).status_code == 204
    assert (await client.get(f"{_base(pid)}/{d['id']}", headers=headers)).status_code == 404


async def test_periode_terbalik_ditolak(client) -> None:
    headers, pid = await _org(client)
    r = await client.post(
        _base(pid), json={**DRAFT, "start": "2026-10-20", "end": "2026-10-11"}, headers=headers
    )
    assert r.status_code == 422


async def test_isolasi_tenant(client) -> None:
    headers_a, pid_a = await _org(client)
    headers_b, _ = await _org(client)
    d = await _draft(client, headers_a, pid_a)
    url = f"{_base(pid_a)}/{d['id']}"
    assert (await client.get(_base(pid_a), headers=headers_b)).status_code == 404
    assert (await client.get(url, headers=headers_b)).status_code == 404
    assert (await client.post(_base(pid_a), json=DRAFT, headers=headers_b)).status_code == 404
    assert (
        await client.patch(url, json={"title": "Dibajak"}, headers=headers_b)
    ).status_code == 404
    assert (
        await client.post(f"{url}/status", json={"status": "review"}, headers=headers_b)
    ).status_code == 404
    assert (await client.delete(url, headers=headers_b)).status_code == 404
    assert (await client.get(url, headers=headers_a)).json()["title"] == DRAFT["title"]


async def test_rls_dan_fungsi_publik_di_lapisan_basis_data() -> None:
    """Langsung ke Postgres sebagai pop_app: tabel tertutup, fungsi hanya 'published'."""
    if not DSN:
        pytest.skip("TEST_DATABASE_URL_APP tidak diset")
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(DSN)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    a, b, pa = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    s_draft, s_pub = f"rls-draf-{a.hex[:8]}", f"rls-terbit-{a.hex[:8]}"
    ins = (
        "INSERT INTO publications (org_id, project_id, slug, title, author_name, snapshot, "
        "status, published_at) VALUES (:o, :p, :s, 'T', 'A', '{}'::jsonb, :st, :at)"
    )
    try:
        for org in (a, b):
            async with sm() as s, s.begin():
                await s.execute(
                    text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org)}
                )
                await s.execute(
                    text("INSERT INTO organizations (id, name, slug) VALUES (:i, 'X', :s)"),
                    {"i": str(org), "s": f"rlsp-{org.hex[:8]}"},
                )
        async with sm() as s, s.begin():
            await s.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(a)})
            await s.execute(
                text("INSERT INTO projects (id, org_id, name) VALUES (:p, :o, 'PA')"),
                {"p": str(pa), "o": str(a)},
            )
            await s.execute(
                text(ins), {"o": str(a), "p": str(pa), "s": s_draft, "st": "draft", "at": None}
            )
            await s.execute(
                text(ins.replace(":at", "now()")),
                {"o": str(a), "p": str(pa), "s": s_pub, "st": "published"},
            )
        # Tanpa organisasi dan sebagai organisasi lain: tabel kosong.
        async with sm() as s, s.begin():
            assert (await s.execute(text("SELECT count(*) FROM publications"))).scalar() == 0
        async with sm() as s, s.begin():
            await s.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(b)})
            assert (await s.execute(text("SELECT count(*) FROM publications"))).scalar() == 0
        # Fungsi publik: hanya yang terbit.
        async with sm() as s, s.begin():
            got = (
                await s.execute(text("SELECT slug FROM public_publication(:s)"), {"s": s_pub})
            ).all()
            assert [r[0] for r in got] == [s_pub]
            none = (
                await s.execute(text("SELECT slug FROM public_publication(:s)"), {"s": s_draft})
            ).all()
            assert none == []
            slugs = [
                r[0]
                for r in (
                    await s.execute(text("SELECT slug FROM public_publications(NULL, 100, 0)"))
                ).all()
            ]
            assert s_pub in slugs and s_draft not in slugs
        # Organisasi B tidak bisa menyisipkan artikel atas nama A.
        with pytest.raises(Exception):  # noqa: B017
            async with sm() as s, s.begin():
                await s.execute(
                    text("SELECT set_config('app.current_org', :o, true)"), {"o": str(b)}
                )
                await s.execute(
                    text(ins),
                    {
                        "o": str(a),
                        "p": str(pa),
                        "s": f"selundup-{b.hex[:8]}",
                        "st": "draft",
                        "at": None,
                    },
                )
    finally:
        await engine.dispose()
