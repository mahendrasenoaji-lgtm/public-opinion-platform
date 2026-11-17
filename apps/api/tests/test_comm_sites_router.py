"""Tes end-to-end keaktifan situs resmi terhadap Postgres dengan RLS aktif.
Jaringan tidak disentuh: `read_site` diganti tiruan."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

DSN = os.getenv("TEST_DATABASE_URL_APP")

if DSN:
    os.environ["DATABASE_URL"] = DSN
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")

pytestmark = pytest.mark.asyncio(loop_scope="session")

seen_list_urls: list[list[str]] = []
# Pukul 03.00 UTC (10.00 WIB) pada tanggal WIB hari ini. Router menghitung "hari ini"
# dalam WIB; memakai tanggal UTC membuat tes gagal antara 00.00 dan 07.00 WIB
# (ketahuan di CI 18 Nov 2026 00.02 WIB: n_30 29, bukan 30).
_WIB_TODAY = (datetime.now(UTC) + timedelta(hours=7)).date()
NOW = datetime(_WIB_TODAY.year, _WIB_TODAY.month, _WIB_TODAY.day, 3, tzinfo=UTC)


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
    slug = f"test-situs-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Situs",
            "org_slug": slug,
            "full_name": "Penguji Situs",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Situs"}, headers=headers)
    assert proj.status_code == 201, proj.text
    return headers, proj.json()["id"]


def _fake(kind: str, days_ago: list[int], *, same_stamp: bool = False):
    from app.connectors import official_site as osite

    async def read_site(base: str, *, list_urls: list[str] | None = None) -> osite.SiteReading:
        seen_list_urls.append(list(list_urls or []))
        base_url = osite.normalize_base(base)
        items = [
            osite.SiteItem(
                url=f"{base_url}/siaran-pers/butir-{d}",
                title=f"Butir {d}" if kind == "rss" else None,
                published_at=NOW if same_stamp else NOW - timedelta(days=d),
            )
            for d in days_ago
        ]
        return osite.SiteReading(
            base_url=base_url,
            kind=kind,  # type: ignore[arg-type]
            source_url=f"{base_url}/rss" if kind != "none" else None,
            items=items,
            notes=["catatan tiruan"],
            n_requests=3,
        )

    return read_site


class TestSitus:
    async def test_feed_terbaca_dan_keaktifan(self, client, monkeypatch) -> None:
        from app.connectors import official_site as osite

        headers, pid = await _org_with_project(client)
        base = f"/v1/projects/{pid}/comm-performance/sites"
        monkeypatch.setattr(osite, "read_site", _fake("rss", list(range(0, 40))))
        r = await client.post(
            base, json={"subject": "Lembaga Contoh", "url": "lembaga.go.id"}, headers=headers
        )
        assert r.status_code == 201, r.text
        assert r.json()["feed_kind"] == "rss" and r.json()["result"]["stored"] == 40

        got = (await client.get(base, headers=headers)).json()
        site = got["sites"][0]
        assert site["base_url"] == "https://lembaga.go.id" and site["n_total"] == 40
        assert site["n_30"] == 30 and site["quiet"] is False and site["days_since_last"] == 0
        assert site["status"] == "hampir tiap hari" and site["median_gap_days"] == 1.0
        assert site["categories"] == [["siaran_pers", "Siaran pers", 40]]
        assert site["origins"] == {"rss": 40} and len(site["latest"]) == 8
        assert got["source"] == "OFFICIAL_SITE" and got["limitations"]

        # Baru saja dibaca: pembacaan ulang ditahan supaya situs tidak dibebani.
        soon = await client.post(f"{base}/{site['id']}/refresh", headers=headers)
        assert soon.status_code == 429 and "Tunggu" in soon.text

        # Baca ulang: butir yang sama diperbarui, bukan digandakan.
        from app.routers import comm_sites

        monkeypatch.setattr(comm_sites, "READ_COOLDOWN", timedelta(0))
        again = await client.post(f"{base}/{site['id']}/refresh", headers=headers)
        assert again.status_code == 200, again.text
        assert again.json()["result"] == {"received": 40, "stored": 0, "updated": 40}

        dup = await client.post(
            base, json={"subject": "Nama lain", "url": "https://lembaga.go.id/x"}, headers=headers
        )
        assert dup.status_code == 409

    async def test_sitemap_bercap_mesin_tidak_dipakai(self, client, monkeypatch) -> None:
        from app.connectors import official_site as osite

        headers, pid = await _org_with_project(client)
        base = f"/v1/projects/{pid}/comm-performance/sites"
        monkeypatch.setattr(osite, "read_site", _fake("sitemap", list(range(30)), same_stamp=True))
        r = await client.post(base, json={"subject": "BX", "url": "badan.go.id"}, headers=headers)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["feed_kind"] == "none" and body["result"]["stored"] == 0
        assert any("cap waktu pembuatan berkas" in n for n in body["notes"])
        site = (await client.get(base, headers=headers)).json()["sites"][0]
        assert site["n_total"] == 0 and site["quiet"] is True
        assert site["status"] == "belum ada terbitan tercatat" and site["source_url"] is None

    async def test_unggah_manual_dan_sepi(self, client, monkeypatch) -> None:
        from app.connectors import official_site as osite

        headers, pid = await _org_with_project(client)
        base = f"/v1/projects/{pid}/comm-performance/sites"
        monkeypatch.setattr(osite, "read_site", _fake("none", []))
        sid = (
            await client.post(base, json={"subject": "KY", "url": "kemeny.go.id"}, headers=headers)
        ).json()["site_id"]

        old = (NOW - timedelta(days=45)).date().isoformat()
        items = [
            {"url": "https://www.kemeny.go.id/berita/a", "title": "A", "published_at": old},
            {"url": "https://kemeny.go.id/x/b", "published_at": old, "category": "Pengumuman"},
        ]
        r = await client.post(f"{base}/{sid}/items", json={"items": items}, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json() == {"received": 2, "stored": 2, "updated": 0}
        site = (await client.get(base, headers=headers)).json()["sites"][0]
        assert site["quiet"] is True and site["n_30"] == 0 and site["n_total"] == 2
        assert site["status"].startswith("sepi:") and site["origins"] == {"manual": 2}
        assert {c[0] for c in site["categories"]} == {"berita", "pengumuman"}

        foreign = await client.post(
            f"{base}/{sid}/items",
            json={"items": [{"url": "https://lain.example.com/a", "published_at": old}]},
            headers=headers,
        )
        assert foreign.status_code == 422 and "bukan dari" in foreign.text
        future = await client.post(
            f"{base}/{sid}/items",
            json={"items": [{"url": "https://kemeny.go.id/b/c", "published_at": "2099-01-01"}]},
            headers=headers,
        )
        assert future.status_code == 422
        bad = await client.post(
            f"{base}/{sid}/items",
            json={"items": [{"url": "https://kemeny.go.id/b/c", "published_at": old,
                             "category": "gosip"}]},
            headers=headers,
        )
        assert bad.status_code == 422

        assert (await client.delete(f"{base}/{sid}", headers=headers)).status_code == 204
        assert (await client.get(base, headers=headers)).json()["sites"] == []

    async def test_halaman_daftar_didaftarkan_lalu_dibaca(self, client, monkeypatch) -> None:
        from app.connectors import official_site as osite

        headers, pid = await _org_with_project(client)
        base = f"/v1/projects/{pid}/comm-performance/sites"
        monkeypatch.setattr(osite, "read_site", _fake("none", []))
        sid = (
            await client.post(base, json={"subject": "KZ", "url": "kemenz.go.id"}, headers=headers)
        ).json()["site_id"]

        monkeypatch.setattr(osite, "read_site", _fake("halaman", [0, 1, 2]))
        r = await client.put(
            f"{base}/{sid}/list-urls", json={"list_urls": ["/berita", " "]}, headers=headers
        )
        assert r.status_code == 200, r.text
        assert r.json()["feed_kind"] == "halaman" and r.json()["result"]["stored"] == 3
        assert seen_list_urls[-1] == ["https://kemenz.go.id/berita"]
        site = (await client.get(base, headers=headers)).json()["sites"][0]
        assert site["list_urls"] == ["https://kemenz.go.id/berita"]
        assert site["origins"] == {"halaman": 3} and site["quiet"] is False

        foreign = await client.put(
            f"{base}/{sid}/list-urls",
            json={"list_urls": ["https://situs-lain.example.com/berita"]},
            headers=headers,
        )
        assert foreign.status_code == 422 and "harus berada di" in foreign.text

    async def test_alamat_tidak_sah(self, client) -> None:
        headers, pid = await _org_with_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/comm-performance/sites",
            json={"subject": "X", "url": "http://127.0.0.1:8000"},
            headers=headers,
        )
        assert r.status_code == 422


class TestIsolasiTenant:
    async def test_org_lain_tidak_melihat_dan_tidak_bisa_menulis(self, client, monkeypatch) -> None:
        from app.connectors import official_site as osite

        monkeypatch.setattr(osite, "read_site", _fake("rss", [1, 2, 3]))
        headers_a, pid_a = await _org_with_project(client)
        headers_b, _ = await _org_with_project(client)
        base_a = f"/v1/projects/{pid_a}/comm-performance/sites"
        sid = (
            await client.post(base_a, json={"subject": "A", "url": "a.go.id"}, headers=headers_a)
        ).json()["site_id"]

        assert (await client.get(base_a, headers=headers_b)).status_code == 404
        item = {"items": [{"url": "https://a.go.id/b/c", "published_at": "2026-11-01"}]}
        for call in (
            client.post(base_a, json={"subject": "B", "url": "b.go.id"}, headers=headers_b),
            client.post(f"{base_a}/{sid}/refresh", headers=headers_b),
            client.put(f"{base_a}/{sid}/list-urls", json={"list_urls": []}, headers=headers_b),
            client.post(f"{base_a}/{sid}/items", json=item, headers=headers_b),
            client.delete(f"{base_a}/{sid}", headers=headers_b),
        ):
            assert (await call).status_code == 404
        assert (await client.get(base_a, headers=headers_a)).json()["sites"][0]["n_total"] == 3
