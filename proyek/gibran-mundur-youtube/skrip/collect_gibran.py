"""Kumpulkan komentar YouTube tentang pengunduran diri Wapres Gibran, 10-17 Nov 2026 (WIB).

Hanya YouTube Data API v3 resmi. Video: terbit dalam jendela + judul/deskripsi menyebut
Gibran dan salah satu kata peristiwa (mundur, wapres, ijazah, pemakzulan, ...).
Komentar (termasuk balasan): ditulis dalam jendela. Nama akun di-hash, link per komentar disimpan.
Bisa dilanjutkan: hasil per video disimpan di <OUT>.parts/ sehingga run ulang melompati yang selesai.

Pakai: YOUTUBE_API_KEY=... python3 -I skrip/collect_gibran.py raw_youtube_api.json [batas_unit]
"""
import hashlib, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

KEY = os.environ["YOUTUBE_API_KEY"]
OUT = sys.argv[1]
BUDGET = int(sys.argv[2]) if len(sys.argv) > 2 else 6000  # unit kuota; kuota harian 10.000 dibagi dengan platform
PARTS = OUT + ".parts"
os.makedirs(PARTS, exist_ok=True)
WIB = timezone(timedelta(hours=7))
START = datetime(2026, 11, 10, tzinfo=WIB)
END = datetime(2026, 11, 18, tzinfo=WIB)  # eksklusif => sampai 17 Nov 23:59 WIB
QUERIES = [
    "gibran mundur", "pengunduran diri gibran", "gibran mengundurkan diri wapres",
    "gibran berhenti wakil presiden", "surat pengunduran diri gibran", "gibran mundur ijazah",
    "pemakzulan gibran", "hak menyatakan pendapat gibran dpr", "pengganti gibran wapres",
    "wapres baru pengganti gibran mpr", "prabowo gibran mundur", "jokowi gibran mundur",
    "gibran mundur reaksi", "wakil presiden kosong gibran",
]
API = "https://www.googleapis.com/youtube/v3/"
units = 0
PAT = re.compile(r"mundur|undur|berhenti|wapres|wakil presiden|makzul|ijazah|menyatakan pendapat|pengganti|lengser|mpr")


