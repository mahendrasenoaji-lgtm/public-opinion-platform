# Pengunduran diri Wapres Gibran — komentar YouTube 10–17 Nov 2026 (WIB)

Folder kerja proyek platform **"PENGUNDURAN DIRI GIBRAN (YouTube 10-17 Nov 2026)"**. Dibuat 17 Nov 2026.
Pola kerja sama dengan `proyek/bbm-bali-youtube/` (baca PROGRESS.md di sana untuk latar).

## 🟢 Mulai dari sini

- **Data mentah dan berkas besar hanya ada di Mac** (tidak di-commit; lihat `.gitignore` folder ini).
  Keputusan pemilik 17 Nov: "simpan di lokal dulu, bertahap diunggahnya".
- **Unggahan bertahap ke platform:** `unggah_bertahap/tahap_NN_dari_10.json`, tiap berkas ±20.000 komentar,
  hasil acak (seed 20261117) dari seluruh data, sehingga setiap tahap adalah sampel acak dan angka di platform
  tetap terbaca wajar walau belum semua masuk. Unggah lewat `/sinyal` → "Unggah data (JSON)". Aman diulang.
  Status tahap ada di tabel bawah.
- **Kuota Supabase:** masa tenggang egress sampai 10 Des 2026. Jangan jalankan "Nilai ulang" untuk proyek ini
  (data baru sudah dinilai `informal-4` saat masuk) dan buka dasbor seperlunya.
- **Video belum ditarik:** 729 video kecil (±88 ribu komentar menurut YouTube). Lanjutkan saat kuota YouTube
  pulih (kuota harian 10.000 unit, pulih ±15.00 WIB):
  `YOUTUBE_API_KEY=... python3 -I skrip/collect_gibran.py raw_youtube_api.json 6000`
  Skrip melompati video yang sudah ada di `raw_youtube_api.json.parts/` dan tidak mencari ulang.
  Kunci diambil pemilik sendiri dari Render → pop-api → Environment (Claude tidak diizinkan membukanya).
  Sesudah itu jalankan ulang `analyze_gibran.py`, lalu buat tahap tambahan HANYA dari komentar baru
  (jangan acak ulang semuanya: tahap lama sudah terunggah; dedup platform memang menahan yang kembar).

## Keputusan

| Hal | Keputusan | Alasan |
|---|---|---|
| Jendela | 10 Nov 00:00 – 17 Nov 23:59 WIB | 10 Nov usulan hak menyatakan pendapat di DPR; 11–12 Nov surat pengunduran diri; sampai hari pengambilan. |
| Cara ambil | Skrip + YouTube Data API v3 resmi | Tombol "Tarik semua" hanya 2 hari terakhir, 100 komentar utama per video. |
| Video | Terbit dalam jendela, judul/deskripsi menyebut "gibran" + kata peristiwa | Lihat `PAT` di `skrip/collect_gibran.py`. |
| Identitas | Nama akun diganti hash 12 karakter | Aturan CLAUDE.md §3. |
| Unggah | Bertahap, 10 berkas acak | Permintaan pemilik; menjaga kuota Supabase. |

## Batas bacaan yang khas proyek ini

- Kamus platform memberi bobot negatif pada kata **"mundur"** (dulu dipakai sebagai tuntutan). Di sini itu kata
  topik. `analyze_gibran.py` menghitung skor kedua tanpa kata topik (`sentiment2`, `overall_tanpa_kata_topik` di
  `stats.json`). Platform sendiri tetap memakai skor biasa.
- Peta aktor di platform (`services/actors.py`) disusun untuk kasus BBM Bali; daftar aktor proyek ini ada di
  `ACTORS` pada `skrip/analyze_gibran.py` (nama saja, tanpa klaim jabatan).
- Yang ditarik lebih dulu adalah 114 video paling ramai; 729 video kecil belum masuk.
- Komentar YouTube bukan sampel penduduk; nada bukan sikap; sarkasme sering salah baca.

## Berkas

| Berkas | Isi | Di repo? |
|---|---|---|
| `skrip/collect_gibran.py`, `skrip/analyze_gibran.py` | pengumpul dan pengolah | ya |
| `stats.json` | angka ringkas untuk laporan | ya |
| `raw_youtube_api.json`, `.parts/` | data mentah API | lokal saja |
| `komentar_youtube_gibran_mundur_10-17nov2026.csv` | satu baris per komentar + link | lokal saja |
| `unggah_platform_gibran_mundur.json`, `unggah_bertahap/` | berkas unggahan | lokal saja |

## Status unggahan

