# Panduan: menyalakan Tarik tema TikTok dan Instagram

Mesinnya sudah ada sejak 21 November 2026 (panel **Tarik tema** di `/sinyal`). Selama
kuncinya kosong, tombol platform tampil dengan keterangan "belum aktif" dan backend
membalas 503 yang menyebut variabel mana yang kurang. **Tidak perlu migrasi** dan tidak
perlu deploy ulang kode: cukup isi variabel environment di Render, lalu Render me-restart
layanan sendiri.

Kode: `apps/api/app/connectors/tiktok_theme.py`, `instagram_theme.py`, `theme_common.py`;
logika murni `apps/api/app/services/theme_pull.py` (`PLATFORMS`); pekerja
`apps/api/app/routers/theme_pulls.py`; panel `apps/web/components/ThemePull.tsx`.
Tes: `apps/api/tests/test_theme_platforms.py`.

Hanya API resmi (batas legal di `apps/api/app/connectors/base.py`). Scraping atau
layanan pihak ketiga yang mengambil data dengan menyamar sebagai peramban **tidak**
dipasang. Data dari alat pihak ketiga yang legal tetap bisa masuk lewat unggah JSON
(panel unggah di `/sinyal`).

---

## TikTok — TikTok Research API

| Variabel (Render → pop-api → Environment) | Isi |
|---|---|
| `TIKTOK_CLIENT_KEY` | Client key aplikasi Research API |
| `TIKTOK_CLIENT_SECRET` | Client secret aplikasi itu |

**Cara mendapatkannya**
1. Buat akun di TikTok for Developers, lalu ajukan aplikasi **Research API**
   (bukan Login Kit / Display API). Pengajuan atas nama peneliti di lembaga nirlaba
   (universitas), dengan rencana riset dan persetujuan komite etik lembaganya.
2. **Kendala utama:** per dokumentasi resmi (FAQ diperbarui Agustus 2026), wilayah
   yang dilayani masih terbatas; materi publik menyebut AS dan Eropa, dan TikTok
   hanya menyatakan "berharap memperluas" ke wilayah lain. Peneliti di Indonesia
   kemungkinan belum bisa disetujui. Cek ulang halaman Research Tools sebelum mengajukan.
3. Pengguna komersial, pengiklan, dan kreator tidak memenuhi syarat.

**Yang dikerjakan mesin**
- `video/query`: kata kunci + `region_code = ID`, periode dipecah per jendela ≤ 27 hari
  (API membatasi 30 hari per permintaan; satu hari ekstra di tiap sisi untuk batas WIB,
  lalu video di luar periode dibuang).
- Penyaring kata kunci pada deskripsi + tagar, urut komentar terbanyak, lalu
  `video/comment/list` per video.
- Disimpan sebagai konten SOCIAL dengan `connector = tiktok_api`.

**Batasan yang ikut ditampilkan di kartu**
- Research API **tidak memberi nama akun komentator**: hitungan akun berbeda dan graf
  balasan antar-akun tidak tersedia untuk TikTok (relasi balasan tetap tercatat lewat
  `parent_comment_id`).
- Ada batas permintaan harian; habis → status "Menunggu kuota TikTok", lanjut sekitar
  07.05 WIB (00.05 UTC).

**Belum diuji terhadap API sungguhan.** Endpoint dan nama field mengikuti dokumentasi
publik; begitu kunci ada, jalankan satu tarikan kecil (1 kata kunci, 3 hari, 5 video)
dan bandingkan isinya dengan fungsi `parse_videos`/`parse_comments`.

---

## Instagram — Instagram Graph API (pencarian tagar)

| Variabel | Isi |
|---|---|
| `INSTAGRAM_ACCESS_TOKEN` | Token akses jangka panjang dengan izin `instagram_basic` + Instagram Public Content Access |
| `INSTAGRAM_USER_ID` | ID akun Instagram Business/Creator yang dipakai untuk mencari |
| `INSTAGRAM_GRAPH_VERSION` | Opsional, bawaan `v23.0`; naikkan bila Meta mempensiunkan versi itu |

**Cara mendapatkannya**
1. Akun Instagram **Business atau Creator**, terhubung ke Halaman Facebook.
2. Aplikasi di Meta for Developers dengan produk Instagram (Graph API).
3. **App Review** untuk fitur *Instagram Public Content Access* (Meta meminta
   penjelasan penggunaan dan video demo). Tanpa ini, pencarian tagar ditolak.
4. Buat token jangka panjang. Token kedaluwarsa ±60 hari: bila kartu menampilkan
   "Instagram menolak akses (token kedaluwarsa …)", perbarui variabelnya.

**Yang dikerjakan mesin**
- `ig_hashtag_search` (tagar → ID), lalu `recent_media` per tagar.
- Yang disimpan adalah **keterangan (caption) unggahan**, `connector = instagram_api`.

**Batasan (dari API, bukan pilihan kode)**
- Hanya tagar, bukan kata kunci bebas. Kata kunci "BBM Bali" diubah jadi `#bbmbali`.
- Maks. **30 tagar unik per 7 hari** per akun. Habis → pekerjaan gagal dengan pesan jelas.
- `recent_media` hanya memuat unggahan **±24 jam terakhir**. Formulir membatasi tanggal
  mulai paling awal kemarin. Untuk memantau tema berhari-hari, tarik tiap hari.
- **Komentar unggahan akun lain tidak bisa diambil.** Untuk komentar akun resmi milik
  sendiri, jalurnya berbeda (Kinerja, akun resmi), dan belum dibangun.
- Nama akun pengunggah tidak dikirim API.

**Belum diuji terhadap API sungguhan.**

---

## Urutan menyalakan (saran)

1. Isi variabel di Render → tunggu restart (±1–2 menit).
2. Buka `/sinyal` → panel Tarik tema: tombol platform tidak lagi "belum aktif".
3. Uji kecil pada proyek uji (bukan proyek riset): 1 kata kunci/tagar, periode pendek,
   maks. 5 unggahan. Cek kartu kemajuan, lalu daftar konten (`/sinyal`, filter periode).
4. Bila respons API berbeda dari yang diharapkan parser, catat contoh responsnya
   (tanpa token) dan perbaiki `parse_*` + tesnya.
