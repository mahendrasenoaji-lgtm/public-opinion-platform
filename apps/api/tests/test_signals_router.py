"""Tes end-to-end endpoint signals + topics.

Pola sama dengan test_dashboard_reads.py: httpx.AsyncClient asli terhadap
Postgres nyata dengan role pop_app (RLS aktif, BUKAN superuser — superuser
mengabaikan RLS dan akan membuat tes isolasi lulus palsu).

Berbeda dari endpoint dashboard yang read-only, di sini ada jalur tulis
sungguhan lewat API (POST /signals/ingest), jadi datanya masuk lewat pintu
yang sama dengan yang dipakai pengguna — bukan di-INSERT lewat SQL langsung.
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


async def _new_project(client) -> tuple[dict[str, str], str]:
    """Daftar org+user baru lalu buat proyek. Return (headers, project_id)."""
    slug = f"sig-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Sinyal",
            "org_slug": slug,
            "full_name": "Penguji Sinyal",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    proj = await client.post("/v1/projects", json={"name": "Proyek Sinyal"}, headers=headers)
    assert proj.status_code == 201, proj.text
    return headers, proj.json()["id"]


def _item(i: int, text: str, *, author: str | None = None, days_ago: int = 1) -> dict:
    return {
        "external_id": f"ext-{uuid.uuid4().hex[:8]}-{i}",
        "text": text,
        "published_at": (datetime.now(UTC) - timedelta(days=days_ago)).isoformat(),
        "author_handle": author,
        "engagement": i,
    }


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


class TestKonektor:
    async def test_daftar_konektor_tersedia(self, client) -> None:
        headers, _ = await _new_project(client)
        r = await client.get("/v1/signals/connectors", headers=headers)
        assert r.status_code == 200, r.text
        keys = {c["key"] for c in r.json()}
        assert {"rss", "youtube_api", "x_api", "manual"} <= keys

    async def test_status_kredensial_dilaporkan_bukan_nilainya(self, client) -> None:
        headers, _ = await _new_project(client)
        listed = (await client.get("/v1/signals/connectors", headers=headers)).json()
        by_key = {c["key"]: c for c in listed}

        # rss tidak butuh kunci, jadi selalu terhitung terkonfigurasi
        assert by_key["rss"]["requires_credential"] is None
        assert by_key["rss"]["credential_configured"] is True

        # youtube butuh kunci; di lingkungan tes kunci itu tidak diset
        yt = by_key["youtube_api"]
        assert yt["requires_credential"] == "YOUTUBE_API_KEY"
        assert yt["credential_configured"] is False

        # yang dilaporkan hanya NAMA env var dan ada/tidaknya — nilai kunci
        # tidak boleh pernah ikut di payload mana pun
        assert "credential_value" not in yt
        assert set(yt) == {
            "key", "label", "source", "requires_credential",
            "credential_configured", "config_fields", "notes",
        }

    async def test_butuh_autentikasi(self, client) -> None:
        assert (await client.get("/v1/signals/connectors")).status_code == 401


class TestSumberData:
    async def test_buat_dan_daftar_sumber(self, client) -> None:
        headers, pid = await _new_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/signals/sources",
            json={"connector": "rss", "config": {"feed_url": "https://contoh.id/feed"}},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["source"] == "MEDIA"

        listed = await client.get(f"/v1/projects/{pid}/signals/sources", headers=headers)
        assert len(listed.json()) == 1

    async def test_konektor_asing_ditolak_saat_dibuat_bukan_saat_ditarik(
        self, client
    ) -> None:
        headers, pid = await _new_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/signals/sources",
            json={"connector": "tiktok_scrape", "config": {}},
            headers=headers,
        )
        assert r.status_code == 422
        assert "tidak dikenal" in r.json()["detail"]

    async def test_config_kurang_ditolak_dengan_nama_fieldnya(self, client) -> None:
        headers, pid = await _new_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/signals/sources",
            json={"connector": "rss", "config": {}},
            headers=headers,
        )
        assert r.status_code == 422
        assert "feed_url" in r.json()["detail"]

    async def test_hapus_sumber(self, client) -> None:
        headers, pid = await _new_project(client)
        created = await client.post(
            f"/v1/projects/{pid}/signals/sources",
            json={"connector": "rss", "config": {"feed_url": "https://contoh.id/feed"}},
            headers=headers,
        )
        sid = created.json()["id"]
        assert (
            await client.delete(f"/v1/projects/{pid}/signals/sources/{sid}", headers=headers)
        ).status_code == 204
        sisa = await client.get(f"/v1/projects/{pid}/signals/sources", headers=headers)
        assert sisa.json() == []

    async def test_tarik_tanpa_kredensial_membalas_503_yang_menyebut_env_var(
        self, client
    ) -> None:
        headers, pid = await _new_project(client)
        created = await client.post(
            f"/v1/projects/{pid}/signals/sources",
            json={"connector": "youtube_api", "config": {"video_id": "abc123"}},
            headers=headers,
        )
        sid = created.json()["id"]
        r = await client.post(
            f"/v1/projects/{pid}/signals/sources/{sid}/collect", headers=headers
        )
        assert r.status_code == 503, r.text
        assert "YOUTUBE_API_KEY" in r.json()["detail"]


class TestIngest:
    async def test_ingest_menyimpan_dan_melaporkan(self, client) -> None:
        headers, pid = await _new_project(client)
        items = [_item(i, t) for i, t in enumerate(_korpus_dua_tema())]
        r = await client.post(
            f"/v1/projects/{pid}/signals/ingest",
            json={"items": items},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["received"] == 24
        assert body["stored"] == 24

    async def test_duplikat_dalam_batch_tidak_dihitung_dua_kali(self, client) -> None:
        headers, pid = await _new_project(client)
        teks = "harga beras di pasar naik lagi minggu ini dan warga mengeluh"
        items = [_item(0, teks), _item(1, teks + "!"), _item(2, "jalan rusak parah sekali")]
        r = await client.post(
            f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
        )
        body = r.json()
        assert body["duplicates_dropped"] == 1
        assert body["stored"] == 2

    async def test_ingest_ulang_id_sama_tidak_menggandakan_volume(self, client) -> None:
        """Menarik ulang rentang waktu yang sama adalah operasi normal."""
        headers, pid = await _new_project(client)
        items = [_item(i, t) for i, t in enumerate(_korpus_dua_tema())]
        first = await client.post(
            f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
        )
        second = await client.post(
            f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
        )
        assert first.json()["stored"] == 24
        assert second.json()["stored"] == 0
        assert second.json()["already_present"] == 24

    async def test_handle_penulis_tidak_pernah_tersimpan_apa_adanya(self, client) -> None:
        """CLAUDE.md §3: identitas tidak disimpan bersama isinya."""
        headers, pid = await _new_project(client)
        await client.post(
            f"/v1/projects/{pid}/signals/ingest",
            json={"items": [_item(0, "harga beras naik sekali", author="@budi_asli")]},
            headers=headers,
        )
        from sqlalchemy import text as sql_text

        from app.db import SessionLocal

        async with SessionLocal() as s, s.begin():
            await s.execute(
                sql_text("SELECT set_config('app.current_org', :o, true)"),
                {"o": _org_of(headers)},
            )
            rows = (
                await s.execute(
                    sql_text("SELECT author_hash FROM mentions WHERE project_id = :p"),
                    {"p": pid},
                )
            ).all()
        assert rows and rows[0][0] is not None
        assert "budi" not in rows[0][0]

    async def test_penyaringan_bahasa_membuang_yang_jelas_bahasa_lain(
        self, client
    ) -> None:
        headers, pid = await _new_project(client)
        items = [
            _item(0, "saya rasa kebijakan ini tidak adil untuk warga yang sudah menunggu"),
            _item(1, "this is the kind of policy that will not work for the people here"),
        ]
        r = await client.post(
            f"/v1/projects/{pid}/signals/ingest",
            json={"items": items, "accept_langs": ["id"]},
            headers=headers,
        )
        assert r.json()["language_rejected"] == 1
        assert r.json()["stored"] == 1

    async def test_batch_kosong_ditolak_validasi(self, client) -> None:
        headers, pid = await _new_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/signals/ingest", json={"items": []}, headers=headers
        )
        assert r.status_code == 422


class TestAgregasi:
    async def test_ringkasan_menahan_sentimen_di_bawah_ambang(self, client) -> None:
        """Angka dari 5 komentar bukan pengukuran."""
        headers, pid = await _new_project(client)
        await client.post(
            f"/v1/projects/{pid}/signals/ingest",
            json={
                "items": [
                    _item(i, f"program bantuan ini bagus sekali nomor {i}") for i in range(5)
                ]
            },
            headers=headers,
        )
        r = await client.get(f"/v1/projects/{pid}/signals/summary", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["sentiment"]["value"] is None
        assert body["sentiment"]["insufficient_data"] is True
        # volume tetap dilaporkan: itu hitungan, bukan estimasi
        assert body["volume"]["value"] == 5

    async def test_ringkasan_menerbitkan_sentimen_di_atas_ambang(self, client) -> None:
        headers, pid = await _new_project(client)
        items = [
            _item(i, f"pelayanan program ini sangat bagus dan membantu warga nomor {i}")
            for i in range(35)
        ]
        await client.post(
            f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
        )
        body = (await client.get(f"/v1/projects/{pid}/signals/summary", headers=headers)).json()
        assert body["sentiment"]["value"] is not None
        assert body["sentiment"]["value"] > 0

    async def test_ringkasan_selalu_membawa_batasan_sumber(self, client) -> None:
        """R1: sentimen sosial tidak boleh tampil tanpa peringatan self-selected."""
        headers, pid = await _new_project(client)
        await client.post(
            f"/v1/projects/{pid}/signals/ingest",
            json={"items": [_item(0, "programnya bagus")]},
            headers=headers,
        )
        body = (await client.get(f"/v1/projects/{pid}/signals/summary", headers=headers)).json()
        assert any("self-selected" in x for x in body["limitations"])

    async def test_proyek_kosong_tidak_jatuh(self, client) -> None:
        headers, pid = await _new_project(client)
        r = await client.get(f"/v1/projects/{pid}/signals/summary", headers=headers)
        assert r.status_code == 200
        assert r.json()["volume"]["value"] == 0

    async def test_tren_harian(self, client) -> None:
        headers, pid = await _new_project(client)
        items = [_item(i, f"harga beras naik terus nomor {i}", days_ago=1) for i in range(3)]
        items += [_item(10 + i, f"jalan rusak parah nomor {i}", days_ago=3) for i in range(2)]
        await client.post(
            f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
        )
        r = await client.get(f"/v1/projects/{pid}/signals/trend", headers=headers)
        assert r.status_code == 200
        points = r.json()
        assert len(points) == 2
        assert sum(p["volume"] for p in points) == 5


class TestMutuSentimen:
    async def test_akurasi_dilaporkan_untuk_ui(self, client) -> None:
        """Syarat roadmap Phase 2: akurasi wajib bisa ditampilkan di UI."""
        headers, pid = await _new_project(client)
        r = await client.get(
            f"/v1/projects/{pid}/signals/sentiment-quality", headers=headers
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["n"] > 0
        assert 0 <= body["macro_f1"] <= 1
        assert "bukan sampel acak" in body["caveat"]


class TestTopics:
    async def test_penemuan_tema_dari_data_asli(self, client) -> None:
        headers, pid = await _new_project(client)
        items = [_item(i, t) for i, t in enumerate(_korpus_dua_tema())]
        await client.post(
            f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
        )
        r = await client.post(f"/v1/projects/{pid}/topics/discover", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["topics"]) >= 2
        assert "TF-IDF" in body["method"]
        assert body["n_analysed"] == 24

    async def test_tema_tersimpan_dan_bisa_dibaca_ulang(self, client) -> None:
        headers, pid = await _new_project(client)
        items = [_item(i, t) for i, t in enumerate(_korpus_dua_tema())]
        await client.post(
            f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
        )
        await client.post(f"/v1/projects/{pid}/topics/discover", headers=headers)
        r = await client.get(f"/v1/projects/{pid}/topics", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) >= 2

    async def test_penjalanan_ulang_mengganti_bukan_menggandakan(self, client) -> None:
        headers, pid = await _new_project(client)
        items = [_item(i, t) for i, t in enumerate(_korpus_dua_tema())]
        await client.post(
            f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
        )
        first = await client.post(f"/v1/projects/{pid}/topics/discover", headers=headers)
        second = await client.post(f"/v1/projects/{pid}/topics/discover", headers=headers)
        listed = await client.get(f"/v1/projects/{pid}/topics", headers=headers)
        assert len(first.json()["topics"]) == len(second.json()["topics"])
        assert len(listed.json()) == len(second.json()["topics"])

    async def test_data_kurang_menolak_bukan_mengarang_tema(self, client) -> None:
        headers, pid = await _new_project(client)
        await client.post(
            f"/v1/projects/{pid}/signals/ingest",
            json={"items": [_item(i, f"harga naik nomor {i}") for i in range(5)]},
            headers=headers,
        )
        r = await client.post(f"/v1/projects/{pid}/topics/discover", headers=headers)
        assert r.json()["insufficient_data"] is True
        assert r.json()["topics"] == []

    async def test_proyek_tanpa_tema_mengembalikan_daftar_kosong(self, client) -> None:
        headers, pid = await _new_project(client)
        assert (await client.get(f"/v1/projects/{pid}/topics", headers=headers)).json() == []


class TestIsolasiTenant:
    """Setiap endpoint bertenant wajib punya tes isolasi (CLAUDE.md §6)."""

    async def test_sinyal_org_lain_tidak_terlihat(self, client) -> None:
        headers_a, pid_a = await _new_project(client)
        headers_b, _ = await _new_project(client)

        await client.post(
            f"/v1/projects/{pid_a}/signals/ingest",
            json={"items": [_item(i, f"harga beras naik nomor {i}") for i in range(35)]},
            headers=headers_a,
        )

        # Org B menembak project_id milik org A secara langsung.
        r = await client.get(f"/v1/projects/{pid_a}/signals/summary", headers=headers_b)
        assert r.status_code == 200
        assert r.json()["volume"]["value"] == 0, "RLS bocor: org lain melihat volume"

    async def test_sumber_data_org_lain_tidak_terlihat(self, client) -> None:
        headers_a, pid_a = await _new_project(client)
        headers_b, _ = await _new_project(client)
        await client.post(
            f"/v1/projects/{pid_a}/signals/sources",
            json={"connector": "rss", "config": {"feed_url": "https://contoh.id/feed"}},
            headers=headers_a,
        )
        r = await client.get(f"/v1/projects/{pid_a}/signals/sources", headers=headers_b)
        assert r.json() == []

    async def test_tema_org_lain_tidak_terlihat(self, client) -> None:
        headers_a, pid_a = await _new_project(client)
        headers_b, _ = await _new_project(client)
        await client.post(
            f"/v1/projects/{pid_a}/signals/ingest",
            json={"items": [_item(i, t) for i, t in enumerate(_korpus_dua_tema())]},
            headers=headers_a,
        )
        await client.post(f"/v1/projects/{pid_a}/topics/discover", headers=headers_a)
        assert (await client.get(f"/v1/projects/{pid_a}/topics", headers=headers_b)).json() == []


def _org_of(headers: dict[str, str]) -> str:
    """Baca org_id dari token tanpa verifikasi — cuma untuk keperluan tes."""
    import jwt

    token = headers["Authorization"].removeprefix("Bearer ")
    return str(jwt.decode(token, options={"verify_signature": False})["org"])
