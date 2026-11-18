"""Percakapan publik tentang tiap lembaga pangan (komentar YouTube), 1 Agu - 31 Okt 2026, untuk C4.

Keputusan peneliti 18 Nov 2026: percakapan = komentar pada video yang MENYEBUT NAMA LEMBAGA
(kueri netral per lembaga), bukan isu pilihan peneliti. Hanya YouTube Data API v3 resmi.

- Video: terbit dalam jendela, judul/deskripsi memuat nama atau singkatan lembaga (`ALIAS`).
- Komentar: utas utama + balasan yang disertakan API (maks 5 per utas, tanpa panggilan
  tambahan), ditulis dalam jendela. Nama akun di-hash; teks disimpan lokal saja.
- Per lembaga paling banyak `MAX_VIDEOS` video dengan komentar terbanyak.
- Bisa dilanjutkan: hasil per video di <OUT>.parts/.

Pakai: YOUTUBE_API_KEY=... python3 -I skrip/collect_percakapan.py data_lokal/percakapan.json [batas_unit]
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KEY = os.environ["YOUTUBE_API_KEY"]
OUT = sys.argv[1]
BUDGET = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
PARTS = OUT + ".parts"
os.makedirs(PARTS, exist_ok=True)
WIB = timezone(timedelta(hours=7))
START = datetime(2026, 8, 1, tzinfo=WIB)
END = datetime(2026, 11, 1, tzinfo=WIB)
MAX_VIDEOS = 60
#: Paling banyak sekian halaman (100 utas) per video, supaya satu video raksasa tidak menghabiskan kuota.
MAX_PAGES = 10
SEARCH_PAGES = 3

AGENCIES = {
    "Kementan": ("Kementerian Pertanian", r"kementan|kementerian pertanian|menteri pertanian|\bmentan\b"),
    "KKP": ("Kementerian Kelautan dan Perikanan", r"\bkkp\b|kelautan dan perikanan"),
    "Kemenhut": ("Kementerian Kehutanan", r"kemenhut|kementerian kehutanan|menteri kehutanan|\bmenhut\b"),
    "BGN": ("Badan Gizi Nasional", r"badan gizi nasional|\bbgn\b"),
    "KLH/BPLH": ("Kementerian Lingkungan Hidup", r"kementerian lingkungan hidup|\bklh\b|\bbplh\b|menteri lingkungan hidup"),
    "Bapanas": ("Badan Pangan Nasional", r"badan pangan nasional|bapanas"),
}
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
            if e.code == 403 and "quota" in body.lower():
                print("KUOTA HABIS", file=sys.stderr)
                raise SystemExit(3)
            if attempt == 3 or e.code in (400, 404):
                print("HTTP", e.code, path, file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                print("ERR", path, type(e).__name__, file=sys.stderr)
                return None
            time.sleep(2)


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def h(name):
    return hashlib.sha256(("kinerja-pangan|" + (name or "")).encode()).hexdigest()[:12]


def row(c, vid, agency, kind):
    sn = c["snippet"]
    return dict(lembaga=agency, video_id=vid, comment_id=c["id"], type=kind,
                published_at=sn["publishedAt"], text=sn.get("textOriginal") or sn.get("textDisplay", ""),
                likes=int(sn.get("likeCount", 0)), author_hash=h(sn.get("authorDisplayName")),
                url=f"https://www.youtube.com/watch?v={vid}&lc={c['id']}")


VFILE = os.path.join(PARTS, "_videos.json")
if os.path.exists(VFILE):
    videos = json.load(open(VFILE))
else:
    videos = {}
    for agency, (query, alias) in AGENCIES.items():
        pat = re.compile(alias, re.I)
        found, tok = [], None
        for _ in range(SEARCH_PAGES):
            p = dict(part="snippet", type="video", q=f'"{query}"', maxResults=50, order="relevance",
                     publishedAfter=START.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     publishedBefore=END.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     regionCode="ID", relevanceLanguage="id")
            if tok:
                p["pageToken"] = tok
            d = get("search", **p)
            if not d:
                break
            found += [it["id"]["videoId"] for it in d.get("items", []) if it["id"].get("videoId")]
            tok = d.get("nextPageToken")
            if not tok:
                break
        kept = []
        for i in range(0, len(found), 50):
            d = get("videos", part="snippet,statistics", id=",".join(found[i:i + 50]))
            for it in (d or {}).get("items", []):
                sn, st = it["snippet"], it.get("statistics", {})
                if not pat.search(sn["title"] + " " + sn.get("description", "")):
                    continue
                kept.append(dict(lembaga=agency, video_id=it["id"], title=sn["title"],
                                 channel=sn["channelTitle"], published_at=sn["publishedAt"],
                                 comment_count=int(st.get("commentCount", 0))))
        kept.sort(key=lambda v: -v["comment_count"])
        videos[agency] = kept[:MAX_VIDEOS]
        print(agency, "kandidat", len(found), "relevan", len(kept), "dipakai", len(videos[agency]),
              "unit", units, file=sys.stderr)
    json.dump(videos, open(VFILE, "w"), ensure_ascii=False)

# Bergiliran antarlembaga (video ke-1 tiap lembaga, lalu ke-2, ...), supaya kuota terbagi rata.
queue = []
for rank in range(MAX_VIDEOS):
    for agency, vids in videos.items():
        if rank < len(vids):
            queue.append((agency, vids[rank]))
capped = []
stopped = False
for agency, v in queue:
    if True:
        vid = v["video_id"]
        part = os.path.join(PARTS, f"{agency.replace('/', '_')}__{vid}.json")
        if v["comment_count"] == 0 or os.path.exists(part):
            continue
        if units >= BUDGET:
            stopped = True
            break
        out, tok, ok, pages = [], None, True, 0
        while True:
            if pages >= MAX_PAGES:
                capped.append(vid)
                break
            pages += 1
            p = dict(part="snippet,replies", videoId=vid, maxResults=100, order="time", textFormat="plainText")
            if tok:
                p["pageToken"] = tok
            d = get("commentThreads", **p)
            if not d:
                ok = tok is None
                break
            for th in d.get("items", []):
                out.append(row(th["snippet"]["topLevelComment"], vid, agency, "komentar"))
                for r in th.get("replies", {}).get("comments", []):
                    out.append(row(r, vid, agency, "balasan"))
            tok = d.get("nextPageToken")
            if not tok:
                break
        if ok:
            json.dump(out, open(part, "w"), ensure_ascii=False)
        print(f"  {agency} {vid} {len(out)} komentar unit={units}", file=sys.stderr)

comments = []
for name in os.listdir(PARTS):
    if name.endswith(".json") and not name.startswith("_"):
        comments += json.load(open(os.path.join(PARTS, name)))
inwin = [c for c in comments if START <= ts(c["published_at"]) < END]
pending = sum(1 for a, vs in videos.items() for v in vs if v["comment_count"]
              and not os.path.exists(os.path.join(PARTS, f"{a.replace('/', '_')}__{v['video_id']}.json")))
json.dump(dict(window=[START.isoformat(), END.isoformat()], agencies={a: q for a, (q, _) in AGENCIES.items()},
               videos=videos, comments=inwin, videos_pending=pending, capped_this_run=capped, max_pages=MAX_PAGES, quota_units_this_run=units,
               collected_at=datetime.now(timezone.utc).isoformat()),
          open(OUT, "w"), ensure_ascii=False)
print("komentar dalam jendela:", len(inwin), "video belum:", pending, "unit:", units, file=sys.stderr)