def get(path, **params):
    global units
    params["key"] = KEY
    url = API + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                units += 100 if path == "search" else 1
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            if e.code == 403 and "commentsDisabled" in body:
                return None
            if e.code == 403 and "quota" in body.lower():
                print("KUOTA HABIS", file=sys.stderr)
                raise SystemExit(3)
            if attempt == 3 or e.code in (400, 404):
                print("HTTP", e.code, path, re.sub(r"key=[^&\s\"]+", "key=***", body), file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                print("ERR", path, type(e).__name__, file=sys.stderr)
                return None
            time.sleep(2)


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def relevant(title, desc):
    t = (title + " " + desc).lower()
    return "gibran" in t and PAT.search(t)


def h(name):
    return hashlib.sha256(("gibran-mundur|" + (name or "")).encode()).hexdigest()[:12]


def row(c, vid, kind, parent=None):
    sn = c["snippet"]
    return dict(
        comment_id=c["id"], parent_id=parent, type=kind, video_id=vid,
        published_at=sn["publishedAt"], updated_at=sn.get("updatedAt"),
        text=sn.get("textOriginal") or sn.get("textDisplay", ""),
        likes=int(sn.get("likeCount", 0)), author_hash=h(sn.get("authorDisplayName")),
        url=f"https://www.youtube.com/watch?v={vid}&lc={c['id']}",
    )


# 1+2. Temukan video (disimpan, supaya run lanjutan tidak mencari ulang: 100 unit per panggilan)
VFILE = os.path.join(PARTS, "_videos.json")
if os.path.exists(VFILE):
    kept = json.load(open(VFILE))
else:
    videos = {}
    for q in QUERIES:
        tok = None
        for _ in range(2):  # maks 2 halaman x 50 per kueri
            p = dict(part="snippet", type="video", q=q, maxResults=50, order="relevance",
                     publishedAfter=START.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     publishedBefore=END.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     regionCode="ID", relevanceLanguage="id")
            if tok:
                p["pageToken"] = tok
            d = get("search", **p)
            if not d:
                break
            for it in d.get("items", []):
                vid = it["id"].get("videoId")
                if vid and vid not in videos:
                    videos[vid] = {"query": q}
            tok = d.get("nextPageToken")
            if not tok:
                break
    print("kandidat video:", len(videos), file=sys.stderr)
    ids = list(videos)
    kept = {}
    for i in range(0, len(ids), 50):
        d = get("videos", part="snippet,statistics", id=",".join(ids[i:i + 50]), maxResults=50)
        for it in (d or {}).get("items", []):
            sn, st = it["snippet"], it.get("statistics", {})
            if not relevant(sn["title"], sn.get("description", "")):
                continue
            kept[it["id"]] = dict(
                video_id=it["id"], title=sn["title"], channel=sn["channelTitle"],
                published_at=sn["publishedAt"], views=int(st.get("viewCount", 0)),
                comment_count=int(st.get("commentCount", 0)),
                url=f"https://www.youtube.com/watch?v={it['id']}", query=videos[it["id"]]["query"],
            )
    json.dump(kept, open(VFILE, "w"), ensure_ascii=False)
print("video relevan:", len(kept), "jumlah komentar menurut YouTube:",
      sum(v["comment_count"] for v in kept.values()), "unit sejauh ini:", units, file=sys.stderr)

# 3. Komentar + balasan, video paling ramai dulu
stopped = False
for vid, v in sorted(kept.items(), key=lambda kv: -kv[1]["comment_count"]):
    part = os.path.join(PARTS, vid + ".json")
    if v["comment_count"] == 0 or os.path.exists(part):
        continue
    if units >= BUDGET:
        stopped = True
        break
    out, tok, n, ok = [], None, 0, True
    while True:
        p = dict(part="snippet,replies", videoId=vid, maxResults=100, order="time", textFormat="plainText")
        if tok:
            p["pageToken"] = tok
        d = get("commentThreads", **p)
        if not d:
            ok = tok is None  # gagal di halaman pertama = komentar dimatikan; di tengah = belum lengkap
            break
        for th in d.get("items", []):
            top = th["snippet"]["topLevelComment"]
            out.append(row(top, vid, "komentar"))
            total = th["snippet"].get("totalReplyCount", 0)
            inline = th.get("replies", {}).get("comments", [])
            if total > len(inline):
                rt, inline = None, []
                while True:
                    rp = dict(part="snippet", parentId=top["id"], maxResults=100, textFormat="plainText")
                    if rt:
                        rp["pageToken"] = rt
                    rd = get("comments", **rp)
                    if not rd:
                        break
                    inline += rd.get("items", [])
                    rt = rd.get("nextPageToken")
                    if not rt:
                        break
            for r in inline:
                out.append(row(r, vid, "balasan", top["id"]))
            n += 1
        tok = d.get("nextPageToken")
        if not tok:
            break
    if ok:
        json.dump(out, open(part, "w"), ensure_ascii=False)
    print(f"  {vid} {n} utas {len(out)} komentar unit={units}{'' if ok else ' (TIDAK LENGKAP, tidak disimpan)'}", file=sys.stderr)

comments, done = [], 0
for vid in kept:
    part = os.path.join(PARTS, vid + ".json")
    if os.path.exists(part):
        done += 1
        comments += json.load(open(part))
inwin = [c for c in comments if START <= ts(c["published_at"]) < END]
pending = [vid for vid, v in kept.items() if v["comment_count"] and not os.path.exists(os.path.join(PARTS, vid + ".json"))]
print("video selesai:", done, "belum:", len(pending), "komentar total:", len(comments),
      "dalam jendela:", len(inwin), "unit run ini ~", units, file=sys.stderr)
json.dump(dict(window=[START.isoformat(), END.isoformat()], queries=QUERIES, videos=list(kept.values()),
               comments=inwin, comments_outside_window=len(comments) - len(inwin),
               videos_pending=pending, quota_units_this_run=units,
               collected_at=datetime.now(timezone.utc).isoformat()),
          open(OUT, "w"), ensure_ascii=False, indent=1)
