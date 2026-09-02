"""Tes verifikasi manusia atas label tema (review workflow).

Pola sama dengan test_signals_router.py: Postgres nyata, role pop_app, RLS
aktif, korpus dua tema yang sama supaya penemuan tema deterministik.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

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


def _korpus_dua_tema() -> list[str]:
    harga = [
        "harga beras di pasar terus naik minggu ini",
        "beras mahal sekali sekarang di pasar tradisional",
        "kenaikan harga pangan memberatkan warga",
        "harga cabai dan beras melonjak tajam",
        "pasar tradisional harga sembako naik lagi",
        "sembako mahal warga mengeluh harga beras",
        "harga pangan naik terus tiap minggu",
        "beras dan minyak goreng makin mahal di pasar",
        "kenaikan sembako bikin belanja dapur membengkak",
        "harga beras premium naik di sejumlah pasar",
        "pangan mahal daya beli warga turun",
        "minyak goreng dan beras harga naik terus",
    ]
    jalan = [
        "jalan rusak parah di jalur utama kecamatan",
        "perbaikan jalan belum selesai sudah berbulan bulan",
        "jalan berlubang bikin kendaraan rusak",
        "infrastruktur jalan di daerah kami terbengkalai",
        "aspal jalan mengelupas setelah hujan deras",
        "jalan provinsi rusak belum diperbaiki juga",
        "kendaraan sulit lewat karena jalan berlubang",
        "perbaikan infrastruktur jalan lambat sekali",
        "jalur transportasi rusak mengganggu distribusi",
        "jalan utama kecamatan rusak berat sejak lama",
        "aspal berlubang membahayakan pengendara motor",
        "infrastruktur jalan daerah butuh perbaikan segera",
    ]
    return harga + jalan


def _item(i: int, text: str) -> dict:
    return {
        "external_id": f"rev-{uuid.uuid4().hex[:8]}-{i}",
        "text": text,
        "published_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        "engagement": i,
    }


async def _new_project_with_topics(client) -> tuple[dict[str, str], str, str]:
    """Daftar org, ingest korpus dua tema, jalankan discover. Return
    (headers, project_id, id salah satu topic)."""
    slug = f"tr-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Review Tema",
            "org_slug": slug,
            "full_name": "Penguji Review",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Review"}, headers=headers)
    pid = proj.json()["id"]

    items = [_item(i, t) for i, t in enumerate(_korpus_dua_tema())]
    await client.post(f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers)
    disc = await client.post(f"/v1/projects/{pid}/topics/discover", headers=headers)
    topic_id = disc.json()["topics"][0]["id"]
    return headers, pid, topic_id


class TestStatusAwal:
    async def test_tema_baru_berstatus_pending(self, client) -> None:
        headers, pid, _tid = await _new_project_with_topics(client)
        rows = (await client.get(f"/v1/projects/{pid}/topics", headers=headers)).json()
        assert all(r["review_status"] == "PENDING" for r in rows)
        assert all(r["reviewed_label"] is None for r in rows)

    async def test_effective_label_default_sama_dengan_label_mentah(self, client) -> None:
        headers, pid, _tid = await _new_project_with_topics(client)
        rows = (await client.get(f"/v1/projects/{pid}/topics", headers=headers)).json()
        assert all(r["effective_label"] == r["label"] for r in rows)


class TestMenyetujuiApaAdanya:
    async def test_approve_tanpa_label_baru(self, client) -> None:
        headers, pid, tid = await _new_project_with_topics(client)
        r = await client.patch(
            f"/v1/projects/{pid}/topics/{tid}/review",
            json={"status": "APPROVED"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["review_status"] == "APPROVED"
        assert body["reviewed_label"] is None
        # disetujui TANPA revisi -> label efektif tetap yang mentah
        assert body["effective_label"] == body["label"]


class TestMerevisiLabel:
    async def test_approve_dengan_label_baru_menggantikan_effective_label(self, client) -> None:
        headers, pid, tid = await _new_project_with_topics(client)
        r = await client.patch(
            f"/v1/projects/{pid}/topics/{tid}/review",
            json={"status": "APPROVED", "label": "Kenaikan harga pangan"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["reviewed_label"] == "Kenaikan harga pangan"
        assert body["effective_label"] == "Kenaikan harga pangan"
        # label ASLI tidak pernah ditimpa
        assert body["label"] != "Kenaikan harga pangan"

    async def test_reject_dengan_label_tidak_mengubah_effective_label(self, client) -> None:
        """Revisi hanya berlaku kalau statusnya APPROVED -- ditolak berarti
        label mentah tetap yang ditampilkan, bukan usulan yang ditolak."""
        headers, pid, tid = await _new_project_with_topics(client)
        r = await client.patch(
            f"/v1/projects/{pid}/topics/{tid}/review",
            json={"status": "REJECTED", "label": "Usulan yang ditolak"},
            headers=headers,
        )
        body = r.json()
        assert body["review_status"] == "REJECTED"
        assert body["reviewed_label"] == "Usulan yang ditolak"  # tetap tersimpan untuk jejak
        assert body["effective_label"] == body["label"]  # tapi TIDAK dipakai sebagai tampilan

    async def test_needs_review_bukan_pilihan_final(self, client) -> None:
        headers, pid, tid = await _new_project_with_topics(client)
        r = await client.patch(
            f"/v1/projects/{pid}/topics/{tid}/review",
            json={"status": "NEEDS_REVIEW"},
            headers=headers,
        )
        assert r.json()["review_status"] == "NEEDS_REVIEW"

    async def test_status_asing_ditolak_validasi(self, client) -> None:
        headers, pid, tid = await _new_project_with_topics(client)
        r = await client.patch(
            f"/v1/projects/{pid}/topics/{tid}/review",
            json={"status": "APPROVED_SEKALI_LAGI"},
            headers=headers,
        )
        assert r.status_code == 422


class TestPersistensi:
    async def test_review_tersimpan_dan_terbaca_ulang_lewat_list(self, client) -> None:
        headers, pid, tid = await _new_project_with_topics(client)
        await client.patch(
            f"/v1/projects/{pid}/topics/{tid}/review",
            json={"status": "APPROVED", "label": "Label revisi"},
            headers=headers,
        )
        rows = (await client.get(f"/v1/projects/{pid}/topics", headers=headers)).json()
        target = next(r for r in rows if r["id"] == tid)
        assert target["effective_label"] == "Label revisi"
        assert target["review_status"] == "APPROVED"


class TestPenolakanYangBenar:
    async def test_tema_tidak_ada_404(self, client) -> None:
        headers, pid, _tid = await _new_project_with_topics(client)
        r = await client.patch(
            f"/v1/projects/{pid}/topics/{uuid.uuid4()}/review",
            json={"status": "APPROVED"},
            headers=headers,
        )
        assert r.status_code == 404

    async def test_label_kosong_string_ditolak_validasi(self, client) -> None:
        headers, pid, tid = await _new_project_with_topics(client)
        r = await client.patch(
            f"/v1/projects/{pid}/topics/{tid}/review",
            json={"status": "APPROVED", "label": ""},
            headers=headers,
        )
        assert r.status_code == 422


class TestIsolasiTenant:
    async def test_org_lain_tidak_bisa_review_tema_asing(self, client) -> None:
        headers_a, pid_a, tid_a = await _new_project_with_topics(client)
        headers_b, _pid_b, _tid_b = await _new_project_with_topics(client)
        r = await client.patch(
            f"/v1/projects/{pid_a}/topics/{tid_a}/review",
            json={"status": "APPROVED", "label": "Diambil alih org lain"},
            headers=headers_b,
        )
        assert r.status_code == 404, "RLS bocor: org lain bisa mereview tema asing"
