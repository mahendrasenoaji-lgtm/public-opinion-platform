"""Tes end-to-end pengodean isi, arus informasi, keselarasan, C4, dan O8
terhadap Postgres dengan RLS aktif."""

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


async def _org_with_project(client) -> tuple[dict[str, str], str]:
    slug = f"test-koding-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Koding",
            "org_slug": slug,
            "full_name": "Penguji Koding",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Koding"}, headers=headers)
    assert proj.status_code == 201, proj.text
    return headers, proj.json()["id"]


async def _upload_posts(client, headers, pid, n: int, **extra) -> list[str]:
    """Unggah n unggahan akun resmi; kembalikan id-nya (terbaru dulu)."""
    base = f"/v1/projects/{pid}/comm-performance"
    items = [
        {
            "platform": "youtube",
            "account": "@lembaga_contoh",
            "external_id": f"vid-{i:03d}",
            "posted_at": f"2026-10-{1 + i % 28:02d}T03:00:00Z",
            "caption": f"Pengumuman nomor {i}",
            "comments": 5,
            **extra,
        }
        for i in range(n)
    ]
    r = await client.post(f"{base}/posts", json={"items": items}, headers=headers)
    assert r.status_code == 200, r.text
    listed = await client.get(f"{base}/coding", params={"limit": 100}, headers=headers)
    assert listed.status_code == 200, listed.text
    return [row["post_id"] for row in listed.json()["items"]]


