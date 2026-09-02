# Progres

Satu tempat untuk melihat **apa yang sudah jadi, apa yang belum, dan apa yang
menahannya.** Diperbarui 2026-09-01.

Dokumen ini melengkapi dua yang lain, tidak menggantikannya:

- `docs/roadmap.md` — daftar centang per fase, urutan pengerjaan.
- `docs/deployment-status.md` — riwayat deploy, kredensial, dan catatan sesi
  per sesi. Itu sumber kebenaran untuk **apa yang hidup di production**.
- **Dokumen ini** — status jujur per komponen: bukan sekadar "ada kodenya",
  tapi seberapa jauh ia sudah dibuktikan bekerja.

## Cara membaca kolom "Bukti"

Kata-kata ini dipakai konsisten dan artinya sempit:

| Label | Artinya |
|---|---|
| **Teruji** | Ada tes otomatis yang lulus terhadap Postgres nyata dengan RLS aktif |
| **Live lokal** | Dijalankan sungguhan di browser/API terhadap Postgres lokal |
| **Live production** | Dijalankan sungguhan terhadap Supabase + Render + Vercel |
| **Kode saja** | Kodenya ada dan lulus lint/tipe, tapi belum pernah dijalankan sungguhan |

Perbedaan "Live lokal" dan "Live production" bukan formalitas. Tujuh bug pada
2026-08-20 dan dua bug RLS pada 2026-08-24 semuanya hanya terlihat setelah
menyentuh database sungguhan — bukan dari membaca kode, dan bukan dari tes
yang lulus tanpa database.

---

## Ringkasan angka

| | |
|---|---|
| Tes backend | **473 lulus** (role `pop_app`, RLS aktif — bukan superuser) |
| Endpoint API | 56, dengan 17 baru pada Phase 2/3 |
| Halaman dashboard | 15 (9 Phase 1 + 6 Phase 2/3) |
| `ruff` | Bersih di `app` dan `tests` |
| `mypy --strict` | Bersih di `app/services`, `app/ai`, `app/connectors` |
| Frontend | `tsc --noEmit` dan `next build` hijau |

---

## Phase 1 — fondasi · **SELESAI**

| Komponen | Bukti |
|---|---|
| Skema database + RLS multi-tenant | Live production |
| Auth JWT + refresh + argon2 + RBAC 8 peran | Live production |
| CRUD organization / project + audit log | Live production |
| Survey builder (9 tipe pertanyaan) + ingest respons | Teruji |
| `services/poi.py` — Public Opinion Index | Live production |
| `services/sampling.py` — kalkulator ukuran sampel | Teruji |
| `services/quality.py` — straight-lining, speeding | Teruji |
| `services/divergence.py` — pembeda utama produk | Live production |
| `services/weighting.py` — raking pasca-stratifikasi | Live lokal |
| `ai/envelope.py` — kontrak keluaran AI (R2) | Teruji |
| Registrasi self-service + project switcher + edit/hapus proyek | Live lokal |
| 9 halaman dashboard Phase 1 | Live production |

**Residual Phase 1 yang masih terbuka:**

- "Isu publik" dan "Peringatan aktif" belum dirender di Command Center. Topic
  modeling kini sudah ada (`/tema`) tapi Command Center belum menariknya;
  anomaly detection belum ada sama sekali.
- Endpoint weighting (raking) dan trend/timeline belum diverifikasi spesifik
  terhadap Supabase — baru di Postgres lokal.

---

## Phase 2 — sinyal · **SELESAI, dengan pengecualian tercatat**

| Komponen | Bukti | Catatan |
|---|---|---|
| `models/signal.py` — Mention, Topic, DataSource | Teruji | Kolom `vector(1024)` sengaja tidak dipetakan |
| `services/ingestion.py` — dedup, bahasa, hash akun | Teruji (28 tes) | MinHash + LSH |
| `services/sentiment.py` + set evaluasi | Teruji (30 tes) | macro-F1 0.902 |
| `services/topics.py` — TF-IDF + LSA + HDBSCAN | Teruji (28 tes) | **Bukan embedding** — lihat di bawah |
| `services/pipeline.py` — perekat ingestion+sentiment | Teruji | |
| `connectors/rss.py` — media monitoring | Teruji parsing | Belum pernah menarik feed sungguhan |
| `connectors/youtube.py` — YouTube Data API v3 | Teruji parsing | Butuh `YOUTUBE_API_KEY` |
| `connectors/x.py` — X API v2 recent search | Teruji parsing | Butuh `X_BEARER_TOKEN` |
| `connectors/manual.py` — unggahan/ekspor vendor | Teruji | Jalur yang benar-benar dipakai sekarang |
| 9 endpoint `signals/*` | Teruji (28 tes) + Live lokal | |
| 2 endpoint `topics/*` | Teruji + Live lokal | |
| `ai/retrieval.py` + `ai/copilot.py` — RAG | Teruji (23 tes) | Jawaban LLM sungguhan belum diuji |
| Halaman `/sinyal`, `/tema`, `/copilot` | Live lokal | |