| Tahap | Item | Status |
|---|---|---|
| 01 | 19.995 | **Terunggah 17 Nov 2026** (19.784 konten unik sesudah dedup; satu kali "Internal Server Error" di item 14.101, dilanjutkan dari titik itu) |
| 02 | 19.995 | **Terunggah 17 Nov** (2.400 + sisa 17.595; 17.436 baru dari sisa) |
| 03 | 19.995 | **Terunggah 17 Nov** (halaman sempat jatuh di ±9.900; sisanya lewat `tahap_03_sisa.json`) |
| 04 | 19.995 | **Terunggah 17 Nov** (19.740 baru) |
| 05 | 19.995 | **Terunggah 17 Nov** (19.724 baru) |
| 06 | 19.995 | **Terunggah 17 Nov** (19.726 baru) |
| 07 | 19.995 | **Terunggah 17 Nov** (19.702 baru) |
| 08 | 19.995 | **Terunggah 17 Nov** (dijeda di ±16.800, lalu berkas utuh diunggah ulang: 777 baru, 19.013 sudah ada) |
| 09 | 19.995 | **Terunggah 17 Nov** (19.708 baru; "Bad Gateway" di item 14.101, lalu dua kali "Internal Server Error" tepat di item 2.401 berkas sisa; dilanjutkan lewat `tahap_09_sisa.json`, `_sisa2`, `_sisa3`) |
| 10 | 19.994 | **Terunggah 17 Nov, 13.28 WIB** (1.200 item pertama pagi: 1.182 baru; sisanya 18.794 item lewat `tahap_10_sisa.json` sesudah jeda: 18.514 baru, 74 sudah ada, 206 duplikat, tanpa galat) |

**Semua 10 tahap sudah masuk (17 Nov 2026, 13.28 WIB).** Yang belum: 729 video kecil.

**PENTING, jangan buka periode penuh dulu:** sesudah tahap 10 selesai, membuka
`/sinyal?dari=2026-11-10&sampai=2026-11-17` menjatuhkan server Render ("This page couldn't load", `/health` 503
selama ±1,5 menit, pulih sendiri 13.31 WIB). Sebabnya `GET /signals/summary` memuat seluruh baris ke memori
(dipanggil 3 kali sekaligus) ditambah panel emosi dan aktor yang memuat seluruh teks; ±197 ribu konten
melampaui 512 MB. Perbaikan: **PR #73** (`sinyal/hemat-memori`): ringkasan dihitung di SQL, emosi dan aktor
dibaca 5.000 baris per potongan. Sampai PR #73 di-merge dan dirilis, buka `/sinyal` hanya per hari
(mis. `dari=2026-11-15&sampai=2026-11-15`) atau periode kosong. Angka total di platform belum dicek ulang
karena itu. Masih terbuka sesudah #73: waktu hitung panel emosi (±24 detik untuk 200 ribu teks di Mac,
lebih lambat di Render) dan aktor (±10 detik); ukur dulu sesudah rilis.

Catatan 17 Nov siang: sejak ±11.24 WIB server Render berkali-kali putus di tengah unggahan walau periode
kosong dipakai (11.24 Bad Gateway, 11.27, 11.31, 11.38 Internal Server Error), padahal tahap 08 dan 14.100
item pertama tahap 09 lancar. `/health` tetap 200. Sebabnya belum diketahui. Bila terulang: buat berkas sisa
mulai dari item yang gagal, muat ulang `/sinyal` periode kosong, unggah berkas sisa.

**Cara unggah yang terbukti lancar (17 Nov):** buka `/sinyal?dari=2026-01-01&sampai=2026-01-02&zona=WIB`
(periode kosong) lalu unggah dari sana. Sebabnya: `ingestBatch` memanggil `revalidatePath("/sinyal")` tiap
potongan 300 item, sehingga seluruh dasbor dihitung ulang 67 kali per tahap. Dengan periode berisi data, itulah
yang menjatuhkan server Render ("Bad Gateway") dan memboroskan kuota Supabase. Perbaikan kode yang disarankan
(belum dikerjakan): revalidasi sekali saja di akhir unggahan. Tiap tahap ±10 menit.
Supabase 17 Nov sesudah tahap 5: basis data 138 / 500 MB, egress 1,49 / 5 GB.

## Angka 17 Nov 2026

**Lokal, seluruh data terkumpul** (`stats.json`): 199.974 komentar + balasan (159.706 + 40.268), 128.842 akun, 114 video.
Puncak 12 Nov (58.115; jam teramai 19.00–20.59 WIB). Dinilai 109.744 (55%), di antaranya 56% negatif, 34% positif;
rata-rata −0,149 (tanpa kata topik "mundur": −0,114). Paling sering disebut: Gibran 41.718, Prabowo 16.900,
Jokowi 10.637, DPR 7.368, MK 4.330.

