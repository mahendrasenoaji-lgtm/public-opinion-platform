"""Tes end-to-end pengumpulan terjadwal: POST .../signals/collect-all + token pengumpul.

Pola sama dengan test_signals_router.py: AsyncClient asli terhadap Postgres
nyata dengan role pop_app (RLS aktif).

Jaringan sengaja tidak disentuh. Konektor `_static_test` di bawah didaftarkan
khusus untuk tes ini dan mengembalikan item tetap — yang diuji adalah jalur
API (otorisasi, penyimpanan, laporan per sumber, deteksi celah), bukan
apakah feed penerbit sedang hidup.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest

from app.connectors.base import (
    Connector,
    ConnectorError,
    FetchStats,
    RawItem,
    register,
)
from app.models.measurement import SignalSource

DSN = os.getenv("TEST_DATABASE_URL_APP")

if DSN:
    os.environ["DATABASE_URL"] = DSN
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")

pytestmark = pytest.mark.asyncio(loop_scope="session")


@register
class _StaticTestConnector(Connector):
    """Mengembalikan dua item tetap; item tertua yang 'ditawarkan' bisa diatur."""

    key: ClassVar[str] = "_static_test"
    label: ClassVar[str] = "Konektor statis untuk tes"
    source: ClassVar[SignalSource] = SignalSource.MEDIA
    config_fields: ClassVar[tuple[str, ...]] = ("name",)
    notes: ClassVar[str] = "Hanya untuk tes; tidak pernah menyentuh jaringan."

    async def fetch(
        self,
        config: dict[str, object],
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[RawItem]:
        if config.get("fail"):
            raise ConnectorError("penerbit menolak permintaan feed (403)")
        if config.get("crash"):
            raise ValueError("bug di konektor")
        now = datetime.now(UTC)
        items = [
            RawItem(
                external_id=f"https://contoh.id/{config['name']}/{i}",
                text=f"Program makan bergizi gratis dievaluasi, bagian {i}",
                published_at=now - timedelta(minutes=10 * (i + 1)),
                url=f"https://contoh.id/{config['name']}/{i}",
            )
            for i in range(2)
        ]
        oldest_minutes = int(str(config.get("oldest_minutes_ago", "20")))
        self.last_fetch = FetchStats(
            offered=2,
            oldest_offered=now - timedelta(minutes=oldest_minutes),
            matched=2,
        )
        return items[:limit]


@pytest.fixture
async def client():
    if not DSN:
        pytest.skip("TEST_DATABASE_URL_APP tidak diset")

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _new_project(client) -> tuple[dict[str, str], str]:
    slug = f"col-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Pengumpul",
            "org_slug": slug,
            "full_name": "Penguji Pengumpul",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Pengumpul"}, headers=headers)
    assert proj.status_code == 201, proj.text
    return headers, proj.json()["id"]


async def _add_source(client, headers, pid, **config: str) -> str:
    r = await client.post(
        f"/v1/projects/{pid}/signals/sources",
        json={"connector": "_static_test", "config": {"name": uuid.uuid4().hex[:8], **config}},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _issue(client, headers, pid) -> dict:
    r = await client.post(
        f"/v1/projects/{pid}/signals/collector-token", json={"days": 30}, headers=headers
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _with_role(headers: dict[str, str], role: str) -> dict[str, str]:
    """Token akses sah untuk user yang sama, dengan peran berbeda."""
    import jwt

    from app.services.auth import create_access_token

    claims = jwt.decode(
        headers["Authorization"].removeprefix("Bearer "), options={"verify_signature": False}
    )
    return _bearer(
        create_access_token(
            user_id=uuid.UUID(claims["sub"]),
            org_id=uuid.UUID(claims["org"]),
            role=role,
            email=claims["email"],
        )
    )


class TestCollectAll:
    async def test_semua_sumber_ditarik_dan_dilaporkan_per_sumber(self, client) -> None:
        headers, pid = await _new_project(client)
        await _add_source(client, headers, pid)
        await _add_source(client, headers, pid)

        r = await client.post(f"/v1/projects/{pid}/signals/collect-all", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["via"] == "user"
        assert body["sources_total"] == 2
        assert body["sources_ok"] == 2
        assert body["sources_failed"] == 0
        assert body["stored_total"] == 4
        assert all(s["offered"] == 2 and s["matched"] == 2 for s in body["results"])

    async def test_satu_sumber_gagal_tidak_menggagalkan_yang_lain(self, client) -> None:
        headers, pid = await _new_project(client)
        await _add_source(client, headers, pid)
        await _add_source(client, headers, pid, fail="1")

        body = (
            await client.post(f"/v1/projects/{pid}/signals/collect-all", headers=headers)
        ).json()
        assert body["sources_ok"] == 1
        assert body["sources_failed"] == 1
        failed = next(s for s in body["results"] if not s["ok"])
        # Pesan penerbit harus sampai ke pemanggil — "gagal" tanpa alasan
        # adalah persis yang membuat routine lama tampak berhasil.
        assert "403" in failed["error"]
        assert body["stored_total"] == 2

    async def test_konektor_yang_crash_diisolasi_per_sumber(self, client) -> None:
        headers, pid = await _new_project(client)
        await _add_source(client, headers, pid)
        await _add_source(client, headers, pid, crash="1")
        r = await client.post(f"/v1/projects/{pid}/signals/collect-all", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["sources_ok"] == 1 and body["sources_failed"] == 1
        assert "ValueError" in next(s for s in body["results"] if not s["ok"])["error"]

    async def test_tarik_ulang_tidak_menggandakan(self, client) -> None:
        headers, pid = await _new_project(client)
        await _add_source(client, headers, pid)
        await client.post(f"/v1/projects/{pid}/signals/collect-all", headers=headers)
        again = (
            await client.post(f"/v1/projects/{pid}/signals/collect-all", headers=headers)
        ).json()
        assert again["stored_total"] == 0
        assert again["results"][0]["result"]["already_present"] == 2

    async def test_celah_cakupan_terdeteksi(self, client) -> None:
        headers, pid = await _new_project(client)
        # Item tertua yang ditawarkan selalu 5 menit di depan "sekarang", jadi
        # pasti lebih baru dari pengambilan sebelumnya — celah yang tidak ambigu
        # tanpa perlu menunggu waktu berjalan di dalam tes.
        await _add_source(client, headers, pid, oldest_minutes_ago="-5")
        first = (
            await client.post(f"/v1/projects/{pid}/signals/collect-all", headers=headers)
        ).json()
        assert first["coverage_gaps"] == 0  # belum pernah ditarik: tidak bisa dinilai
        second = (
            await client.post(f"/v1/projects/{pid}/signals/collect-all", headers=headers)
        ).json()
        assert second["coverage_gaps"] == 1
        assert second["results"][0]["previous_sync_at"] is not None

    async def test_tanpa_celah_bila_feed_masih_mencakup_pengambilan_lalu(self, client) -> None:
        headers, pid = await _new_project(client)
        await _add_source(client, headers, pid, oldest_minutes_ago="600")
        await client.post(f"/v1/projects/{pid}/signals/collect-all", headers=headers)
        second = (
            await client.post(f"/v1/projects/{pid}/signals/collect-all", headers=headers)
        ).json()
        assert second["coverage_gaps"] == 0

    async def test_proyek_tanpa_sumber_tidak_jatuh(self, client) -> None:
        headers, pid = await _new_project(client)
        body = (
            await client.post(f"/v1/projects/{pid}/signals/collect-all", headers=headers)
        ).json()
        assert body["sources_total"] == 0
        assert body["results"] == []

    async def test_peran_di_bawah_researcher_ditolak(self, client) -> None:
        headers, pid = await _new_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/signals/collect-all", headers=_with_role(headers, "VIEWER")
        )
        assert r.status_code == 403


class TestTokenPengumpul:
    async def test_token_bisa_menarik_proyeknya(self, client) -> None:
        headers, pid = await _new_project(client)
        await _add_source(client, headers, pid)
        issued = await _issue(client, headers, pid)

        r = await client.post(
            f"/v1/projects/{pid}/signals/collect-all", headers=_bearer(issued["token"])
        )
        assert r.status_code == 200, r.text
        assert r.json()["via"] == "collector_token"
        assert r.json()["stored_total"] == 2

    async def test_token_bukan_sesi_pengguna(self, client) -> None:
        """Token pengumpul tidak boleh membuka endpoint lain mana pun."""
        headers, pid = await _new_project(client)
        token = (await _issue(client, headers, pid))["token"]
        for method, path in [
            ("get", "/v1/projects"),
            ("get", f"/v1/projects/{pid}/mentions"),
            ("get", f"/v1/projects/{pid}/signals/sources"),
            ("post", f"/v1/projects/{pid}/signals/collector-token"),
            ("get", "/v1/auth/me"),
        ]:
            r = await client.request(method.upper(), path, headers=_bearer(token), json={})
            assert r.status_code == 401, f"{method} {path} menerima token pengumpul"

    async def test_refresh_token_juga_bukan_sesi(self, client) -> None:
        """Pengerasan decode_token: hanya type=access yang diterima."""
        slug = f"col-org-{uuid.uuid4().hex[:10]}"
        reg = await client.post(
            "/v1/auth/register",
            json={
                "org_name": "Org",
                "org_slug": slug,
                "full_name": "X",
                "email": f"{slug}@example.com",
                "password": "PasswordAsli123",
            },
        )
        refresh = reg.json()["refresh_token"]
        assert (await client.get("/v1/projects", headers=_bearer(refresh))).status_code == 401

    async def test_token_proyek_lain_ditolak(self, client) -> None:
        headers, pid = await _new_project(client)
        other = await client.post("/v1/projects", json={"name": "Lain"}, headers=headers)
        token = (await _issue(client, headers, pid))["token"]
        r = await client.post(
            f"/v1/projects/{other.json()['id']}/signals/collect-all", headers=_bearer(token)
        )
        assert r.status_code == 403

    async def test_menerbitkan_ulang_mematikan_token_lama(self, client) -> None:
        headers, pid = await _new_project(client)
        old = (await _issue(client, headers, pid))["token"]
        new = (await _issue(client, headers, pid))["token"]
        url = f"/v1/projects/{pid}/signals/collect-all"
        assert (await client.post(url, headers=_bearer(old))).status_code == 401
        assert (await client.post(url, headers=_bearer(new))).status_code == 200

    async def test_dicabut_langsung_ditolak(self, client) -> None:
        headers, pid = await _new_project(client)
        token = (await _issue(client, headers, pid))["token"]
        revoked = await client.delete(
            f"/v1/projects/{pid}/signals/collector-token", headers=headers
        )
        assert revoked.status_code == 204
        r = await client.post(f"/v1/projects/{pid}/signals/collect-all", headers=_bearer(token))
        assert r.status_code == 401

        status_ = await client.get(f"/v1/projects/{pid}/signals/collector-token", headers=headers)
        assert status_.json()["active"] is False

    async def test_status_tidak_pernah_memuat_token(self, client) -> None:
        headers, pid = await _new_project(client)
        issued = await _issue(client, headers, pid)
        status_ = await client.get(f"/v1/projects/{pid}/signals/collector-token", headers=headers)
        body = status_.json()
        assert body["active"] is True
        assert body["token_id"] == issued["token_id"]
        assert "token" not in body

    async def test_hanya_research_director_ke_atas_yang_menerbitkan(self, client) -> None:
        headers, pid = await _new_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/signals/collector-token",
            json={},
            headers=_with_role(headers, "RESEARCHER"),
        )
        assert r.status_code == 403

    async def test_masa_berlaku_dibatasi(self, client) -> None:
        headers, pid = await _new_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/signals/collector-token", json={"days": 400}, headers=headers
        )
        assert r.status_code == 422

    async def test_proyek_tidak_ada_404(self, client) -> None:
        headers, _ = await _new_project(client)
        r = await client.post(
            f"/v1/projects/{uuid.uuid4()}/signals/collector-token", json={}, headers=headers
        )
        assert r.status_code == 404


class TestIsolasiTenant:
    """Setiap endpoint bertenant wajib punya tes isolasi (CLAUDE.md §6)."""

    async def test_org_lain_tidak_bisa_menerbitkan_token_untuk_proyek_org_ini(
        self, client
    ) -> None:
        _, pid_a = await _new_project(client)
        headers_b, _ = await _new_project(client)
        # RLS menyembunyikan proyek A dari B, jadi yang terlihat: tidak ada.
        r = await client.post(
            f"/v1/projects/{pid_a}/signals/collector-token", json={}, headers=headers_b
        )
        assert r.status_code == 404

    async def test_org_lain_tidak_bisa_menarik_sumber_org_ini(self, client) -> None:
        headers_a, pid_a = await _new_project(client)
        headers_b, _ = await _new_project(client)
        await _add_source(client, headers_a, pid_a)

        r = await client.post(f"/v1/projects/{pid_a}/signals/collect-all", headers=headers_b)
        assert r.status_code == 200
        assert r.json()["sources_total"] == 0, "RLS bocor: org lain melihat sumber"

    async def test_token_org_lain_tidak_berlaku_walau_project_id_ditempel(
        self, client
    ) -> None:
        """Token B, diarahkan ke proyek A: ditolak karena proyeknya bukan milik token."""
        _, pid_a = await _new_project(client)
        headers_b, pid_b = await _new_project(client)
        token_b = (await _issue(client, headers_b, pid_b))["token"]
        r = await client.post(
            f"/v1/projects/{pid_a}/signals/collect-all", headers=_bearer(token_b)
        )
        assert r.status_code == 403
