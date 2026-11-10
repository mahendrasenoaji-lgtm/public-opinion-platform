# Benchmark: NoLimit Dashboard vs Public Opinion Platform

Dibuat 2026-11-08. Sumber: pengamatan langsung `dashboard.nolimit.id` lewat
sesi Chrome pengguna yang sudah login (proyek NoLimit "Ilkom UGM - 5"), plus
pemeriksaan kode repo ini pada commit `9155007`.

> **Batas metode.** Yang dilihat hanya (1) tampilan tiap menu dan (2) nama
> operasi GraphQL yang tertulis di file JavaScript publik yang dimuat halaman.
> API NoLimit tidak dipanggil langsung, tidak ada data yang diunduh, dan isi
> respons tidak diperiksa. Jadi daftar fitur di bawah = apa yang *ada di kode
> klien*, bukan bukti bahwa semuanya aktif untuk semua paket.

---

## 1. Cara NoLimit dibangun

| Lapisan | Temuan |
|---|---|
| Frontend | React SPA (Create React App, chunk `static/js/*.chunk.js`, ±5 MB JS) |
| Backend | **Satu endpoint GraphQL**: `https://v5.backend.dashboard.nolimit.id/graphql` (versi 5). Halaman Overview saja memicu ±50 POST |
| Ukuran API | **492 operasi** (query + mutation), pola nama `Domain_operasi`, mis. `conversation_getTalkV2`, `onlineMedia_getTopPeople` |
| Konsep inti | **Project** → berisi **Object** (akun / kata kunci / hashtag per platform) → bisa dikelompokkan jadi **Group** |
| Lainnya | Google Tag Manager, PWA manifest, AppSumo + billing internal, referral code |

Proyek yang diamati: 9 objek X, 1 Facebook, 2 Instagram, 1 YouTube, 1 TikTok.
Jendela 1 minggu: Talk 10,6 rb · Engagement 3,2 jt · Potential reach 226,3 jt.
(Catatan: kartu "Total Followers" menampilkan `0` dengan label "100% Increased",
tanda ada metrik yang tampil tanpa data dasar.)

### Peta menu (rute)

| Grup | Rute |
|---|---|
| Customization | `/customization/custom_dashboard`, `/customization/custom_report` |
| Stream Panel | `/stream_panel/social_media`, `/online_media`, `/people_panel`, `/offline_media` |
| Social Media | `/social_media/overview`, `content`, `community`, `campaign`, `conversation`, `comparison`, `sna`, `dna`, `clustering` |
| Social Media Integration | `/social_media_integration/instagram_performance` (akun milik sendiri, lewat otorisasi) |
| Online Media | `/online_media/statistic`, `clipping`, `comparison` |
| Print & Broadcast | `/offline_media/statistic`, `clipping`, `comparison` |
| Lainnya | `/settings`, `/news_letter`, tombol **AI Assistant** di semua halaman |

### Jumlah operasi per domain (yang paling relevan)

| Domain | Ops | Isi penting |
|---|---|---|
| `onlineMedia` | 49 | kliping (manual + auto), press release, nilai PR, outreach, top people/organization/location, **kutipan per tokoh** (`QuotationWithPerson`), word cloud, koreksi sentimen/label/visibilitas massal |
| `conversation` | 26 | talk, talker, positif/negatif + pertumbuhannya, talk by media, talk type (share of voice), **gender, interest, location**, word cloud, top talk |
| `comparison` (+ online/offline) | 21+13+11 | perbandingan merek: popularity, positioning, sentiment, peak time, share of views |
| `customReportV2` | 21 | wizard laporan dan template |
| `content` | 18 | post made, like/comment/share kronologis, **peak time**, top post |
| `offlineMedia` | 15 | cetak dan siaran: artikel, sentimen, top people/location, nilai PR |
| `peoplePanel` | 14 | **melabeli pengguna** yang terlibat: gender, umur, minat, lokasi, label bebas |
| `rawStream` | 13 | **koreksi manual per item**: sentimen, emosi, tipe media, visibilitas, dan versi massal "by filter" |
| `objectManagement` | 14 | tambah/edit/hapus objek, batas objek per paket, pratinjau stream |
| `overview` / `Overview` | 10+2 | engagement, reach, follower, talk, `reputationHealthScore`, `platformSentimentBreakdown` |
| `campaign` | 10 | kampanye dengan tanggal mulai/selesai, audience engagement |
| `alertSystem` | 6 | alert otomatis/manual, **WhatsApp**, laporan harian |
| `labellingSystem` / `autoLabel` | 6+5 | label manual + aturan auto-label |
| `clusteringOnm` | 4 | klaster topik berita + treemap |
| `networkAnalyst` | 1 | `NetworkAnalystOntology` (SNA/DNA) |
| `Chat` | 4 | AI Assistant (percakapan) |
| `ecommerce*`, `googleReview` | ±50 | perbandingan marketplace dan rating Google, di luar lingkup kita |

