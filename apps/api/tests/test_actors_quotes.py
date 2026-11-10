"""Tes peta aktor (ringkasan) dan kutipan berita: fungsi murni + endpoint."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.services import actors
from app.services.news_quotes import extract_quotes

DSN = os.getenv("TEST_DATABASE_URL_APP")

if DSN:
    os.environ["DATABASE_URL"] = DSN
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")


# ----------------------------------------------------------------- kutipan ----


def test_penutur_sesudah_kutipan():
    (q,) = extract_quotes(
        '"Stok BBM di Bali aman untuk 20 hari," kata Menteri ESDM Bahlil Lahadalia di Denpasar.'
    )
    assert q.text == "Stok BBM di Bali aman untuk 20 hari"
    assert q.speaker == "Menteri ESDM Bahlil Lahadalia"


def test_penutur_sebelum_kutipan_dan_petik_melengkung():
    (q,) = extract_quotes(
        "Gubernur Bali Wayan Koster mengatakan, “Kami sudah meminta tambahan kuota.”"
    )
    assert q.speaker == "Gubernur Bali Wayan Koster"
    assert q.text == "Kami sudah meminta tambahan kuota."


def test_nama_hari_di_belakang_nama_dibuang():
    (q,) = extract_quotes('"Distribusi kembali normal hari ini," ujar Budi Santoso Senin.')
    assert q.speaker == "Budi Santoso"


def test_tanpa_atribusi_penutur_none_bukan_tebakan():
    assert extract_quotes("“Antrean ini tidak boleh terulang,” tegasnya.")[0].speaker is None
    assert extract_quotes('"Kami kecewa dengan pelayanan ini," ujar seorang warga.')[
        0
    ].speaker is None
    assert extract_quotes('Ia menegaskan: "Tidak ada kelangkaan sama sekali."')[0].speaker is None


def test_istilah_pendek_dalam_petik_bukan_kutipan_dan_duplikat_dibuang():
    assert extract_quotes('Program "makan gratis" dimulai besok.') == []
    twice = '"Stok aman sampai akhir bulan" dan lagi "Stok aman sampai akhir bulan".'
    assert len(extract_quotes(twice)) == 1
    assert extract_quotes("teks tanpa tanda petik") == []


# ------------------------------------------------------------------- aktor ----


def test_ringkasan_aktor_menghitung_sebutan_dan_nada():
    out = actors.summarize(
        [
            ("bahlil harus tanggung jawab", -0.6),
            ("pak koster dan bahlil sama saja", -0.4),
            ("gubernur diam saja", None),
            ("antrean panjang sekali", -0.5),
        ]
    )
    assert out.n_total == 4
    assert out.n_with_actor == 2
    by = {t.key: t for t in out.actors}
    assert by["bahlil"].n == 2 and by["bahlil"].mean == -0.5
    assert by["koster"].n == 1 and by["koster"].scored == 1
    assert out.actors[0].key == "bahlil"
    levels = {t.key: t for t in out.levels}
    assert levels["Pemerintah pusat"].n == 2
    # "gubernur" (kata jabatan umum) menambah tingkat, bukan aktor bernama.
    assert levels["Pemerintah daerah"].n == 2
    assert levels["Pemerintah daerah"].scored == 1


def test_ringkasan_kosong():
    out = actors.summarize([])
    assert out.n_total == 0 and out.actors == [] and out.levels == []


# ---------------------------------------------------------------- endpoint ----

asyncio_mark = pytest.mark.asyncio(loop_scope="session")


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
    slug = f"akr-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Aktor",
            "org_slug": slug,
            "full_name": "Penguji Aktor",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Aktor"}, headers=headers)
    assert proj.status_code == 201, proj.text
    return headers, proj.json()["id"]


async def _ingest(client, headers, pid, texts, source="SOCIAL") -> None:
    when = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    items = [
        {
            "external_id": f"https://contoh.test/{uuid.uuid4().hex}",
            "text": t,
            "published_at": when,
        }
        for t in texts
    ]
    r = await client.post(
        f"/v1/projects/{pid}/signals/ingest",
        json={"items": items, "source": source},
        headers=headers,
    )
    assert r.status_code == 200, r.text


@asyncio_mark
class TestAktorEndpoint:
    async def test_aktor_per_sumber_dan_kutipan_hanya_dari_liputan(self, client) -> None:
        headers, pid = await _new_project(client)
        await _ingest(
            client,
            headers,
            pid,
            [f"bahlil mengecewakan sekali, buruk nomor {i}" for i in range(31)]
            + ['kata orang "stok aman sampai akhir bulan" tapi antre terus'],
        )
        await _ingest(
            client,
            headers,
            pid,
            ['"Stok BBM di Bali aman untuk 20 hari," kata Menteri ESDM Bahlil Lahadalia.'],
            source="MEDIA",
        )
        r = await client.get(f"/v1/projects/{pid}/signals/actors", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        by = {s["source"]: s for s in body["by_source"]}
        social, media = by["SOCIAL"], by["MEDIA"]

        assert social["n_total"] == 32 and social["n_with_actor"] == 31
        bahlil = social["actors"][0]
        assert bahlil["key"] == "bahlil" and bahlil["n"] == 31
        assert bahlil["role"].startswith("Menteri ESDM")
        assert bahlil["sentiment"] is not None and bahlil["sentiment"] < 0
        # Tanda petik di komentar bukan kutipan berita.
        assert social["quotes"] == [] and social["quotes_total"] == 0

        assert media["actors"][0]["n"] == 1
        # Satu liputan: jumlah ditampilkan, nada ditahan.
        assert media["actors"][0]["sentiment"] is None
        assert media["quotes_total"] == 1
        quote = media["quotes"][0]
        assert quote["speaker"] == "Menteri ESDM Bahlil Lahadalia"
        assert quote["source_url"].startswith("https://contoh.test/")
        assert body["limitations"]

    async def test_org_lain_tidak_melihat(self, client) -> None:
        headers_a, pid_a = await _new_project(client)
        headers_b, _ = await _new_project(client)
        await _ingest(client, headers_a, pid_a, ["bahlil dan koster harus jelaskan"])
        r = await client.get(f"/v1/projects/{pid_a}/signals/actors", headers=headers_b)
        assert r.status_code == 200
        assert r.json()["by_source"] == [], "RLS bocor: org lain melihat peta aktor"
