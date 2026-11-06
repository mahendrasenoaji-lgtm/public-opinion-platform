"""Ambil 100 komentar acak (seed 20261107) yang dulu abstain (informal-1) dan kini dinilai (informal-2),
di luar sampel 400. Dipakai untuk uji presisi buta; label dibuat SEBELUM melihat skor alat.

Pakai: python3 -X utf8 skrip/ambil_sampel_buta_informal2.py <komentar.csv> <sampel400.json> <keluaran.json>
sampel400.json dibuat oleh skrip/ambil_sampel_abstain.py. Jalankan dengan kode informal-2 di apps/api.
"""
import csv
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "apps", "api"))
from app.services import sentiment as S  # noqa: E402
rows = list(csv.DictReader(open(sys.argv[1], encoding='utf-8-sig')))
used = {o['id'] for o in json.load(open(sys.argv[2], encoding='utf-8'))}
pool = [r for r in rows if r['sentiment_label'] == 'abstain' and r['comment_id'] not in used
        and S.score(r['text'], register='informal').score is not None]
print('kolam baru-dinilai di luar sampel 400:', len(pool))
random.seed(20261107)
pick = random.sample(pool, 100)
json.dump([{'i': k + 1, 'id': r['comment_id'], 'text': ' '.join(r['text'].split())[:240],
            'skor': S.score(r['text'], register='informal').score,
            'label': S.score(r['text'], register='informal').label,
            'matched': S.score(r['text'], register='informal').matched} for k, r in enumerate(pick)],
          open(sys.argv[3], 'w', encoding='utf-8'), ensure_ascii=False)
for k, r in enumerate(pick):
    print(k + 1, '|', ' '.join(r['text'].split())[:240])
