# Catatan sesi 12 November 2026 — situs publikasi + modul kinerja komunikasi pemerintah

> Disimpan LOKAL atas permintaan pengguna (belum di-commit / belum di-push). Pengguna akan
> melanjutkan dengan model lain (Fable 5.2). Sesi berikutnya: baca file ini sesudah blok
> "MULAI DARI SINI" di `docs/deployment-status.md` dan `docs/rencana-situs-publikasi.md`.
>
> Status repo saat sesi: `main` = `d2699ae` (PR #57), tidak ada PR terbuka, belum ada kode baru
> di sesi ini. Ada file lokal tak terlacak: `proyek/bbm-bali-youtube/presentasi_bbm_bali_youtube_FINAL.pptx`
> dan `skrip/build_pptx_final.js` (deck FINAL sengaja lokal saja, pilihan pengguna).

---

## Giliran 1 — "cek public opinion, apa yang akan dikerjakan; saya akan menambah list"

Ringkasan yang diberikan agen:

**A. Bisa dikerjakan agen sendiri**
1. Verifikasi production `/sinyal` + `/laporan` BBM Bali (`?dari=2026-10-11&sampai=2026-10-20&zona=WITA`).
2. Jalankan penemuan tema di `/tema` untuk BBM Bali (pertanyaan 6 di `/laporan` masih kosong).
3. Periode tanggal tetap untuk halaman lain (Tema, Command Center, dll. masih jendela relatif).
4. Daftar aktor per proyek (sekarang satu daftar tetap di kode).
5. P11 estimasi gender/umur/minat per akun (sudah diizinkan, belum dimulai; ukuran M–L).

**B. Menunggu pemilik produk**
6. P0 `ANTHROPIC_API_KEY` di Render.
7. P5 label manusia untuk evaluasi leksikon emosi.
8. P8 kanal alert (Telegram gratis / WhatsApp berbayar).
9. P9 format ekspor laporan (PDF / PPTX / DOCX).
10. P10 platform tambahan (X berbayar; TikTok/IG/FB via unggah JSON).
11. Situs publikasi — 5 keputusan di `docs/rencana-situs-publikasi.md` bagian 5.

Catatan: pengumpulan terjadwal masih dimatikan sejak 30 Okt; proyek selain BBM Bali belum
di-rescore ke `informal-4`.

Pengguna belum menambahkan daftar; langsung bertanya soal situs publikasi.

---

## Giliran 2 — "apakah bisa dibuatkan website untuk hasil olah data: tulisan, analisa, artikel ilmiah?"

Jawaban agen: **bisa**, rencana sudah ada di `docs/rencana-situs-publikasi.md`.

Tiga jenis isi:

| Jenis | Isi |
|---|---|
| Tulisan / analisa singkat | Gaya tanya-jawab Drone Emprit, grafik, temuan utama |
| Laporan analisis | Metode, n, sentimen, emosi, aktor, isu, batasan (bahan dari `/laporan`) |
| Artikel ilmiah | Format paper, unduh DOCX/PDF, memakai `~/Documents/panduan-menulis-jurnal/POLA_MENULIS_JURNAL.md` |

Alur: tombol "Buat draf publikasi" di `/laporan` → snapshot angka/grafik (beku) → sunting →
Terbitkan → situs publik dengan grafik interaktif, n, metode, batasan, unduh CSV agregat,
panduan sitasi.

Rekomendasi agen untuk 5 keputusan:
1. Nama/domain — contoh `opini.ms-id.workers.dev` (Cloudflare, sesuai kebijakan hosting) atau domain sendiri. **Belum dijawab.**
2. Bangun sendiri (`apps/pers` di monorepo) vs Ghost — saran: bangun sendiri. **Belum dijawab.**
3. Siapa menerbitkan — saran: hanya pemilik (Research Director). **Belum dijawab.**
4. Nama akun tokoh publik boleh disebut? (warga biasa tetap hash) **Belum dijawab.**
5. Bahasa: ID saja atau ID + EN. **Belum dijawab.**

Perkiraan 3–4 sesi: (1) tabel `publications` + RLS + snapshot + tombol draf + tes isolasi,
(2) situs publik (beranda, artikel, tag, metodologi, tentang, RSS), (3) artikel pertama BBM Bali,
(4) ekspor paper DOCX/PDF + CSV + sitasi.

---

## Giliran 3 — prompt "Analisis Performa Komunikasi Pemerintahan pada Kementerian Koordinator"

Pengguna menempelkan prompt di bawah (disimpan utuh) dan bertanya apakah bisa dimasukkan ke
platform sebagai tambahan untuk melihat performa komunikasi pemerintahan.

### Prompt asli (verbatim)

```markdown
# PROMPT: ANALISIS PERFORMA KOMUNIKASI PEMERINTAHAN PADA KEMENTERIAN KOORDINATOR

## 1. Peran dan Keahlian

Bertindaklah sebagai konsultan senior dan peneliti bidang:
- Government Communication Management.
- Public Sector Communication.
- Digital and Social Media Analytics.
- Strategic Communication.
- Communication Audit.
- Organizational Communication.
- Information Flow and Knowledge Management.

Gunakan perspektif akademis dan praktis untuk mengevaluasi performa komunikasi pemerintahan, khususnya pada Kementerian Koordinator di Indonesia.

## 2. Latar Belakang

Saya ingin mengembangkan kerangka evaluasi performa komunikasi pemerintahan pada Kementerian Koordinator.

Fokus penelitian adalah bagaimana Kementerian Koordinator mengelola informasi dan komunikasi melalui media sosial Instagram, TikTok, dan X.

Berbeda dengan kementerian teknis yang berkomunikasi berdasarkan sektor dan kewenangannya, Kementerian Koordinator mempunyai karakteristik khusus, yaitu mengoordinasikan kebijakan dan informasi lintas kementerian/lembaga.

Karena itu, evaluasi tidak hanya mengukur jumlah followers, likes, comments, shares, views, dan engagement rate, tetapi juga menilai:

1. Bagaimana informasi dikumpulkan dari kementerian teknis.
2. Bagaimana informasi diverifikasi dan diselaraskan.
3. Bagaimana koordinasi komunikasi internal dilakukan.
4. Bagaimana pesan kebijakan dirumuskan.
5. Bagaimana informasi didistribusikan melalui media sosial.
6. Bagaimana pemerintah merespons pertanyaan, kritik, dan isu publik.
7. Bagaimana umpan balik masyarakat diteruskan kembali kepada unit terkait.

## 3. Tujuan Analisis

Bangun sebuah Government Communication Performance Framework yang mampu mengevaluasi:

A. Performa komunikasi digital:
- Instagram.
- TikTok.
- X (Twitter).

B. Performa pengelolaan informasi internal:
- Information gathering.
- Information verification.
- Information coordination.
- Message alignment.
- Information distribution.
- Feedback management.

C. Efektivitas komunikasi publik:
- Visibility.
- Attention.
- Understanding.
- Acceptance.
- Action.

D. Efektivitas koordinasi komunikasi lintas kementerian:
- Konsistensi pesan.
- Kecepatan pertukaran informasi.
- Sinkronisasi komunikasi.
- Kejelasan sumber informasi.
- Mekanisme klarifikasi.
- Tindak lanjut terhadap isu publik.

## 4. Dimensi dan Indikator Evaluasi

Susun indikator secara sistematis dalam empat dimensi utama:

### A. Input
- Ketersediaan SDM komunikasi.
- Kompetensi pengelola media sosial.
- Anggaran komunikasi.
- Infrastruktur digital.
- SOP pengelolaan informasi.
- Sistem koordinasi lintas kementerian.

### B. Process
- Mekanisme pengumpulan informasi.
- Proses verifikasi informasi.
- Koordinasi antardepartemen.
- Proses editorial dan persetujuan konten.
- Strategi distribusi informasi.
- Monitoring dan respons isu.
- Pengelolaan umpan balik masyarakat.

### C. Output
- Jumlah publikasi.
- Reach.
- Impressions.
- Views.
- Engagement rate.
- Shares.
- Saves.
- Response rate.
- Konsistensi pesan lintas platform.

### D. Outcome
- Pemahaman masyarakat.
- Kejelasan informasi kebijakan.
- Keselarasan pesan antarkementerian.
- Kecepatan respons pemerintah.
- Kepercayaan terhadap informasi resmi.
- Tindak lanjut atas masukan masyarakat.

Buat tabel yang memuat:
1. Dimensi.
2. Indikator.
3. Definisi operasional.
4. Cara pengukuran.
5. Sumber data.
6. Metode analisis.
7. Kriteria interpretasi.

Jangan mencampuradukkan indikator output dengan outcome.

## 5. Analisis Karakteristik Platform

Analisis setiap platform dengan indikator yang sesuai karakteristiknya.

Instagram:
- Kualitas infografis.
- Kualitas carousel.
- Reach dan impressions.
- Engagement.
- Saves dan shares.
- Konsistensi identitas visual.

TikTok:
- Video views.
- Average watch time.
- Completion rate.
- Kualitas storytelling.
- Kemudahan memahami kebijakan.
- Interaksi audiens.

X:
- Kecepatan penyampaian informasi.
- Kecepatan klarifikasi.
- Respons terhadap isu.
- Repost dan engagement.
- Percakapan publik.
- Konsistensi pernyataan resmi.

Jelaskan mengapa setiap indikator digunakan dan apa keterbatasannya.

## 6. Pemetaan Arus Informasi Internal

Buat model pemetaan aliran informasi Kementerian Koordinator.

Gunakan alur:

Sumber Informasi
→ Pengumpulan Informasi
→ Koordinasi Lintas Kementerian
→ Verifikasi dan Validasi
→ Perumusan Pesan
→ Persetujuan
→ Produksi Konten
→ Distribusi Media Sosial
→ Respons Publik
→ Monitoring
→ Evaluasi dan Umpan Balik.

Identifikasi:
- Aktor yang terlibat.
- Unit yang bertanggung jawab.
- Titik pengambilan keputusan.
- Potensi hambatan informasi.
- Potensi keterlambatan komunikasi.
- Risiko perbedaan pesan.
- Mekanisme koreksi dan klarifikasi.

Buat diagram alur yang dapat digunakan dalam presentasi.

## 7. Metodologi Penelitian dan Audit

Rekomendasikan pendekatan mixed methods dengan kombinasi:

1. Content Analysis.
2. Social Media Analytics.
3. Communication Audit.
4. Wawancara mendalam.
5. Document Analysis.
6. Social Network Analysis jika relevan.

Jelaskan kebutuhan data, unit analisis, teknik pengumpulan data, teknik pengolahan data, dan metode validasi.

Buat contoh instrumen:
- Lembar coding konten.
- Matriks audit komunikasi.
- Pedoman wawancara pengelola media sosial.
- Pedoman wawancara unit koordinasi.
- Kuesioner pemahaman masyarakat.

## 8. Sistem Penilaian Performa

Rancang sistem evaluasi kuantitatif yang dapat digunakan untuk mengukur performa komunikasi.

Gunakan skala penilaian 1–5 untuk indikator yang memungkinkan dinilai secara ordinal.

Jelaskan:
- Bobot masing-masing dimensi.
- Cara menghitung skor.
- Normalisasi indikator.
- Penanganan data yang tidak tersedia.
- Interpretasi hasil.
- Keterbatasan penilaian.

Jangan membuat bobot atau standar penilaian seolah-olah merupakan standar resmi pemerintah. Tandai sebagai rancangan model yang perlu diuji dan divalidasi.

## 9. Rancangan Dashboard Evaluasi

Buat konsep dashboard Government Communication Performance dengan fitur:

### Dashboard 1: Executive Overview
- Skor performa komunikasi.
- Tren performa bulanan.
- Total publikasi.
- Total engagement.
- Reach dan views.
- Ringkasan temuan utama.

### Dashboard 2: Social Media Performance
- Perbandingan Instagram, TikTok, dan X.
- Engagement rate.
- Reach.
- Views.
- Interaksi.
- Tren konten.

### Dashboard 3: Content Analysis
- Kategori konten.
- Tema kebijakan.
- Sentimen komentar.
- Konsistensi pesan.
- Kualitas informasi.
- Jenis komunikasi.

### Dashboard 4: Information Flow
- Sumber informasi.
- Proses koordinasi.
- Waktu verifikasi.
- Waktu persetujuan.
- Waktu publikasi.
- Titik hambatan informasi.

### Dashboard 5: Public Feedback
- Pertanyaan masyarakat.
- Kritik dan keluhan.
- Isu dominan.
- Waktu respons.
- Status tindak lanjut.

### Dashboard 6: Strategic Recommendations
- Permasalahan prioritas.
- Temuan audit.
- Rekomendasi perbaikan.
- Prioritas tindak lanjut.

## 10. Landasan Teori dan Literatur

Gunakan teori dan literatur akademik yang relevan, terutama:

- Government Communication.
- Strategic Communication.
- Organizational Communication.
- Communication Audit.
- Public Relations Evaluation.
- Excellence Theory.
- Social Media Engagement.
- Information Management.
- Public Sector Performance Measurement.

Identifikasi teori utama dan teori pendukung.

Gunakan referensi ilmiah yang dapat diverifikasi, utamakan jurnal internasional bereputasi, buku akademik, dan dokumen resmi pemerintah.

Jangan membuat referensi, DOI, atau kutipan fiktif.

## 11. Hasil Akhir yang Harus Dihasilkan

Susun hasil dalam urutan:

1. Executive Summary.
2. Konsep Performa Komunikasi Pemerintahan.
3. Karakteristik Komunikasi Kementerian Koordinator.
4. Kerangka Government Communication Performance.
5. Matriks Indikator Evaluasi.
6. Analisis Instagram, TikTok, dan X.
7. Diagram Arus Informasi Internal.
8. Metodologi Audit Komunikasi.
9. Model Penilaian Performa.
10. Rancangan Dashboard.
11. Rekomendasi Strategis.
12. Referensi Akademik.

## 12. Prinsip Analisis

Perhatikan beberapa ketentuan berikut:

- Bedakan popularitas media sosial dengan efektivitas komunikasi pemerintahan.
- Jangan menyimpulkan keberhasilan komunikasi hanya dari engagement rate.
- Bedakan komunikasi internal, komunikasi antarlembaga, dan komunikasi publik.
- Perhatikan karakteristik khusus Kementerian Koordinator.
- Gunakan data empiris, bukan asumsi.
- Tandai data yang tidak tersedia.
- Pisahkan fakta, interpretasi, dan rekomendasi.
- Hindari memberikan penilaian tanpa indikator dan bukti.

Hasil akhir harus menjadi kerangka evaluasi yang dapat digunakan oleh peneliti, pengelola komunikasi pemerintahan, dan pimpinan Kementerian Koordinator untuk memahami sekaligus memperbaiki performa komunikasi organisasi.
```

### Jawaban agen: bisa, sebagai modul baru "Kinerja Komunikasi Pemerintah"

Platform kuat di sisi **publik** (respons publik, isi konten, konsistensi pesan); sisi
**internal** kementerian (Input/Process) harus dari audit + wawancara, tidak bisa otomatis.

**Sudah ada dan bisa dipakai ulang**

| Kebutuhan prompt | Yang sudah ada |
|---|---|
| Sentimen komentar, isu dominan, kritik | `/sinyal`, `/tema`, `/laporan`, kartu emosi (`emosi-id-2`), peta aktor |
| Kuesioner pemahaman masyarakat | Modul survei (`models/survey.py`, `routers/surveys.py`) |
| Survei vs sosial vs media | `/consistency` (`/opinion/divergence`) |
| Lembar coding manual | Pola koreksi label manual (`manual-1`, 10 Nov) |
| Jejak perubahan | `audit_logs` |
| Pilot | 3 proyek POLKAM (Kemendagri 293, Kemenlu 745, Kemenhan 116 konten per 1 Nov) — semua di bawah koordinasi **Kemenko Polkam**; tinggal tambah proyek Kemenko Polkam. Materi kuliah terkait: repo `manajemen-komunikasi-polkam` |

**Perlu dibangun**
1. Data akun resmi IG/TikTok/X per kementerian (per unggahan: tanggal, jenis, like, komentar, share, views).
2. Matriks indikator Input/Process/Output/Outcome (definisi operasional, cara ukur, sumber, metode, kriteria) — output dan outcome dipisah tegas.
3. Coding konten (kategori, tema kebijakan, jenis komunikasi, kualitas informasi) + uji kesepakatan antar-pengode.
4. Konsistensi pesan lintas kementerian: siapa duluan, selisih waktu, pernyataan bertentangan.
5. Kecepatan respons/klarifikasi: waktu dari lonjakan isu ke unggahan resmi.
6. Form audit komunikasi (SDM, SOP, waktu verifikasi/persetujuan) dari wawancara/dokumen.
7. Skor 1–5, bobot bisa diubah, label wajib "rancangan model, belum divalidasi, bukan standar resmi"; data kosong = "tidak tersedia", bukan ditebak.
8. Enam dashboard sesuai prompt (sebagian memakai halaman yang ada).

**Batasan yang harus jujur disampaikan**
- Reach, impressions, saves, average watch time, completion rate = **hanya pemilik akun** (Meta Business Suite, TikTok Studio). Tanpa kerja sama humas → "data tidak tersedia".
- IG/TikTok/X tidak punya API publik gratis. Angka publik via unggah JSON/CSV dari alat pihak ketiga yang legal (jalur PR #43), atau X API berbayar. Scraping melanggar ketentuan.
- Arus informasi internal tidak terlihat dari media sosial; platform hanya menyediakan formulir + visualisasi.
- Teori + referensi paling tepat sebagai dokumen/artikel, referensi dicek via Crossref (jangan fiktif), lalu bisa terbit di situs publikasi.
- Aturan CLAUDE.md tetap berlaku (R1 per sumber, R2 `AIEnvelope`, R3 RLS di commit yang sama, §3 akun hash / tidak menyimpulkan sebab).

**Usulan urutan**
1. Dokumen kerangka (tanpa kode): matriks indikator, diagram arus informasi, instrumen (lembar coding, matriks audit, pedoman wawancara pengelola medsos + unit koordinasi, kuesioner), model skor, referensi terverifikasi. Sekaligus bahan artikel.
2. Data akun resmi (unggah) + dashboard Social Media Performance.
3. Coding konten + konsistensi pesan + kecepatan respons.
4. Form audit + skor + dashboard Executive Overview.
5. Terbit di situs publikasi.

**Pertanyaan yang belum dijawab pengguna**
1. Kemenko yang mana? (saran: Kemenko Polkam)
2. Akses data: ada kemungkinan ekspor insight dari humas, atau hanya data publik?
3. Tujuan: tugas kuliah/artikel, atau alat untuk klien/kementerian?
4. Mulai dari tahap 1 (dokumen kerangka) atau langsung modul platform?

---

## Giliran 4

Pengguna meminta seluruh percakapan disimpan lokal karena akan berganti ke model Fable 5.2.
File ini dibuat; tidak ada commit/push.