**Platform sesudah tahap 1** (`/sinyal?dari=2026-11-10&sampai=2026-11-17&zona=WIB`): 19.784 konten, 18.234 akun,
sentimen −0,15 (n 10.724), jam paling ramai Kamis 19.00 WIB, aktor: Gibran 3.837, Prabowo 1.664, Jokowi 992.
Catatan: daftar aktor platform masih menulis Gibran "Wakil Presiden RI" (jabatan per Oktober 2026) dan memuat
aktor BBM Bali; perlu diperbarui lewat PR bila proyek ini mau dipublikasikan.

## Ringkasan percakapan (17 Nov 2026, satu sesi Claude Code di Mac)

Ditulis supaya pekerjaan bisa dilanjutkan di komputer lain tanpa riwayat chat.

1. **Pemilik:** minta satu jurnal Indonesia dan satu jurnal internasional yang berkaitan dengan kajian BBM Bali.
   **Hasil:** Mulia dkk. (2024), "Analisis Sentimen dan Topik Perbincangan Netizen Indonesia Terkait Pengurangan
   Subsidi BBM", *Jurnal Linguistik Komputasional*; dan Nasrullah dkk. (2026), "Emotional discourse and symbolic
   contestation in Indonesia's digital public sphere… YouTube comments on LPG subsidy regulatory adjustment news",
   *Frontiers in Communication*. Cadangan: Frevita dkk. (2026, JAIEA, Pertalite di komentar YouTube) dan Mukti dkk.
   (2025, IJSSHR, LPG 3 kg). Ditemukan lewat Consensus; volume dan DOI perlu dicek di situs jurnal sebelum dikutip.
2. **Pemilik:** "pengunduran diri Gibran Rakabuming Raka, buatkan di sentimen analisisnya" di platform.
   **Yang terjadi:** platform belum login di Chrome (pemilik login sendiri). Claude mencoba membuka halaman
   Environment Render untuk mengambil kunci YouTube dan ditolak pengaman izin Claude Code.
3. **Pemilik:** "sudah. kerjakan sampai tuntas. ingat supabase… tidak boleh melebihi kuota bulanan. kenapa ada
   batasan? api youtube sudah ada di platform ini."
   **Jawaban:** kunci ada di server Render dan hanya terpakai lewat tombol "Tarik semua", yang dirancang untuk
   pengumpulan rutin: 2 hari terakhir, 100 komentar utama per video, tanpa balasan (menjaga timeout dan kuota
   10.000 unit per hari). Puncak 11–12 Nov tidak terjangkau tombol itu.
   Pemilik memilih **skrip penuh seperti BBM Bali** (bukan token pengumpul, bukan tombol biasa).
4. **Pemilik:** minta dipandu lewat Chrome. Claude membuka halaman Environment `pop-api` (nilai tetap tertutup),
   pemilik menekan ikon salin sendiri lalu menjalankan `pbpaste > ~/.yt_key && chmod 600 ~/.yt_key`.
5. **Pengumpulan:** 874 kandidat video, 872 relevan, ±288 ribu komentar menurut YouTube. Berhenti di 6.011 unit:
   114 video teramai selesai (199.974 komentar), 729 video kecil belum.
6. **Pemilik (soal unggahan):** "simpan di lokal dulu, bertahap diunggahnya." Data dipecah menjadi 10 tahap acak.
   Tahap 1 diunggah dan dicek di `/sinyal`.
7. **Pemilik:** "lanjutkan. simpan semua di github ya supaya dapat saya baca progress dan percakapannya."
   Folder ini masuk repo lewat PR #72 (cabang `proyek/gibran-mundur-youtube`). Tahap 2 baru masuk 2.400 item:
   Render membalas "Bad Gateway", lalu sesudah server pulih halaman `/sinyal` menampilkan nol di semua kartu
   dan ekstensi Claude di Chrome terputus. Belum diketahui apakah nol itu karena sesi login habis atau hal lain;
   cek dulu dengan memuat ulang `/sinyal` sebelum mengunggah lagi.

### Hal yang perlu diketahui sesi berikutnya

- Berkas `~/.yt_key` (kunci YouTube, izin 600) masih ada di Mac untuk menarik 729 video sisanya. Hapus dengan
  `rm ~/.yt_key` bila tidak dipakai lagi. Tidak pernah masuk repo.
- Data mentah (95 MB) dan berkas unggahan tidak masuk GitHub (melewati batas wajar ukuran berkas dan repo ini
  publik). Di komputer lain data bisa dibuat ulang dengan `collect_gibran.py`, tetapi hasilnya bisa sedikit berbeda.
- Alat unggah Chrome dibatasi 10 MB per berkas; tiap tahap ±7,7 MB.
- Jangan pindah halaman selagi "Mengunggah N / N…" masih tampil; potongan terakhir bisa belum selesai.
- Sesi login platform dan Render dilakukan pemilik sendiri.
