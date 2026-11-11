# Rencana: situs publikasi hasil riset (padanan pers.droneemprit.id)

> Dibuat 2026-11-11 dari diskusi dengan pemilik produk. **Belum ada kode yang ditulis.**
> Dokumen ini berisi: (1) status repo per 11 Nov, (2) analisis pola Drone Emprit,
> (3) apa yang perlu disiapkan, (4) bagaimana bisa lebih baik dari Drone Emprit,
> (5) keputusan yang ditunggu dari pemilik produk, (6) urutan kerja.
>
> Dokumen terkait: `docs/benchmark-nolimit.md` (prioritas P0–P11),
> `docs/deployment-status.md` (blok "MULAI DARI SINI"), `CLAUDE.md` (aturan R1–R3, batas etis §3).

---

## 1. Status repo per 11 November 2026

`main` = `2a50ead` (PR #56). Tidak ada PR terbuka. CI hijau.

### Sudah dikerjakan

- **Phase 1–3 selesai**: auth + RBAC + RLS, survei, Public Opinion Index, kalkulator sampel,
  cek kualitas; sinyal (RSS, YouTube, unggah JSON), tema, narasi, jaringan, pengaruh;
  forecast, what-if, deret waktu (Wikipedia pageviews, Open-Meteo).
- **Sentimen**: leksikon formal + `informal-4` + 13 bahasa daerah + pola frasa;
  akurasi diukur dan dibuka (presisi negatif 95,6%).
- **10 Nov (PR #55, #56)**: kartu emosi, engagement + peta jam ramai, periode tanggal tetap
  di `/sinyal`, koreksi sentimen manual + audit log, panel aktor + kutipan,
  halaman **Laporan Percakapan** `/laporan` (11 pertanyaan, bisa dicetak),
  leksikon emosi `emosi-id-2` (cakupan 5% → 26%).
- **Proyek data**: BBM Bali (36 rb komentar) + laporan + deck + Excel.

### Masih kurang

Bisa dikerjakan agen sendiri:

1. Cek production dengan data asli: `/sinyal` dan `/laporan` proyek BBM Bali,
   `?dari=2026-10-11&sampai=2026-10-20&zona=WITA`. Fitur 10 Nov baru terbukti rutenya hidup.
2. Pertanyaan 6 di `/laporan` kosong sampai penemuan tema dijalankan di `/tema` untuk BBM Bali.
3. Periode tanggal tetap baru ada di `/sinyal`; Tema, Command Center, dll. masih jendela relatif.
4. Daftar aktor masih satu daftar tetap di kode, belum per proyek.
5. P11 (estimasi gender/umur/minat per akun) sudah diizinkan, belum dimulai.

Menunggu pemilik produk:

6. P0 `ANTHROPIC_API_KEY` di Render (Brief, Copilot, Pembaca AI, ringkasan AI per grafik).
7. P5 label manusia untuk evaluasi leksikon emosi (sarkasme belum dikenali).
8. P8 kanal alert (Telegram gratis / WhatsApp berbayar).
9. P9 format laporan (PDF / PPTX / DOCX).
10. P10 platform tambahan (X berbayar; TikTok/IG/FB lewat unggah JSON).

Catatan: pengumpulan terjadwal (`collect-signals.yml`, `keepalive.yml`) **sengaja dimatikan**
sejak 30 Okt atas permintaan pengguna. Proyek selain BBM Bali sengaja tidak di-rescore ke
`informal-4`.

---

## 2. Pola Drone Emprit

Drone Emprit punya **dua lapisan terpisah**:

1. **Dashboard internal** untuk mengolah data (tidak publik).
2. **Situs publikasi** `pers.droneemprit.id` yang hanya memuat hasil akhir sebagai artikel.

Ciri situs publikasinya (dicek 11 Nov 2026):

- Dibangun dengan **Ghost** (bukan WordPress). Tagline: "We don't claim to be neutral, but
  insist on being truthful."
- Menu: Home, Trending, Politik, Hoaks, Tokoh, Citation, About. Sebagian besar menu = halaman tag.
- Format artikel berulang: "SENTIMEN PUBLIK TERHADAP …", "UPDATE SENTIMEN PUBLIK …",
  "ANALISIS …", "ASPIRASI PUBLIK …". Contoh terbaru: "Sentimen Publik terhadap Salam Tiga Jari"
  (6 Nov 2026), 49 subbab tanya-jawab.
- Daftar artikel: gambar sampul, judul kapital, ringkasan berupa pertanyaan, penulis, tanggal,
  estimasi waktu baca. Arsip bernomor halaman (±22 halaman).
- Newsletter lewat portal anggota Ghost.
- **Tidak ada halaman metodologi khusus**; artikel tidak menyebut jumlah mention, metode,
  atau akurasi.

Platform kita baru punya lapisan pertama. Modul `reports` (`routers/reports.py`) hanya
`GET /summary` (ekspor ringkasan), bukan alur terbit.

---

## 3. Yang perlu disiapkan

### Sudah ada dan bisa langsung dipakai

- `/laporan` (11 pertanyaan) = kerangka satu artikel ala Drone Emprit.
- Laporan/deck/Excel BBM Bali = kandidat artikel pertama.
- Setiap angka sudah membawa `source`, `method`, n, batasan (R1).

### 3.1 Alur "Terbitkan" dari dashboard

- Tombol di `/laporan`: **Buat draf publikasi**.
- Sistem membuat **snapshot beku**: periode, n, metode, versi penilai sentimen, batasan, dan
  semua angka grafik. Angka di artikel tidak berubah walau data dashboard di-rescore.
- Status: `draft` → `review` (manusia) → `published`, plus jalur **ralat** yang tercatat
  (versi lama tetap bisa dibaca).

### 3.2 Data dan backend

- Tabel baru `publications`: `slug`, `title`, `summary`, `body`, `cover`, `tags`, `author`,
  `status`, `published_at`, `project_id` (asal), `snapshot` (JSON), `version`, `corrections`.
  Tabel bertenant → kebijakan RLS di `db/rls.sql` di commit yang sama (R3).
- API publik **hanya-baca** untuk artikel berstatus `published`, tanpa login.
- Situs publik **tidak boleh** membaca tabel proyek secara langsung (dikunci RLS per organisasi);
  hanya membaca snapshot artikel yang sudah terbit.
- Setiap terbit/ralat masuk `audit_logs`.

### 3.3 Situs publik (front end hasil penelitian)

- Beranda (daftar artikel), halaman per tag (Politik, Kebijakan, Bencana, Ekonomi, …),
  arsip bernomor halaman.
- Halaman artikel dengan **grafik interaktif** dari komponen dashboard yang sudah ada, dan
  kotak "Metode & batasan" (`<Provenance />`) di setiap grafik.
- Halaman **Metodologi**: cara kerja kamus sentimen, akurasi terukur, apa yang tidak bisa diklaim.
- Tentang, feed RSS, newsletter, tombol bagikan, gambar OG untuk media sosial.
- Bagian **Sitasi**: cara mengutip, unduh PDF, unduh data agregat (CSV).

### 3.4 Jalur ke paper

- Ekspor artikel ke DOCX/PDF berformat jurnal, mengikuti pola penulis di
  `~/Documents/panduan-menulis-jurnal/POLA_MENULIS_JURNAL.md` (lokal di Mac).
- Dataset agregat diberi DOI lewat Zenodo supaya bisa dikutip.

### 3.5 Aturan editorial dan hukum

- Tidak ada klaim kausal ("berkaitan dengan", bukan "menyebabkan"); tidak menyatakan akun
  "mengendalikan" opini (CLAUDE.md §3).
- Komentar yang dikutip **dianonimkan** (UU PDP 27/2022, ketentuan YouTube API).
- Narasi buatan AI hanya setelah P0, wajib lewat `AIEnvelope` (R2) dan ditinjau manusia.

### 3.6 Operasional

- Nama merek + domain; hosting di Cloudflare Workers (`<nama>.ms-id.workers.dev`, sesuai
  kebijakan proyek baru); penulis dan penerbit; jadwal terbit.

---

## 4. Bisa lebih baik dari Drone Emprit?

**Bisa, tetapi tidak di semua hal.** Arah yang disarankan: jangan meniru, jadilah
**"Drone Emprit versi riset"** — sedikit lebih lambat, tetapi angkanya bisa diuji,
dibandingkan dengan survei, dan dikutip di paper.

### Di mana kita bisa unggul

1. **Metode terbuka di setiap artikel**: n, periode, akurasi kamus, batasan per grafik.
2. **Survei + sosial + berita berdampingan**: "apa kata survei vs netizen vs media"
   (modul divergensi sudah ada). Drone Emprit hanya membaca percakapan online.
3. **Melihat ke depan**: forecast, peringatan dini, skor risiko opini sudah dibangun.
4. **Bahasa daerah dan ragam informal**: 13 bahasa daerah + pola frasa.
5. **Siap jadi paper**: DOI, cara mengutip, unduh data agregat, halaman metodologi.
6. **Laporan interaktif dan berversi**: pembaca memilih periode/sumber; versi lama tersimpan
   dengan catatan ralat.
7. **Dwibahasa ID/EN** untuk pembaca internasional.

### Di mana sulit menyaingi (sekarang)

| Hal | Kenapa sulit | Yang dibutuhkan |
|---|---|---|
| X/Twitter | Kekuatan utama DE = peta jaringan akun di X (klaster, retweet); kita belum punya data X | API X berbayar (cek harga terbaru) |
| TikTok, IG, FB | Tidak ada API listening gratis; scraping melanggar ketentuan | Unggah JSON dari alat pihak ketiga yang legal |
| Kecepatan terbit | DE terbit 1–2 hari setelah isu ramai | Pengumpulan otomatis dinyalakan lagi + penulis |
| Arsip dan volume | Bertahun-tahun, jutaan percakapan | Waktu |
| Reputasi dan pembaca | Sudah dikenal, sering dikutip media | Konsistensi terbit + distribusi |

### Prasyarat supaya benar-benar lebih baik

1. P0 kunci Anthropic di Render.
2. P5 label manusia untuk emosi (tanpa ini klaim "lebih teliti" belum terbukti untuk emosi).
3. Pengumpulan otomatis dinyalakan lagi.
4. Keputusan anggaran API X.
5. Tinjauan sejawat ringan (mis. dosen/rekan UGM) sebelum terbit.

---

## 5. Keputusan yang ditunggu dari pemilik produk

1. **Nama dan domain** situs publikasi.
2. **Bangun sendiri atau Ghost.** Saran agen: bangun sendiri sebagai aplikasi kedua di monorepo
   (mis. `apps/pers`) — grafik interaktif dengan provenance, isi langsung dari snapshot.
   Ghost lebih cepat jadi, tetapi grafik hanya gambar dan isi disalin manual.
3. **Siapa yang boleh menerbitkan** (mis. hanya peran Research Director).
4. **Nama akun pemengaruh**: DE menyebut nama akun; platform kita menyimpan akun sebagai hash
   (CLAUDE.md §3). Apakah tokoh publik (pejabat, media resmi) boleh disebut namanya?
5. Arah "versi riset" (bagian 4) disetujui atau tidak.

---

## 6. Urutan kerja yang diusulkan (±3–4 sesi)

1. Tabel `publications` + RLS + snapshot + tombol "Buat draf publikasi" di `/laporan` + tes isolasi.
2. Situs publik: beranda, artikel, tag, metodologi, tentang, RSS.
3. Artikel pertama: BBM Bali (dari snapshot proyek KELANGKAAN BBM BALI).
4. Ekspor paper (DOCX/PDF) + unduh CSV agregat + panduan sitasi.

Sesudahnya (keunggulan bagian 4): halaman "survei vs sosial vs media", forecast di artikel,
versi EN, DOI Zenodo.

Sebelum mulai di komputer mana pun: `git pull`, baca `CLAUDE.md`, lalu blok
"MULAI DARI SINI" di `docs/deployment-status.md`, lalu dokumen ini.
