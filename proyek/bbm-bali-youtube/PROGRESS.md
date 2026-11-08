# Kelangkaan BBM Bali — komentar YouTube 11–20 Okt 2026

Folder `proyek/bbm-bali-youtube/` di repo **publik** `public-opinion-platform` (atas pilihan pengguna,
5 Nov 2026: semua file termasuk teks komentar masuk repo publik; nama akun sudah di-hash). Isinya: data
komentar YouTube, laporan, dan skrip pengolahnya. Data yang sama juga ada di database platform.
Dibuat 5 Nov 2026 dalam satu sesi Claude Code. Ringkasan percakapannya ada di bawah supaya
pekerjaan bisa dilanjutkan di komputer lain tanpa riwayat chat.

## 🟢 Mulai dari sini

1. Komputer lain: clone/`git pull` repo `mahendrasenoaji-lgtm/public-opinion-platform` dan buka folder ini
   (`proyek/bbm-bali-youtube/`). Semua pekerjaan BBM Bali sudah ada di `main`.
2. Sebelum kerja: `git pull`. Sesudah kerja: commit + push lewat PR, seperti bagian lain repo.
3. **Status 6 Nov 2026 (akhir hari): proyek BBM Bali SELESAI.**
   - PR #45 (sampel manual 400 + SNA + laporan) dan PR #46 (kode `informal-2`) digabung ke `main`
     6 Nov atas izin pengguna; Render sudah deploy `informal-2`.
   - **Rescore BBM Bali di platform sudah dijalankan sampai tuntas** (tombol "Nilai ulang konten lama"
     di `/sinyal`, sesi Chrome pengguna): sisa 0. Platform kini: 35.772 konten (sesudah dedup), 18.358
     dinilai (51%), model `lexicon-id-1+informal-2`, sentimen rata-rata sosial −0,31. Sejalan dengan
     laporan (36.319 komentar, 18.592 dinilai, 51%).
   - Artifact https://claude.ai/artifact/E7TiPtANVW32KoeLQygC7v **versi 4** (privat; bagikan lewat Share):
     dicek di browser (grafik harian, linimasa, tabel), kalimat "platform masih informal-1" diganti.
     `laporan_pembaruan_sampel_manual.html` di repo = isi artifact; `skrip/build_report_pembaruan.py`
     dari `stats_informal2.json` menghasilkan HTML yang identik.
   - Laporan 5 Nov (`laporan.html`, artifact `WFPjyhn…`, PDF) sengaja tidak diubah (versi informal-1).
   - Deck PowerPoint 12 slide: `presentasi_bbm_bali_youtube.pptx` (angka = laporan versi 4, grafik asli
     PowerPoint, catatan pembicara tiap slide; dicek lewat ekspor PDF PowerPoint). Pembuat: `skrip/build_pptx.js`.
4. **8 Nov 2026 — kamus bahasa daerah `informal-3`** (cabang `sentimen/informal-3-bahasa-daerah`):
   modul `apps/api/app/services/regional.py` (13 bahasa daerah + Indonesia cakap, dengan arti dan
   daftar kata yang sengaja dikecualikan karena artinya berbeda antarbahasa). Abstain BBM Bali
   48,8% → 46,7%; presisi label negatif pada komentar yang baru dinilai 95,6% (sampel buta 100).
   CSV/XLSX komentar **dibuat ulang dengan informal-3** (kolom kata penanda + bahasa, sheet
   "Kamus daerah"); label informal-1 lama di `label_informal1_per_komentar.csv`. Rincian:
   `UKUR_ULANG_INFORMAL3.md`. Setelah PR digabung: rescore platform (tombol di `/sinyal`).
5. **Belum dinilai ulang (proyek lain, bukan bagian BBM Bali):** MBG AGUSTUS 2026, KEBAKARAN HUTAN,
   KDMP 2026, tiga POLKAM (Kemendagri/Kemenlu/Kemenhan), dan proyek lain yang punya komentar YouTube.
   Sampai dinilai ulang, deret sentimen sosialnya bercampur `informal-1` dan `informal-2`.