### Yang SENGAJA tidak dikerjakan di Phase 2, dan alasannya

**Topic discovery memakai TF-IDF, bukan embedding.** Roadmap menulis
"embedding → HDBSCAN → label LLM". Belum ada provider embedding yang
dikonfigurasi di deployment mana pun, jadi yang dijalankan TF-IDF → LSA →
HDBSCAN → label kata kunci — dan `method` mengembalikan persis itu. Mengklaim
"embedding" untuk vektor TF-IDF melanggar R1 di tempat paling mahal: metadata
metode adalah satu-satunya cara pembaca laporan tahu seberapa jauh angka ini
bisa dipercaya. Titik penggantinya satu fungsi (`_vectorize`); label metodenya
**wajib ikut berubah di commit yang sama** saat diganti.

**Verifikasi manusia atas label tema belum ada.** Label sekarang gabungan kata
kunci, bukan kalimat interpretatif — justru karena kalimat interpretatif butuh
verifikasi yang belum dibangun.

**Stance tingkat artikel belum ada.** Yang ada baru volume dan sentimen
leksikon atas judul + ringkasan yang penerbit sediakan di feed. Isi artikel
lengkap sengaja tidak diambil (hak cipta penerbit).

**Pipeline belum pindah ke worker.** `POST .../collect` jalan sinkron di dalam
permintaan HTTP, dengan batas `limit` supaya di bawah timeout. Cukup untuk
menarik satu sumber atas permintaan pengguna; pengumpulan terjadwal berskala
besar masih perlu worker terpisah.

**Peta geografis MapLibre belum ada.** Belum ada sumber data bergeoreferensi
asli. Grid provinsi berperingkat tetap dipakai. Provinsi **tidak** diinferensi
dari isi teks — hasilnya akan dipakai sebagai georeferensi padahal bukan.

---

## Phase 3 — prediksi · **SELESAI, dengan pengecualian tercatat**

| Komponen | Bukti | Catatan |
|---|---|---|
| `services/timeseries.py` — state-space di-fit | Teruji (17 tes) | Menggantikan `DEFAULT_SPREAD` tetap |
| `GET .../forecast/baseline` | Teruji (15 tes) | |
| `POST .../forecast/what-if` di atas model terpasang | Teruji | `fitted: false` bila riwayat kurang |
| Polarization Index | Live lokal | Selesai 2026-08-27 |
| `GET .../risk/score` — 9 komponen | Teruji (25 tes unit) + Live lokal | 8 dari 9 komponen nyata |
| `services/influence.py` + endpoint | Teruji (16 tes unit) | |
| `services/impact.py` — DiD + synthetic control + endpoint | Teruji (40 tes unit) | Synthetic control: gating donor/periode, placebo |
| `services/network.py` + endpoint | Teruji (10 tes unit) | Graf balasan/kutipan, bukan pengaruh kausal |
| Tes router influence + impact + network | Teruji (33 tes) | Termasuk tes isolasi tenant |
| Halaman `/risiko`, `/pengaruh`, `/dampak`, `/jaringan` | Live lokal | `/dampak` sekarang dua panel: DiD + synthetic control |

### Yang SENGAJA tidak dikerjakan di Phase 3, dan alasannya

**`geographic_spread` — 1 dari 9 komponen risiko — tetap kosong.** Ia butuh
geotag resmi dari sumbernya, dan sebagian besar percakapan tidak punya itu.
Ia dilaporkan sebagai komponen yang hilang beserta alasannya di UI, bukan
ditebak. Skor tidak diterbitkan sama sekali bila cakupan bobot di bawah 60%.

**Skala komponen risiko belum dikalibrasi.** `SENTIMENT_DROP_AT_FULL_RISK`,
`GROWTH_PCT_AT_FULL_RISK`, dan `POINT_DECLINE_AT_FULL_RISK` adalah penilaian
tim, bukan hasil kalibrasi terhadap kejadian krisis nyata — belum ada dataset
berlabel untuk itu. Konsekuensinya tertulis di `limitations` yang tampil di
layar: skor ini untuk **membandingkan periode atau proyek berskala sama**,
bukan sebagai ambang absolut ("di atas 60 berarti krisis").

**Fitting model belum pindah ke worker.** Sama seperti pipeline ingestion:
cukup cepat untuk jumlah pengamatan sekarang, perlu dipindah begitu riwayatnya
panjang atau proyeknya banyak.

