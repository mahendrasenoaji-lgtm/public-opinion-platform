# Set uji berlabel Profil Audiens (P11, `profil-id-1`)

Tujuan: mengukur seberapa tepat estimasi gender, kelompok umur, dan minat di halaman
`/audiens`, **sebelum** angkanya dipakai untuk promosi (syarat di `docs/benchmark-nolimit.md` P11
dan CLAUDE.md §3). Dibuat 24 Nov 2026.

## Isi sampel (301 akun, seed 20261124)

| Strata | Isi | Gibran (165.294 akun) | BBM Bali (22.803 akun) |
|---|---|---|---|
| A | semua akun yang diberi estimasi gender/umur | 19 dari 19 | 2 dari 2 |
| B | acak dari akun yang diberi estimasi minat | 60 dari 260 | 40 dari 138 |
| C | ada "saya/aku/gue + kata peran" tapi sistem tidak memberi estimasi | 25 dari 514 | 15 dari 24 |
| D | acak dari semua akun | 100 | 40 |

Kenapa berstrata: estimasi gender hanya ada di 21 akun dari ±188 ribu. Sampel acak 300 akun
hampir pasti tidak memuat satu pun, sehingga presisi tidak bisa diukur. A mengukur presisi
gender/umur (sensus), B presisi minat, C apa yang terlewat oleh aturan, D cakupan dan recall.

## Berkas

| Berkas | Di git? | Isi |
|---|---|---|
| `lembar_penilai_1.xlsx`, `lembar_penilai_2.xlsx` | tidak | lembar buta: komentar per akun, tanpa keluaran sistem, urutan berbeda |
| `kunci_sistem.csv` | tidak | keluaran sistem + strata. **Jangan dibuka penilai** |
| `ringkasan_sampel.json` | ya | ukuran strata |
| `skrip/ambil_sampel_profil.py` | ya | membuat ulang semua di atas (deterministik) |
| `skrip/hitung_akurasi.py` | ya | kesepakatan + presisi/recall → `hasil_akurasi.json/.md` |

Lembar dan kunci di-gitignore karena memuat teks komentar per akun (CLAUDE.md §3: data per
akun tidak ikut beredar). Bisa dibuat ulang kapan saja dengan skrip di atas.

## Cara kerja

1. Dua penilai **manusia** masing-masing mengisi satu lembar, sendiri-sendiri. Petunjuk ada di
   tab "Petunjuk". Perkiraan waktu: 2–3 jam per penilai (kebanyakan akun hanya 1–2 komentar
   dan jawabannya "tidak bisa ditentukan").
2. Taruh kedua lembar terisi di folder ini, lalu jalankan dari akar repo:
   `python proyek/uji-profil-audiens/skrip/hitung_akurasi.py` (butuh `openpyxl`).
3. Butir yang berbeda masuk `adjudikasi.csv`. Kedua penilai mengisi kolom `final` bersama,
   lalu skrip dijalankan lagi.
4. Angka yang boleh dikutip: presisi ketat dan longgar per atribut, recall di strata D, kappa.
   Selalu sebutkan n (gender/umur hanya ±21 akun → selang kepercayaan lebar).

Penilai AI tidak menggantikan penilai manusia di sini (sama seperti catatan di
`apps/api/app/services/sentiment_eval_field.py`).