### Pertanyaan yang dijawab halaman Conversation (judul kartu)

Day-to-day conversation (+ **AI Summary**) · Conversation by media · Sentiment
analysis · Share of voice (talk type) · Engaged user by gender / interest /
location · **Emotion analysis** · Talker by emotion · List of talk paling
engaging · Top talker · **Peak time** · Word cloud per sentimen.

---

## 2. Perbandingan

| Aspek | NoLimit | Platform kita | Siapa unggul |
|---|---|---|---|
| Fokus | Pemantauan merek dan media: volume, jangkauan, PR | Riset opini publik: sikap, tren, indeks, prediksi | beda tujuan |
| Platform sosial | X, FB, IG, TikTok, YouTube | YouTube (API + search). Konektor X ada, `X_BEARER_TOKEN` belum dipasang | NoLimit |
| Berita | Online + cetak + siaran, kliping, nilai PR | RSS online (±14 feed per proyek) | NoLimit |
| Volume dan jangkauan | Engagement, reach, impression, follower, peak time | `engagement` tersimpan (YouTube = like + balasan), tampil di /sinyal dan /pengaruh; `reach_est` ada di model tapi kosong | NoLimit |
| Sentimen | Pos/neg/netral, tanpa angka akurasi yang dipublikasikan | Leksikon formal + informal-4 + 13 bahasa daerah, **akurasi diukur dan dibuka** (F1, abstain, presisi negatif 95,6%) | **Kita** |
| Emosi | Tampil di dashboard + "talker by emotion" | **Sudah dihitung** (`services/sentiment.py:emotions`, kolom `mentions.emotion`), **belum tampil** di UI dan belum dievaluasi | NoLimit (tampilan) |
| Koreksi manual | Per item dan massal (sentimen, emosi, label, visibilitas) | Belum ada; hanya rescore massal berbasis kamus | NoLimit |
| Profil pengguna | Gender, umur, minat, lokasi per pengguna | Belum ada; diputuskan dibangun (P11) | NoLimit |
| Aktor dan jaringan | SNA, DNA, top people/org dari berita, kutipan per tokoh | Peta aktor (`services/actors.py`), jaringan, pengaruh | setara, NoLimit lebih luas di berita |
| Topik | Clustering + word cloud | Tema, narasi (`services/topics.py`) | setara |
| Survei dan indeks | Tidak ada | POI, bobot raking, segmen, konsistensi, divergensi | **Kita** |
| Prediksi | Tidak ada | Forecast state-space, what-if, deret metrik | **Kita** |
| AI | AI Assistant + AI Summary per grafik, aktif | Brief, Copilot, Pembaca AI sudah dibangun, **menunggu `ANTHROPIC_API_KEY` di Render** | NoLimit (aktif) |
| Laporan | Wizard laporan, dashboard kustom, newsletter | Modul `reports` ada, belum ada builder | NoLimit |
| Alert | Otomatis/manual, WhatsApp, laporan harian | Anomali z-score di Command Center, hanya di dalam aplikasi | NoLimit |
| Jejak sumber dan tata kelola | Tidak terlihat | URL asal, `source_url_origin`, audit log, halaman Governance | **Kita** |

**Kesimpulan.** NoLimit unggul di cakupan (platform, media cetak/siaran) dan
di metrik operasional PR (volume, jangkauan, alert). Platform kita unggul di
kedalaman metodologi: indeks opini, forecast, sentimen yang akurasinya terukur,
bahasa daerah, dan jejak sumber. Kita tidak perlu mengejar semua fitur NoLimit;
ambil yang memperkuat riset dan yang datanya sudah ada.

---

## 3. Prioritas pekerjaan

Urutan berdasarkan: dampak untuk riset × seberapa banyak yang sudah ada ×
risiko. Ukuran: **S** ≤ 1 sesi, **M** 2–3 sesi, **L** > 3 sesi.