class TestPengodean:
    async def test_simpan_baca_dan_lembar_terpisah(self, client) -> None:
        headers, pid = await _org_with_project(client)
        base = f"/v1/projects/{pid}/comm-performance"
        post_id = (await _upload_posts(client, headers, pid, 3))[0]

        r = await client.put(
            f"{base}/coding/{post_id}",
            json={"coder": 1, "coder_name": "Pengode A", "codes": {"A9": 3, "A14": 4, "A12": None}},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["codes"] == {"A9": 3, "A14": 4}
        assert r.json()["coded_by_other"] is False

        one = (await client.get(f"{base}/coding", params={"coder": 1}, headers=headers)).json()
        assert one["total"] == 3 and one["n_coded"] == 1
        assert {v["code"] for v in one["variables"]} >= {"A9", "A11", "A17"}
        assert one["accounts"] == ["@lembaga_contoh"]

        # Lembar 2 melihat unggahan yang sama sebagai belum dikode, tanpa nilai lembar 1.
        two = (await client.get(f"{base}/coding", params={"coder": 2}, headers=headers)).json()
        row = next(x for x in two["items"] if x["post_id"] == post_id)
        assert row["coded"] is False and row["codes"] == {} and row["coded_by_other"] is True

        uncoded = (
            await client.get(
                f"{base}/coding", params={"coder": 1, "only_uncoded": True}, headers=headers
            )
        ).json()
        assert post_id not in [x["post_id"] for x in uncoded["items"]]

    async def test_menyimpan_ulang_menimpa(self, client) -> None:
        headers, pid = await _org_with_project(client)
        base = f"/v1/projects/{pid}/comm-performance"
        post_id = (await _upload_posts(client, headers, pid, 1))[0]
        for value in (1, 5):
            r = await client.put(
                f"{base}/coding/{post_id}", json={"coder": 1, "codes": {"A9": value}},
                headers=headers,
            )
            assert r.status_code == 200, r.text
        got = (await client.get(f"{base}/coding", headers=headers)).json()
        assert got["n_coded"] == 1 and got["items"][0]["codes"] == {"A9": 5}

    async def test_nilai_tidak_sah_dan_lembar_ketiga_ditolak(self, client) -> None:
        headers, pid = await _org_with_project(client)
        base = f"/v1/projects/{pid}/comm-performance"
        post_id = (await _upload_posts(client, headers, pid, 1))[0]
        bad = await client.put(
            f"{base}/coding/{post_id}", json={"coder": 1, "codes": {"A9": 9}}, headers=headers
        )
        assert bad.status_code == 422 and "tidak sah" in bad.text
        third = await client.put(
            f"{base}/coding/{post_id}", json={"coder": 3, "codes": {"A9": 1}}, headers=headers
        )
        assert third.status_code == 422
        missing = await client.put(
            f"{base}/coding/{uuid.uuid4()}", json={"coder": 1, "codes": {"A9": 1}}, headers=headers
        )
        assert missing.status_code == 404

    async def test_reliabilitas_ditahan_lalu_terbit(self, client) -> None:
        headers, pid = await _org_with_project(client)
        base = f"/v1/projects/{pid}/comm-performance"
        ids = await _upload_posts(client, headers, pid, 24)

        async def code(post_id: str, coder: int, a9: int, a12: int) -> None:
            r = await client.put(
                f"{base}/coding/{post_id}",
                json={"coder": coder, "codes": {"A9": a9, "A12": a12}},
                headers=headers,
            )
            assert r.status_code == 200, r.text

        for i, post_id in enumerate(ids[:10]):
            await code(post_id, 1, 1 + i % 3, i % 2)
            await code(post_id, 2, 1 + i % 3, i % 2)
        early = (await client.get(f"{base}/coding/reliability", headers=headers)).json()
        a9 = next(v for v in early["variables"] if v["code"] == "A9")
        assert early["n_double_coded"] == 10 and a9["alpha"] is None
        assert "data tidak cukup" in a9["label"]
        # Belum diuji: sebaran tetap tampil, ditandai belum teruji.
        d9 = next(d for d in early["distributions"] if d["code"] == "A9")
        assert d9["tested"] is False and d9["published"] is True and d9["n"] == 10

        # A9 sepakat penuh; A12 selalu berlawanan.
        for i, post_id in enumerate(ids[10:], start=10):
            await code(post_id, 1, 1 + i % 3, i % 2)
            await code(post_id, 2, 1 + i % 3, 1 - i % 2)
        late = (await client.get(f"{base}/coding/reliability", headers=headers)).json()
        assert late["n_posts"] == 24 and late["n_double_coded"] == 24
        assert late["meets_target"] is True
        a9 = next(v for v in late["variables"] if v["code"] == "A9")
        a12 = next(v for v in late["variables"] if v["code"] == "A12")
        assert a9["alpha"] == 1.0 and a9["label"] == "dapat diandalkan"
        assert a12["alpha"] < 0.667 and a12["label"] == "kategori perlu diperbaiki"
        d12 = next(d for d in late["distributions"] if d["code"] == "A12")
        assert d12["published"] is False and d12["counts"] == []
        d9 = next(d for d in late["distributions"] if d["code"] == "A9")
        # Satu kode per unggahan: 24, bukan 48.
        assert d9["published"] is True and d9["n"] == 24
        assert late["limitations"]


class TestArus:
    record = {
        "subject": "Kemenko Contoh",
        "label": "Klarifikasi isu A",
        "kind": "klarifikasi",
        "requested_at": "2026-10-01T01:00:00Z",
        "received_at": "2026-10-01T07:00:00Z",
        "approved_at": "2026-10-02T03:00:00Z",
        "published_at": "2026-10-02T04:30:00Z",
        "bottleneck_stage": 6,
    }

    async def test_catat_ringkas_hapus(self, client) -> None:
        headers, pid = await _org_with_project(client)
        base = f"/v1/projects/{pid}/comm-performance"
        first = await client.post(f"{base}/flow", json=self.record, headers=headers)
        assert first.status_code == 201, first.text
        assert first.json()["hours"] == {"T1": 6.0, "T2": None, "T3": None, "T4": 1.5}

        few = (await client.get(f"{base}/flow", headers=headers)).json()
        t1 = next(i for i in few["intervals"] if i["code"] == "T1")
        assert few["n_records"] == 1 and t1["n"] == 1 and t1["median_hours"] is None

        for i in range(4):
            r = await client.post(
                f"{base}/flow", json={**self.record, "label": f"Konten {i}"}, headers=headers
            )
            assert r.status_code == 201, r.text
        full = (await client.get(f"{base}/flow", headers=headers)).json()
        by = {i["code"]: i for i in full["intervals"]}
        assert by["T1"]["median_hours"] == 6.0 and by["T4"]["median_hours"] == 1.5
        assert by["T2"]["median_hours"] is None and full["slowest"] == "T1"
        stage6 = next(s for s in full["stages"] if s["stage"] == 6)
        assert stage6["n_bottleneck"] == 5 and len(full["stages"]) == 11
        assert full["subjects"] == ["Kemenko Contoh"]

        other = (
            await client.get(f"{base}/flow", params={"subject": "Lembaga lain"}, headers=headers)
        ).json()
        assert other["n_records"] == 0 and other["subjects"] == ["Kemenko Contoh"]

        gone = await client.delete(f"{base}/flow/{first.json()['id']}", headers=headers)
        assert gone.status_code == 204
        assert (await client.get(f"{base}/flow", headers=headers)).json()["n_records"] == 4

    async def test_cap_waktu_mundur_ditolak(self, client) -> None:
        headers, pid = await _org_with_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/comm-performance/flow",
            json={**self.record, "received_at": "2026-09-30T00:00:00Z"},
            headers=headers,
        )
        assert r.status_code == 422 and "lebih awal" in r.text

    async def test_tanpa_cap_waktu_ditolak(self, client) -> None:
        headers, pid = await _org_with_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/comm-performance/flow",
            json={"subject": "X", "label": "Y", "kind": "rutin"},
            headers=headers,
        )
        assert r.status_code == 422


