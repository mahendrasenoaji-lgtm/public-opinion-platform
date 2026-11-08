"""Sampel buta 100 komentar yang abstain di informal-3 dan dinilai di informal-4 (di luar sampel 400).

Pakai: python3 -X utf8 skrip/ambil_sampel_buta_informal3.py tulis   -> sampel_buta_100_informal4.csv (tanpa skor)
       python3 -X utf8 skrip/ambil_sampel_buta_informal3.py nilai   -> isi skor alat lalu hitung presisi
Kolom label_buta diisi SEBELUM langkah `nilai` dijalankan, tanpa melihat skor alat.
"""
import csv, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("POP_API_DIR", os.path.join(HERE, "..", "..", "..", "apps", "api")))
from app.services import sentiment as S  # noqa: E402
P = os.path.join(HERE, "..")
OUT = os.path.join(P, "sampel_buta_100_informal4.csv")
rows = list(csv.DictReader(open(os.path.join(P, "komentar_youtube_bbm_bali_11-20okt2026.csv"), encoding="utf-8-sig")))
old = {r["comment_id"]: r["label_informal3"] for r in csv.DictReader(open(os.path.join(P, "label_informal3_per_komentar.csv"), encoding="utf-8-sig"))}
sample400 = {m["url"] for m in csv.DictReader(open(os.path.join(P, "sampel_manual_400_label.csv"), encoding="utf-8-sig"))}

if sys.argv[1] == "tulis":
    pool = [r for r in rows if old[r["comment_id"]] == "abstain" and r["url"] not in sample400
            and S.score(r["text"], register="informal").score is not None]
    seen, uniq = set(), []
    for r in pool:  # komentar kembar (salin-tempel) cukup sekali
        if r["text"] not in seen:
            seen.add(r["text"]); uniq.append(r)
    random.seed(20261109)
    pick = random.sample(uniq, 100)
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["no", "label_buta", "text", "url"])
        for i, r in enumerate(pick, 1):
            w.writerow([i, "", r["text"], r["url"]])
    print(len(uniq), "kandidat unik; ditulis", OUT)
else:
    data = list(csv.DictReader(open(OUT, encoding="utf-8-sig")))
    def wilson(k, n, z=1.96):
        p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
        return (c - m) / d, (c + m) / d
    out = []
    for m in data:
        s = S.score(m["text"], register="informal")
        out.append({**m, "label_informal4": s.label, "skor_informal4": s.score,
                    "kata_pemicu": "; ".join(f"{w}:{v}" for w, v in s.matched)})
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["no", "label_buta", "label_informal4", "skor_informal4", "kata_pemicu", "text", "url"])
        w.writeheader(); w.writerows(out)
    for lab in ("negatif", "positif"):
        sel = [o for o in out if o["label_informal4"] == lab]
        k = sum(o["label_buta"] == lab for o in sel)
        if sel:
            lo, hi = wilson(k, len(sel))
            print(f"alat {lab}: {len(sel)}; benar menurut label buta {k} ({k/len(sel):.1%}; Wilson 95% {lo:.1%}-{hi:.1%})")
    agree = sum(o["label_buta"] == o["label_informal4"] for o in out)
    print(f"selaras keseluruhan: {agree}/{len(out)}")
    for o in out:
        if o["label_buta"] != o["label_informal4"]:
            print("  beda:", o["label_buta"], "vs", o["label_informal4"], o["kata_pemicu"], "|", o["text"][:120])