> **Status 2026-11-10.** P1, P3, P4, dan P6 (tahap pertama) selesai dikerjakan; P2 ternyata sudah ada
> (kartu sentimen per sumber sejak 12 Okt). Ditambah satu hal di luar daftar: periode
> tanggal tetap di `/sinyal`. P4 dibuat **tanpa kolom baru** (label manual memakai
> `sentiment_model = "manual-1"`), jadi catatan migrasi di baris P4 tidak berlaku lagi.
> P6 memakai peta aktor yang sudah ada + kutipan bertanda petik dari liputan; daftar
> aktor per proyek belum ada. Rincian dan bukti: blok 10 November di
> `docs/deployment-status.md`. Berikutnya: P5 (butuh label manusia), P11.

### Tahap A — data sudah ada, tinggal ditampilkan

| # | Pekerjaan | Ukuran | Kenapa | Titik mulai | Selesai bila |
|---|---|---|---|---|---|
| **P1** | **Kartu emosi** di /sinyal (atau halaman Tema): distribusi marah/takut/sedih/senang/dll. per jendela waktu, dipisah MEDIA vs SOSIAL | S | Sudah dihitung tiap mention tapi tidak pernah terlihat | `services/sentiment.py:493 emotions()`, `routers/signals.py:651`, `apps/web/app/(dashboard)/sinyal/page.tsx` | Kartu tampil dari data prod, dengan label metode "leksikon emosi, belum dievaluasi" |
| **P2** | **Pisahkan kartu sentimen MEDIA vs SOSIAL** + share of voice per sumber | S | Sudah ada di daftar celah (`deployment-status.md`); NoLimit memisah per platform | router sentimen di `signals.py`, halaman /sinyal | Dua angka terpisah, masing-masing dengan n |
| **P3** | **Metrik engagement dan jam ramai**: total engagement per hari, komentar paling engaging, heatmap jam × hari | S–M | `engagement` dan `published_at` sudah tersimpan | `models/signal.py`, `routers/signals.py`, halaman /sinyal atau /deret | Grafik dari data BBM Bali/MBG di prod |

### Tahap B — fitur baru yang memperkuat riset

| # | Pekerjaan | Ukuran | Kenapa | Catatan |
|---|---|---|---|---|
| **P4** | **Koreksi sentimen manual per item** (+ massal dengan filter) | M | Setiap koreksi = label emas baru untuk evaluasi kamus; peneliti bisa membetulkan sarkasme | Butuh kolom baru (mis. `sentiment_manual`, `corrected_by`, `corrected_at`). **Ingat pelajaran PR #7:** jalankan migrasi Supabase **sebelum** deploy kode yang membaca kolom itu. Koreksi manual harus menang atas rescore dan tercatat di audit log |
| **P5** | **Evaluasi leksikon emosi** pada sampel berlabel (seperti `sentiment_eval_field.py`) | S–M | Supaya P1 bisa dipertanggungjawabkan | Bisa memakai hasil P4 sebagai sumber label |
| **P6** | **Tokoh, organisasi, lokasi, dan kutipan dari berita** | M | NoLimit punya `TopPeople` dan `QuotationWithPerson`; kita punya peta aktor untuk komentar | Perluas `services/actors.py` ke teks berita RSS; kutipan = kalimat dalam tanda petik + nama di dekatnya |
| **P7** | **AI Summary per grafik** | S, setelah kunci API ada | NoLimit menaruh ringkasan AI di tiap kartu | Pakai `ai/brief.py`; wajib lewat `ai/envelope.py` (sumber + metode) |

### Tahap C — butuh keputusan atau akun dari pengguna

