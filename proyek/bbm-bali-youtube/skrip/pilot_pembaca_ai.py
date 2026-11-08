"""Uji pembaca komentar LLM (app/ai/comment_reader.py) pada sampel manual 400 komentar BBM Bali.

Butuh kunci API milik pengguna di lingkungan, BUKAN di repo:
    ANTHROPIC_API_KEY=... LLM_MODEL=claude-sonnet-5-5 \
        python3 -X utf8 skrip/pilot_pembaca_ai.py
(Python dari venv apps/api.) Biaya: 400 komentar ~ 16 panggilan.

Keluaran: pilot_pembaca_ai_400.csv (bacaan per komentar) dan ringkasan di layar:
selaras dengan label manual, berapa komentar negatif yang abstain di leksikon
kini terbaca, alat bahasa yang paling sering, dan sasaran yang paling sering.
Catatan: label manual sampel ini dibuat agen AI (satu pelabel), jadi kesepakatan
ini bukan akurasi terhadap manusia.
"""

import asyncio
import collections
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("POP_API_DIR", os.path.join(HERE, "..", "..", "..", "apps", "api")))
from app.ai.comment_reader import read_comments  # noqa: E402
from app.ai.provider import AnthropicProvider  # noqa: E402
from app.services import sentiment as S  # noqa: E402

P = os.path.join(HERE, "..")
key = os.environ.get("ANTHROPIC_API_KEY")
if not key:
    sys.exit("ANTHROPIC_API_KEY belum disetel di lingkungan; skrip berhenti tanpa memanggil API.")

sample = list(csv.DictReader(open(os.path.join(P, "sampel_manual_400_label.csv"), encoding="utf-8-sig")))
comments = [(m["no"], m["text"]) for m in sample]
llm = AnthropicProvider(key, os.environ.get("LLM_MODEL", "claude-sonnet-5-5"))
env = asyncio.run(read_comments(llm, comments, topic="Kelangkaan BBM di Bali, 11–20 Oktober 2026 (komentar YouTube)"))
by_no = {r.id: r for r in env.payload}

peta = {"negatif": "negatif", "positif": "positif", "netral/informatif": "netral", "tidak jelas": "tidak jelas"}
rows, agree, both = [], 0, 0
recovered = 0
for m in sample:
    r = by_no.get(m["no"])
    lex = S.score(m["text"], register="informal")
    if r:
        both += 1
        agree += peta[m["label_manual"]] == r.nada
        if m["label_manual"] == "negatif" and lex.score is None and r.nada == "negatif":
            recovered += 1
    rows.append({"no": m["no"], "label_manual": m["label_manual"], "label_leksikon": lex.label if lex.score is not None else "abstain",
                 "nada_ai": r.nada if r else "", "sasaran_ai": "; ".join(r.sasaran) if r else "", "alat_ai": "; ".join(r.alat) if r else "",
                 "bukti_ai": r.bukti if r else "", "alasan_ai": r.alasan if r else "", "text": m["text"]})
out = os.path.join(P, "pilot_pembaca_ai_400.csv")
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
neg_abstain = sum(1 for m in sample if m["label_manual"] == "negatif" and S.score(m["text"], register="informal").score is None)
print("model", env.model_version, "| bacaan valid", len(env.payload), "dari", len(sample))
print(f"selaras dengan label manual: {agree}/{both}")
print(f"negatif manual yang abstain di leksikon, kini terbaca negatif oleh AI: {recovered}/{neg_abstain}")
print("alat:", collections.Counter(a for r in env.payload for a in r.alat).most_common())
print("sasaran:", collections.Counter(s for r in env.payload for s in r.sasaran).most_common(12))
print("batasan:", env.limitations)
print("ditulis", out)
