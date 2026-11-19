# Pengunduran diri Wapres Gibran — komentar YouTube 10–17 Nov 2026 (WIB)

Folder kerja proyek platform **"PENGUNDURAN DIRI GIBRAN (YouTube 10-17 Nov 2026)"**. Dibuat 17 Nov 2026.
Pola kerja sama dengan `proyek/bbm-bali-youtube/` (baca PROGRESS.md di sana untuk latar).

## 🟢 Mulai dari sini

- **18 Nov 2026 malam — artikel /pers siap terbit, menunggu OK pemilik.** Draf baru
  `d8508323-02d7-47f0-90ff-94018b16a37c` ("Delapan hari pengunduran diri Gibran dalam komentar YouTube") dibuat dari
  `/laporan` 10–17 Nov WIB sesudah PR #80 dan #81 digabung, jadi snapshot-nya memuat akun berbeda (163.940) dan
  tokoh. Teksnya `artikel_pers_v2.md` (penanda `[[grafik-harian]]` dan `[[nada]]`, tabel tema dan tokoh dari berkas
  analisis 292.377 komentar). Pratinjau di `/publikasi` sudah dicek. Status **Menunggu tinjauan**; menerbitkan
  (tidak bisa ditarik) keputusan pemilik. Sebelum terbit sebaiknya PR #82 digabung (label sumbu "100.000"
  terpotong menjadi "00.000").
- **Draf lama** `52d9f210-...` (18 Nov 09.47, teks saja) masih berstatus tinjauan dan sudah digantikan; hapus hanya
  bila pemilik setuju.
- Catatan: halaman `/laporan` proyek ini bisa menampilkan "Backend belum memuat bagian ini" (8 hitungan berat
  sekaligus), tetapi tombol "Buat draf publikasi" tetap jalan (±4 menit, `/health` tetap 200).

- **Data mentah dan berkas besar hanya ada di Mac** (tidak di-commit; lihat `.gitignore` folder ini).
  Keputusan pemilik 17 Nov: "simpan di lokal dulu, bertahap diunggahnya".
- **Unggahan bertahap ke platform:** `unggah_bertahap/tahap_NN_dari_10.json`, tiap berkas ±20.000 komentar,
  hasil acak (seed 20261117) dari seluruh data, sehingga setiap tahap adalah sampel acak dan angka di platform
  tetap terbaca wajar walau belum semua masuk. Unggah lewat `/sinyal` → "Unggah data (JSON)". Aman diulang.
  Status tahap ada di tabel bawah.
- **Kuota Supabase:** masa tenggang egress sampai 10 Des 2026. Jangan jalankan "Nilai ulang" untuk proyek ini
  (data baru sudah dinilai `informal-4` saat masuk) dan buka dasbor seperlunya.
- **729 video kecil sudah ditarik (17 Nov 2026 malam, 22.23–22.50 WIB, ±1.940 unit kuota).** Total 842 video,
  292.377 komentar + balasan dalam jendela (230.460 + 61.917), 165.316 akun. Satu video sudah dihapus (404).
  Catatan: komentar 17 Nov sesudah jam pengambilan tidak ikut (114 video teramai diambil 02.42 WIB, sisanya ±22.30 WIB).
- **Tahap tambahan 11–15** (`unggah_bertahap/tahap_NN_tambahan.json`, hanya komentar yang belum ada di tahap 01–10,
  dibuat `skrip/tahap_baru.py`, seed sama): 92.396 item, **semua terunggah 17 Nov 23.00–23.57 WIB**. Platform kini
  **288.683 konten** (dicek di dasbor 18 Nov 08.18 WIB).

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
| 11 | 19.995 | **Terunggah 17 Nov** (19.772 baru) |
| 12 | 19.995 | **Terunggah 17 Nov** (halaman jatuh ±item 6.300; sisanya lewat `tahap_12_sisa.json`: 11.182 baru, 2.686 sudah ada) |
| 13 | 19.995 | **Terunggah 17 Nov** (macet di item 7.801; sisanya lewat `tahap_13_sisa.json`: 11.168 baru) |
| 14 | 19.995 | **Terunggah 17 Nov** (19.771 baru) |
| 15 | 12.416 | **Terunggah 17 Nov** (12.248 baru) |

**Semua 10 tahap sudah masuk (17 Nov 2026, 13.28 WIB).** Yang belum: 729 video kecil.

**Periode penuh aman dibuka lagi sejak PR #76 dirilis (18 Nov 2026, 08.12 WIB, `11a8fa3`).** Dicek 08.12–08.18 WIB:
halaman 10–17 Nov termuat lengkap, `/health` tetap 200 (paling lambat 2,3 detik). Halaman tetap berat (±2 menit
render), buka seperlunya. Sebelumnya (17 Nov 23.57 WIB, ±289 ribu konten) leksikon emosi/aktor di event loop
membuat Render me-restart server; PR #76 memindahkannya ke thread.

Riwayat: **Periode penuh sudah bisa dibuka (17 Nov, 13.54 WIB).** Sebelumnya, sesudah tahap 10 selesai, membuka
`/sinyal?dari=2026-11-10&sampai=2026-11-17` menjatuhkan server Render (`/health` 503 selama ±1,5 menit):
`GET /signals/summary` memuat seluruh baris ke memori (dipanggil 3 kali sekaligus) ditambah panel emosi dan
aktor yang memuat seluruh teks. **PR #73** (di-merge 17 Nov, rilis Render `a98fe58`) memindahkan ringkasan ke
SQL dan membaca teks emosi/aktor 5.000 baris per potongan. Sesudah rilis, halaman periode penuh termuat
lengkap dalam ±1,5 menit dan `/health` tetap 200 (paling lambat 8,9 detik). Halaman itu tetap berat: buka
seperlunya. `/signals/report` (halaman `/laporan`) dan `/signals/activity` masih memuat satu jendela sekaligus.

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

**Platform sesudah 15 tahap** (18 Nov 08.18 WIB, periode 10–17 Nov, WIB): **288.683 konten**, 163.940 akun,
sentimen −0,16 (n 156.734), 81.012 konten berpenanda emosi (28,1%), 81.943 menyebut aktor bernama, jam paling ramai
Kamis 19.00 WIB. Volume harian: 10 Nov 35.469; 11 Nov 44.560; 12 Nov 89.351; 13 Nov 46.349; 14 Nov 27.908;
15 Nov 22.731; 16 Nov 19.244; 17 Nov 3.071 (17 Nov tidak lengkap: komentar diambil 02.42 dan ±22.30 WIB).
Aktor: Gibran 56.228 (nada −0,07), Prabowo 25.033 (−0,21), Jokowi 13.924 (−0,18).

**Platform sesudah 10 tahap** (17 Nov 13.54 WIB, periode 10–17 Nov, zona WIB): 197.331 konten, 127.742 akun,
sentimen −0,15 (n 108.553), 56.927 konten berpenanda emosi (28,8%), jam paling ramai Kamis 19.00 WIB, total
engagement 287.047. Volume harian: 10 Nov 24.246; 11 Nov 28.908; 12 Nov 62.160; 13 Nov 33.130; 14 Nov 20.189;
15 Nov 17.030; 16 Nov 11.668. Aktor: Gibran 39.472, Prabowo 17.032, Jokowi 9.720.

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
