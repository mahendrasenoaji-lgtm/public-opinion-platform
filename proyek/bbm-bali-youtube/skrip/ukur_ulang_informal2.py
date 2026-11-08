"""Ukur ulang abstain dan keselarasan penilai informal-2 pada komentar BBM Bali.

Pakai:
    python3 -I -X utf8 skrip/ukur_ulang_informal2.py <komentar.csv> <sampel_manual_400_label.csv>

Skor lama dibaca dari kolom `sentiment_label` di CSV komentar (hasil informal-1).
Sejak 8 Nov CSV komentar memuat label informal-3; label informal-1 disimpan di
label_informal1_per_komentar.csv (kolom sama) — pakai file itu sebagai argumen pertama.
Skor baru dihitung dari kode di apps/api. Butuh sampel_manual_400_label.csv (PR #45).
Dijalankan dengan Python dari venv apps/api supaya `app.services` bisa diimpor.
"""

import collections
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "apps", "api"))
from app.services import sentiment as S  # noqa: E402

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8-sig")))
sample = list(csv.DictReader(open(sys.argv[2], encoding="utf-8-sig")))
new = [S.score(r["text"], register="informal") for r in rows]
print("versi", S.INFORMAL_MODEL_VERSION)

n = len(rows)
ab_old = sum(r["sentiment_label"] == "abstain" for r in rows)
ab_new = sum(s.score is None for s in new)
print(f"abstain keseluruhan: {ab_old} ({ab_old / n:.1%}) -> {ab_new} ({ab_new / n:.1%})")

scored = [s for s in new if s.score is not None]
negatif = sum(s.label == "negatif" for s in scored)
print(f"dinilai: {len(scored)}; negatif {negatif / len(scored):.1%}")
turun = sum(1 for r, s in zip(rows, new, strict=True) if r["sentiment_label"] != "abstain" and s.score is None)
print("dulu dinilai, kini abstain:", turun)

ch: collections.Counter[tuple[str, str]] = collections.Counter()
for r, s in zip(rows, new, strict=True):
    if r["sentiment_label"] != "abstain":
        ch[(r["sentiment_label"], s.label)] += 1
tot = sum(ch.values())
same = sum(v for (a, b), v in ch.items() if a == b)
print(f"yang sudah dinilai: {tot}, label sama {same} ({same / tot:.1%}); berubah:")
for (a, b), v in sorted(ch.items(), key=lambda kv: -kv[1]):
    if a != b:
        print("   ", a, "->", b, v)

# Sampel manual 400 (SEMUA abstain di informal-1). Catatan: sampel ini sudah dibaca
# penyusun saat memilih kata, jadi bukan data uji yang murni.
by_url = {r["url"]: s for r, s in zip(rows, new, strict=True)}
peta = {"negatif": "negatif", "positif": "positif", "netral/informatif": "netral", "tidak jelas": None}
dinilai = [(m["label_manual"], by_url[m["url"]]) for m in sample if by_url[m["url"]].score is not None]
print(f"sampel 400: kini dinilai {len(dinilai)}")
cm = collections.Counter((m, s.label) for m, s in dinilai)
terbaca = sum(v for (m, _), v in cm.items() if peta[m] is not None)
cocok = sum(v for (m, label), v in cm.items() if peta[m] == label)
print(f"selaras dengan label manual: {cocok}/{terbaca}")
masih = sum(1 for m in sample if m["label_manual"] == "negatif" and by_url[m["url"]].score is None)
print("label manual negatif yang masih abstain:", masih)
