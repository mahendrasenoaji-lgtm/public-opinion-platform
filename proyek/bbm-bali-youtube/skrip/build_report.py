import html, json, sys

s = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
e = html.escape

DAYS_ID = {"2026-10-11": "Min 11", "2026-10-12": "Sen 12", "2026-10-13": "Sel 13", "2026-10-14": "Rab 14",
           "2026-10-15": "Kam 15", "2026-10-16": "Jum 16", "2026-10-17": "Sab 17", "2026-10-18": "Min 18",
           "2026-10-19": "Sen 19", "2026-10-20": "Sel 20"}
EVENTS = {
    "2026-10-12": "Antrean mulai dilaporkan; Gubernur Koster memanggil Pertamina",
    "2026-10-13": "Pertamina menyebut kendala bongkar muat kapal; disepakati 92 SPBU buka 24 jam",
    "2026-10-14": "Antrean sampai 3 km, warga pingsan; Dirut Pertamina minta maaf; Presiden menggelar rapat terbatas",
    "2026-10-15": "Video Gubernur Koster diprotes petugas SPBU beredar; sekolah daring dan WFH di beberapa daerah",
    "2026-10-16": "Ganjil-genap pembelian BBM diumumkan untuk 17–19 Okt",
    "2026-10-17": "Ganjil-genap mulai berlaku",
    "2026-10-19": "Menteri ESDM Bahlil: distribusi normal, cadangan dinaikkan ke 15 hari; ganjil-genap diperpanjang",
}

