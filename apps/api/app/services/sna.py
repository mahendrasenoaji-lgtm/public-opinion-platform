"""Social Network Analysis (SNA) percakapan media sosial — logika murni.

Melengkapi ``services/network.py`` (peringkat in-degree) dengan analisis
jaringan yang lazim dipakai peneliti komunikasi:

1. **Graf** terarah berbobot akun → akun dari relasi balasan/kutipan yang
   DINYATAKAN sumbernya (``reply_to_hash``/``quote_of_hash``), bukan ditebak
   dari "@nama" di teks (batas di ``connectors/base.py``).
2. **Sentralitas**: degree masuk/keluar, betweenness, closeness, PageRank,
   eigenvector.
3. **Struktur dan komunitas**: density, resiprositas, komponen, koefisien
   klaster, komunitas Louvain + modularity.
4. **Gabungan konten**: sentimen dan kata dominan per komunitas
   (``summarize_communities``).
5. **Visualisasi**: subgraf akun teratas dengan tata letak yang sudah dihitung
   (``layout``), supaya peramban tidak perlu pustaka graf.
6. **Graf akun–unggahan** (``bridges``): siapa berkomentar di video mana. Di
   YouTube ini sering lebih kaya daripada graf balasan, karena API hanya
   mencatat balasan ke komentar utama.

## Kata yang dipakai (CLAUDE.md §3)

Semua angka di sini adalah **posisi struktural** dalam graf yang teramati.
Betweenness tinggi = akun sering berada di jalur terpendek antar-akun lain;
itu tidak berarti ia "menggerakkan" atau "mengendalikan" opini, dan bukan
deteksi buzzer atau koordinasi. Identitas yang masuk dan keluar hanya
``author_hash``.

## Pendekatan untuk graf besar

Server produksi punya memori 512 MB. Karena itu:

- relasi diagregasi di SQL menjadi pasangan (sumber, tujuan, bobot);
- betweenness dihitung dengan sampel ``BETWEENNESS_SAMPLES`` simpul sumber
  (Brandes, perkiraan) pada inti graf = ``MAX_CORE_NODES`` akun ber-degree
  tertinggi bila graf lebih besar dari itu;
- closeness dihitung hanya untuk akun yang ditampilkan;
- semua itu dicatat di ``method``/``notes`` hasilnya, bukan disembunyikan.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, cast

import networkx as nx
from networkx.algorithms import community as nx_comm

from app.services.ingestion import wordset
from app.services.sentiment import NEGATIVE_THRESHOLD, POSITIVE_THRESHOLD
from app.services.topics import STOPWORDS_ID

MIN_ACCOUNTS = 10
MIN_EDGES = 15
#: Batas akun di graf yang dianalisis (memori server 512 MB). Graf lebih besar
#: dipangkas ke akun dengan interaksi terbanyak, dan itu dicatat di ``notes``.
MAX_GRAPH_NODES = 25000
#: Inti graf untuk betweenness/eigenvector/klaster bila graf lebih besar.
MAX_CORE_NODES = 3000
BETWEENNESS_SAMPLES = 250
SEED = 42
#: Akun per metrik yang ditampilkan; tabel = gabungan teratas tiap metrik.
TOP_PER_METRIC = 15
#: Simpul pada peta jaringan, dan berapa di antaranya "pusat" (PageRank
#: tertinggi); sisanya akun yang paling banyak berinteraksi dengan pusat itu.
VIZ_NODES = 150
VIZ_SEEDS = 40
#: Komunitas yang diberi warna/kartu sendiri; sisanya "lainnya".
MAX_COMMUNITIES = 8
MIN_COMMUNITY_SIZE = 3
#: Sentimen per komunitas baru ditampilkan dari sekian konten bernilai
#: (sama dengan MIN_SCORED di services/conversation_report.py).
MIN_SCORED = 30

EdgeKind = Literal["reply", "quote"]

METHOD = (
    "graf terarah berbobot dari relasi balasan/kutipan yang dinyatakan sumbernya; "
    "sentralitas networkx (degree, betweenness Brandes, closeness Wasserman-Faust, "
    "PageRank α=0,85, eigenvector), komunitas Louvain (resolusi 1, seed 42) "
    "pada graf tak berarah berbobot"
)

LIMITATIONS = (
    "Graf hanya memuat relasi antar-akun yang KEDUANYA muncul sebagai penulis dalam "
    "data yang terambil; akun di luar data tidak tampil, bukan bernilai nol.",
    "Sentralitas adalah posisi struktural dalam graf yang teramati, bukan ukuran "
    "pengaruh kausal, kendali atas opini, atau bukti koordinasi/buzzer.",
    "YouTube hanya mencatat balasan ke komentar utama; balasan ke balasan tercatat "
    "ke penulis komentar utama, sehingga graf cenderung memusat di komentar ramai.",
    "Komunitas Louvain adalah pengelompokan berdasarkan kepadatan interaksi, bukan "
    "kelompok ideologis atau organisasi; hasilnya bisa sedikit berubah bila data berubah.",
)


# ------------------------------------------------------------- graf ----


@dataclass(frozen=True, slots=True)
class WeightedEdge:
    """Relasi teragregasi: ``source`` membalas/mengutip ``target`` ``weight`` kali."""

    source: str
    target: str
    kind: EdgeKind
    weight: int = 1


def build_graph(edges: Iterable[WeightedEdge]) -> nx.DiGraph[str]:
    """Graf terarah berbobot; balasan + kutipan ke pasangan sama dijumlah.

    Self-loop dibuang: utas panjang satu orang bukan interaksi ANTAR akun.
    """
    g: nx.DiGraph[str] = nx.DiGraph()
    for e in edges:
        if not e.source or not e.target or e.source == e.target or e.weight <= 0:
            continue
        if g.has_edge(e.source, e.target):
            data = g[e.source][e.target]
            data["weight"] += e.weight
            data[e.kind] = data.get(e.kind, 0) + e.weight
        else:
            g.add_edge(e.source, e.target, weight=e.weight, **{e.kind: e.weight})
    return g


def prune(
    edges: Sequence[WeightedEdge], max_nodes: int
) -> tuple[list[WeightedEdge], int]:
    """Pertahankan ``max_nodes`` akun dengan interaksi (berbobot, dua arah)
    terbanyak dan relasi di antara mereka. Mengembalikan (relasi, akun semula)."""
    degree: Counter[str] = Counter()
    for e in edges:
        if e.source and e.target and e.source != e.target and e.weight > 0:
            degree[e.source] += e.weight
            degree[e.target] += e.weight
    total = len(degree)
    if total <= max_nodes:
        return list(edges), total
    keep = {a for a, _ in sorted(degree.items(), key=lambda t: (-t[1], t[0]))[:max_nodes]}
    return [e for e in edges if e.source in keep and e.target in keep], total


def undirected(g: nx.DiGraph[str]) -> nx.Graph[str]:
    """Versi tak berarah; bobot dua arah dijumlah."""
    u: nx.Graph[str] = nx.Graph()
    u.add_nodes_from(g.nodes)
    for a, b, d in g.edges(data=True):
        w = int(d.get("weight", 1))
        if u.has_edge(a, b):
            u[a][b]["weight"] += w
        else:
            u.add_edge(a, b, weight=w)
    return u


# ------------------------------------------------------- keluaran ----


@dataclass(frozen=True, slots=True)
class AccountMetrics:
    author_hash: str
    #: Jumlah interaksi masuk (dibalas/dikutip), berbobot.
    in_degree: int
    #: Jumlah interaksi keluar (membalas/mengutip), berbobot.
    out_degree: int
    #: Akun berbeda yang terhubung (dua arah).
    partners: int
    betweenness: float | None
    closeness: float | None
    pagerank: float
    eigenvector: float | None
    #: Nomor komunitas (1 = terbesar); 0 = komunitas kecil/lainnya.
    community: int


@dataclass(frozen=True, slots=True)
class CommunityInfo:
    id: int
    size: int
    share: float
    internal_edges: int
    external_edges: int
    density: float
    #: Akun ber-PageRank tertinggi di komunitas ini (hash).
    top_accounts: list[str]


@dataclass(frozen=True, slots=True)
class VizNode:
    id: str
    x: float
    y: float
    community: int
    pagerank: float
    in_degree: int
    out_degree: int


@dataclass(frozen=True, slots=True)
class VizEdge:
    source: str
    target: str
    weight: int


@dataclass(frozen=True, slots=True)
class GraphSummary:
    nodes: int
    #: Akun sebelum dipangkas (sama dengan ``nodes`` bila tidak dipangkas).
    original_nodes: int
    edges: int
    interactions: int
    density: float
    reciprocity: float
    components: int
    largest_component_share: float
    avg_clustering: float | None
    modularity: float | None
    communities: int


@dataclass(slots=True)
class SNAReport:
    summary: GraphSummary
    accounts: list[AccountMetrics] = field(default_factory=list)
    communities: list[CommunityInfo] = field(default_factory=list)
    #: hash → nomor komunitas untuk SEMUA akun di komunitas yang ditampilkan.
    membership: dict[str, int] = field(default_factory=dict)
    viz_nodes: list[VizNode] = field(default_factory=list)
    viz_edges: list[VizEdge] = field(default_factory=list)
    insufficient_data: bool = False
    note: str | None = None
    notes: list[str] = field(default_factory=list)
    method: str = METHOD
    limitations: list[str] = field(default_factory=lambda: list(LIMITATIONS))


def _empty_summary(g: nx.DiGraph[str]) -> GraphSummary:
    return GraphSummary(
        nodes=g.number_of_nodes(),
        original_nodes=g.number_of_nodes(),
        edges=g.number_of_edges(),
        interactions=int(sum(d.get("weight", 1) for _, _, d in g.edges(data=True))),
        density=0.0,
        reciprocity=0.0,
        components=0,
        largest_component_share=0.0,
        avg_clustering=None,
        modularity=None,
        communities=0,
    )


def _core(u: nx.Graph[str], max_nodes: int) -> nx.Graph[str]:
    if u.number_of_nodes() <= max_nodes:
        return u
    ranked = sorted(u.degree(weight="weight"), key=lambda t: (-t[1], t[0]))
    keep = [n for n, _ in ranked[:max_nodes]]
    return u.subgraph(keep).copy()


def _communities(u: nx.Graph[str]) -> tuple[list[set[str]], float | None]:
    if u.number_of_edges() == 0:
        return [], None
    parts = nx_comm.louvain_communities(u, weight="weight", resolution=1.0, seed=SEED)
    groups = sorted((set(p) for p in parts), key=lambda s: (-len(s), min(s)))
    try:
        q = float(nx_comm.modularity(u, groups, weight="weight"))
    except (ZeroDivisionError, nx.NetworkXError):
        q = None
    return groups, q


def _id(n: int) -> str:
    """Angka dengan pemisah ribuan Indonesia (titik)."""
    return f"{n:,}".replace(",", ".")


def _top(scores: Mapping[str, float], k: int) -> list[str]:
    return [n for n, _ in sorted(scores.items(), key=lambda t: (-t[1], t[0]))[:k]]


def analyze(
    edges: Iterable[WeightedEdge],
    *,
    max_graph_nodes: int = MAX_GRAPH_NODES,
    max_core_nodes: int = MAX_CORE_NODES,
    betweenness_samples: int = BETWEENNESS_SAMPLES,
    top_per_metric: int = TOP_PER_METRIC,
    viz_nodes: int = VIZ_NODES,
) -> SNAReport:
    """Analisis jaringan lengkap. Fungsi murni: tanpa I/O, deterministik (seed)."""
    pruned, original_nodes = prune(list(edges), max_graph_nodes)
    g = build_graph(pruned)
    n, m = g.number_of_nodes(), g.number_of_edges()
    if n < MIN_ACCOUNTS:
        return SNAReport(
            summary=_empty_summary(g),
            insufficient_data=True,
            note=(
                f"Perlu minimal {MIN_ACCOUNTS} akun yang terhubung lewat balasan/kutipan; "
                f"baru ada {n}."
            ),
        )
    if m < MIN_EDGES:
        return SNAReport(
            summary=_empty_summary(g),
            insufficient_data=True,
            note=f"Perlu minimal {MIN_EDGES} relasi antar-akun; baru ada {m}.",
        )

    notes: list[str] = []
    if original_nodes > n:
        notes.append(
            f"Graf semula {_id(original_nodes)} akun; dianalisis {_id(n)} akun dengan interaksi "
            "terbanyak beserta relasi di antara mereka (batas memori server)."
        )
    u = undirected(g)
    components = list(nx.connected_components(u))
    largest = max((len(c) for c in components), default=0)

    # --- komunitas (graf penuh) ---
    groups, modularity = _communities(u)
    shown = [s for s in groups if len(s) >= MIN_COMMUNITY_SIZE][:MAX_COMMUNITIES]
    membership: dict[str, int] = {}
    for i, s in enumerate(shown, start=1):
        for node in s:
            membership[node] = i

    # --- sentralitas ---
    pagerank: dict[str, float] = nx.pagerank(g, alpha=0.85, weight="weight")
    core = _core(u, max_core_nodes)
    if core.number_of_nodes() < n:
        notes.append(
            f"Graf besar ({_id(n)} akun): betweenness, eigenvector, dan koefisien klaster "
            f"dihitung pada inti {_id(core.number_of_nodes())} akun ber-degree tertinggi."
        )
    k = min(betweenness_samples, core.number_of_nodes())
    if k < core.number_of_nodes():
        notes.append(
            f"Betweenness diperkirakan dari {k} simpul sumber acak (seed {SEED}), "
            "bukan dihitung eksak."
        )
    betweenness: dict[str, float] = nx.betweenness_centrality(
        core, k=k if k < core.number_of_nodes() else None, normalized=True, seed=SEED
    )
    # Eigenvector hanya terdefinisi tunggal pada graf terhubung: dihitung di
    # komponen terbesar inti; akun di komponen lain dikosongkan, bukan nol.
    eigen: dict[str, float] = {}
    core_parts = list(nx.connected_components(core))
    lcc = core.subgraph(max(core_parts, key=len)) if core_parts else core
    if lcc.number_of_nodes() >= 3:
        try:
            eigen = nx.eigenvector_centrality_numpy(lcc, weight="weight", max_iter=500)
        except (nx.NetworkXException, ValueError, TypeError, ArithmeticError):
            notes.append("Eigenvector tidak konvergen pada graf ini; kolomnya dikosongkan.")
    if eigen and len(core_parts) > 1:
        notes.append(
            f"Eigenvector dihitung pada komponen terbesar ({_id(lcc.number_of_nodes())} akun); "
            "akun di komponen lain ditandai \u2013."
        )
    try:
        clustering = nx.average_clustering(core)
    except ZeroDivisionError:
        clustering = None

    in_w = dict(g.in_degree(weight="weight"))
    out_w = dict(g.out_degree(weight="weight"))
    by_in = {a: float(v) for a, v in in_w.items()}
    by_out = {a: float(v) for a, v in out_w.items()}

    chosen: list[str] = []
    for scores in (pagerank, by_in, by_out, betweenness, eigen):
        for a in _top(scores, top_per_metric):
            if a not in chosen:
                chosen.append(a)

    accounts = [
        AccountMetrics(
            author_hash=a,
            in_degree=int(in_w.get(a, 0)),
            out_degree=int(out_w.get(a, 0)),
            partners=u.degree(a),
            betweenness=round(betweenness[a], 6) if a in betweenness else None,
            closeness=round(cast(float, nx.closeness_centrality(u, u=a, wf_improved=True)), 6),
            pagerank=round(pagerank.get(a, 0.0), 6),
            eigenvector=round(eigen[a], 6) if a in eigen else None,
            community=membership.get(a, 0),
        )
        for a in chosen
    ]
    accounts.sort(key=lambda r: (-r.pagerank, r.author_hash))

    communities: list[CommunityInfo] = []
    for i, s in enumerate(shown, start=1):
        sub = u.subgraph(s)
        internal = sub.number_of_edges()
        external = sum(1 for a in s for b in u.neighbors(a) if b not in s)
        size = len(s)
        possible = size * (size - 1) / 2
        communities.append(
            CommunityInfo(
                id=i,
                size=size,
                share=round(size / n, 4),
                internal_edges=internal,
                external_edges=external,
                density=round(internal / possible, 4) if possible else 0.0,
                top_accounts=_top({a: pagerank.get(a, 0.0) for a in s}, 5),
            )
        )

    vn, ve = layout(g, pagerank, membership, in_w, out_w, limit=viz_nodes)

    summary = GraphSummary(
        nodes=n,
        original_nodes=original_nodes,
        edges=m,
        interactions=int(sum(d.get("weight", 1) for _, _, d in g.edges(data=True))),
        density=round(float(nx.density(g)), 6),
        reciprocity=round(cast(float, nx.reciprocity(g)) or 0.0, 4),
        components=len(components),
        largest_component_share=round(largest / n, 4) if n else 0.0,
        avg_clustering=round(clustering, 4) if clustering is not None else None,
        modularity=round(modularity, 4) if modularity is not None else None,
        communities=len(groups),
    )
    return SNAReport(
        summary=summary,
        accounts=accounts,
        communities=communities,
        membership=membership,
        viz_nodes=vn,
        viz_edges=ve,
        notes=notes,
    )


def _seeds(
    pagerank: Mapping[str, float], membership: Mapping[str, int], k: int
) -> list[str]:
    """Pusat peta, dibagi rata antar-komunitas yang ditampilkan.

    Tanpa pembagian ini, komunitas dengan PageRank tinggi menghabiskan seluruh
    kuota dan komunitas lain tidak muncul di peta sama sekali.
    """
    groups: dict[int, list[str]] = {}
    for a, c in membership.items():
        groups.setdefault(c, []).append(a)
    per = k // max(1, len(groups)) if groups else 0
    chosen: list[str] = []
    for c in sorted(groups):
        ranked = sorted(groups[c], key=lambda a: (-pagerank.get(a, 0.0), a))
        chosen.extend(ranked[:per])
    for a in _top(pagerank, k + len(chosen)):
        if len(chosen) >= k:
            break
        if a not in chosen:
            chosen.append(a)
    return chosen[:k]


def layout(
    g: nx.DiGraph[str],
    pagerank: Mapping[str, float],
    membership: Mapping[str, int],
    in_w: Mapping[str, float],
    out_w: Mapping[str, float],
    *,
    limit: int = VIZ_NODES,
) -> tuple[list[VizNode], list[VizEdge]]:
    """Subgraf untuk peta + posisi force-directed (0..1).

    ``VIZ_SEEDS`` akun ber-PageRank tertinggi menjadi pusat; sisa kuota diisi akun
    yang paling banyak berinteraksi (berbobot) dengan pusat-pusat itu. Tanpa
    langkah kedua, graf berbentuk bintang (umum di YouTube) tampil sebagai titik
    pusat tanpa satu garis pun, karena pusat jarang saling membalas.
    """
    seeds = _seeds(pagerank, membership, min(VIZ_SEEDS, limit))
    seed_set = set(seeds)
    pull: Counter[str] = Counter()
    for sd in seeds:
        for nb in g.successors(sd):
            if nb not in seed_set:
                pull[nb] += int(g[sd][nb].get("weight", 1))
        for nb in g.predecessors(sd):
            if nb not in seed_set:
                pull[nb] += int(g[nb][sd].get("weight", 1))
    extra = [a for a, _ in sorted(pull.items(), key=lambda t: (-t[1], t[0]))]
    keep = seeds + extra[: max(0, limit - len(seeds))]
    sub = undirected(g.subgraph(keep).copy())
    if sub.number_of_nodes() == 0:
        return [], []
    pos: dict[Any, Any] = nx.spring_layout(
        sub, weight="weight", seed=SEED, iterations=80, k=1.6 / math.sqrt(sub.number_of_nodes())
    )
    xs = [float(p[0]) for p in pos.values()]
    ys = [float(p[1]) for p in pos.values()]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sx = (x1 - x0) or 1.0
    sy = (y1 - y0) or 1.0
    nodes = [
        VizNode(
            id=str(a),
            x=round((float(pos[a][0]) - x0) / sx, 4),
            y=round((float(pos[a][1]) - y0) / sy, 4),
            community=membership.get(str(a), 0),
            pagerank=round(pagerank.get(str(a), 0.0), 6),
            in_degree=int(in_w.get(str(a), 0)),
            out_degree=int(out_w.get(str(a), 0)),
        )
        for a in sub.nodes
    ]
    nodes.sort(key=lambda v: (-v.pagerank, v.id))
    edges = [
        VizEdge(source=str(a), target=str(b), weight=int(d.get("weight", 1)))
        for a, b, d in g.subgraph(keep).edges(data=True)
    ]
    edges.sort(key=lambda e: (-e.weight, e.source, e.target))
    return nodes, edges


# ------------------------------------------- konten per komunitas ----


@dataclass(frozen=True, slots=True)
class AuthorStats:
    """Agregat konten satu akun pada periode: dari SQL, tanpa teks."""

    contents: int
    scored: int
    sentiment_sum: float
    negative: int
    neutral: int
    positive: int


@dataclass(frozen=True, slots=True)
class CommunityContent:
    id: int
    contents: int
    scored: int
    #: None bila ``scored < MIN_SCORED``.
    sentiment_mean: float | None
    negative_share: float | None
    neutral_share: float | None
    positive_share: float | None
    top_terms: list[tuple[str, int]]


_TOKEN = re.compile(r"[a-zA-ZÀ-ɏ]{3,}")
EXTRA_STOP = wordset("""
    yg gak ga gk nggak ngga engga tdk udah udh aja aj sdh krn karna jd jadi kalo klo
    biar bikin buat sama lagi lg banget bgt mau emang memang terus trus kayak kaya
    semua apa siapa kenapa gimana bagaimana dgn utk pak bu bang kak min
