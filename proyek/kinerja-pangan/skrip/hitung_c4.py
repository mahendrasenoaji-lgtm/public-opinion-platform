"""C4 per lembaga dengan fungsi platform `comm_flow.response_time` (definisi yang sama dengan /kinerja/analisis).

Percakapan: komentar YouTube publik pada video yang menyebut nama lembaga (skrip/collect_percakapan.py),
1 Agu - 31 Okt 2026, TANPA video dari kanal yang dikelola lembaga itu sendiri atau unitnya: komentar di
sana memuncak karena lembaga mengunggah, sehingga lonjakan -> tanggapan menjadi melingkar.
Pernyataan resmi: unggahan kanal YouTube resmi lembaga (data/youtube_2026-08..10 + data_lokal/youtube_2026-11
untuk batas 72 jam sesudah lonjakan akhir Oktober). Situs resmi tidak dipakai karena butirnya hanya November.

Pakai (dengan Python yang bisa mengimpor apps/api):
  python skrip/hitung_c4.py data_lokal/percakapan.json data/c4_per_lembaga.json
"""
import csv
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "apps", "api"))
from app.services.comm_flow import response_time  # noqa: E402

SRC, OUT = sys.argv[1], sys.argv[2]
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
WIB = timezone(timedelta(hours=7))
OWN = {
    "Kementan": r"kementan|kementerian pertanian|bppsdmp",
    "KKP": r"\bkkp\b|kementerian kelautan",
    "Kemenhut": r"kemenhut|kementerian kehutanan",
    "BGN": r"badan gizi nasional|\bbgn\b",
    "KLH/BPLH": r"\bklh\b|bplh|kementerian lingkungan hidup",
    "Bapanas": r"badan pangan nasional|bapanas",
}
data = json.load(open(SRC))
kanal = json.load(open(os.path.join(HERE, "data_lokal", "kanal_video.json")))
official = set(kanal["official_channels"].values())
own_videos, kept_videos = {}, {}
for agency, vids in data["videos"].items():
    own, kept = set(), set()
    for v in vids:
        if kanal["video_channel"].get(v["video_id"]) in official or re.search(OWN[agency], v["channel"], re.I):
            own.add(v["video_id"])
        else:
            kept.add(v["video_id"])
    own_videos[agency], kept_videos[agency] = own, kept

posts = {}
for path in [os.path.join(HERE, "data", f"youtube_2026-{m}_video.csv") for m in ("08", "09", "10")] + \
            [os.path.join(HERE, "data_lokal", "youtube_2026-11_video.csv")]:
    for r in csv.DictReader(open(path)):
        posts.setdefault(r["lembaga"], []).append(datetime.fromisoformat(r["terbit_wib"]))

out = {}
for agency in OWN:
    daily = Counter()
    n = 0
    for c in data["comments"]:
        if c["lembaga"] == agency and c["video_id"] in kept_videos[agency]:
            t = datetime.fromisoformat(c["published_at"].replace("Z", "+00:00")).astimezone(WIB)
            daily[t.date()] += 1
            n += 1
    rt = response_time(dict(daily), posts.get(agency, []), tz_offset_hours=7)
    out[agency] = dict(
        komentar=n, video_percakapan=len(kept_videos[agency]), video_dikeluarkan_kanal_sendiri=len(own_videos[agency]),
        hari_berdata=rt.n_days, median_harian=rt.median_daily_volume, unggahan_resmi=len(posts.get(agency, [])),
        lonjakan=[dict(hari=s.day.isoformat(), volume=s.volume, rasio=s.ratio, jam=s.hours,
                       unggahan_pertama=s.first_post_at.isoformat() if s.first_post_at else None) for s in rt.spikes],
        median_jam=rt.median_hours, tak_dijawab=rt.n_unanswered, saran_skor_c4=rt.suggested_score,
    )
json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
for a, r in out.items():
    print(f"{a:9s} komentar {r['komentar']:6d} hari {r['hari_berdata']:3d} median/hari {r['median_harian']:6.1f} "
          f"lonjakan {len(r['lonjakan']):2d} tak dijawab {r['tak_dijawab']:2d} median jam {r['median_jam']} saran C4 {r['saran_skor_c4']}")