class TestKeselarasan:
    @staticmethod
    def _pair(i: int, coder: int = 1, code: str = "selaras", **extra) -> dict:
        return {
            "issue": f"Isu {i}",
            "subject_a": "Kemenko Contoh",
            "subject_b": "Kementerian Teknis",
            "url_a": "https://contoh.go.id/a",
            "coder": coder,
            "code": code,
            **extra,
        }

    async def test_saran_skor_mengikuti_rubrik(self, client) -> None:
        headers, pid = await _org_with_project(client)
        url = f"/v1/projects/{pid}/comm-performance/alignment"
        for i in range(4):
            assert (await client.put(url, json=self._pair(i), headers=headers)).status_code == 200
        few = (await client.get(url, headers=headers)).json()
        assert few["n_pairs"] == 4 and few["suggested_score"] is None

        await client.put(url, json=self._pair(4), headers=headers)
        assert (await client.get(url, headers=headers)).json()["suggested_score"] == 5

        # Lembar 2 pada pasangan yang sama tidak menambah jumlah pasangan.
        await client.put(url, json=self._pair(4, coder=2, code="beda_penekanan"), headers=headers)
        both = (await client.get(url, headers=headers)).json()
        assert both["n_pairs"] == 5 and both["suggested_score"] == 5
        assert both["n_double_coded"] == 1 and both["alpha"] is None

        await client.put(url, json=self._pair(5, code="bertentangan"), headers=headers)
        assert (await client.get(url, headers=headers)).json()["suggested_score"] == 1
        # Menyimpan ulang pasangan yang sama menimpa: kini sudah diralat.
        fixed = await client.put(
            url, json=self._pair(5, code="bertentangan", corrected=True), headers=headers
        )
        after = (await client.get(url, headers=headers)).json()
        assert after["n_pairs"] == 6 and after["suggested_score"] == 3
        assert after["n_contradiction_open"] == 0

        assert (
            await client.delete(f"{url}/{fixed.json()['id']}", headers=headers)
        ).status_code == 204
        assert (await client.get(url, headers=headers)).json()["suggested_score"] == 5

    async def test_lembaga_sama_dan_tautan_bukan_http_ditolak(self, client) -> None:
        headers, pid = await _org_with_project(client)
        url = f"/v1/projects/{pid}/comm-performance/alignment"
        same = await client.put(
            url, json=self._pair(1, subject_b="kemenko contoh"), headers=headers
        )
        assert same.status_code == 422
        js = await client.put(url, json=self._pair(1, url_a="javascript:alert(1)"), headers=headers)
        assert js.status_code == 422


