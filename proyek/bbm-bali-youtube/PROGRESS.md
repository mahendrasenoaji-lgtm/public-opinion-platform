# Kelangkaan BBM Bali — komentar YouTube 11–20 Okt 2026

Folder `proyek/bbm-bali-youtube/` di repo **publik** `public-opinion-platform` (atas pilihan pengguna,
5 Nov 2026: semua file termasuk teks komentar masuk repo publik; nama akun sudah di-hash). Isinya: data
komentar YouTube, laporan, dan skrip pengolahnya. Data yang sama juga ada di database platform.
Dibuat 5 Nov 2026 dalam satu sesi Claude Code. Ringkasan percakapannya ada di bawah supaya
pekerjaan bisa dilanjutkan di komputer lain tanpa riwayat chat.

## 🟢 Mulai dari sini

1. Komputer lain: `cd ~/Documents/public-opinion-platform && git pull` → buka folder ini.
2. Sebelum kerja: `git pull`. Sesudah kerja: commit + push (lewat PR, seperti bagian lain repo).
3. Status: **SELESAI** untuk laporan 5 Nov. Pembaruan 6 Nov (sampel manual + SNA) ada di PR cabang
   `bbm-bali-sampel-manual`; setelah PR di-merge, tidak ada pekerjaan yang menggantung. Pilihan
   lanjutan ada di bagian "Kalau mau dilanjutkan".
4. Membaca pembaruan 6 Nov: lihat bagian "Pembaruan 6 November 2026" di bawah. Laporan yang masih
   memuat "63% negatif" saja (`laporan.html`, artifact lama, PDF) sengaja tidak diubah; versi yang
   benar ada di `laporan_pembaruan_sampel_manual.html`.

## Permintaan pengguna (urut)

1. "Cek repo public opinion, lalu buatkan mengenai kelangkaan BBM di Bali, hanya untuk komentar
   YouTube saja, tidak perlu pemberitaan media. Tarik data komentar dengan kurun 10 hari dari awal
   krisis BBM hingga solusi dari pemerintah, sumber komentarnya diberikan linknya juga."
2. "Buatkan PDF dari artifact BBM Bali YouTube. Lalu akun yang berkomentar apakah bisa dideteksi
   akun organik atau buzzer?"
3. "Simpan percakapan dan progress di repo supaya dapat saya kerjakan di komputer lain." (file ini)
4. "Jadikan satu dengan public opinion seperti proyek yang lain" → dipilih: semua file ke repo publik ini.

5. (6 Nov) "Cek repo public opinion, lalu baca hasil di artifacts mengenai kelangkaan BBM di Bali.
   Dari 36.319 komentar dalam jendela dan 63% negatif, dari 15.299 komentar yang bisa dinilai. Yang
   tidak dinilai kenapa?" → jawaban: lihat "Pembaruan 6 November 2026".
6. (6 Nov) "Apakah bisa dinilai menggunakan SNA data yang sudah ada?" → diuji, tidak bisa untuk menilai
   nada (lihat di bawah). Lalu: "mulai langkah 1, nilai sampel manual" → 400 komentar dilabeli.
7. (6 Nov) "Buatkan file baru saja supaya tidak menimpa yang lama" → artifact + HTML baru.
8. (6 Nov) "Simpan 400 baris berlabel ke csv di proyek. Jika analisa SNA, apakah bisa di halaman
   terakhir?" → CSV disimpan; SNA jadi bagian terakhir laporan baru.
9. (6 Nov) "Commit dan push", lalu "buatkan PR-nya … simpan percakapan dan progressnya di github" → PR
   cabang `bbm-bali-sampel-manual`, bagian ini.

## Pembaruan 6 November 2026

