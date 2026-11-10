"""Tes koreksi sentimen manual: fungsi murni + endpoint."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.services import rescoring as rs
from app.services import sentiment as sentiment_svc

DSN = os.getenv("TEST_DATABASE_URL_APP")

if DSN:
    os.environ["DATABASE_URL"] = DSN
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")


# ------------------------------------------------------------ fungsi murni ----


def test_label_manual_mengarsipkan_skor_mesin_sosial_sekali_saja():
    first = rs.apply_manual(
        social=True,
        label="negatif",
        sentiment=0.4,
        sentiment_model=sentiment_svc.INFORMAL_MODEL_VERSION,
        sentiment_alt=None,
        sentiment_alt_model=None,
    )
    assert first.sentiment == -0.5
    assert first.sentiment_model == rs.MANUAL_MODEL_VERSION
    assert first.sentiment_alt == 0.4
    assert first.sentiment_alt_model == sentiment_svc.INFORMAL_MODEL_VERSION
    assert first.primary_changed is True

    second = rs.apply_manual(
        social=True,
        label="positif",
        sentiment=first.sentiment,
        sentiment_model=first.sentiment_model,
        sentiment_alt=first.sentiment_alt,
        sentiment_alt_model=first.sentiment_alt_model,
    )
    assert second.sentiment == 0.5
    # Arsip tetap skor MESIN, bukan label manual sebelumnya.
    assert second.sentiment_alt == 0.4


def test_label_manual_liputan_tidak_menyentuh_skor_ragam_berita():
    out = rs.apply_manual(
        social=False,
        label="netral",
        sentiment=0.6,
        sentiment_model=sentiment_svc.MODEL_VERSION,
        sentiment_alt=0.0,
        sentiment_alt_model=sentiment_svc.NEWS_MODEL_VERSION,
    )
    assert out.sentiment == 0.0 and out.sentiment_model == rs.MANUAL_MODEL_VERSION
    assert out.sentiment_alt == 0.0
    assert out.sentiment_alt_model == sentiment_svc.NEWS_MODEL_VERSION


def test_label_sama_dua_kali_tidak_dihitung_berubah_dan_label_asing_ditolak():
    kw = dict(
        social=True,
        sentiment=-0.5,
        sentiment_model=rs.MANUAL_MODEL_VERSION,
        sentiment_alt=0.2,
        sentiment_alt_model="lexicon-id-1",
    )
    assert rs.apply_manual(label="negatif", **kw).primary_changed is False
    with pytest.raises(ValueError):
        rs.apply_manual(label="marah", **kw)


def test_penilaian_ulang_tidak_menimpa_label_manual():
    out = rs.rescore(
        social=True,
        text="pelayanan bagus sekali mantap",
        sentiment=-0.5,
        sentiment_model=rs.MANUAL_MODEL_VERSION,
        sentiment_alt=None,
        sentiment_alt_model=None,
    )
    assert out.sentiment == -0.5
    assert out.sentiment_model == rs.MANUAL_MODEL_VERSION
    assert out.primary_changed is False

    media = rs.rescore(
        social=False,
        text="pemerintah dukung program baru",
        sentiment=-0.5,
        sentiment_model=rs.MANUAL_MODEL_VERSION,
        sentiment_alt=None,
        sentiment_alt_model=None,
    )
    assert media.sentiment == -0.5 and media.sentiment_model == rs.MANUAL_MODEL_VERSION
    assert media.sentiment_alt_model == sentiment_svc.NEWS_MODEL_VERSION


def test_pembatalan_mengembalikan_skor_mesin_terkini():
    text = "pelayanan bagus sekali mantap"
    out = rs.revert_manual(
        social=True,
        text=text,
        sentiment=-0.5,
        sentiment_model=rs.MANUAL_MODEL_VERSION,
        sentiment_alt=0.3,
        sentiment_alt_model="lexicon-id-1",
    )
    assert out.primary_changed is True
    assert out.sentiment_model == sentiment_svc.INFORMAL_MODEL_VERSION
    assert out.sentiment == sentiment_svc.score(text, register="informal").score
    assert out.sentiment is not None and out.sentiment > 0

    untouched = rs.revert_manual(
        social=True,
        text=text,
        sentiment=0.3,
        sentiment_model=sentiment_svc.INFORMAL_MODEL_VERSION,
        sentiment_alt=None,
        sentiment_alt_model=None,
    )
    assert untouched.primary_changed is False and untouched.sentiment == 0.3


def test_mutu_koreksi_menghitung_sepakat_dan_abstain():
    stats = rs.correction_quality(
        [
            ("negatif", "negatif"),
            ("negatif", "positif"),
            ("positif", None),
            ("netral", "netral"),
            ("asing", "positif"),
        ]
    )
    assert stats.n == 4
    assert stats.machine_abstained == 1
    assert stats.agreed == 2
    assert stats.agreement == pytest.approx(2 / 3)
    assert stats.confusion["negatif"]["positif"] == 1
    assert stats.confusion["positif"]["abstain"] == 1
    assert rs.correction_quality([]).agreement is None


def test_label_mesin_none_bila_abstain():
    assert rs.machine_label(social=True, text="antrean di spbu jalan raya") is None
    assert rs.machine_label(social=True, text="pelayanan bagus sekali") == "positif"


# ---------------------------------------------------------------- endpoint ----

pytestmark_async = pytest.mark.asyncio(loop_scope="session")


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
    slug = f"kor-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Koreksi",
            "org_slug": slug,
            "full_name": "Penguji Koreksi",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Koreksi"}, headers=headers)
    assert proj.status_code == 201, proj.text
    return headers, proj.json()["id"]


async def _seed(client, headers, pid, texts: list[str]) -> list[dict]:
    when = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    items = [
        {"external_id": f"kor-{uuid.uuid4().hex[:10]}", "text": t, "published_at": when}
        for t in texts
    ]
    r = await client.post(
        f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
    )
    assert r.status_code == 200, r.text
    listed = await client.get(f"/v1/projects/{pid}/mentions?limit=200", headers=headers)
    assert listed.status_code == 200, listed.text
    return listed.json()


@pytestmark_async
class TestKoreksiManual:
    async def test_koreksi_lalu_batal(self, client) -> None:
        headers, pid = await _new_project(client)
        rows = await _seed(client, headers, pid, ["hebat sekali pak, rakyat antre berjam-jam"])
        mid = rows[0]["id"]
        assert rows[0]["sentiment_manual"] is False
        before = rows[0]["sentiment"]

        r = await client.put(
            f"/v1/projects/{pid}/mentions/{mid}/sentiment",
            json={"label": "negatif"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json() == {
            "id": mid,
            "sentiment": -0.5,
            "sentiment_manual": True,
            "changed": True,
        }
        listed = (await client.get(f"/v1/projects/{pid}/mentions", headers=headers)).json()
        assert listed[0]["sentiment"] == -0.5 and listed[0]["sentiment_manual"] is True

        r = await client.delete(f"/v1/projects/{pid}/mentions/{mid}/sentiment", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["sentiment_manual"] is False
        assert r.json()["sentiment"] == before

    async def test_penilaian_ulang_melewati_label_manual(self, client) -> None:
        headers, pid = await _new_project(client)
        rows = await _seed(client, headers, pid, ["mantap sekali pelayanannya bagus"])
        mid = rows[0]["id"]
        await client.put(
            f"/v1/projects/{pid}/mentions/{mid}/sentiment",
            json={"label": "negatif"},
            headers=headers,
        )
        r = await client.post(f"/v1/projects/{pid}/signals/rescore", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["remaining"] == 0
        listed = (await client.get(f"/v1/projects/{pid}/mentions", headers=headers)).json()
        assert listed[0]["sentiment"] == -0.5 and listed[0]["sentiment_manual"] is True

    async def test_ringkasan_menyebut_jumlah_koreksi(self, client) -> None:
        headers, pid = await _new_project(client)
        rows = await _seed(
            client, headers, pid, [f"pelayanan bagus sekali nomor {i}" for i in range(4)]
        )
        r = await client.post(
            f"/v1/projects/{pid}/mentions/sentiment-bulk",
            json={"ids": [rows[0]["id"], rows[1]["id"], str(uuid.uuid4())], "label": "netral"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"requested": 3, "changed": 2, "not_found": 1}
        body = (await client.get(f"/v1/projects/{pid}/signals/summary", headers=headers)).json()
        expected = "2 konten memakai label sentimen koreksi manual"
        assert any(expected in x for x in body["limitations"])

    async def test_filter_label_dan_pencarian(self, client) -> None:
        headers, pid = await _new_project(client)
        await _seed(
            client,
            headers,
            pid,
            [
                "pelayanan bagus sekali dan cepat",
                "antrean buruk dan lambat mengecewakan",
                "antrean di spbu jalan raya",
                "diskon 100% katanya",
            ],
        )
        base = f"/v1/projects/{pid}/mentions"
        pos = (await client.get(f"{base}?label=positif", headers=headers)).json()
        neg = (await client.get(f"{base}?label=negatif", headers=headers)).json()
        abst = (await client.get(f"{base}?label=abstain", headers=headers)).json()
        assert [m["text"] for m in pos] == ["pelayanan bagus sekali dan cepat"]
        assert [m["text"] for m in neg] == ["antrean buruk dan lambat mengecewakan"]
        assert all(m["sentiment"] is None for m in abst) and abst
        found = (await client.get(f"{base}?q=ANTREAN", headers=headers)).json()
        assert len(found) == 2
        # "%" dicari sebagai teks, bukan wildcard.
        pct = (await client.get(f"{base}", params={"q": "100%"}, headers=headers)).json()
        assert [m["text"] for m in pct] == ["diskon 100% katanya"]

    async def test_mutu_koreksi_per_sumber(self, client) -> None:
        headers, pid = await _new_project(client)
        rows = await _seed(
            client, headers, pid, [f"pelayanan bagus sekali nomor {i}" for i in range(32)]
        )
        ids = [m["id"] for m in rows]
        await client.post(
            f"/v1/projects/{pid}/mentions/sentiment-bulk",
            json={"ids": ids[:24], "label": "positif"},
            headers=headers,
        )
        await client.post(
            f"/v1/projects/{pid}/mentions/sentiment-bulk",
            json={"ids": ids[24:], "label": "negatif"},
            headers=headers,
        )
        r = await client.get(f"/v1/projects/{pid}/signals/correction-quality", headers=headers)
        assert r.status_code == 200, r.text
        (social,) = r.json()
        assert social["source"] == "SOCIAL"
        assert social["n"] == 32 and social["agreed"] == 24
        assert social["agreement"] == 0.75
        assert social["confusion"]["negatif"]["positif"] == 8
        assert "bukan sampel acak" in social["caveat"]

    async def test_label_asing_ditolak_dan_konten_asing_404(self, client) -> None:
        headers, pid = await _new_project(client)
        rows = await _seed(client, headers, pid, ["pelayanan bagus sekali"])
        url = f"/v1/projects/{pid}/mentions/{rows[0]['id']}/sentiment"
        assert (await client.put(url, json={"label": "marah"}, headers=headers)).status_code == 422
        ghost = f"/v1/projects/{pid}/mentions/{uuid.uuid4()}/sentiment"
        assert (
            await client.put(ghost, json={"label": "netral"}, headers=headers)
        ).status_code == 404

    async def test_org_lain_tidak_bisa_mengoreksi(self, client) -> None:
        headers_a, pid_a = await _new_project(client)
        headers_b, _ = await _new_project(client)
        rows = await _seed(client, headers_a, pid_a, ["pelayanan bagus sekali"])
        url = f"/v1/projects/{pid_a}/mentions/{rows[0]['id']}/sentiment"
        r = await client.put(url, json={"label": "negatif"}, headers=headers_b)
        assert r.status_code == 404, "RLS bocor: org lain mengoreksi konten"
        listed = (await client.get(f"/v1/projects/{pid_a}/mentions", headers=headers_a)).json()
        assert listed[0]["sentiment_manual"] is False
        q = await client.get(
            f"/v1/projects/{pid_a}/signals/correction-quality", headers=headers_b
        )
        assert q.status_code == 200 and q.json() == []
