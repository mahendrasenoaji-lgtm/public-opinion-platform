"""Kumpulkan komentar YouTube tentang kelangkaan BBM di Bali, 11-20 Okt 2026 (WITA).

Hanya YouTube Data API v3 resmi. Video: diterbitkan dalam jendela + judul/deskripsi
menyebut Bali dan BBM. Komentar (termasuk balasan): ditulis dalam jendela.
Nama akun di-hash (sama dengan aturan platform), link per komentar disimpan.
"""
import hashlib, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

KEY = os.environ["YOUTUBE_API_KEY"]
OUT = sys.argv[1]
WITA = timezone(timedelta(hours=8))
START = datetime(2026, 10, 11, tzinfo=WITA)
END = datetime(2026, 10, 21, tzinfo=WITA)  # eksklusif => sampai 20 Okt 23:59 WITA
QUERIES = [
    "bbm langka bali", "kelangkaan bbm bali", "antrean spbu bali", "antre bbm bali",
    "pertalite bali langka", "ganjil genap spbu bali", "pertamina bali bbm",
    "koster bbm bali", "bahlil bbm bali", "krisis bbm bali", "spbu bali kosong",
    "bbm bali normal",
]
API = "https://www.googleapis.com/youtube/v3/"
units = 0


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
            if attempt == 3 or e.code in (400, 404):
                print("HTTP", e.code, path, body, file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                print("ERR", path, e, file=sys.stderr)
                return None
            time.sleep(2)


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def relevant(title, desc):
    t = (title + " " + desc).lower()
    return "bali" in t and re.search(r"bbm|pertalite|pertamax|spbu|bensin|solar|bahan bakar|pertamina", t)


# 1. Temukan video
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

# 2. Detail video + saring relevansi
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
print("video relevan:", len(kept), file=sys.stderr)


def h(name):
    return hashlib.sha256(("bbm-bali|" + (name or "")).encode()).hexdigest()[:12]


def row(c, vid, kind, parent=None):
    sn = c["snippet"]
    return dict(
        comment_id=c["id"], parent_id=parent, type=kind, video_id=vid,
        published_at=sn["publishedAt"], updated_at=sn.get("updatedAt"),
        text=sn.get("textOriginal") or sn.get("textDisplay", ""),
        likes=int(sn.get("likeCount", 0)), author_hash=h(sn.get("authorDisplayName")),
        url=f"https://www.youtube.com/watch?v={vid}&lc={c['id']}",
    )


# 3. Komentar + balasan
comments = []
for vid, v in kept.items():
    if v["comment_count"] == 0:
        continue
    tok, n = None, 0
    while True:
        p = dict(part="snippet,replies", videoId=vid, maxResults=100, order="time", textFormat="plainText")
        if tok:
            p["pageToken"] = tok
        d = get("commentThreads", **p)
        if not d:
            break
        for th in d.get("items", []):
            top = th["snippet"]["topLevelComment"]
            comments.append(row(top, vid, "komentar"))
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
                comments.append(row(r, vid, "balasan", top["id"]))
            n += 1
        tok = d.get("nextPageToken")
        if not tok:
            break
    print(f"  {vid} {n} utas", file=sys.stderr)

inwin = [c for c in comments if START <= ts(c["published_at"]) < END]
print("komentar total:", len(comments), "dalam jendela:", len(inwin), "unit kuota ~", units, file=sys.stderr)
json.dump(dict(window=[START.isoformat(), END.isoformat()], queries=QUERIES, videos=list(kept.values()),
               comments=inwin, comments_outside_window=len(comments) - len(inwin), quota_units=units,
               collected_at=datetime.now(timezone.utc).isoformat()),
          open(OUT, "w"), ensure_ascii=False, indent=1)
