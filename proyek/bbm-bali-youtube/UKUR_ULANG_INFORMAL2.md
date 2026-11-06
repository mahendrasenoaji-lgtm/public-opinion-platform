# Ukur ulang abstain: kamus informal `informal-2` (6 Nov 2026)

Lanjutan dari "Pembaruan 6 November" (PR #45): 58% komentar BBM Bali tidak dinilai karena tidak memuat kata
kamus. Perubahan di `apps/api/app/services/sentiment.py` dan `informal.py`:

- `INFORMAL_MODEL_VERSION` naik ke `lexicon-id-1+informal-2` (ragam baku `lexicon-id-1` tidak bergeser).
- 33 kata baru di `_INFORMAL_NEGATIVE` (arogan, sombong, memalukan, mundur, copot, bahlul, omon, salah, capek, …).
- `_AFFIX_GROUPS` di `informal.py`: bentuk berimbuhan yang ditulis tangan (kebohongan, dimarahin, memuakkan, …),
  bukan stemmer.

## Cara kata dipilih

Dari komentar yang abstain **di luar** sampel manual 400 (supaya sampel itu tetap bisa menguji). Kata dipilih
dari maknanya. Cek "porsi negatif di komentar yang sudah dinilai" tidak dipakai sebagai bukti: hampir semua
kandidat 60–70%, sama dengan angka dasar 63%, jadi tidak membedakan.

Sengaja **tidak** ditambahkan, dengan alasan terukur:

| Kata | Alasan |
|---|---|
| empati, manusiawi, bijak, pantas, mengayomi | hanya 28–66% bernegasi; sisanya tuntutan ("harusnya mengayomi") yang justru kritik |
| sok | 17% dalam larangan ("gak usah sok kaget"); negasi membaliknya jadi positif (ditemukan di sampel buta) |
| penderitaan → menderita | 22% bernegasi ("tidak merasakan penderitaan rakyat"); terbaca pujian (sampel buta) |
| drama, pusing | 21% dan 19% terbalik jadi positif karena larangan ("gak usah drama") |
| langka, kosong, antri | kata topik, bukan penilaian; kamus dipakai lintas proyek |

## Hasil

| Ukuran | Sebelum (informal-1) | Sesudah (informal-2) |
|---|---|---|
| Komentar tidak dinilai (dari 36.319) | 21.020 (57,9%) | 17.727 (48,8%) |
| Komentar dinilai | 15.299 | 18.592 |
| Negatif di antara yang dinilai | 63,3% | 69,8% |
| Yang dulu dinilai lalu kini abstain | | 0 |
| Label sama pada 15.299 yang dulu sudah dinilai | | 94,9% |
| Evaluasi lapangan repo, belahan `uji`: abstain / akurasi / F1 makro | 27,3% / 0,560 / 0,612 | 26,3% / 0,569 / 0,618 |

Perubahan pada yang dulu sudah dinilai: positif→netral 440, netral→negatif 188, positif→negatif 90,
negatif→netral 60, netral→positif 6.

**Presisi komentar yang baru dinilai.** 100 komentar acak (seed 20261107) yang dulu abstain dan kini dinilai,
di luar sampel 400, dilabeli **tanpa melihat skor alat**: dari komentar yang alat beri label negatif, 94,7%
benar negatif (89/94; Wilson 95%: 88–98%) pada versi sebelum dua kata dibuang; 94,4% (84/89; 87,5–97,6%)
pada kode akhir. Berkas: `sampel_buta_100_informal2.csv`. Catatan: kata "sok" dan "penderitaan" dibuang
setelah melihat galat di sampel ini, jadi angka kode akhir tidak sepenuhnya independen.

**Yang belum membaik.** Dari 279 komentar negatif di sampel manual 400, **208 (75%) masih tidak dinilai**.
Sisanya kritik tanpa kata sentimen baku, bahasa daerah, atau sindiran. Kamus tidak bisa menutup itu. Estimasi
negatif di seluruh data tetap sekitar 67% (64–70%) dari sampel manual; 69,8% dari alat kini mendekati angka itu
tetapi hanya karena alat menilai lebih banyak komentar negatif, bukan karena ia lebih akurat pada yang sulit.

## Batasan yang diketahui

- Pelabel tunggal (Claude), tanpa penilai kedua.
- Sampel manual 400 sudah dibaca penyusun saat memilih kata, jadi kecocokan 70/73 pada sampel itu optimistis.
- Kelemahan lama yang belum diperbaiki (ada di `_modifier`, bukan kamus): negator terhitung sampai kata
  bermuatan kedua di jendelanya, sehingga "gk becus copot" membalik "copot" juga (6–14% kata baru terbalik).
- Menaikkan versi menandai mention SOCIAL lama sebagai usang; skor di database baru berubah setelah rescore
  dijalankan (lihat PR).

## Mengulang

```bash
# dari akar repo, dengan Python venv apps/api
apps/api/.venv-test/Scripts/python.exe -X utf8 proyek/bbm-bali-youtube/skrip/ukur_ulang_informal2.py \
  proyek/bbm-bali-youtube/komentar_youtube_bbm_bali_11-20okt2026.csv \
  proyek/bbm-bali-youtube/sampel_manual_400_label.csv   # dari PR #45
```