---

## Phase 4 — enterprise · **BELUM DIMULAI**

Tidak ada satu pun item Phase 4 yang dikerjakan. Ini keputusan, bukan
kehabisan waktu.

| Item | Yang menahan |
|---|---|
| SSO / SAML / SCIM | Penyedia identitas mana yang dipakai — keputusan organisasi |
| MFA wajib | Kolom `users.mfa_secret` sudah ada di schema; alur enrolmen dan pemulihan butuh keputusan kebijakan |
| Billing + kredit survei/data/AI | Penyedia pembayaran mana, dan model harga apa |
| API publik + webhook | Kontrak API publik tidak bisa ditarik lagi setelah ada yang memakainya |
| Rate limiting per tenant | Menyusul API publik |
| Report generator PDF/DOCX/PPTX/XLSX | Bisa dikerjakan kapan saja; belum ada permintaan konkret soal format laporan |
| Observability: tracing, evaluasi model, deteksi drift | Bisa dikerjakan; paling berguna setelah ada trafik produksi nyata |
| Orkestrasi multi-agent penuh | `ai/agents.py:Orchestrator` sudah ada dan dipakai Brief + Copilot, tapi baru menjalankan satu agen berurutan |

Empat item pertama butuh keputusan yang bukan wewenang agen. Sesuai
CLAUDE.md §8, lebih baik berhenti dan bertanya daripada memilih sendiri lalu
mengunci proyek ke pilihan itu.

---

## Yang BELUM diverifikasi — baca sebelum mengandalkan angka mana pun

Ini bagian terpenting dari dokumen ini.

1. **Tidak ada satu pun fitur Phase 2/3 yang diuji terhadap Supabase
   produksi.** Seluruh verifikasi memakai Postgres lokal. Langkah lanjutan:
   tunggu Render + Vercel redeploy, lalu ulangi pemeriksaan manual terhadap
   production. Itu butuh login `SITE_PASSWORD` yang di luar kemampuan agen.

2. **Konektor RSS, YouTube, dan X belum pernah menarik data sungguhan.** Yang
   diuji adalah parsing responsnya (fungsi murni) dan penanganan kredensial
   kosong. Menarik sungguhan butuh kunci API di Render, dan untuk RSS butuh
   jaringan keluar dari Render ke penerbitnya.

3. **Copilot belum pernah menjawab dengan LLM sungguhan.** Jalur suksesnya
   diuji lewat provider tiruan yang mengembalikan JSON valid. Yang terbukti
   adalah pipa di sekelilingnya — envelope tersusun benar, baris `ai_outputs`
   tertulis dan terbaca kembali — **bukan mutu jawaban model**. Sama seperti
   Executive Brief, ini menunggu `ANTHROPIC_API_KEY` aktif.

4. **Forecast state-space belum pernah di-fit pada data produksi.** Seed
   Supabase hanya punya satu snapshot per metrik, jadi `/forecast/baseline`
   akan membalas `insufficient_data` di sana sampai ada gelombang kedua. Itu
   perilaku yang benar, bukan bug.

5. **Akurasi sentimen yang tampil di `/sinyal` adalah batas ATAS.** Ia diukur
   pada 52 kalimat yang ditulis tim pengembang, bukan pada percakapan proyek
   mana pun. Kalimat yang ditulis sendiri selalu lebih rapi dan lebih jelas
   polaritasnya daripada yang ditemukan di lapangan. Sebelum dipakai untuk
   keputusan, ukur ulang terhadap sampel berlabel dari data proyek itu sendiri.

---

## Langkah berikutnya yang paling masuk akal

Berurutan, dari yang paling murah dan paling menaikkan kepercayaan:

1. **Verifikasi Phase 2/3 terhadap production.** Semua kodenya sudah di
   `main`; yang kurang cuma menjalankannya di sana.
2. **Aktifkan `ANTHROPIC_API_KEY` di Render**, lalu verifikasi Executive Brief
   dan Copilot menghasilkan jawaban yang masuk akal dan tidak memuat klaim di
   luar fakta yang dikirim.
3. **Sambungkan satu konektor sungguhan** — RSS paling murah, tidak butuh
   kunci — dan lihat apakah pipeline bertahan pada data lapangan yang berantakan.
4. **Ukur ulang akurasi sentimen** terhadap sampel berlabel dari data nyata
   itu. Ini yang menentukan apakah seluruh lapisan sinyal layak dipakai untuk
   keputusan, atau baru layak untuk eksplorasi.
5. Baru setelah itu: gelombang survei kedua (membuka forecast), lalu Phase 4
   dengan keputusan-keputusan yang sudah diambil lebih dulu.
