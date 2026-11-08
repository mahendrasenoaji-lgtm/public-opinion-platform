"""Ukur ulang penilai informal-4 (pola frasa) terhadap informal-3, plus peta aktor, pada komentar BBM Bali.

Pakai (dari folder proyek/bbm-bali-youtube, Python dari venv apps/api):
    python3 -X utf8 skrip/ukur_ulang_informal4.py
Label lama dibaca dari label_informal3_per_komentar.csv.
"""
import collections, csv, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("POP_API_DIR", os.path.join(HERE, "..", "..", "..", "apps", "api")))
from app.services import actors as A  # noqa: E402
from app.services import phrases as F  # noqa: E402
from app.services import sentiment as S  # noqa: E402

P = os.path.join(HERE, "..")
rows = list(csv.DictReader(open(os.path.join(P, "komentar_youtube_bbm_bali_11-20okt2026.csv"), encoding="utf-8-sig")))
old = {r["comment_id"]: r["label_informal3"] for r in csv.DictReader(open(os.path.join(P, "label_informal3_per_komentar.csv"), encoding="utf-8-sig"))}
sample = list(csv.DictReader(open(os.path.join(P, "sampel_manual_400_label.csv"), encoding="utf-8-sig")))
in_sample = {m["url"] for m in sample}
new = [S.score(r["text"], register="informal") for r in rows]
lab = lambda s: "abstain" if s.score is None else s.label  # noqa: E731
print("versi", S.INFORMAL_MODEL_VERSION)
n = len(rows)
a0 = sum(old[r["comment_id"]] == "abstain" for r in rows); a1 = sum(s.score is None for s in new)
print(f"abstain: informal-3 {a0} ({a0/n:.1%}) -> informal-4 {a1} ({a1/n:.1%})")
sc = [s for s in new if s.score is not None]
print(f"dinilai {len(sc)}; negatif {sum(s.label=='negatif' for s in sc)/len(sc):.1%}; positif {sum(s.label=='positif' for s in sc)/len(sc):.1%}")
ch = collections.Counter((old[r["comment_id"]], lab(s)) for r, s in zip(rows, new, strict=True) if old[r["comment_id"]] != "abstain")
tot = sum(ch.values()); same = sum(v for (a, b), v in ch.items() if a == b)
print(f"sudah dinilai di informal-3: {tot}, label sama {same} ({same/tot:.2%}); berubah:", {f"{a}->{b}": v for (a, b), v in ch.items() if a != b})
labels = {p.label for p in F.PATTERNS}
cnt = collections.Counter(w for r, s in zip(rows, new, strict=True) if r["url"] not in in_sample for w, _ in s.matched if w in labels)
print("\nfrasa (komentar di luar sampel 400):")
for k, v in cnt.most_common():
    print(f"   {k:32s} {v}")
by_url = {r["url"]: s for r, s in zip(rows, new, strict=True)}
peta = {"negatif": "negatif", "positif": "positif", "netral/informatif": "netral", "tidak jelas": None}
din = [(m["label_manual"], by_url[m["url"]]) for m in sample if by_url[m["url"]].score is not None]
cm = collections.Counter((m, s.label) for m, s in din)
terbaca = sum(v for (m, _), v in cm.items() if peta[m]); cocok = sum(v for (m, l), v in cm.items() if peta[m] == l)
masih = sum(1 for m in sample if m["label_manual"] == "negatif" and by_url[m["url"]].score is None)
print(f"\nsampel 400: dinilai {len(din)}; selaras {cocok}/{terbaca}; label manual negatif masih abstain {masih}/279")
print("\naktor: komentar | abstain | negatif di antara yang dinilai | rata-rata skor")
for a in A.ACTORS:
    sel = [s for r, s in zip(rows, new, strict=True) if a.key in A.detect(r["text"])]
    if not sel: continue
    d = [s for s in sel if s.score is not None]
    print(f"   {a.name:28s} {len(sel):6d} | {sum(s.score is None for s in sel)/len(sel):4.0%} | {sum(s.label=='negatif' for s in d)/max(1,len(d)):4.0%} | {sum(s.score for s in d)/max(1,len(d)):+.2f}")
print("tingkat kekuasaan:")
for lv in A.LEVELS:
    sel = [s for r, s in zip(rows, new, strict=True) if lv in A.levels(r["text"])]
    d = [s for s in sel if s.score is not None]
    print(f"   {lv:20s} {len(sel):6d} | {sum(s.score is None for s in sel)/len(sel):4.0%} | {sum(s.label=='negatif' for s in d)/max(1,len(d)):4.0%} | {sum(s.score for s in d)/max(1,len(d)):+.2f}")