class TestWaktuTanggap:
    async def test_lonjakan_dan_unggahan_resmi(self, client) -> None:
        headers, pid = await _org_with_project(client)
        base = f"/v1/projects/{pid}/comm-performance"
        today = datetime.now(UTC).replace(hour=5, minute=0, second=0, microsecond=0)
        volumes = {8: 3, 7: 3, 6: 3, 5: 12, 4: 3}
        items = [
            {
                "external_id": f"m-{days_ago}-{i}",
                "text": f"percakapan warga nomor {i} hari {days_ago} tentang layanan publik",
                "published_at": (today - timedelta(days=days_ago)).isoformat(),
            }
            for days_ago, n in volumes.items()
            for i in range(n)
        ]
        r = await client.post(
            f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
        )
        assert r.status_code == 200, r.text

        none_yet = await client.get(
            f"{base}/response-time", params={"account": "@lembaga_contoh"}, headers=headers
        )
        assert none_yet.status_code == 200, none_yet.text
        body = none_yet.json()
        assert len(body["spikes"]) == 1 and body["spikes"][0]["volume"] == 12
        assert body["spikes"][0]["hours"] is None and body["suggested_score"] == 1

        # Unggahan resmi 05.00 UTC pada hari lonjakan = 12.00 WIB = 12 jam dari 00.00 WIB.
        spike_day = today - timedelta(days=5)
        posted = await client.post(
            f"{base}/posts",
            json={
                "items": [
                    {
                        "platform": "youtube",
                        "account": "@lembaga_contoh",
                        "external_id": "klarifikasi-1",
                        "posted_at": spike_day.isoformat(),
                        "caption": "Klarifikasi layanan",
                    }
                ]
            },
            headers=headers,
        )
        assert posted.status_code == 200, posted.text
        got = (
            await client.get(
                f"{base}/response-time", params={"account": "@lembaga_contoh"}, headers=headers
            )
        ).json()
        assert got["spikes"][0]["hours"] == 12.0
        assert got["median_hours"] == 12.0 and got["suggested_score"] == 4
        assert got["indicator"] == "C4" and got["limitations"]

        # Kata kunci yang tidak ada di takarir: unggahan itu tidak dihitung.
        filtered = (
            await client.get(
                f"{base}/response-time",
                params={"account": "@lembaga_contoh", "keyword": "banjir"},
                headers=headers,
            )
        ).json()
        assert filtered["spikes"][0]["hours"] is None

        # Akun lain tidak ikut.
        other = (
            await client.get(
                f"{base}/response-time", params={"account": "@akun_lain"}, headers=headers
            )
        ).json()
        assert other["n_official_posts"] == 0

    async def test_tanpa_data_tidak_ada_saran(self, client) -> None:
        headers, pid = await _org_with_project(client)
        r = await client.get(
            f"/v1/projects/{pid}/comm-performance/response-time",
            params={"account": "@x"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["suggested_score"] is None and r.json()["spikes"] == []


class TestTingkatJawab:
    async def test_dihitung_tanpa_menyimpan_teks(self, client, monkeypatch) -> None:
        from app.connectors import youtube_channel as ytc

        headers, pid = await _org_with_project(client)
        base = f"/v1/projects/{pid}/comm-performance"
        await _upload_posts(client, headers, pid, 3)
        seen: list[list[str]] = []

        async def fake(video_ids: list[str]) -> ytc.ThreadFetch:
            seen.append(video_ids)
            threads = (
                [ytc.Thread("kapan dibuka?", True, False)] * 10
                + [ytc.Thread("apa syaratnya", False, False)] * 13
                + [ytc.Thread("bagaimana daftarnya", False, True)] * 2
                + [ytc.Thread("mantap", True, False)] * 40
            )
            return ytc.ThreadFetch(
                threads=threads, n_videos=3, n_videos_skipped=0, quota_units=3
            )

        monkeypatch.setattr(ytc, "fetch_threads", fake)
        r = await client.post(
            f"{base}/youtube-response-rate", json={"account": "@lembaga_contoh"}, headers=headers
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(seen[0]) == 3
        assert (body["n_comments"], body["n_questions"], body["n_answered"]) == (65, 25, 10)
        assert body["rate_pct"] == 40.0 and body["suggested_score"] == 4
        assert body["n_uncertain"] == 2 and "2 pertanyaan" in body["limitations"][0]
        # Tidak ada teks komentar di respons.
        assert "kapan dibuka" not in r.text and "syaratnya" not in r.text

    async def test_akun_tanpa_video_404(self, client) -> None:
        headers, pid = await _org_with_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/comm-performance/youtube-response-rate",
            json={"account": "@tidak_ada"},
            headers=headers,
        )
        assert r.status_code == 404


class TestIsolasiTenant:
    async def test_org_lain_tidak_melihat_dan_tidak_bisa_menulis(self, client) -> None:
        headers_a, pid_a = await _org_with_project(client)
        headers_b, _pid_b = await _org_with_project(client)
        base_a = f"/v1/projects/{pid_a}/comm-performance"
        post_id = (await _upload_posts(client, headers_a, pid_a, 1))[0]
        await client.put(
            f"{base_a}/coding/{post_id}", json={"coder": 1, "codes": {"A9": 1}}, headers=headers_a
        )
        flow = await client.post(f"{base_a}/flow", json=TestArus.record, headers=headers_a)
        pair = await client.put(
            f"{base_a}/alignment", json=TestKeselarasan._pair(1), headers=headers_a
        )

        for path in ("coding", "coding/reliability", "flow", "alignment"):
            assert (await client.get(f"{base_a}/{path}", headers=headers_b)).status_code == 404
        assert (
            await client.get(
                f"{base_a}/response-time", params={"account": "@x"}, headers=headers_b
            )
        ).status_code == 404
        writes = [
            client.put(
                f"{base_a}/coding/{post_id}", json={"coder": 2, "codes": {"A9": 2}},
                headers=headers_b,
            ),
            client.post(f"{base_a}/flow", json=TestArus.record, headers=headers_b),
            client.put(f"{base_a}/alignment", json=TestKeselarasan._pair(2), headers=headers_b),
            client.delete(f"{base_a}/flow/{flow.json()['id']}", headers=headers_b),
            client.delete(f"{base_a}/alignment/{pair.json()['id']}", headers=headers_b),
            client.post(
                f"{base_a}/youtube-response-rate", json={"account": "@lembaga_contoh"},
                headers=headers_b,
            ),
        ]
        for call in writes:
            assert (await call).status_code == 404

        # Milik A utuh.
        assert (await client.get(f"{base_a}/flow", headers=headers_a)).json()["n_records"] == 1
        assert (await client.get(f"{base_a}/alignment", headers=headers_a)).json()["n_pairs"] == 1
        assert (await client.get(f"{base_a}/coding", headers=headers_a)).json()["n_coded"] == 1