""")


def label_counts(score: float) -> tuple[int, int, int]:
    """(negatif, netral, positif) untuk satu skor, ambang sama dengan sentiment.label_for."""
    if score > POSITIVE_THRESHOLD:
        return 0, 0, 1
    if score < NEGATIVE_THRESHOLD:
        return 1, 0, 0
    return 0, 1, 0


def top_terms(texts: Iterable[str], k: int = 10) -> list[tuple[str, int]]:
    """Kata terbanyak (frekuensi dokumen) tanpa stopword. Deskriptif, bukan topik."""
    counts: Counter[str] = Counter()
    for t in texts:
        words = {w.lower() for w in _TOKEN.findall(t)}
        counts.update(w for w in words if w not in STOPWORDS_ID and w not in EXTRA_STOP)
    return [(w, c) for w, c in counts.most_common(k) if c >= 2]


def summarize_communities(
    membership: Mapping[str, int],
    stats: Mapping[str, AuthorStats],
    texts_by_author: Mapping[str, Sequence[str]],
    community_ids: Sequence[int],
) -> list[CommunityContent]:
    """Sentimen (SOSIAL) dan kata dominan per komunitas."""
    out: list[CommunityContent] = []
    for cid in community_ids:
        members = [a for a, c in membership.items() if c == cid]
        contents = scored = neg = neu = pos = 0
        total = 0.0
        texts: list[str] = []
        for a in members:
            s = stats.get(a)
            if s is not None:
                contents += s.contents
                scored += s.scored
                total += s.sentiment_sum
                neg += s.negative
                neu += s.neutral
                pos += s.positive
            texts.extend(texts_by_author.get(a, ()))
        enough = scored >= MIN_SCORED
        out.append(
            CommunityContent(
                id=cid,
                contents=contents,
                scored=scored,
                sentiment_mean=round(total / scored, 3) if enough else None,
                negative_share=round(neg / scored, 3) if enough else None,
                neutral_share=round(neu / scored, 3) if enough else None,
                positive_share=round(pos / scored, 3) if enough else None,
                top_terms=top_terms(texts),
            )
        )
    return out


# --------------------------------------------- graf akun–unggahan ----

def container_url(container: str) -> str | None:
    kind, _, ident = container.partition(":")
    if kind == "yt":
        return f"https://www.youtube.com/watch?v={ident}"
    if kind == "tt":
        return f"https://www.tiktok.com/video/{ident}"
    return None


@dataclass(frozen=True, slots=True)
class ContainerInfo:
    container: str
    url: str | None
    commenters: int
    comments: int
    #: Porsi komentatornya yang juga berkomentar di unggahan lain dalam data.
    shared_share: float


@dataclass(frozen=True, slots=True)
class CrossAccount:
    author_hash: str
    containers: int
    comments: int


@dataclass(frozen=True, slots=True)
class Overlap:
    a: str
    b: str
    shared: int
    jaccard: float


@dataclass(slots=True)
class BridgeReport:
    accounts: int
    containers: int
    comments: int
    cross_accounts: int
    cross_share: float
    top_containers: list[ContainerInfo] = field(default_factory=list)
    top_cross_accounts: list[CrossAccount] = field(default_factory=list)
    overlaps: list[Overlap] = field(default_factory=list)
    insufficient_data: bool = False
    note: str | None = None
    method: str = (
        "graf dua-mode akun–unggahan dari URL komentar (YouTube/TikTok); akun lintas "
        "unggahan = berkomentar di ≥2 unggahan; tumpang-tindih = Jaccard himpunan komentator"
    )
    limitations: list[str] = field(
        default_factory=lambda: [
            "Hanya unggahan yang komentarnya ditarik ke proyek ini; unggahan dipilih "
            "pencarian/peneliti, bukan sampel.",
            "Berkomentar di banyak unggahan menunjukkan keterlibatan lintas unggahan, "
            "bukan koordinasi atau akun palsu.",
            "TikTok tidak memberi nama akun komentator, jadi hanya YouTube yang biasanya "
            "menyumbang akun di graf ini.",
        ]
    )


@dataclass(frozen=True, slots=True)
class BridgeAggregates:
    """Agregat graf akun–unggahan, cukup kecil untuk dihitung di SQL.

    ``containers``: (unggahan, akun berbeda, komentar) untuk SEMUA unggahan.
    ``cross_per_container``: akun lintas unggahan per unggahan (cukup unggahan
    teratas). ``pair_shared``: akun yang sama untuk pasangan unggahan teratas.
    ``top_cross``: (akun, unggahan berbeda, komentar), sudah urut.
    """

    containers: list[tuple[str, int, int]]
    accounts: int
    cross_accounts: int
    cross_per_container: Mapping[str, int]
    pair_shared: list[tuple[str, str, int]]
    top_cross: list[tuple[str, int, int]]


#: Unggahan teratas yang ditampilkan, dan yang dibandingkan berpasangan.
BRIDGE_TOP = 15
BRIDGE_OVERLAP_TOP = 12


def bridges_from_aggregates(agg: BridgeAggregates, *, top: int = BRIDGE_TOP) -> BridgeReport:
    """Rakit laporan akun–unggahan dari agregat. Fungsi murni."""
    total = sum(n for _, _, n in agg.containers)
    containers = len(agg.containers)
    if containers < 2 or agg.accounts < MIN_ACCOUNTS:
        return BridgeReport(
            accounts=agg.accounts,
            containers=containers,
            comments=total,
            cross_accounts=0,
            cross_share=0.0,
            insufficient_data=True,
            note=(
                "Perlu komentar dari minimal 2 unggahan dan "
                f"{MIN_ACCOUNTS} akun; baru {containers} unggahan, {agg.accounts} akun."
            ),
        )
    ranked = sorted(agg.containers, key=lambda t: (-t[1], t[0]))
    size = {c: n for c, n, _ in agg.containers}
    infos = [
        ContainerInfo(
            container=c,
            url=container_url(c),
            commenters=n,
            comments=k,
            shared_share=round(agg.cross_per_container.get(c, 0) / n, 4) if n else 0.0,
        )
        for c, n, k in ranked[:top]
    ]
    overlaps = [
        Overlap(a=a, b=b, shared=sh, jaccard=round(sh / (size[a] + size[b] - sh), 4))
        for a, b, sh in agg.pair_shared
        if sh > 0 and a in size and b in size
    ]
    overlaps.sort(key=lambda o: (-o.jaccard, -o.shared, o.a, o.b))
    return BridgeReport(
        accounts=agg.accounts,
        containers=containers,
        comments=total,
        cross_accounts=agg.cross_accounts,
        cross_share=round(agg.cross_accounts / agg.accounts, 4),
        top_containers=infos,
        top_cross_accounts=[
            CrossAccount(author_hash=a, containers=c, comments=k) for a, c, k in agg.top_cross[:top]
        ],
        overlaps=overlaps[:20],
    )


def bridges(
    rows: Iterable[tuple[str, str, int]],
    *,
    top: int = BRIDGE_TOP,
    overlap_top: int = BRIDGE_OVERLAP_TOP,
) -> BridgeReport:
    """Versi Python dari agregat SQL di routers/network.py, untuk tes dan data kecil.

    ``rows`` = (author_hash, container, jumlah komentar). Definisi tiap angka di
    sini menjadi acuan bagi kueri SQL-nya.
    """
    by_container: dict[str, set[str]] = {}
    comments_c: Counter[str] = Counter()
    by_author: dict[str, set[str]] = {}
    comments_a: Counter[str] = Counter()
    for author, container, count in rows:
        if not author or not container or count <= 0:
            continue
        by_container.setdefault(container, set()).add(author)
        by_author.setdefault(author, set()).add(container)
        comments_c[container] += count
        comments_a[author] += count
    cross = {a for a, cs in by_author.items() if len(cs) >= 2}
    ranked = sorted(by_container, key=lambda c: (-len(by_container[c]), c))
    head = ranked[:overlap_top]
    pairs = [
        (a, b, len(by_container[a] & by_container[b]))
        for i, a in enumerate(head)
        for b in head[i + 1 :]
    ]
    cross_ranked = sorted(cross, key=lambda a: (-len(by_author[a]), -comments_a[a], a))
    agg = BridgeAggregates(
        containers=[(c, len(by_container[c]), comments_c[c]) for c in by_container],
        accounts=len(by_author),
        cross_accounts=len(cross),
        cross_per_container={c: len(by_container[c] & cross) for c in ranked[:top]},
        pair_shared=pairs,
        top_cross=[(a, len(by_author[a]), comments_a[a]) for a in cross_ranked[:top]],
    )
    return bridges_from_aggregates(agg, top=top)


# ---------------------------------------------------------- ekspor ----


def to_gexf(edges: Iterable[WeightedEdge], membership: Mapping[str, int]) -> str:
    """Graf penuh sebagai GEXF 1.2 untuk Gephi. Node = hash akun, tanpa teks."""
    g = build_graph(edges)
    for node in g.nodes:
        g.nodes[node]["community"] = int(membership.get(str(node), 0))
        g.nodes[node]["label"] = str(node)[:12]
    lines = nx.generate_gexf(g, version="1.2draft")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + "\n".join(lines) + "\n"


def to_csv(edges: Iterable[WeightedEdge], membership: Mapping[str, int]) -> tuple[str, str]:
    """(nodes.csv, edges.csv) — format impor Gephi (Id/Label, Source/Target/Weight)."""
    g = build_graph(edges)
    node_lines = ["Id,Label,community,in_degree,out_degree"]
    for node in sorted(g.nodes):
        node_lines.append(
            f"{node},{str(node)[:12]},{membership.get(str(node), 0)},"
            f"{int(g.in_degree(node, weight='weight'))},{int(g.out_degree(node, weight='weight'))}"
        )
    edge_lines = ["Source,Target,Type,Weight,reply,quote"]
    for a, b, d in sorted(g.edges(data=True), key=lambda t: (t[0], t[1])):
        edge_lines.append(
            f"{a},{b},Directed,{int(d.get('weight', 1))},{int(d.get('reply', 0))},"
            f"{int(d.get('quote', 0))}"
        )
    return "\n".join(node_lines) + "\n", "\n".join(edge_lines) + "\n"
