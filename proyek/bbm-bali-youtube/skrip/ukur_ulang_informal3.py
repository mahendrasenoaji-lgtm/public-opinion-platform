"""Ukur ulang abstain dan keselarasan penilai informal-3 (bahasa daerah) pada komentar BBM Bali.

Pakai (dari folder proyek/bbm-bali-youtube, Python dari venv apps/api):
    python3 -X utf8 skrip/ukur_ulang_informal3.py

Membaca label informal-2 per komentar (label_informal2_per_komentar.csv), menilai ulang
dengan kode apps/api saat ini, lalu melaporkan:
  1. abstain sebelum/sesudah, dan perubahan label pada komentar yang sudah dinilai;
  2. per kata daerah: berapa komentar memuatnya dan berapa persen kemunculannya
     terbalik tanda karena negator (aturan penyusunan: kata yang sering terbalik dibuang);
  3. sampel manual 400 (label manusia) — berapa yang kini dinilai dan selaras.
Kata daerah dipilih dari komentar di LUAR sampel 400, jadi sampel itu tetap bisa menguji.
"""

import collections
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("POP_API_DIR", os.path.join(HERE, "..", "..", "..", "apps", "api")))
from app.services import regional as R  # noqa: E402
from app.services import sentiment as S  # noqa: E402

P = os.path.join(HERE, "..")
rows = list(csv.DictReader(open(os.path.join(P, "komentar_youtube_bbm_bali_11-20okt2026.csv"), encoding="utf-8-sig")))
old = {r["comment_id"]: r for r in csv.DictReader(open(os.path.join(P, "label_informal2_per_komentar.csv"), encoding="utf-8-sig"))}
sample = list(csv.DictReader(open(os.path.join(P, "sampel_manual_400_label.csv"), encoding="utf-8-sig")))
in_sample = {m["url"] for m in sample}
new = {r["comment_id"]: S.score(r["text"], register="informal") for r in rows}
print("versi", S.INFORMAL_MODEL_VERSION)

n = len(rows)
ab_old = sum(old[r["comment_id"]]["label_informal2"] == "abstain" for r in rows)
ab_new = sum(new[r["comment_id"]].score is None for r in rows)
print(f"abstain: informal-2 {ab_old} ({ab_old / n:.1%}) -> informal-3 {ab_new} ({ab_new / n:.1%})")
scored = [s for s in new.values() if s.score is not None]
print(f"dinilai {len(scored)}; negatif {sum(s.label == 'negatif' for s in scored) / len(scored):.1%}; "
      f"positif {sum(s.label == 'positif' for s in scored) / len(scored):.1%}")

ch: collections.Counter[tuple[str, str]] = collections.Counter()
for r in rows:
    a, b = old[r["comment_id"]]["label_informal2"], new[r["comment_id"]].label
    b = "abstain" if b == "tidak dinilai" else b
    if a != "abstain":
        ch[(a, b)] += 1
tot = sum(ch.values())
same = sum(v for (a, b), v in ch.items() if a == b)
print(f"sudah dinilai di informal-2: {tot}, label sama {same} ({same / tot:.2%}); berubah:")
for (a, b), v in sorted(ch.items(), key=lambda kv: -kv[1]):
    if a != b:
        print("   ", a, "->", b, v)

# Per kata daerah, di luar sampel 400.
regional = R.lexicon()
docs: collections.Counter[str] = collections.Counter()
flipped: collections.Counter[str] = collections.Counter()
for r in rows:
    if r["url"] in in_sample:
        continue
    for word, value in new[r["comment_id"]].matched:
        if word in regional:
            docs[word] += 1
            if (value > 0) != (regional[word] > 0):
                flipped[word] += 1
print("\nkata daerah/tambahan yang muncul (komentar | terbalik negasi | bahasa):")
for word, k in docs.most_common():
    print(f"   {word:16s} {k:5d} | {flipped[word] / k:5.0%} | {R.origin(word)}")
print("kata yang tidak muncul sama sekali:", len(regional) - len(docs), "dari", len(regional))

by_url = {r["url"]: new[r["comment_id"]] for r in rows}
peta = {"negatif": "negatif", "positif": "positif", "netral/informatif": "netral", "tidak jelas": None}
dinilai = [(m["label_manual"], by_url[m["url"]]) for m in sample if by_url[m["url"]].score is not None]
cm = collections.Counter((m, s.label) for m, s in dinilai)
terbaca = sum(v for (m, _), v in cm.items() if peta[m] is not None)
cocok = sum(v for (m, label), v in cm.items() if peta[m] == label)
neg_total = sum(m["label_manual"] == "negatif" for m in sample)
masih = sum(1 for m in sample if m["label_manual"] == "negatif" and by_url[m["url"]].score is None)
print(f"\nsampel manual 400: kini dinilai {len(dinilai)}; selaras dengan label manual {cocok}/{terbaca}")
print(f"label manual negatif yang masih abstain: {masih} dari {neg_total}")
