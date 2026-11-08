"""Bacaan manual (satu pembaca: Claude, 8 Nov 2026) atas komentar sampel 400 yang berlabel negatif
tetapi tetap tidak dinilai leksikon informal-4. Tiap komentar diberi SATU alat bahasa utama dan SATU
sasaran utama. Ini taksiran kualitatif dari satu pembaca, bukan ukuran akurasi.

Pakai: python3 -X utf8 skrip/baca_manual_185.py  -> baca_manual_185.csv + ringkasan
"""
import collections, csv, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("POP_API_DIR", os.path.join(HERE, "..", "..", "..", "apps", "api")))
from app.services import sentiment as S  # noqa: E402

ALAT = {
    "tuntutan": "tuntutan (ganti, pecat, suruh jaga sendiri, tenggelamkan)",
    "kiasan": "kiasan dan julukan (boneka ogoh-ogoh, air mata buaya, goblin)",
    "sindiran": "sindiran atau ironi (menuju emas, revolusi mental)",
    "retoris": "pertanyaan retoris",
    "tuduhan": "tuduhan atau kecurigaan (sabotase, KKN, amplop, pemakan uang rakyat)",
    "elektoral": "ajakan elektoral atau serangan partai (jangan pilih, 2029)",
    "daerah": "bahasa daerah yang belum tercatat",
    "penilaian": "penilaian sikap/kinerja tanpa kata kamus (judes, gak ngurus, arogansinya)",
    "keluhan": "keluhan dampak atau keadaan (antre, ojol, gaji dari pajak)",
    "kutipan": "mengutip 'diam kamu' untuk mengejek",
}
# no: (alat, sasaran). Sasaran: daerah, pusat, partai, bumn, petugas, warga (warga Bali/turis/sesama komentator), umum (pejabat umumnya)
B = """
2 tuduhan daerah|3 sindiran pusat|6 kiasan partai|7 penilaian daerah|8 keluhan pusat|9 kiasan daerah|14 tuduhan umum|15 sindiran pusat
18 retoris warga|19 penilaian umum|20 keluhan pusat|23 sindiran umum|25 tuduhan umum|29 daerah daerah|30 sindiran umum|32 penilaian pusat
33 penilaian daerah|34 sindiran daerah|36 penilaian pusat|40 elektoral partai|41 keluhan umum|45 tuduhan partai|47 tuntutan daerah|48 tuntutan daerah
49 tuduhan umum|50 sindiran umum|57 retoris pusat|59 daerah warga|62 daerah warga|64 tuntutan petugas|65 kutipan daerah|67 kiasan warga
68 keluhan umum|73 elektoral partai|76 tuduhan pusat|77 tuduhan umum|79 keluhan umum|81 penilaian warga|84 sindiran daerah|85 sindiran daerah
94 tuntutan umum|95 penilaian warga|98 elektoral umum|99 elektoral daerah|100 keluhan umum|101 tuduhan daerah|102 penilaian daerah|104 tuduhan petugas
106 tuntutan daerah|108 retoris daerah|109 kiasan warga|111 sindiran partai|112 penilaian umum|113 tuntutan umum|114 sindiran warga|116 kiasan warga
118 penilaian daerah|119 tuntutan daerah|120 penilaian daerah|121 elektoral partai|122 kiasan umum|124 tuntutan umum|128 elektoral partai|130 kiasan daerah
134 penilaian umum|135 tuntutan daerah|136 sindiran umum|138 sindiran pusat|141 tuntutan umum|143 sindiran daerah|144 penilaian petugas|145 kutipan warga
147 penilaian daerah|150 tuduhan pusat|151 tuduhan pusat|153 tuntutan warga|155 penilaian pusat|161 penilaian daerah|163 kutipan daerah|165 tuduhan umum
166 penilaian daerah|167 tuntutan umum|168 tuntutan umum|169 retoris daerah|171 penilaian umum|173 sindiran warga|175 daerah daerah|176 penilaian daerah
178 kiasan daerah|183 tuduhan pusat|185 tuntutan daerah|186 penilaian daerah|187 kutipan daerah|190 tuntutan daerah|192 penilaian daerah|198 penilaian daerah
199 tuntutan daerah|202 tuntutan umum|205 penilaian umum|206 tuntutan pusat|209 retoris umum|212 elektoral daerah|222 tuntutan daerah|223 sindiran umum
224 tuduhan pusat|228 daerah pusat|230 penilaian daerah|237 sindiran pusat|238 sindiran daerah|242 retoris partai|243 tuduhan daerah|244 retoris daerah
245 penilaian daerah|246 tuduhan umum|248 penilaian daerah|249 tuduhan pusat|250 tuduhan pusat|256 penilaian umum|258 keluhan umum|263 sindiran daerah
267 tuduhan umum|269 tuduhan daerah|270 sindiran daerah|271 kiasan daerah|272 retoris daerah|273 tuntutan pusat|274 elektoral pusat|275 penilaian daerah
276 sindiran pusat|278 sindiran daerah|279 daerah warga|280 retoris daerah|283 tuduhan daerah|284 kutipan daerah|285 penilaian pusat|287 tuntutan umum
291 retoris umum|292 tuduhan pusat|294 retoris umum|295 tuduhan pusat|296 sindiran pusat|297 penilaian pusat|298 tuduhan umum|303 tuduhan umum
305 daerah daerah|306 sindiran warga|308 penilaian pusat|310 sindiran pusat|311 tuntutan umum|314 keluhan umum|316 tuntutan umum|317 penilaian daerah
318 penilaian daerah|319 penilaian daerah|321 kiasan pusat|326 kiasan partai|328 tuntutan daerah|329 sindiran daerah|332 tuntutan pusat|334 penilaian daerah
337 tuduhan umum|339 penilaian daerah|344 tuduhan umum|345 tuntutan umum|347 tuntutan umum|353 tuntutan daerah|354 sindiran warga|356 tuntutan daerah
358 tuntutan umum|365 sindiran pusat|371 tuntutan umum|373 tuntutan petugas|374 penilaian petugas|376 tuduhan pusat|377 sindiran daerah|378 sindiran partai
381 kutipan umum|382 tuntutan partai|383 penilaian umum|386 penilaian umum|389 penilaian pusat|391 penilaian daerah|392 penilaian daerah|395 keluhan petugas
398 keluhan umum
"""
read = {}
for item in B.replace("\n", "|").split("|"):
    if item.strip():
        no, alat, sas = item.split()
        read[no] = (alat, sas)
P = os.path.join(HERE, "..")
sample = list(csv.DictReader(open(os.path.join(P, "sampel_manual_400_label.csv"), encoding="utf-8-sig")))
target = [m for m in sample if m["label_manual"] == "negatif" and S.score(m["text"], register="informal").score is None]
missing = [m["no"] for m in target if m["no"] not in read]
extra = [k for k in read if k not in {m["no"] for m in target}]
assert not missing and not extra, (missing, extra)
with open(os.path.join(P, "baca_manual_185.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["no", "alat_utama", "sasaran_utama", "text", "url"])
    for m in target:
        w.writerow([m["no"], *read[m["no"]], m["text"], m["url"]])
n = len(target)
print(n, "komentar")
for k, v in collections.Counter(a for a, _ in read.values()).most_common():
    print(f"   {v:3d} ({v/n:.0%})  {ALAT[k]}")
print("sasaran:", collections.Counter(s for _, s in read.values()).most_common())