**Kenapa 58% komentar tidak dinilai.** Penilai `lexicon-id-1+informal-1` (`apps/api/app/services/
sentiment.py`, fungsi `score()`) mengembalikan abstain (`None`) bila tidak ada satu pun kata kamus atau
emoji yang cocok. Abstain sengaja bukan netral. Makin pendek komentar, makin sering abstain:
0 kata 78%, 1–2 kata 71%, 3–5 kata 74%, 6–10 kata 66%, 11–20 kata 52%, ≥21 kata 32%. Balasan lebih
sering abstain (64%) daripada komentar utama (57%). Contoh yang lolos: "GUBENUR SOMBONG … DIBAYAR
DARI DUIT RAKYAT", "GUBENUR MEMALUKAN", "pensiun mbah…". Maka **63% negatif hanya berlaku untuk 42%
komentar yang memuat kata kamus**.

**Sampel manual (langkah 1).** 400 komentar acak dari 21.020 yang abstain (seed 20261106), dibaca dan
dilabeli satu pembaca (Claude, tanpa penilai kedua; belum ada pengecekan kesepakatan):

| Label | Jumlah | Porsi | Rentang 95% |
|---|---|---|---|
| negatif | 279 | 69,8% | 65–74% |
| netral/informatif | 58 | 14,5% | 11–18% |
| tidak jelas (emoji/tawa saja, bahasa daerah tak pasti, obrolan antar-pengguna) | 58 | 14,5% | 11–18% |
| positif | 5 | 1,2% | 0,5–2,9% |

Dari 342 yang terbaca: 81,6% negatif (77–85%). Perkiraan negatif di seluruh 36.319 komentar ≈ **67%
(64–70%)**, dengan komentar "tidak jelas" dihitung bukan negatif. Positif nyaris nihil di kelompok ini
(pujian untuk petugas/pemilik SPBU dan Gubernur Jabar); sebaliknya 29% dari yang dinilai alat berlabel
positif, sebagian sarkasme → 63% dari alat kemungkinan terlalu rendah, bukan terlalu tinggi.
Aturan label yang memengaruhi hasil: dugaan/tuduhan tanpa kata evaluatif ("pasti ada oknum") dihitung
negatif; sindiran yang jelas arahnya dihitung negatif. Aturan lebih ketat → negatif turun, netral naik.

**SNA tidak bisa mengisi sentimen yang kosong.** Dari 962 pasangan induk–balasan yang sama-sama
dinilai, hanya 49% searah (peluang kebetulan ≈49%). Dari 1.955 akun dengan ≥2 komentar positif/negatif,
60% konsisten (kebetulan ≈57%). Prior per video (51–80% negatif, median 64%) hanya mengulang rata-rata.
Maka jaringan dipakai untuk **struktur**, bukan imputasi.

**Hasil SNA** (agregat, tanpa nama akun): 78,9% akun hanya di 1 video; 4.810 akun (21%) di ≥2 video
menulis 46% komentar; 105 akun di ≥10 video. Tumpang-tindih pengomentar antar video rendah (Jaccard
tertinggi 0,07; tidak ada gugus video). Jaringan balasan: 5.062 balasan, 4.275 pasangan akun unik,
4.561 akun, 10 akun teratas hanya menerima 8,3% balasan, 597 gugus (terbesar 3.047 akun), 330 balasan ke
komentar sendiri. Nada (alat, hanya yang dinilai): 63,7% negatif untuk akun sekali, 62,3% untuk akun
≥2 komentar di 1 video, 62,7% untuk akun di ≥3 video → pengomentar rajin tidak lebih negatif. Batas:
YouTube meratakan balasan atas balasan ke komentar induk, jadi timbal balik antarakun tak terukur (0).

**Berkas baru (6 Nov)**

| Apa | Lokasi |
|---|---|
| Laporan pembaruan (HTML) | `laporan_pembaruan_sampel_manual.html` |
| Artifact pembaruan (privat) | https://claude.ai/artifact/E7TiPtANVW32KoeLQygC7v (versi 2) |
| 400 komentar berlabel | `sampel_manual_400_label.csv` (kolom label_manual, label_alat, teks, tautan) |
| Skrip ambil sampel | `skrip/ambil_sampel_abstain.py` (seed 20261106; menulis JSON sampel) |
| Skrip hitung porsi + Wilson | `skrip/hitung_sampel.py <csv>` |
| Skrip SNA | `skrip/sna_jaringan.py <komentar csv>` (Python murni, tanpa networkx) |

