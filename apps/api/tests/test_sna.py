"""SNA (services/sna.py + endpoint /network/sna, /bridges, /export).

Bagian pertama tanpa jaringan dan tanpa database: perhitungan graf diuji pada
graf kecil yang jawabannya bisa dihitung tangan. Bagian kedua terhadap
Postgres nyata (RLS aktif) lewat endpoint ingest resmi, supaya hashing akun
yang sungguhan ikut dipakai.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.services import sna
from app.services.sna import AuthorStats, WeightedEdge


def _two_groups() -> list[WeightedEdge]:
    """Dua kelompok rapat (a*, b*) yang dihubungkan satu jembatan a0—b0.

    Tiap kelompok: 8 akun, semua membalas pusatnya (a0 / b0) dan beberapa
    saling membalas. a0 dan b0 saling membalas → satu-satunya jalur antar-kelompok.
    """
    edges: list[WeightedEdge] = []
    for g in ("a", "b"):
        for i in range(1, 8):
            edges.append(WeightedEdge(f"{g}{i}", f"{g}0", "reply", 2))
            edges.append(WeightedEdge(f"{g}{i}", f"{g}{(i % 7) + 1}", "reply", 1))
    edges.append(WeightedEdge("a0", "b0", "reply", 1))
    edges.append(WeightedEdge("b0", "a0", "quote", 1))
    return edges


class TestGraf:
    def test_self_loop_dibuang_dan_bobot_dijumlah(self) -> None:
        g = sna.build_graph([
            WeightedEdge("x", "x", "reply", 5),
            WeightedEdge("x", "y", "reply", 2),
            WeightedEdge("x", "y", "quote", 1),
        ])
        assert g.number_of_edges() == 1
        d = g["x"]["y"]
        assert d["weight"] == 3 and d["reply"] == 2 and d["quote"] == 1

    def test_kurang_akun_insufficient(self) -> None:
        r = sna.analyze([WeightedEdge("a", "b", "reply")])
        assert r.insufficient_data and "akun" in (r.note or "")
        assert r.accounts == [] and r.viz_nodes == []

    def test_kurang_relasi_insufficient(self) -> None:
        # 10 akun tapi hanya 9 relasi.
        r = sna.analyze([WeightedEdge(f"u{i}", "pusat", "reply") for i in range(9)] +
                        [WeightedEdge("pusat", "u0", "reply")])
        assert r.insufficient_data and "relasi" in (r.note or "")

    def test_pangkas_graf_besar(self) -> None:
        edges = [WeightedEdge(f"u{i}", "pusat", "reply", 1) for i in range(30)]
        kept, total = sna.prune(edges, 11)
        assert total == 31
        assert {e.source for e in kept} | {e.target for e in kept} <= {
            "pusat", *[f"u{i}" for i in range(30)]
        }
        assert len({e.source for e in kept} | {e.target for e in kept}) == 11


class TestAnalisis:
    def test_jembatan_dan_komunitas(self) -> None:
        r = sna.analyze(_two_groups())
        assert not r.insufficient_data
        s = r.summary
        assert s.nodes == 16 and s.original_nodes == 16
        assert s.components == 1 and s.largest_component_share == 1.0
        assert s.communities == 2 and s.modularity is not None and s.modularity > 0.3
        assert 0 < s.density < 1 and 0 < s.reciprocity < 1

        by = {a.author_hash: a for a in r.accounts}
        # Pusat kelompok = betweenness tertinggi (semua jalur antar-kelompok lewat a0/b0).
        top_btw = max(r.accounts, key=lambda a: a.betweenness or 0)
        assert top_btw.author_hash in {"a0", "b0"}
        # Pusat juga PageRank tertinggi dan in-degree tertinggi.
        assert r.accounts[0].author_hash in {"a0", "b0"}
        assert by["a0"].in_degree == 7 * 2 + 1 and by["a0"].out_degree == 1
        assert by["a0"].closeness is not None and by["a0"].closeness > by["a3"].closeness  # type: ignore[operator]
        # Dua kelompok jadi dua komunitas yang berbeda, masing-masing 8 akun.
        assert by["a0"].community != by["b0"].community
        assert sorted(c.size for c in r.communities) == [8, 8]
        assert all(r.membership[f"a{i}"] == by["a0"].community for i in range(8))

    def test_eigenvector_terisi_dan_komponen_terpisah_dicatat(self) -> None:
        r = sna.analyze(_two_groups())
        assert all(a.eigenvector is not None for a in r.accounts)
        lepas = _two_groups() + [WeightedEdge(f"z{i}", "z0", "reply", 1) for i in range(1, 5)]
        r2 = sna.analyze(lepas)
        by = {a.author_hash: a for a in r2.accounts}
        assert by["a0"].eigenvector is not None
        assert any("komponen terbesar" in n for n in r2.notes)
        assert r2.summary.components == 2

    def test_deterministik(self) -> None:
        a, b = sna.analyze(_two_groups()), sna.analyze(_two_groups())
        assert a.accounts == b.accounts and a.membership == b.membership
        assert a.viz_nodes == b.viz_nodes

    def test_peta_punya_garis_dan_posisi_ternormalisasi(self) -> None:
        r = sna.analyze(_two_groups(), viz_nodes=12)
        assert 0 < len(r.viz_nodes) <= 12
        assert r.viz_edges, "graf bintang tetap harus menampilkan garis"
        ids = {v.id for v in r.viz_nodes}
        assert all(e.source in ids and e.target in ids for e in r.viz_edges)
        assert all(0 <= v.x <= 1 and 0 <= v.y <= 1 for v in r.viz_nodes)

    def test_inti_dan_sampel_dicatat(self) -> None:
        r = sna.analyze(_two_groups(), max_core_nodes=10, betweenness_samples=5)
        assert any("inti" in n for n in r.notes)
        assert any("diperkirakan" in n for n in r.notes)


class TestKontenKomunitas:
    def test_sentimen_hanya_dari_ambang_minimum(self) -> None:
        membership = {"a": 1, "b": 1, "c": 2}
        stats = {
            "a": AuthorStats(contents=25, scored=20, sentiment_sum=-6.0,
                             negative=12, neutral=6, positive=2),
            "b": AuthorStats(contents=15, scored=12, sentiment_sum=-2.4,
                             negative=6, neutral=4, positive=2),
            "c": AuthorStats(contents=5, scored=5, sentiment_sum=1.0,
                             negative=0, neutral=3, positive=2),
        }
        texts = {"a": ["Harga beras naik terus", "beras mahal sekali"],
                 "b": ["beras langka di pasar"], "c": ["setuju"]}
        out = {c.id: c for c in sna.summarize_communities(membership, stats, texts, [1, 2])}
        assert out[1].scored == 32 and out[1].sentiment_mean == round(-8.4 / 32, 3)
        assert out[1].negative_share == round(18 / 32, 3)
        assert out[1].top_terms[0] == ("beras", 3)
        assert out[2].sentiment_mean is None  # 5 < MIN_SCORED: tidak ditampilkan

    def test_label_counts_sama_dengan_ambang_sentimen(self) -> None:
        assert sna.label_counts(0.5) == (0, 0, 1)
        assert sna.label_counts(-0.5) == (1, 0, 0)
        assert sna.label_counts(0.0) == (0, 1, 0)

    def test_stopword_informal_dibuang(self) -> None:
        terms = dict(sna.top_terms(["yg gak jelas beras", "yg beras", "gak tau"]))
        assert "yg" not in terms and "gak" not in terms and terms["beras"] == 2


class TestAkunUnggahan:
    def test_lintas_unggahan_dan_tumpang_tindih(self) -> None:
        rows = [(f"u{i}", "yt:AAAAAAAAAAA", 1) for i in range(10)]
        rows += [(f"u{i}", "yt:BBBBBBBBBBB", 2) for i in range(5, 12)]
        rows += [("u0", "tt:123", 1)]
        r = sna.bridges(rows)
        assert not r.insufficient_data
        assert r.accounts == 12 and r.containers == 3
        assert r.cross_accounts == 6  # u5..u9 (A+B) + u0 (A+TikTok)
        top = r.top_containers[0]
        assert top.container == "yt:AAAAAAAAAAA" and top.commenters == 10
        assert top.url == "https://www.youtube.com/watch?v=AAAAAAAAAAA"
        assert top.shared_share == 0.6
        ab = next(o for o in r.overlaps if {o.a, o.b} == {"yt:AAAAAAAAAAA", "yt:BBBBBBBBBBB"})
        assert ab.shared == 5 and ab.jaccard == round(5 / 12, 4)
        assert r.top_cross_accounts[0].containers == 2

    def test_satu_unggahan_insufficient(self) -> None:
        r = sna.bridges([(f"u{i}", "yt:AAAAAAAAAAA", 1) for i in range(20)])
        assert r.insufficient_data


class TestEkspor:
    def test_gexf_dan_csv_tanpa_teks(self) -> None:
        edges = _two_groups()
        r = sna.analyze(edges)
        gexf = sna.to_gexf(edges, r.membership)
        assert gexf.startswith("<?xml") and "<gexf" in gexf and 'id="a0"' in gexf
        assert "community" in gexf
        nodes, rels = sna.to_csv(edges, r.membership)
        assert nodes.splitlines()[0] == "Id,Label,community,in_degree,out_degree"
        assert len(nodes.strip().splitlines()) == 17
        assert rels.splitlines()[0] == "Source,Target,Type,Weight,reply,quote"
        assert "a0,b0,Directed,2,1,1" in rels or "b0,a0,Directed" in rels


# ------------------------------------------------------ endpoint ----

DSN = os.getenv("TEST_DATABASE_URL_APP")
if DSN:
    os.environ["DATABASE_URL"] = DSN
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")


@pytest.fixture
async def client():
    if not DSN:
        pytest.skip("TEST_DATABASE_URL_APP tidak diset")
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _project(client) -> tuple[dict[str, str], str]:
    slug = f"sna-{uuid.uuid4().hex[:10]}"
    reg = await client.post("/v1/auth/register", json={
        "org_name": "Org SNA", "org_slug": slug, "full_name": "Penguji SNA",
        "email": f"{slug}@example.com", "password": "PasswordAsli123",
    })
    assert reg.status_code == 201, reg.text
    h = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek SNA"}, headers=h)
    return h, proj.json()["id"]


def _with_role(headers: dict[str, str], role: str) -> dict[str, str]:
    import jwt

    from app.services.auth import create_access_token

    claims = jwt.decode(headers["Authorization"].removeprefix("Bearer "),
                        options={"verify_signature": False})
    token = create_access_token(user_id=uuid.UUID(claims["sub"]), org_id=uuid.UUID(claims["org"]),
                                role=role, email=claims["email"])
    return {"Authorization": f"Bearer {token}"}


async def _seed(client, h: dict[str, str], pid: str) -> None:
    """Dua kelompok percakapan di dua video YouTube, dihubungkan dua pusatnya."""
    now = datetime.now(UTC) - timedelta(days=1)
    items = []
    texts = {"a": "harga beras naik mahal sekali tidak masuk akal",
             "b": "pupuk subsidi langka petani rugi besar"}
    video = {"a": "AAAAAAAAAAA", "b": "BBBBBBBBBBB"}
    for g in ("a", "b"):
        for i in range(1, 8):
            for k, target in enumerate((f"{g}0", f"{g}{(i % 7) + 1}")):
                items.append({
                    "external_id": f"{g}{i}-{k}-{uuid.uuid4().hex[:6]}",
                    "text": f"{texts[g]} komentar {i}",
                    "published_at": now.isoformat(),
                    "author_handle": f"{g}{i}",
                    "reply_to_handle": target,
                    "url": f"https://www.youtube.com/watch?v={video[g]}&lc={g}{i}{k}",
                })
    for src, dst in (("a0", "b0"), ("b0", "a0")):
        items.append({
            "external_id": f"{src}-{uuid.uuid4().hex[:6]}", "text": "saling membalas di sini",
            "published_at": now.isoformat(), "author_handle": src, "reply_to_handle": dst,
            "url": f"https://www.youtube.com/watch?v={video[src[0]]}&lc={src}",
        })
    # u5 juga berkomentar di video kelompok a → akun lintas unggahan.
    items.append({
        "external_id": f"cross-{uuid.uuid4().hex[:6]}", "text": "ikut komentar di video lain",
        "published_at": now.isoformat(), "author_handle": "b5",
        "url": f"https://www.youtube.com/watch?v={video['a']}&lc=x",
    })
    r = await client.post(f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=h)
    assert r.status_code == 200, r.text


@pytest.mark.asyncio(loop_scope="session")
class TestEndpointSNA:
    async def test_sna_lengkap(self, client) -> None:
        h, pid = await _project(client)
        await _seed(client, h, pid)
        r = await client.get(f"/v1/projects/{pid}/network/sna?days=7", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "SOCIAL" and not body["insufficient_data"]
        assert body["summary"]["nodes"] == 16 and body["summary"]["communities"] == 2
        assert len(body["communities"]) == 2
        c = body["communities"][0]
        assert c["contents"] > 0 and c["top_terms"]
        assert body["viz_nodes"] and body["viz_edges"]
        # Identitas keluar sebagai hash, bukan nama akun.
        assert all(len(a["author_hash"]) >= 32 for a in body["accounts"])
        assert "a0" not in {a["author_hash"] for a in body["accounts"]}
        assert body["limitations"] and body["method"]

    async def test_bridges(self, client) -> None:
        h, pid = await _project(client)
        await _seed(client, h, pid)
        r = await client.get(f"/v1/projects/{pid}/network/bridges?days=7", headers=h)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["containers"] == 2 and b["cross_accounts"] >= 1
        assert {c["container"] for c in b["top_containers"]} == {"yt:AAAAAAAAAAA", "yt:BBBBBBBBBBB"}
        assert b["overlaps"] and b["overlaps"][0]["shared"] >= 1

    async def test_ekspor_butuh_peran_dan_tercatat(self, client) -> None:
        h, pid = await _project(client)
        await _seed(client, h, pid)
        url = f"/v1/projects/{pid}/network/export?days=7"
        denied = await client.get(url, headers=_with_role(h, "COMM_STRATEGIST"))
        assert denied.status_code == 403
        ok = await client.get(url + "&format=gexf", headers=_with_role(h, "DATA_ANALYST"))
        assert ok.status_code == 200, ok.text
        assert "attachment" in ok.headers["content-disposition"]
        assert "<gexf" in ok.text and "harga beras" not in ok.text
        nodes = await client.get(url + "&format=nodes", headers=h)
        assert nodes.text.startswith("Id,Label,community")
        import jwt
        from sqlalchemy import select

        from app.db import SessionLocal
        from app.deps import bind_org
        from app.models.governance import AuditLog

        org = jwt.decode(h["Authorization"].removeprefix("Bearer "),
                         options={"verify_signature": False})["org"]
        async with SessionLocal() as session:
            await bind_org(session, uuid.UUID(org))
            actions = (await session.execute(
                select(AuditLog.metadata_).where(AuditLog.action == "network_export")
            )).scalars().all()
        assert [m["format"] for m in actions] == ["gexf", "nodes"]

    async def test_organisasi_lain_tidak_melihat(self, client) -> None:
        h, pid = await _project(client)
        await _seed(client, h, pid)
        other, _ = await _project(client)
        r = await client.get(f"/v1/projects/{pid}/network/sna?days=7", headers=other)
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert r.json()["insufficient_data"] is True and r.json()["accounts"] == []
