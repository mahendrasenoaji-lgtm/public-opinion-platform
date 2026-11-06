import csv, sys, collections, itertools, json
rows = list(csv.DictReader(open(sys.argv[1], encoding='utf-8-sig')))
by_id = {r['comment_id']: r for r in rows}
out = {}
# --- bipartite akun-video
av = collections.defaultdict(set)
for r in rows: av[r['author_hash']].add(r['video_url'])
nacc = len(av); nvid = len({r['video_url'] for r in rows})
dist = collections.Counter(min(len(v), 6) for v in av.values())
out['akun'] = nacc; out['video'] = nvid
out['akun_per_jumlah_video'] = {k: dist[k] for k in sorted(dist)}
multi_vid = [a for a, v in av.items() if len(v) >= 2]
out['akun_2plus_video'] = len(multi_vid)
out['akun_3plus_video'] = sum(len(v) >= 3 for v in av.values())
out['akun_10plus_video'] = sum(len(v) >= 10 for v in av.values())
# komentar dari akun lintas-video
cm = collections.Counter(r['author_hash'] for r in rows)
out['komentar_dari_akun_2plus_video'] = sum(cm[a] for a in multi_vid)
# --- jaringan balasan (akun -> akun)
edges = collections.Counter()
self_r = 0
for r in rows:
    if r['parent_id']:
        a, b = r['author_hash'], by_id[r['parent_id']]['author_hash']
        if a == b: self_r += 1
        else: edges[(a, b)] += 1
nodes = set(x for e in edges for x in e)
out['balasan_total'] = sum(1 for r in rows if r['parent_id'])
out['balasan_ke_diri_sendiri'] = self_r
out['sisi_balasan_unik'] = len(edges)
out['simpul_balasan'] = len(nodes)
recip = sum(1 for (a, b) in edges if (b, a) in edges) // 2
out['pasangan_timbal_balik'] = recip
# komponen terhubung (tak berarah)
adj = collections.defaultdict(set)
for a, b in edges: adj[a].add(b); adj[b].add(a)
seen = set(); comps = []
for n in nodes:
    if n in seen: continue
    st = [n]; seen.add(n); c = 0
    while st:
        x = st.pop(); c += 1
        for y in adj[x]:
            if y not in seen: seen.add(y); st.append(y)
    comps.append(c)
comps.sort(reverse=True)
out['komponen_balasan'] = len(comps); out['komponen_terbesar'] = comps[:5]
indeg = collections.Counter();
for (a, b), w in edges.items(): indeg[b] += w
tot_in = sum(indeg.values())
out['balasan_diterima_top10_akun_persen'] = round(sum(v for _, v in indeg.most_common(10)) / tot_in * 100, 1)
out['akun_menerima_balasan'] = len(indeg)
out['akun_dengan_3plus_balasan_diterima'] = sum(v >= 3 for v in indeg.values())
# utas terdalam: apakah balasan hanya 1 tingkat (YouTube) -> ya
# --- jaringan video-video lewat akun bersama
vv = collections.Counter()
for a, vs in av.items():
    vs = sorted(vs)
    if 2 <= len(vs) <= 30:
        for x, y in itertools.combinations(vs, 2): vv[(x, y)] += 1
title = {}; chan = {}; vc = collections.Counter()
for r in rows: title[r['video_url']] = r['video_title']; chan[r['video_url']] = r['channel']; vc[r['video_url']] += 1
# jaccard
vacc = collections.defaultdict(set)
for a, vs in av.items():
    for v in vs: vacc[v].add(a)
top = []
for (x, y), w in vv.items():
    if min(len(vacc[x]), len(vacc[y])) >= 100:
        j = w / len(vacc[x] | vacc[y]); top.append((j, w, x, y))
top.sort(reverse=True)
out['pasangan_video_teratas'] = [(round(j, 3), w, chan[x], title[x][:50], chan[y], title[y][:50]) for j, w, x, y in top[:6]]
# komunitas video: komponen dari sisi dengan jaccard >= ambang
def comps_at(th):
    g = collections.defaultdict(set)
    for j, w, x, y in top:
        if j >= th: g[x].add(y); g[y].add(x)
    seen = set(); res = []
    for n in g:
        if n in seen: continue
        st = [n]; seen.add(n); c = [n]
        while st:
            x = st.pop()
            for y in g[x]:
                if y not in seen: seen.add(y); st.append(y); c.append(y)
        res.append(c)
    return sorted(res, key=len, reverse=True)
for th in (0.04, 0.06, 0.08):
    cs = comps_at(th); out[f'komunitas_video_jaccard>={th}'] = [len(c) for c in cs[:5]]
# --- sentimen alat per kelompok akun (hanya yang dinilai)
def neg_rate(sel):
    sc = [r for r in sel if r['sentiment_label'] != 'abstain']
    if not sc: return None
    return len(sc), round(sum(r['sentiment_label'] == 'negatif' for r in sc) / len(sc) * 100, 1)
g1 = [r for r in rows if len(av[r['author_hash']]) == 1 and cm[r['author_hash']] == 1]
g2 = [r for r in rows if len(av[r['author_hash']]) >= 3]
g3 = [r for r in rows if 2 <= cm[r['author_hash']] and len(av[r['author_hash']]) == 1]
out['negatif_akun_sekali(n_dinilai,%)'] = neg_rate(g1)
out['negatif_akun_2plus_komentar_1video'] = neg_rate(g3)
out['negatif_akun_3plus_video'] = neg_rate(g2)
out['jumlah_komentar_kelompok'] = (len(g1), len(g3), len(g2))
print(json.dumps(out, ensure_ascii=False, indent=1))