Jalankan dengan `python3 -I -X utf8 skrip/<nama>.py …` (di Windows, `-X utf8` perlu supaya cetak tidak
gagal). `ambil_sampel_abstain.py` menerima: csv komentar, JSON keluaran, indeks awal, indeks akhir.
Label manual aslinya dibuat dengan membaca teks; CSV adalah sumber label, bukan skrip.

**Belum dilakukan dari pembaruan ini:** `laporan.html`, artifact lama, dan PDF belum diberi catatan "42%
dari komentar"; kamus informal belum diperluas; belum ada pelabel kedua.

## Keputusan yang diambil

| Hal | Keputusan | Alasan |
|---|---|---|
| Jendela waktu | **11 Okt 00:00 – 20 Okt 23:59 WITA** | Antrean mulai 11–12 Okt; 19 Okt Bahlil + Koster menyatakan pasokan normal (cadangan 15 hari, ganjil-genap diperpanjang). +1 hari penutup. |
| Cara ambil | Skrip sendiri, **YouTube Data API v3 resmi** | `collect-all` di platform hanya menarik komentar TERBARU (order=time, 100/video, UI 2 hari) → rentang lampau tak terjangkau. |
| Kunci API | `YOUTUBE_API_KEY` disalin dari env Render `pop-api` (izin pengguna) | Tidak disimpan di repo mana pun. Di komputer lain: ambil lagi dari Render → pop-api → Environment. |
| Masuk platform | Ya (pilihan pengguna) → PR #43 di public-opinion-platform | Panel "Unggah data (JSON)" di `/sinyal` memanggil endpoint lama `POST /signals/ingest`. |
| Identitas akun | Nama akun **tidak disimpan**, diganti hash 12 karakter | Aturan CLAUDE.md §3 repo platform. |
| Buzzer | **Tidak** melabeli akun tertentu; hanya indikator agregat | Aturan platform: tidak menandai fraud / "mengendalikan opini". |

## Hasil

- 527 video (judul menyebut Bali + BBM/SPBU/Pertamina), 458 punya komentar dalam jendela.
- **36.319 komentar + balasan**, 22.803 akun berbeda; 425 komentar sesudah 20 Okt dibuang.
- Puncak **15 Okt (11.916 komentar, 33%)** — hari video Gubernur Koster diprotes petugas SPBU beredar.
  11 Okt nol karena video krisis pertama baru terbit 12 Okt.