6. **Catatan rescore di production:** satu klik tombol = sampai 20 × 500 baris. Selama rescore 36 rb baris,
   Render beberapa kali membalas 502/503 (restart ±40 dtk) dan 429 (batas 120 permintaan/menit per org).
   Datanya aman (bertahap, idempoten); cukup tunggu lalu klik lagi. Jangan klik beruntun cepat.

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
10. (6 Nov) "Perluas kamus informal dan ukur ulang abstain" → PR #46, `informal-2`; hasil di bawah dan di
    `UKUR_ULANG_INFORMAL2.md` (cabang #46).
11. (6 Nov) "Perbarui laporan dengan angka informal-2. Update ke artifacts" → artifact yang sama, versi 3;
    seluruh angka sentimen dihitung ulang (bukan hanya kepala halaman).
12. (6 Nov) "Aku akan meneruskan di komputer lain, simpan semua progress dan percakapan nya di github" →
    blok "Mulai dari sini" di atas dan bagian "Pelajaran dari sesi 6 Nov" di bawah.
13. (6 Nov, sesi berikut) "merge #45 dan #46 … BBM Bali selesaikan sampai tuntas. kamus sudah diperbaiki?" →
    #46 lalu #45 digabung; rescore BBM Bali di platform sampai sisa 0; artifact versi 4; catatan ini.
14. (6 Nov) "buatkan pptx nya untuk bbm bali" → `presentasi_bbm_bali_youtube.pptx` + `skrip/build_pptx.js`.
15. (8 Nov) "abstain itu indikatornya apa? … cuih menjijikan … akan melihatnya sebagai negatif" → dijelaskan
    (abstain = tak ada kata kamus; Excel masih informal-1). Lalu: "ya buat ulang, tapi lengkapi kamusnya
    … bahasa daerah/kesukuan … masing2 memiliki makna yang berbeda" → `informal-3`, Excel dibuat ulang.

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

**Laporan dihitung ulang dengan informal-2 (6 Nov, lanjutan).** Kamus informal diperluas di PR #46
(cabang `sentimen-perluas-kamus-informal`; hasil ukur: `UKUR_ULANG_INFORMAL2.md` di cabang itu). Laporan
`laporan_pembaruan_sampel_manual.html` (artifact versi 3, URL sama) kini memakai `lexicon-id-1+informal-2`
untuk SEMUA angka sentimen: tidak dinilai 17.727 (48,8%), dinilai 18.592, negatif 69,8% dari yang dinilai,
skor harian −0,26 s.d. −0,34, tidak ada tema berskor positif (terdekat: permintaan maaf/normal −0,03).
Taksiran ±67% (64–70%) dari sampel manual tetap untuk seluruh komentar. Nada menurut pola akun (informal-2):
70,2% / 69,4% / 69,1% (sekali / ≥2 komentar 1 video / ≥3 video).

| Apa | Lokasi |
|---|---|
| Statistik informal-2 | `stats_informal2.json` (`stats.json` 5 Nov tetap informal-1) |
| Label informal-2 tiap komentar | `label_informal2_per_komentar.csv` (comment_id, skor, label) |
| Skrip | `skrip/build_report.py` (narasi kini dibuat dari angka), `skrip/build_report_pembaruan.py` (menyisipkan bagian pembaruan + SNA), `skrip/analyze_bbm.py` (mencatat `model_version`) |

Membangun ulang laporan (kode informal-2 sudah di `main`; `analyze_bbm.py` butuh `openpyxl`):
```bash
POP_API_DIR=<checkout informal-2>/apps/api python3 -X utf8 skrip/analyze_bbm.py raw_youtube_api.json <keluaran>
python3 -X utf8 skrip/build_report.py <keluaran>/stats.json <keluaran>/laporan_dasar.html
python3 -X utf8 skrip/build_report_pembaruan.py <keluaran>/laporan_dasar.html laporan_pembaruan_sampel_manual.html
```
CSV/XLSX 5 Nov (`komentar_youtube_bbm_bali_11-20okt2026.*`) sengaja tidak ditimpa: label di dalamnya tetap
informal-1. Angka di platform (Vercel) sudah informal-2 sejak rescore 6 Nov.

**Belum dilakukan:** `laporan.html`, artifact lama (WFPjyhn…), dan PDF tetap versi informal-1 tanpa catatan
"42% dari komentar"; belum ada pelabel kedua; perbaikan `_modifier` (negator sampai kata bermuatan kedua).

## Pelajaran dari sesi 6 Nov (supaya tidak diulang)

- **Abstain bukan netral.** Jangan mengisi komentar yang tidak dinilai dengan tebakan. SNA diuji dan
  gagal untuk itu (kesamaan induk–balasan 49% = kebetulan; konsistensi akun 60% vs kebetulan 57%).
  Cara jujur: sampel manual berinterval kepercayaan (Wilson), atau kamus yang diukur.
- **Cek "porsi negatif di komentar yang sudah dinilai" tidak membuktikan kata baru**: hampir semua kandidat
  60–70%, sama dengan angka dasar. Pilih kata dari maknanya, uji pada sampel yang dilabeli tanpa melihat
  skor alat.
- **Sampel buta menangkap cacat nyata**: "sok" dan "penderitaan" terbalik jadi positif oleh negasi;
  "drama" dan "pusing" juga (larangan "gak usah …"). Semuanya dibuang. Kata positif prescriptive
  (empati, manusiawi, bijak, pantas, mengayomi) sengaja tidak ditambahkan.
- **Kelemahan lama belum diperbaiki** (ada di `_modifier`, `sentiment.py`): negator masih terhitung sampai
  kata bermuatan kedua di jendela 3 kata, jadi "gk becus copot" membalik "copot". Layak PR sendiri + tes.
- **Kebocoran data uji**: sampel manual 400 dibaca penyusun saat memilih kata, jadi kecocokan 70/73 di sana
  optimistis. Yang bisa dipegang: sampel buta 100 (`sampel_buta_100_informal2.csv`, presisi negatif 94,4%,
  87,5–97,6%) dan evaluasi lapangan repo (F1 0,612 → 0,618).
- Satu pelabel (Claude), tanpa penilai kedua. Langkah lanjut terbaik: minta orang lain melabeli ulang
  50–100 baris `sampel_manual_400_label.csv` dan hitung kesepakatan (kappa).
- Windows: jalankan Python dengan `-X utf8` (cetak/baca JSON gagal tanpa itu); `-I` mengabaikan
  `PYTHONIOENCODING`. Venv tes: `apps/api/.venv-test/Scripts/python.exe`. `networkx` tidak terpasang
  (SNA ditulis dengan Python murni). Heredoc panjang di Git Bash rawan gagal; tulis berkas lewat tool Write.
- Berkas sementara di folder scratchpad sesi tidak ikut tersimpan; semua yang perlu sudah di repo:
  label sampel (CSV), skrip ambil sampel (`skrip/ambil_sampel_abstain.py`, `skrip/ambil_sampel_buta_informal2.py`),
  hitung (`skrip/hitung_sampel.py`), SNA (`skrip/sna_jaringan.py`). Catatan: `skrip/ukur_ulang_informal2.py`,
  `UKUR_ULANG_INFORMAL2.md`, dan `sampel_buta_100_informal2.csv` ada di cabang PR #46, bukan #45.

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
