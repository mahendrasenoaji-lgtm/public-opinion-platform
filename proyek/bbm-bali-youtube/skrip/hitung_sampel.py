"""Hitung porsi label dari sampel manual (sampel_manual_400_label.csv) + rentang Wilson 95%.

Pakai: python3 -I -X utf8 skrip/hitung_sampel.py sampel_manual_400_label.csv

Proyeksi ke seluruh data memakai angka yang tetap dari laporan: 36.319 komentar, 21.020 tidak dinilai
alat, dan di antara yang dinilai alat: 9.683 negatif, 4.402 positif, 1.214 netral.
"""
import collections
import csv
import math
import sys

TOTAL, ABSTAIN, ALAT_NEG = 36319, 21020, 9683


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    m = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, m - h, m + h


rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8-sig")))
n = len(rows)
c = collections.Counter(r["label_manual"] for r in rows)
for k in ("negatif", "positif", "netral/informatif", "tidak jelas"):
    p, lo, hi = wilson(c[k], n)
    print(f"{k:18} {c[k]:4} {p:6.1%} [{lo:.1%}-{hi:.1%}]")
terbaca = n - c["tidak jelas"]
p, lo, hi = wilson(c["negatif"], terbaca)
print(f"negatif dari {terbaca} yang terbaca: {p:.1%} [{lo:.1%}-{hi:.1%}]")
for nama, i in (("titik", 0), ("bawah", 1), ("atas", 2)):
    f = wilson(c["negatif"], n)[i]
    print(f"negatif seluruh data ({nama}): {(ALAT_NEG + ABSTAIN * f) / TOTAL:.1%}")