- Sentimen (penilai platform `lexicon-id-1+informal-1`): 58% abstain; dari yang dinilai 63% negatif;
  rata-rata −0,2 s.d. −0,27 tiap hari. Sarkasme sering terbaca positif (komentar teratas "hebat nih
  Gubenur" dinilai positif).
- Tema: pemerintah daerah 6.194 komentar > antrean 5.446 > pemerintah pusat 4.222 > Pertamina 2.711.
- **Buzzer/organik** (agregat): 74% akun berkomentar sekali; 20 akun teraktif = 1,8% komentar;
  **0** teks kembar (≥30 huruf) dari ≥3 akun; 3 teks kembar dari 2 akun (pesan menenangkan "stok bbm
  aman"); 104 akun mengulang teks sama ≥3× (1.001 komentar, ±3%); 32 akun ≥10 komentar/jam;
  19 akun di ≥20 video. Kesimpulan: dominan organik; sekelompok kecil akun pengulang layak dibaca
  manual, belum cukup disebut buzzer.

## Di mana hasilnya

| Apa | Lokasi |
|---|---|
| Laporan online (privat, bagikan lewat Share) | https://claude.ai/artifact/WFPjyhn1CKxprVTMjVX1qQ (versi 2) |
| Laporan PDF (9 hlm, link bisa diklik) | `laporan_bbm_bali_youtube.pdf` |
| Laporan HTML (sumber PDF) | `laporan.html` |
| Excel (sheet Komentar / Video / Harian / Metode) | `komentar_youtube_bbm_bali_11-20okt2026.xlsx` |
| CSV satu baris per komentar + link | `komentar_youtube_bbm_bali_11-20okt2026.csv` |
| Data mentah API | `raw_youtube_api.json` |
| Statistik untuk laporan | `stats.json` |
| File unggahan platform | `unggah_platform_bbm_bali.json` (36.319 item, connector `youtube_api`, source SOCIAL) |
| Platform | proyek **"KELANGKAAN BBM BALI (YouTube 11-20 Okt 2026)"** di public-opinion-platform.vercel.app → 35.772 konten unik (547 teks kembar dibuang dedup), sentimen −0,24 (n 15.105), 22.704 akun |

Link per komentar: `https://www.youtube.com/watch?v=<video_id>&lc=<comment_id>`.

## Menjalankan ulang

```bash
cd ~/Documents/public-opinion-platform/proyek/bbm-bali-youtube
export YOUTUBE_API_KEY=...            # dari Render → pop-api → Environment
python3 -I skrip/collect_bbm.py raw_youtube_api.json        # ±30 menit, ±3.200 unit kuota
python3 -m venv .venv && .venv/bin/pip install openpyxl
.venv/bin/python skrip/analyze_bbm.py raw_youtube_api.json .  # ±20 menit (Excel lambat)
python3 skrip/build_report.py stats.json laporan.html
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --no-pdf-header-footer \
  --print-to-pdf=laporan_bbm_bali_youtube.pdf "file://$PWD/laporan.html"
```

`analyze_bbm.py` memakai penilai sentimen dari `apps/api` di repo yang sama; bisa diganti lewat env
`POP_API_DIR`.
Catatan: menjalankan ulang `collect` hari ini bisa memberi angka sedikit berbeda (komentar dihapus,
video baru terindeks). Indikator buzzer dihitung dengan skrip sekali pakai di sesi; angkanya tertulis
di laporan dan di atas.

## Hal yang perlu diketahui

- Unggah ke platform sempat 2× "Bad Gateway" dan 1× "Service Unavailable" dari Render; diulang dari
  titik berhenti, aman karena `ON CONFLICT DO NOTHING`. Unggah ±5 detik per 300 item.
- Dashboard platform memakai jendela relatif dari hari ini (bawaan 30 hari) → data Okt keluar dari
  tampilan bawaan sekitar **19 Nov 2026**. Data tetap tersimpan.
- Sesi login platform di Chrome bisa kedaluwarsa; login dilakukan pengguna sendiri.
- Unggah file lewat alat Chrome dibatasi 10 MB → file unggahan dipecah dua.

## Kalau mau dilanjutkan

1. **Pemeriksaan akun lebih dalam:** tarik ulang `authorChannelId` untuk ±150 akun paling aktif, lalu
   `channels.list` (tanggal kanal dibuat, jumlah video/subscriber). Kuota kecil. Tetap tanpa
   menyebut akun di laporan.
2. ~~Pelabelan manual sampel~~ → dikerjakan 6 Nov (400 komentar, satu pelabel). Lanjutannya:
   minta orang lain melabeli ulang 50–100 baris dari `sampel_manual_400_label.csv` untuk menghitung
   kesepakatan (kappa), lalu perluas kamus informal (kata seperti "memalukan", "arogan", "copot",
   "mundur", "bahlul", ejaan "gubenur") dan ukur ulang abstain; pakai sampel ini sebagai set uji.
   Perubahan `sentiment.py` butuh tes + PR terpisah (aturan CLAUDE.md repo).
3. Perluas jendela (mis. sampai 31 Okt) untuk melihat ekor percakapan sesudah pernyataan "normal".