| # | Pekerjaan | Keputusan yang dibutuhkan |
|---|---|---|
| **P0** | Pasang `ANTHROPIC_API_KEY` di Render | Pengguna memasang kunci sendiri (Brief, Copilot, Pembaca AI langsung hidup) |
| **P8** | **Alert keluar** (email / Telegram / WhatsApp) + ringkasan harian | Pilih kanal. Telegram bot gratis dan paling mudah; WhatsApp butuh WhatsApp Business API berbayar |
| **P9** | **Builder laporan / ekspor PDF** dari dashboard | Format mana yang paling dipakai (PDF vs PPTX vs DOCX)? Skrip deck BBM Bali bisa jadi dasar |
| **P10** | **Platform tambahan**: X (token berbayar), TikTok/IG/FB | X: mau bayar API? TikTok/IG/FB tidak punya API listening publik yang gratis, dan scraping melanggar ketentuan mereka. **Rekomendasi:** X dulu kalau ada anggaran, sisanya lewat unggah JSON (panel PR #43) dari alat pihak ketiga yang legal |

### Tahap D — segmentasi audiens untuk promosi (diputuskan 2026-11-08)

**P11 — Estimasi gender, kelompok umur, dan minat per akun** (padanan People
Panel NoLimit). Ukuran **M–L**. Disetujui pemilik produk untuk data promosi
yang tersegmen; pengecualian sempit tercatat di CLAUDE.md §3.

Supaya hasilnya benar-benar tepat sasaran (dan bisa dipertanggungjawabkan):

| Bagian | Isi |
|---|---|
| Atribut | `gender_est` (L/P/null), `age_band_est` (≤17, 18–24, 25–34, 35–44, 45+ / null), `interests_est` (daftar kategori tetap, mis. otomotif, kuliner, olahraga, gim, keluarga, keuangan, wisata). **Tidak** agama, etnis, orientasi seksual, kesehatan, atau afiliasi politik |
| Sinyal | Nama tampilan (kamus nama Indonesia → gender), kata ganti dan sapaan dalam komentar sendiri ("saya ibu dua anak", "bro", "gue anak SMA"), kosakata dan topik video yang dikomentari (→ minat), pola jam aktif. Hanya data publik yang sudah dikumpulkan konektor |
| Keluaran | Setiap nilai membawa `method`, `confidence` 0–1, dan `evidence` (kata penanda). Di bawah ambang (mis. 0,6) → `null` = "tidak diketahui", bukan tebakan paksa |
| Akurasi | Wajib ada set uji berlabel manual (±300 akun, dua penilai) seperti `sentiment_eval_field.py`, sebelum angka dipakai untuk promosi. Tampilkan presisi per atribut di UI |
| Tampilan | Bawaan agregat: piramida umur × gender, minat teratas per segmen, sentimen per segmen. Ekspor daftar akun per segmen hanya untuk peran berizin (mis. `analyst`+), tercatat di audit log |
| Data | Tabel baru `author_profiles` (bertenant → kebijakan RLS di `db/rls.sql` di commit yang sama, CLAUDE.md R3), terpisah dari `respondents` survei. Retensi (mis. 180 hari) + endpoint koreksi/hapus per akun |
| Kode | `services/profiling.py` (fungsi murni + tes), dipanggil dari pipeline; kartu baru di /segments atau /pengaruh |

**Yang perlu diperhatikan sebelum dipakai untuk promosi:**

1. **UU PDP (UU 27/2022).** Profiling untuk pemasaran adalah pemrosesan data
   pribadi; perlu dasar pemrosesan yang sah dan hak subjek data (akses, koreksi,
   hapus, keberatan atas profiling). Konsultasikan dengan penasihat hukum klien.
2. **Ketentuan platform.** Kebijakan pengembang YouTube API membatasi
   penyimpanan dan pemakaian data pengguna; cek ulang sebelum mengekspor daftar
   akun ke pihak ketiga atau ke alat iklan.
3. **Ketepatan sasaran.** Tebakan dari teks publik lebih lemah daripada
   demografi yang dipakai platform iklan (data akun yang login). Pemakaian
   paling efektif: profil agregat dari P11 untuk **memilih setelan target**
   di Google Ads / Meta Ads, dan pesan per segmen; bukan menghubungi akun satu
   per satu.

### Sengaja tidak ditiru

- **E-commerce dan Google Review comparison**, di luar lingkup opini publik.
- **"Potential reach" tanpa dasar.** NoLimit menampilkan 226 juta tanpa
  penjelasan; aturan kita (CLAUDE.md) melarang angka tanpa sumber dan metode.

---

## 4. Cara melanjutkan di komputer lain

```bash
cd ~/Documents/public-opinion-platform   # atau lokasi clone di komputer itu
git pull
open docs/benchmark-nolimit.md           # dokumen ini
```

P1–P4 dan P6 tahap pertama selesai (lihat status 10 November di bagian 3). Lanjut
dari **P11**; P5 butuh label manusia lebih dulu. Urutan kerja umum
tetap: `docs/deployment-status.md` (blok MULAI DARI SINI) → `CLAUDE.md` →
dokumen ini.
