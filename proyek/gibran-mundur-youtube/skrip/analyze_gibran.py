"""Olah raw_youtube_api.json -> CSV, JSON unggahan platform, stats.json. Penilai sentimen = milik platform."""
import csv, json, os, re, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.environ.get("POP_API_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "apps", "api")))
from app.services.sentiment import INFORMAL_MODEL_VERSION, score  # noqa: E402

RAW, OUT = sys.argv[1], sys.argv[2]
WIB = timezone(timedelta(hours=7))
d = json.load(open(RAW))
videos = {v["video_id"]: v for v in d["videos"]}

THEMES = {
    "Ijazah / syarat pencalonan": r"ijazah|ijasah|ijaza\b|sma\b|smk\b|lulus|setara|paket c|syarat|uts insearch|mdis",
    "Putusan MK 2023 / jalur pencalonan": r"\bmk\b|mahkamah konstitusi|paman|usman|putusan 90|anak haram konstitusi|cacat (hukum|konstitusi)|karpet merah",
    "Pemakzulan / DPR / hak menyatakan pendapat": r"makzul|impeach|\bdpr\b|menyatakan pendapat|purnawirawan|\bhmp\b",
    "Jokowi / keluarga / dinasti": r"jokowi|joko widodo|mulyono|\bjkw\b|dinasti|kaesang|bobby|iriana|keluarga solo|geng solo",
    "Prabowo / presiden": r"prabowo|presiden|pak bowo|\b08\b",
    "Pengganti wapres / MPR": r"pengganti|gantikan|menggantikan|\bmpr\b|wapres baru|calon wapres|cawapres|pasal 8",
    "Tuntutan hukum lanjut": r"adili|tangkap|penjara|pidana|proses hukum|usut|kpk|korupsi|dipenjara|hukum mati",
    "Simpati / dukungan kepada Gibran": r"semangat mas|sabar mas|tetap semangat|kasihan|kasian|ksatria|kesatria|legowo|jiwa besar|terima kasih mas|salut|hormat",
    "Syukur / merayakan mundurnya": r"alhamdulillah|akhirnya|syukur|selamat tinggal|mampus|rasain|kapok|karma|good bye|bye bye",
    "Relawan / pendukung (termul, projo)": r"termul|ternak mulyono|projo|relawan|buzzer|cebong|kampret|kadrun",
    "Fufufafa / akun lama": r"fufufafa|fufu",
    "Curiga skenario / deal politik": r"skenario|setting|settingan|sandiwara|drama|deal|pengalihan|strategi|2029|nyapres|capres",
}
ACTORS = {
    "Gibran Rakabuming Raka": r"gibran|\bgbr\b|samsul|fufufafa|mas wapres",
    "Joko Widodo": r"jokowi|joko widodo|mulyono|\bjkw\b|pakde|pak de\b",
    "Prabowo Subianto": r"prabowo|pak bowo|\bwowo\b",
    "Kaesang Pangarep": r"kaesang",
    "Bobby Nasution": r"bobby|bobi nasution",
    "Anwar Usman": r"anwar usman|paman usman|\busman\b",
    "Roy Suryo": r"roy suryo|\broy\b",
    "Megawati / PDIP": r"megawati|\bmega\b|pdip|pdi perjuangan|banteng",
    "Puan Maharani": r"\bpuan\b",
    "Anies Baswedan": r"anies|anis baswedan",
    "Ganjar Pranowo": r"ganjar",
    "Agus Harimurti Yudhoyono": r"\bahy\b|agus harimurti",
    "Sufmi Dasco Ahmad": r"dasco",
    "Ahmad Muzani": r"muzani",
    "Mahfud MD": r"mahfud",
    "DPR": r"\bdpr\b|dewan perwakilan",
    "MPR": r"\bmpr\b",
    "Mahkamah Konstitusi": r"\bmk\b|mahkamah konstitusi",
    "KPU": r"\bkpu\b",
    "PSI": r"\bpsi\b",
    "Gerindra": r"gerindra",
    "Golkar": r"golkar",
    "Purnawirawan TNI": r"purnawirawan",
}
THEMES_C = {k: re.compile(p) for k, p in THEMES.items()}
ACTORS_C = {k: re.compile(p) for k, p in ACTORS.items()}

TOPIK = re.compile(r"\b(mundur|undur|mengundurkan|pengunduran)\b", re.I)
rows = []
for c in d["comments"]:
    t = datetime.fromisoformat(c["published_at"].replace("Z", "+00:00")).astimezone(WIB)
    s = score(c["text"], register="informal")
    v = videos[c["video_id"]]
    low = c["text"].lower()
    # "mundur" berbobot negatif di kamus (dulu dipakai sebagai tuntutan), padahal di sini ia kata topik.
    # Skor kedua dihitung tanpa kata itu supaya biasnya terlihat.
    s2 = score(TOPIK.sub(" ", c["text"]), register="informal")
    rows.append({
        "sentiment2": s2.score, "label2": s2.label if s2.score is not None else "abstain",
        **c,
        "tanggal_wib": t.strftime("%Y-%m-%d"), "jam_wib": t.hour, "waktu_wib": t.strftime("%Y-%m-%d %H:%M"),
        "video_title": v["title"], "channel": v["channel"], "video_url": v["url"],
        "sentiment": s.score, "sentiment_label": s.label if s.score is not None else "abstain",
        "themes_l": [k for k, p in THEMES_C.items() if p.search(low)],
        "aktor_l": [k for k, p in ACTORS_C.items() if p.search(low)],
        "kata_penanda": "; ".join(f"{w} ({val:+g})" for w, val in s.matched),
    })
rows.sort(key=lambda r: r["published_at"])
for r in rows:
    r["themes"] = "; ".join(r["themes_l"])
    r["aktor"] = "; ".join(r["aktor_l"])


def agg2(sel):
    sc = [r for r in sel if r["sentiment2"] is not None]
    lab = Counter(r["label2"] for r in sc)
    return dict(n=len(sel), scored=len(sc), abstain=len(sel) - len(sc), positif=lab["positif"], negatif=lab["negatif"],
                netral=lab["netral"], mean=round(sum(r["sentiment2"] for r in sc) / len(sc), 3) if sc else None)


def agg(sel):
    sc = [r for r in sel if r["sentiment"] is not None]
    lab = Counter(r["sentiment_label"] for r in sc)
    return dict(n=len(sel), scored=len(sc), abstain=len(sel) - len(sc), positif=lab["positif"], negatif=lab["negatif"],
                netral=lab["netral"], mean=round(sum(r["sentiment"] for r in sc) / len(sc), 3) if sc else None)


by_day = defaultdict(list)
for r in rows:
    by_day[r["tanggal_wib"]].append(r)
days = [dict(date=k, **agg(by_day[k])) for k in sorted(by_day)]
hours = Counter((r["tanggal_wib"], r["jam_wib"]) for r in rows)
top_hours = [dict(date=k[0], hour=k[1], n=n) for k, n in hours.most_common(10)]
hour_of_day = [sum(n for (dt, h), n in hours.items() if h == i) for i in range(24)]
themes = {k: agg([r for r in rows if k in r["themes_l"]]) for k in THEMES}
actor_stats = sorted((dict(name=k, **agg([r for r in rows if k in r["aktor_l"]])) for k in ACTORS), key=lambda a: -a["n"])
actor_by_day = {k: {dy: sum(1 for r in by_day[dy] if k in r["aktor_l"]) for dy in sorted(by_day)} for k in list(ACTORS)[:3]}
per_video = Counter(r["video_id"] for r in rows)
per_channel = Counter(r["channel"] for r in rows)
top_videos = [dict(**{k: videos[v][k] for k in ("title", "channel", "url", "published_at", "views", "comment_count")}, comments_in_window=n,
                   **{k: val for k, val in agg([r for r in rows if r["video_id"] == v]).items() if k in ("scored", "negatif", "positif", "mean")})
              for v, n in per_video.most_common(20)]
authors = Counter(r["author_hash"] for r in rows)
once = sum(1 for n in authors.values() if n == 1)
top20 = sum(n for _, n in authors.most_common(20))
texts = defaultdict(set)
for r in rows:
    tx = re.sub(r"\s+", " ", r["text"].strip().lower())
    if len(tx) >= 30:
        texts[tx].add(r["author_hash"])
dup3 = sum(1 for a in texts.values() if len(a) >= 3)
pick = ("waktu_wib", "text", "likes", "sentiment_label", "url", "video_title", "channel", "themes", "aktor")
stats = dict(
    window=d["window"], collected_at=d["collected_at"], queries=d["queries"],
    videos_found=len(videos), videos_collected=len(per_video), videos_pending=len(d.get("videos_pending", [])),
    comments_pending_est=sum(videos[i]["comment_count"] for i in d.get("videos_pending", [])),
    comments=len(rows), top_level=sum(r["type"] == "komentar" for r in rows), replies=sum(r["type"] == "balasan" for r in rows),
    unique_authors=len(authors), authors_once=once, top20_authors_comments=top20, identical_text_3plus_accounts=dup3,
    model_version=INFORMAL_MODEL_VERSION, overall=agg(rows), overall_tanpa_kata_topik=agg2(rows),
    days_tanpa_kata_topik=[dict(date=k, **agg2(by_day[k])) for k in sorted(by_day)],
    actors_tanpa_kata_topik={k: agg2([r for r in rows if k in r["aktor_l"]]) for k in list(ACTORS)[:3]}, days=days, top_hours=top_hours, hour_of_day=hour_of_day,
    themes=themes, actors=actor_stats, actor_by_day=actor_by_day, top_videos=top_videos,
    top_channels=[dict(channel=c, n=n) for c, n in per_channel.most_common(15)],
    top_liked=[{k: r[k] for k in pick} for r in sorted(rows, key=lambda r: -r["likes"])[:40]],
    by_day_samples={dy: [{k: r[k] for k in pick} for r in sorted(by_day[dy], key=lambda r: -r["likes"])[:5]] for dy in sorted(by_day)},
)
json.dump(stats, open(f"{OUT}/stats.json", "w"), ensure_ascii=False, indent=1)

cols = ["waktu_wib", "type", "text", "likes", "sentiment", "sentiment_label", "sentiment2", "label2", "kata_penanda", "aktor", "themes", "url",
        "video_title", "channel", "video_url", "comment_id", "parent_id", "author_hash", "published_at"]
with open(f"{OUT}/komentar_youtube_gibran_mundur_10-17nov2026.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

items = [dict(external_id=r["comment_id"], text=r["text"], published_at=r["published_at"], url=r["url"],
              author_handle=r["author_hash"], engagement=r["likes"],
              conversation_id=r["parent_id"] or r["comment_id"]) for r in rows if r["text"].strip()]
json.dump(dict(connector="youtube_api", source="SOCIAL", items=items),
          open(f"{OUT}/unggah_platform_gibran_mundur.json", "w"), ensure_ascii=False)
print(json.dumps({k: stats[k] for k in ("videos_found", "videos_collected", "comments", "top_level", "replies", "unique_authors", "overall")}, ensure_ascii=False))
