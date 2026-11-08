# Frasa, peta aktor, dan pembaca AI: `informal-4` (8 Nov 2026)

Pemicu: komentar "Bahlil tu lo.ganti aja kok.gk bisa mengatasi bbm. Kalau ngomong mulutnya kok kaya
ular berbisa" berlabel abstain. Pemilik proyek bertanya apakah alat bisa melihat relasi kuasa, tema
besar, dan konteks (Bahlil sebagai Menteri ESDM yang menjamin pasokan, juga ketua partai). Jawaban:
kamus kata tunggal tidak bisa. Tiga perbaikan dikerjakan.

## 1. Pola frasa (`apps/api/app/services/phrases.py`, versi `lexicon-id-1+informal-4`)

20 pola frasa dinilai utuh pada token yang sudah dinormalisasi: "tidak bisa/mampu/becus +
mengatasi/mengurus/kerja", "tidak punya otak/hati/empati/malu", "tidak tahu diri/malu", "tidak
pantas", "ganti aja", "jangan pilih (lagi)", "cari muka", "asal ngomong", "biang kerok",
"pengalihan isu", "muka tembok", "lepas tangan", "ular berbisa", dan lainnya. Kata "tidak" di dalam
frasa tidak lagi membalik kata lain. Ditambah satu kata: "konoha" (julukan sinis untuk negara).

Sengaja tidak ada: "tidak mampu" tanpa kata kerja ("rakyat tidak mampu" = miskin), "ular" sendirian
("antrean kayak ular"), "diam kamu" (kutipan ucapan gubernur), "bukan robot", "petugas partai".

| | informal-3 | informal-4 |
|---|---|---|
| Komentar tidak dinilai | 16.965 (46,7%) | 16.241 (44,7%) |
| Dinilai | 19.354 | 20.078 |
| Negatif di antara yang dinilai | 71,2% | 73,0% |
| Label sama pada yang sudah dinilai | | 98,7% |
| Label manual negatif (sampel 400) masih abstain | 198/279 | 185/279 |
| Eval lapangan MBG (uji) abstain / akurasi / F1 | 26,3% / 0,569 / 0,618 | sama persis |

Sampel buta 100 komentar yang baru dinilai (seed 20261109, di luar sampel 400; pelabel Claude):
label negatif benar **95% (95/100; Wilson 89–98%)** (`sampel_buta_100_informal4.csv`). Perubahan
label pada yang sudah dinilai: positif → netral 97, netral → negatif 95, positif → negatif 53
(mis. "pejabat gak punya malu" dulu positif karena negasi membalik "malu"), negatif → netral 4.

## 2. Peta aktor (`apps/api/app/services/actors.py`)

Pejabat, lembaga, dan partai yang disebut, dengan jabatan per Oktober 2026, dipetakan ke tingkat
kekuasaan: pemerintah pusat, pemerintah daerah, BUMN energi, legislatif, partai, petugas lapangan.
Kata jabatan umum ("gubernur") dihitung ke tingkat, bukan ke orang. Afiliasi politik penulis
komentar tidak ditebak. Excel: kolom "Aktor disebut" dan "Tingkat kekuasaan", sheet "Aktor &
kekuasaan". Angka utama (informal-4):

| Tingkat | Komentar | Tidak dinilai | Negatif* |
|---|---|---|---|
| Pemerintah daerah | 7.019 | 38% | 79% |
| Pemerintah pusat | 4.793 | 32% | 76% |
| BUMN energi (Pertamina) | 1.590 | 28% | 76% |
| Petugas lapangan | 1.359 | 30% | 71% |
| Partai politik | 1.093 | 53% | 79% |
| Legislatif | 646 | 49% | 72% |

\* di antara yang dinilai. Bahlil 2.119 komentar (78% negatif), Koster 1.837 (77%), Pertamina 1.590,
Prabowo 1.291, PDI Perjuangan 520, Golkar 52, Dedi Mulyadi 286 (skor hampir netral, −0,05, dipakai
sebagai pembanding). 62% komentar tidak menyebut aktor atau jabatan. 430 komentar menyebut pusat dan
daerah sekaligus; 788 menyebut pejabat dan petugas SPBU sekaligus (19 dari 20 contoh acak membela
petugas).

## 3. Pembaca AI (`apps/api/app/ai/comment_reader.py`) dan bacaan 185 komentar

Kerangka pembaca LLM per komentar: nada, sasaran (aktor/tingkat), alat bahasa, dan bukti yang wajib
berupa kutipan persis dari teks; bacaan dengan bukti karangan dibuang; keluaran dibungkus
`AIEnvelope`. Tes memakai provider palsu. **Belum dijalankan**: tidak ada `ANTHROPIC_API_KEY` di
komputer ini maupun di Render. Skrip uji siap: `skrip/pilot_pembaca_ai.py` (sampel 400, ~16 panggilan).

Sebagai gantinya, 185 komentar negatif di sampel 400 yang tetap abstain dibaca satu per satu
(`baca_manual_185.csv`, `skrip/baca_manual_185.py`; satu pembaca, Claude): penilaian sikap tanpa kata
kamus 23%, tuntutan 18%, sindiran 16%, tuduhan 15%, kiasan 6%, pertanyaan retoris 6%, keluhan 5%,
ajakan elektoral 4%, bahasa daerah 4%, kutipan "diam kamu" 3%. Sasaran: pemda 68, pejabat umum 51,
pusat 34, sesama warga 15, partai 11, petugas 6.

## Skrip

`skrip/ukur_ulang_informal4.py` (angka di atas, per frasa, per aktor), `skrip/ambil_sampel_buta_informal4.py`,
`skrip/baca_manual_185.py`, `skrip/pilot_pembaca_ai.py`, `skrip/analyze_bbm.py` (CSV/XLSX/stats).
Label lama: `label_informal3_per_komentar.csv`.
