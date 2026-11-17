"""O4 (median tayangan) dan O5 (engagement per pelanggan) kanal YouTube resmi, satu bulan kalender.

Hanya YouTube Data API v3 resmi, hanya angka yang tampil publik. Video dihitung bila TERBIT
dalam bulan itu (WIB). Angka tayangan/suka/komentar adalah angka saat diambil (`captured_at`),
bukan angka akhir bulan; video yang terbit di akhir bulan sempat ditonton lebih singkat.

O5 versi publik: (suka + komentar) / pelanggan per video, lalu median. YouTube tidak
menampilkan jumlah bagikan, jadi "share" tidak ikut (berbeda dari rumus di kerangka bagian 5.3).
Median ditahan bila video kurang dari 5 (sama dengan MIN_POSTS_FOR_MEDIAN di platform).

Pakai: YOUTUBE_API_KEY=... python3 -I skrip/youtube_bulanan.py 2026-10 data/
"""
import csv
import json
import os
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KEY = os.environ["YOUTUBE_API_KEY"]
MONTH, OUT = sys.argv[1], sys.argv[2]
WIB = timezone(timedelta(hours=7))
year, month = map(int, MONTH.split("-"))
START = datetime(year, month, 1, tzinfo=WIB)
END = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=WIB)
MIN_POSTS = 5

#: Lembaga -> handle kanal resmi (diambil dari situs .go.id tiap lembaga, 14 Nov 2026).
CHANNELS = {
    "Kementan": "@kementanri",
    "KKP": "@kkp_ri",
    "Kemenhut": "@kemenhut_ri",
    "BGN": "@badangizinasional",
    "KLH/BPLH": "@klh-bplh",
    "Bapanas": "@badanpangannasionalofficial",
}
units = 0


def get(path, **params):
    global units
    params["key"] = KEY
    url = "https://www.googleapis.com/youtube/v3/" + path + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        units += 1
        return json.load(r)


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


os.makedirs(OUT, exist_ok=True)
captured = datetime.now(timezone.utc)
summary, videos_out = [], []
for agency, handle in CHANNELS.items():
    ch = get("channels", part="contentDetails,statistics", forHandle=handle)["items"][0]
    subs = int(ch["statistics"].get("subscriberCount", 0)) or None
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, tok = [], None
    while True:  # daftar unggahan terbaru dulu; berhenti begitu lewat awal bulan
        p = dict(part="contentDetails", playlistId=uploads, maxResults=50)
        if tok:
            p["pageToken"] = tok
        d = get("playlistItems", **p)
        older = False
        for it in d.get("items", []):
            at = ts(it["contentDetails"]["videoPublishedAt"])
            if START <= at < END:
                ids.append(it["contentDetails"]["videoId"])
            elif at < START:
                older = True
        tok = d.get("nextPageToken")
        if older or not tok:
            break
    rows = []
    for i in range(0, len(ids), 50):
        for v in get("videos", part="snippet,statistics", id=",".join(ids[i:i + 50]))["items"]:
            st = v["statistics"]
            views = int(st["viewCount"]) if "viewCount" in st else None
            likes = int(st["likeCount"]) if "likeCount" in st else None
            comments = int(st["commentCount"]) if "commentCount" in st else None
            er = (likes or 0) + (comments or 0)
            rows.append(dict(
                lembaga=agency, kanal=handle, video_id=v["id"], judul=v["snippet"]["title"],
                terbit_wib=ts(v["snippet"]["publishedAt"]).astimezone(WIB).isoformat(),
                tayangan=views, suka=likes, komentar=comments, pelanggan=subs,
                er_per_pelanggan=round(er / subs, 6) if subs and likes is not None else None,
                url=f"https://www.youtube.com/watch?v={v['id']}",
            ))
    views = [r["tayangan"] for r in rows if r["tayangan"] is not None]
    ers = [r["er_per_pelanggan"] for r in rows if r["er_per_pelanggan"] is not None]
    summary.append(dict(
        lembaga=agency, kanal=handle, pelanggan=subs, video=len(rows),
        median_tayangan=statistics.median(views) if len(views) >= MIN_POSTS else None,
        median_er_per_pelanggan=round(statistics.median(ers), 6) if len(ers) >= MIN_POSTS else None,
    ))
    videos_out += rows

meta = dict(bulan=MONTH, captured_at=captured.isoformat(), quota_units=units,
            catatan="angka publik saat diambil; share tidak tersedia di YouTube")
json.dump(dict(meta=meta, ringkasan=summary), open(f"{OUT}/youtube_{MONTH}_ringkasan.json", "w"),
          ensure_ascii=False, indent=1)
with open(f"{OUT}/youtube_{MONTH}_video.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(videos_out[0]) if videos_out else ["lembaga"])
    w.writeheader()
    w.writerows(videos_out)
print(json.dumps(dict(meta=meta, ringkasan=summary), ensure_ascii=False, indent=1))