# ---------- chart: volume harian (batang) + rata-rata skor (titik)
days = s["days"]
W, H, PL, PR, PT, PB = 760, 300, 56, 56, 24, 46
iw, ih = W - PL - PR, H - PT - PB
vmax = 12000
bw = iw / len(days)
svg = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Volume komentar harian dan rata-rata skor sentimen, 11–20 Oktober 2026">']
for v in range(0, vmax + 1, 3000):
    y = PT + ih - ih * v / vmax
    svg.append(f'<line x1="{PL}" x2="{W-PR}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
    svg.append(f'<text x="{PL-8}" y="{y+4:.1f}" class="ax" text-anchor="end">{v:,}</text>'.replace(",", "."))
# sumbu kanan sentimen 0 .. -0.5 (informal-2: 12 Okt rata-rata -0,42)
AX = 0.5
for v in (0, -0.1, -0.2, -0.3, -0.4, -0.5):
    y = PT + ih * (-v) / AX
    lbl = "0" if v == 0 else f"{v:.1f}".replace(".", ",").replace("-", "−")
    svg.append(f'<text x="{W-PR+8}" y="{y+4:.1f}" class="ax sx">{lbl}</text>')
pts = []
for i, d in enumerate(days):
    x = PL + i * bw
    h = ih * d["n"] / vmax
    neg_h = ih * d["negatif"] / vmax
    svg.append(f'<rect x="{x+6:.1f}" y="{PT+ih-h:.1f}" width="{bw-12:.1f}" height="{h:.1f}" class="bar"><title>{DAYS_ID[d["date"]]} Okt: {d["n"]} komentar</title></rect>')
    svg.append(f'<rect x="{x+6:.1f}" y="{PT+ih-neg_h:.1f}" width="{bw-12:.1f}" height="{neg_h:.1f}" class="barneg"><title>{d["negatif"]} dinilai negatif</title></rect>')
    if d["n"]:
        svg.append(f'<text x="{x+bw/2:.1f}" y="{PT+ih-h-6:.1f}" class="val" text-anchor="middle">{d["n"]:,}</text>'.replace(",", "."))
    svg.append(f'<text x="{x+bw/2:.1f}" y="{H-PB+18:.1f}" class="ax" text-anchor="middle">{DAYS_ID[d["date"]]}</text>')
    if d["mean"] is not None:
        pts.append((x + bw / 2, PT + ih * (-d["mean"]) / AX, d["mean"]))
svg.append('<polyline class="line" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts) + '"/>')
for x, y, m in pts:
    svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" class="dot"><title>rata-rata skor {m:+.3f}</title></circle>')
svg.append(f'<text x="{PL}" y="{H-6}" class="ax">Komentar per hari (WITA)</text>')
svg.append(f'<text x="{W-PR+48}" y="{H-6}" class="ax sx" text-anchor="end">Rata-rata skor</text>')
svg.append("</svg>")
chart = "\n".join(svg)

def n(x):
    return f"{x:,}".replace(",", ".")

def pct(a, b):
    return f"{100*a/b:.0f}%".replace(".", ",") if b else "–"

lab = s["labels"]
scored = lab.get("positif", 0) + lab.get("negatif", 0) + lab.get("netral", 0)
MODEL = s.get("model_version", "lexicon-id-1+informal-1")  # stats lama (5 Nov) belum mencatat versi


def fmt(x):
    return f"{x:+.2f}".replace(".", ",").replace("-", "−")


# Narasi yang bergantung angka dibuat dari data, bukan ditulis tangan: kisaran skor harian
# (hari dengan >= 300 komentar) dan tema yang skornya positif berubah bila penilai berubah.
big = [d["mean"] for d in days if d["n"] >= 300 and d["mean"] is not None]
range_txt = f"−{abs(max(big)):.2f} sampai −{abs(min(big)):.2f}".replace(".", ",")
pos_themes = [k for k, v in s["themes"].items() if v["mean"] is not None and v["mean"] > 0]
closest = max((kv for kv in s["themes"].items() if kv[1]["mean"] is not None), key=lambda kv: kv[1]["mean"])
if pos_themes:
    theme_txt = "Satu-satunya tema dengan skor rata-rata positif adalah " + ", ".join(pos_themes) + "."
else:
    theme_txt = (f"Tidak ada tema yang skor rata-ratanya positif; yang paling dekat ke netral adalah "
                 f"“{closest[0]}” ({fmt(closest[1]['mean'])}).")

timeline = []
for d in days:
    ev = EVENTS.get(d["date"])
    samples = s["by_day_samples"].get(d["date"], [])
    seen, items = set(), []
    for r in samples:
        if r["text"] in seen:
            continue
        seen.add(r["text"])
        items.append(f'<li><q>{e(r["text"][:240])}</q> <span class="meta">{n(r["likes"])} suka · {e(r["channel"])} · <a href="{e(r["url"])}" target="_blank" rel="noopener">lihat komentar</a></span></li>')
    timeline.append(f'''<li class="day">
  <div class="dhead"><span class="ddate">{DAYS_ID[d["date"]]} Okt</span><span class="dn">{n(d["n"])} komentar</span>{f'<span class="dm">skor {d["mean"]:+.2f}</span>'.replace(".", ",") if d["mean"] is not None else ""}</div>
  {f'<p class="ev">{e(ev)}</p>' if ev else ""}
  {"<ul class='qs'>" + "".join(items) + "</ul>" if items else "<p class='none'>Belum ada video tentang krisis yang terbit hari ini, jadi belum ada komentar.</p>"}
</li>''')

themes = sorted(s["themes"].items(), key=lambda kv: -kv[1]["n"])
tmax = themes[0][1]["n"]
theme_rows = "".join(
    f'<tr><td>{e(k)}</td><td class="num">{n(v["n"])}</td><td class="barcell"><span style="width:{100*v["n"]/tmax:.1f}%"></span></td><td class="num">{(f"{v["mean"]:+.2f}").replace(".", ",") if v["mean"] is not None else "–"}</td></tr>'
    for k, v in themes)

vid_rows = "".join(
    f'<tr><td><a href="{e(v["url"])}" target="_blank" rel="noopener">{e(v["title"])}</a><div class="meta">{e(v["channel"])} · terbit {v["published_at"][:10]} · {n(v["views"])} tayangan</div></td><td class="num">{n(v["comments_in_window"])}</td></tr>'
    for v in s["top_videos"][:12])

liked, seen = [], set()
for r in s["top_liked"]:
    if r["text"] in seen:
        continue
    seen.add(r["text"])
    liked.append(f'<li><q>{e(r["text"][:260])}</q><span class="meta">{n(r["likes"])} suka · {r["waktu_wita"]} WITA · label: {r["sentiment_label"]} · <a href="{e(r["url"])}" target="_blank" rel="noopener">lihat komentar</a></span></li>')
    if len(liked) == 12:
        break

page = f'''<title>BBM Bali di Kolom YouTube</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo+Narrow:wght@500;700&family=Source+Sans+3:wght@400;600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* Layout: satu kolom laporan, papan angka ala papan harga SPBU di atas, linimasa harian sebagai tulang punggung */
:root {{
  --bg: #f6f6f3; --surface: #ffffff; --ink: #1d2124; --muted: #5d656b; --line: #dcdfd9;
  --social: #c4501b; --social-soft: #f6d9c9; --neg: #8f2d1a; --accent: #0f6b5c;
  --display: "Archivo Narrow", "Arial Narrow", system-ui, sans-serif;
  --body: "Source Sans 3", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, Menlo, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #15181a; --surface: #1d2124; --ink: #e8eae6; --muted: #a0a8ad; --line: #30363a;
  --social: #ff8a55; --social-soft: #4a2a1b; --neg: #ff9b84; --accent: #5fc9b4; color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #15181a; --surface: #1d2124; --ink: #e8eae6; --muted: #a0a8ad; --line: #30363a;
  --social: #ff8a55; --social-soft: #4a2a1b; --neg: #ff9b84; --accent: #5fc9b4; color-scheme: dark; }}
body {{ background: var(--bg); color: var(--ink); font: 17px/1.55 var(--body); }}
.wrap {{ max-width: 860px; margin: 0 auto; padding-block: 40px 64px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); display: grid; gap: 44px; }}
h1, h2 {{ font-family: var(--display); font-weight: 700; text-wrap: balance; margin: 0; letter-spacing: -0.01em; }}
h1 {{ font-size: clamp(2rem, 6vw, 3.1rem); line-height: 1.05; }}
h2 {{ font-size: 1.6rem; }}
.eyebrow {{ font: 600 0.78rem/1 var(--mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--social); }}
.lede {{ max-width: 65ch; color: var(--muted); margin: 0; }}
header {{ display: grid; gap: 14px; }}
a {{ color: var(--accent); }}
a:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.board {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1px; background: var(--line); border: 1px solid var(--line); }}
.board div {{ background: var(--surface); padding: 14px 16px; display: grid; gap: 4px; }}
.board b {{ font: 600 1.7rem/1.1 var(--mono); font-variant-numeric: tabular-nums; }}
.board span {{ font-size: 0.86rem; color: var(--muted); }}
section {{ display: grid; gap: 16px; min-width: 0; }}
section > p {{ margin: 0; max-width: 65ch; }}
.chart {{ background: var(--surface); border: 1px solid var(--line); padding: 12px; overflow-x: auto; }}
.chart svg {{ min-width: 560px; width: 100%; height: auto; display: block; }}
.grid {{ stroke: var(--line); stroke-width: 1; }}
.ax {{ fill: var(--muted); font: 11px var(--mono); }}
.sx {{ fill: var(--ink); }}
.val {{ fill: var(--ink); font: 600 11px var(--mono); }}
.bar {{ fill: var(--social-soft); }}
.barneg {{ fill: var(--social); }}
.line {{ fill: none; stroke: var(--ink); stroke-width: 1.5; }}
.dot {{ fill: var(--ink); }}
.legend {{ display: flex; flex-wrap: wrap; gap: 18px; font-size: 0.86rem; color: var(--muted); }}
.legend i {{ display: inline-block; width: 12px; height: 12px; vertical-align: -1px; margin-right: 6px; }}
ol.tl {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 0; border-left: 2px solid var(--line); }}
.day {{ padding: 0 0 26px 20px; position: relative; display: grid; gap: 8px; }}
.day::before {{ content: ""; position: absolute; left: -7px; top: 6px; width: 12px; height: 12px; border-radius: 50%; background: var(--social); }}
.dhead {{ display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: baseline; }}
.ddate {{ font: 700 1.2rem var(--display); }}
.dn, .dm {{ font: 0.85rem var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; }}
.ev {{ margin: 0; font-weight: 600; }}
.qs, .liked {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }}
q {{ quotes: "“" "”"; display: block; }}
.meta {{ display: block; font-size: 0.82rem; color: var(--muted); }}
.none {{ margin: 0; color: var(--muted); font-style: italic; }}
.tbl-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.95rem; }}
th {{ text-align: left; font: 600 0.75rem var(--mono); letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); padding: 8px 10px; border-bottom: 1px solid var(--ink); }}
td {{ padding: 9px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
.num {{ text-align: right; font-family: var(--mono); font-variant-numeric: tabular-nums; white-space: nowrap; }}
.barcell {{ width: 30%; min-width: 90px; }}
.barcell span {{ display: block; height: 10px; background: var(--social); margin-top: 6px; }}
.note {{ background: var(--surface); border: 1px solid var(--line); padding: 16px 18px; display: grid; gap: 8px; }}
.note ul {{ margin: 0; padding-left: 20px; display: grid; gap: 6px; }}
code {{ font-family: var(--mono); font-size: 0.88em; }}
</style>
<div class="wrap">
<header>
  <div class="eyebrow">Komentar YouTube · 11–20 Oktober 2026</div>
  <h1>Kelangkaan BBM di Bali, menurut kolom komentar YouTube</h1>
  <p class="lede">{n(s["comments"])} komentar dan balasan yang ditulis selama sepuluh hari, dari antrean pertama di SPBU sampai pemerintah menyatakan pasokan normal. Sumbernya hanya YouTube; pemberitaan media tidak dihitung. Setiap kutipan bisa dibuka langsung di YouTube lewat tautannya.</p>
</header>

<div class="board" aria-label="Ringkasan angka">
  <div><b>{n(s["comments"])}</b><span>komentar dalam jendela</span></div>
  <div><b>{n(s["videos_with_comments"])}</b><span>video yang dikomentari (dari {n(s["videos_found"])})</span></div>
  <div><b>{n(s["unique_authors"])}</b><span>akun berbeda</span></div>
  <div><b>{pct(lab.get("negatif",0), scored)}</b><span>negatif, dari {n(scored)} komentar yang bisa dinilai ({pct(scored, s["comments"])} dari semua)</span></div>
</div>

<section>
  <h2>Percakapan memuncak pada 15 Oktober</h2>
  <p>Sepertiga komentar ({pct(days[4]["n"], s["comments"])}) ditulis pada Kamis 15 Oktober, hari ketika video Gubernur Koster diprotes petugas SPBU beredar. Sejak itu volume turun setiap hari. Rata-rata skor sentimen (hanya komentar yang dinilai alat) bertahan negatif di kisaran {range_txt} pada hari-hari dengan ratusan komentar atau lebih, termasuk setelah pemerintah menyatakan pasokan normal.</p>
  <div class="chart">{chart}</div>
  <div class="legend"><span><i style="background:var(--social-soft)"></i>semua komentar</span><span><i style="background:var(--social)"></i>dinilai negatif</span><span><i style="background:var(--ink);height:3px;vertical-align:3px"></i>rata-rata skor (sumbu kanan, hanya komentar yang bisa dinilai)</span></div>
</section>

<section>
  <h2>Hari demi hari</h2>
  <p>Peristiwa diambil dari judul video berita pada hari itu, hanya sebagai penanda waktu. Kutipan adalah komentar dengan suka terbanyak pada hari itu.</p>
  <ol class="tl">{"".join(timeline)}</ol>
</section>

<section>
  <h2>Siapa yang disorot</h2>
  <p>Tema ditandai dari kata kunci di teks komentar. Satu komentar bisa masuk lebih dari satu tema, dan sebagian besar komentar tidak masuk tema mana pun. Komentar yang menyebut pemerintah daerah lebih banyak daripada yang menyebut Pertamina. {theme_txt}</p>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Tema</th><th class="num">Komentar</th><th></th><th class="num">Skor rata-rata</th></tr></thead>
    <tbody>{theme_rows}</tbody>
  </table></div>
</section>

<section>
  <h2>Video dengan komentar terbanyak</h2>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Video</th><th class="num">Komentar 11–20 Okt</th></tr></thead>
    <tbody>{vid_rows}</tbody>
  </table></div>
</section>

<section>
  <h2>Komentar yang paling banyak disukai</h2>
  <p>Perhatikan label sentimennya. Komentar teratas, “hebat nih Gubenur”, dinilai positif oleh leksikon padahal jelas sindiran. Karena itu angka sentimen di halaman ini adalah perkiraan nada kasar, bukan ukuran sikap.</p>
  <ul class="liked">{"".join(liked)}</ul>
</section>

<section>
  <h2>Akun organik atau buzzer?</h2>
  <p>Dari komentar saja, satu akun tidak bisa dipastikan buzzer atau bukan. YouTube tidak membuka siapa yang membayar atau mengatur sebuah akun. Yang bisa diukur adalah pola yang biasanya muncul pada kampanye terkoordinasi, dihitung untuk seluruh data tanpa menunjuk akun tertentu.</p>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Pola yang diperiksa</th><th class="num">Hasil</th><th>Bacaan</th></tr></thead>
    <tbody>
      <tr><td>Akun yang hanya berkomentar sekali</td><td class="num">16.912 akun (74%)</td><td>Sebagian besar pengomentar datang sekali, pola khas percakapan organik.</td></tr>
      <tr><td>Porsi komentar dari 20 akun paling aktif</td><td class="num">1,8%</td><td>Tidak ada segelintir akun yang mendominasi. 1% akun teraktif menulis 9% komentar.</td></tr>
      <tr><td>Teks sama persis (≥30 huruf) dari 3 akun atau lebih</td><td class="num">0</td><td>Tanda paling umum kampanye salin-tempel tidak ditemukan.</td></tr>
      <tr><td>Teks sama persis (≥40 huruf) dari 2 akun</td><td class="num">3 teks</td><td>Ketiganya pesan menenangkan, mis. “jangan sampai terprovokasi isu negatif ya guys ingat stok bbm aman”. Jumlahnya terlalu kecil untuk disebut kampanye.</td></tr>
      <tr><td>Akun yang mengulang teks yang sama ≥3 kali</td><td class="num">104 akun · 1.001 komentar</td><td>Ada yang menyebar satu narasi berulang, mis. satu akun menulis “pengurangan jatah bergilir… terstruktur dan terencana” puluhan kali di 8 video.</td></tr>
      <tr><td>Akun dengan ≥10 komentar dalam satu jam</td><td class="num">32 akun</td><td>Bisa berarti akun yang sedang berdebat di utas balasan, bisa juga akun yang menyebar pesan. Perlu dibaca manual.</td></tr>
      <tr><td>Akun yang muncul di ≥20 video berbeda</td><td class="num">19 akun</td><td>Pengomentar sangat aktif lintas video; aktif tidak sama dengan dibayar.</td></tr>
    </tbody>
  </table></div>
  <p>Kesimpulan: percakapan ini tampak didominasi komentar organik. Ada sekelompok kecil akun yang sangat aktif dan mengulang pesan (sekitar 3% komentar). Itu layak ditinjau manual, tetapi belum cukup untuk menyebut mereka buzzer. Pemeriksaan yang lebih kuat butuh data profil kanal (tanggal dibuat, jumlah video, pola nama), yang tidak ikut disimpan di data ini.</p>
</section>

<section class="note">
  <h2>Cara data diambil dan batasnya</h2>
  <ul>
    <li>YouTube Data API v3 resmi. {len(s["queries"])} kata kunci pencarian (mis. <code>bbm langka bali</code>, <code>antrean spbu bali</code>, <code>ganjil genap spbu bali</code>, <code>bahlil bbm bali</code>). Video yang diambil hanya yang terbit 11–20 Okt dan judul atau deskripsinya menyebut Bali dan BBM/SPBU/Pertamina.</li>
    <li>Diambil semua komentar dan balasan pada video itu, lalu disaring menurut waktu tulis: 11 Okt 00:00 sampai 20 Okt 23:59 WITA. {n(s["outside_window"])} komentar yang ditulis sesudah 20 Okt dibuang.</li>
    <li>Tidak ada komentar pada 11 Okt karena video pertama tentang krisis baru terbit 12 Okt. Penurunan menjelang 20 Okt sebagian karena video yang terbit sesudah 20 Okt tidak ikut diambil.</li>
    <li>Nama akun tidak disimpan. Diganti kode acak supaya jumlah akun berbeda tetap bisa dihitung.</li>
    <li>Sentimen dinilai dengan penilai leksikon ragam informal milik platform Public Opinion (<code>{MODEL}</code>). {pct(lab.get("abstain",0), s["comments"])} komentar tidak bisa dinilai. Sarkasme sering terbaca positif, dan nada tidak sama dengan sikap.</li>
    <li>Komentator YouTube memilih sendiri untuk berkomentar. Mereka tidak mewakili warga Bali, dan urutan hasil pencarian ditentukan algoritma YouTube.</li>
    <li>Tidak ada klaim sebab-akibat. Peristiwa dan lonjakan komentar hanya terjadi pada waktu yang sama.</li>
  </ul>
  <p class="meta">Dikumpulkan {s["collected_at"][:16].replace("T", " ")} UTC. Data lengkap (Excel/CSV, satu baris per komentar dengan tautan) ada di folder <code>~/Documents/bbm-bali-youtube</code> dan di proyek “KELANGKAAN BBM BALI (YouTube 11-20 Okt 2026)” pada platform Public Opinion.</p>
</section>
</div>
'''
open(OUT, "w").write(page)
print("ok", len(page))
