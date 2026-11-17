"""Buat tahap unggahan tambahan HANYA dari komentar yang belum ada di tahap 01-10.

Dipakai sesudah pengumpulan lanjutan (729 video kecil, 17 Nov 2026 malam) dan
`analyze_gibran.py` dijalankan ulang. Tahap lama tidak diacak ulang: isinya sudah
di platform. Item baru diacak dengan seed yang sama (20261117) lalu dipecah per
±20.000 item, sama seperti tahap 01-10 (±7,7 MB, di bawah batas 10 MB alat unggah).

Pakai: python3 -I skrip/tahap_baru.py unggah_platform_gibran_mundur.json unggah_bertahap [mulai_nomor]
"""
import glob
import json
import os
import random
import sys

SRC, DIR = sys.argv[1], sys.argv[2]
START = int(sys.argv[3]) if len(sys.argv) > 3 else 11
PER_STAGE = 19995
SEED = 20261117

done: set[str] = set()
for path in sorted(glob.glob(os.path.join(DIR, "tahap_*_dari_10.json"))):
    done.update(i["external_id"] for i in json.load(open(path))["items"])

data = json.load(open(SRC))
new = [i for i in data["items"] if i["external_id"] not in done]
random.Random(SEED).shuffle(new)

stages = [new[i : i + PER_STAGE] for i in range(0, len(new), PER_STAGE)]
for n, chunk in enumerate(stages, start=START):
    out = os.path.join(DIR, f"tahap_{n:02d}_tambahan.json")
    json.dump(dict(connector=data["connector"], source=data["source"], items=chunk),
              open(out, "w"), ensure_ascii=False)
    print(f"{out}: {len(chunk)} item, {os.path.getsize(out) / 1e6:.1f} MB")
print(f"sudah di tahap 01-10: {len(done)} | item sumber: {len(data['items'])} | baru: {len(new)}")
