"""Olah raw.json -> XLSX, CSV, JSON unggahan platform, dan stats.json untuk laporan."""
import csv, json, os, re, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

# Penilai sentimen diambil dari apps/api di repo yang sama (proyek/bbm-bali-youtube/skrip -> ../../../apps/api).
sys.path.insert(0, os.environ.get("POP_API_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "apps", "api")))
from app.services.sentiment import INFORMAL_MODEL_VERSION, score  # noqa: E402  (penilai yang sama dengan platform)
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Font  # noqa: E402

RAW, OUT = sys.argv[1], sys.argv[2]
WITA = timezone(timedelta(hours=8))
d = json.load(open(RAW))
videos = {v["video_id"]: v for v in d["videos"]}

THEMES = {
    "Antrean & dampak harian": r"antr|ngantri|ngantre|berjam|jam an|mogok|dorong motor|jalan kaki|telat kerja|kerja",
    "Pertamina / distribusi": r"pertamina|depo|kapal|tanker|distribusi|pasokan|stok|logistik",
    "Pemerintah daerah (Koster/Pemprov)": r"koster|gubernur|pemprov|pemda|bupati|walikota|wali kota",
    "Pemerintah pusat (Bahlil/ESDM/Presiden)": r"bahlil|esdm|menteri|prabowo|presiden|pusat|dpr|puan",
    "Ganjil-genap / pembatasan": r"ganjil|genap|pembatasan|batas(an)? pembelian|kuota|barcode|qr",
    "Pariwisata & ekonomi": r"turis|wisata|wisatawan|tourist|ekonomi|usaha|dagang|ojol|ojek|driver|grab|gojek|nelayan|petani",
    "Sekolah/WFH daring": r"sekolah|daring|online|wfh|libur",
    "Pengecer / harga / penimbunan": r"eceran|pengecer|botol|pertamini|timbun|nimbun|harga|mahal|calo",
    "Curiga/teori konspirasi": r"sengaja|setting|settingan|skenario|pengalihan|konspirasi|naik(kan)? harga|mau naik",
    "Pertamax / jenis BBM lain": r"pertamax|solar|shell|bp |vivo|dexlite",
    "Permintaan maaf / sudah normal": r"maaf|normal|lancar|sudah aman|udah aman|terurai",
}

rows = []
for c in d["comments"]:
    t = datetime.fromisoformat(c["published_at"].replace("Z", "+00:00")).astimezone(WITA)
    s = score(c["text"], register="informal")
    v = videos[c["video_id"]]
    low = c["text"].lower()
    themes = [k for k, pat in THEMES.items() if re.search(pat, low)]
    rows.append({
        **c,
        "tanggal_wita": t.strftime("%Y-%m-%d"), "waktu_wita": t.strftime("%Y-%m-%d %H:%M"),
        "video_title": v["title"], "channel": v["channel"], "video_url": v["url"],
        "sentiment": s.score, "sentiment_label": s.label if s.score is not None else "abstain",
        "themes": "; ".join(themes),
    })
rows.sort(key=lambda r: r["published_at"])

# ---- statistik
by_day = defaultdict(lambda: Counter())
for r in rows:
    by_day[r["tanggal_wita"]]["n"] += 1
    by_day[r["tanggal_wita"]][r["sentiment_label"]] += 1
    if r["sentiment"] is not None:
        by_day[r["tanggal_wita"]]["sum"] += r["sentiment"]
days = []
start = datetime(2026, 10, 11)
for i in range(10):
    k = (start + timedelta(days=i)).strftime("%Y-%m-%d")
    c = by_day[k]
    scored = c["positif"] + c["negatif"] + c["netral"]
    days.append(dict(date=k, n=c["n"], positif=c["positif"], negatif=c["negatif"], netral=c["netral"],
                     abstain=c["abstain"], mean=round(c["sum"] / scored, 3) if scored else None))
theme_counts = Counter(t for r in rows for t in r["themes"].split("; ") if t)
theme_sent = {}
for k in THEMES:
    sc = [r["sentiment"] for r in rows if k in r["themes"] and r["sentiment"] is not None]
    theme_sent[k] = dict(n=theme_counts[k], scored=len(sc), mean=round(sum(sc) / len(sc), 3) if sc else None)
per_video = Counter(r["video_id"] for r in rows)
top_videos = [dict(**{k: videos[v][k] for k in ("title", "channel", "url", "published_at", "views")}, comments_in_window=n)
              for v, n in per_video.most_common(15)]
labels = Counter(r["sentiment_label"] for r in rows)
top_liked = sorted(rows, key=lambda r: -r["likes"])[:40]
stats = dict(
    window=d["window"], collected_at=d["collected_at"], queries=d["queries"], quota_units=d["quota_units"],
    videos_found=len(videos), videos_with_comments=len(per_video), comments=len(rows),
    top_level=sum(r["type"] == "komentar" for r in rows), replies=sum(r["type"] == "balasan" for r in rows),
    outside_window=d["comments_outside_window"], unique_authors=len({r["author_hash"] for r in rows}),
    model_version=INFORMAL_MODEL_VERSION, labels=dict(labels), days=days, themes=theme_sent, top_videos=top_videos,
    top_liked=[{k: r[k] for k in ("waktu_wita", "text", "likes", "sentiment_label", "url", "video_title", "channel", "themes")} for r in top_liked],
    by_day_samples={},
)
# contoh per hari: 4 komentar paling disukai
for day in days:
    rs = sorted([r for r in rows if r["tanggal_wita"] == day["date"]], key=lambda r: -r["likes"])[:4]
    stats["by_day_samples"][day["date"]] = [{k: r[k] for k in ("waktu_wita", "text", "likes", "sentiment_label", "url", "channel")} for r in rs]
json.dump(stats, open(f"{OUT}/stats.json", "w"), ensure_ascii=False, indent=1)

# ---- CSV + XLSX
cols = ["waktu_wita", "type", "text", "likes", "sentiment", "sentiment_label", "themes", "url",
        "video_title", "channel", "video_url", "comment_id", "parent_id", "author_hash", "published_at"]
with open(f"{OUT}/komentar_youtube_bbm_bali_11-20okt2026.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

wb = Workbook()
ws = wb.active
ws.title = "Komentar"
ws.append(["Waktu (WITA)", "Jenis", "Komentar", "Suka", "Skor sentimen", "Label", "Tema", "Link komentar",
           "Judul video", "Kanal", "Link video", "ID komentar", "ID induk", "Akun (hash)", "Waktu (UTC)"])
for r in rows:
    ws.append([r[k] for k in cols])
    ws.cell(ws.max_row, 8).hyperlink = r["url"]
    ws.cell(ws.max_row, 11).hyperlink = r["video_url"]
vs = wb.create_sheet("Video")
vs.append(["Judul", "Kanal", "Terbit (UTC)", "Ditonton", "Komentar total", "Komentar dalam jendela", "Link", "Kueri penemu"])
for v in sorted(videos.values(), key=lambda v: -per_video.get(v["video_id"], 0)):
    vs.append([v["title"], v["channel"], v["published_at"], v["views"], v["comment_count"], per_video.get(v["video_id"], 0), v["url"], v["query"]])
    vs.cell(vs.max_row, 7).hyperlink = v["url"]
hs = wb.create_sheet("Harian")
hs.append(["Tanggal (WITA)", "Komentar", "Positif", "Negatif", "Netral", "Abstain", "Rata-rata skor"])
for day in days:
    hs.append([day["date"], day["n"], day["positif"], day["negatif"], day["netral"], day["abstain"], day["mean"]])
ms = wb.create_sheet("Metode")
for line in [
    "Sumber: YouTube Data API v3 resmi (search.list, videos.list, commentThreads.list, comments.list).",
    "Jendela: 11 Okt 2026 00:00 WITA s.d. 20 Okt 2026 23:59 WITA (awal kelangkaan s.d. pernyataan pasokan normal oleh pemerintah 19 Okt + 1 hari).",
    "Video: diterbitkan dalam jendela, ditemukan lewat kueri di bawah, judul/deskripsi menyebut Bali dan BBM/SPBU/Pertamina.",
    "Kueri: " + "; ".join(d["queries"]),
    "Komentar: semua komentar dan balasan pada video tersebut, disaring menurut waktu tulis dalam jendela.",
    "Nama akun tidak disimpan; diganti hash (12 karakter) agar tetap bisa menghitung akun unik.",
    f"Sentimen: penilai leksikon ragam informal platform Public Opinion ({INFORMAL_MODEL_VERSION}). Abstain = tak ada kata penanda.",
    "Batas: komentar YouTube self-selected, tidak mewakili warga Bali; urutan pencarian ditentukan YouTube; nada ≠ sikap; sarkasme sering salah baca.",
    f"Dikumpulkan: {d['collected_at']} — kuota API ~{d['quota_units']} unit.",
]:
    ms.append([line])
for sh in wb.worksheets:
    for cell in sh[1]:
        cell.font = Font(bold=True)
ws.column_dimensions["C"].width = 80
wb.save(f"{OUT}/komentar_youtube_bbm_bali_11-20okt2026.xlsx")

# ---- JSON unggahan platform
items = [dict(external_id=r["comment_id"], text=r["text"], published_at=r["published_at"], url=r["url"],
              author_handle=r["author_hash"], engagement=r["likes"],
              conversation_id=r["parent_id"] or r["comment_id"]) for r in rows if r["text"].strip()]
json.dump(dict(connector="youtube_api", source="SOCIAL", items=items),
          open(f"{OUT}/unggah_platform_bbm_bali.json", "w"), ensure_ascii=False)
print(json.dumps({k: stats[k] for k in ("videos_found", "videos_with_comments", "comments", "top_level", "replies", "outside_window", "unique_authors", "labels")}, ensure_ascii=False))
print(json.dumps(days))
print(json.dumps(theme_sent, ensure_ascii=False))
