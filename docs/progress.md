# Progres

Satu tempat untuk melihat **apa yang sudah jadi, apa yang belum, dan apa yang
menahannya.** Diperbarui 2026-09-02.

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
| Tes backend | **474 lulus** (role `pop_app`, RLS aktif — bukan superuser; 473→474 dikonfirmasi via CI [PR #2](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/2), bukan lokal — Docker tidak tersedia di sandbox sesi 2026-09-02) |
| Endpoint API | 59 |
| Halaman dashboard | 17 (9 Phase 1 + 8 Phase 2/3, termasuk `/jaringan` baru) |
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
| `services/sentiment.py` + set evaluasi | Teruji (31 tes) | macro-F1 0.902 di set evaluasi; lihat catatan leksikon "asal" di bawah |
| `services/topics.py` — TF-IDF + LSA + HDBSCAN | Teruji (28 tes) | **Bukan embedding** — lihat di bawah |
| `services/pipeline.py` — perekat ingestion+sentiment | Teruji | |
| `connectors/rss.py` — media monitoring | Teruji parsing + jaringan nyata (2026-09-02) | 215 artikel sungguhan dari 5 outlet, lihat poin 2 di bawah |
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
   **Migrasi skema belum diterapkan ke Supabase** untuk dua perubahan Phase 3
   terakhir — kolom `topics.reviewed_label`/`review_status`/`reviewed_by`/
   `reviewed_at`, dan `mentions.reply_to_hash`/`quote_of_hash`/
   `conversation_id`. `db/schema.sql` sudah memuatnya di definisi
   `CREATE TABLE`, tapi itu cuma berlaku untuk instalasi baru — tabel yang
   sudah ada di Supabase butuh `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...`
   manual per kolom (persis seperti yang dijalankan ke Postgres lokal sesi
   ini) sebelum fitur review label atau `/jaringan` bisa dipakai di
   production.

2. **Konektor YouTube dan X belum pernah menarik data sungguhan** — butuh
   kunci API yang tidak tersedia di sandbox mana pun sejauh ini. **RSS
   sekarang sudah, sebagian** (2026-09-02): `RSSConnector().fetch()` — kode
   produksi apa adanya, tidak ditulis ulang — dipakai lewat skrip mandiri di
   venv terisolasi untuk menarik 5 feed media Indonesia sungguhan (Antara,
   CNN Indonesia, Tempo, Republika, CNBC Indonesia), menghasilkan 215 item
   nyata. Dua URL feed yang dicoba pertama kali (Kompas, Detik) ternyata
   404/mati — bukti kecil bahwa URL RSS memang rapuh dan berubah, persis
   seperti disinggung di `connectors/rss.py`. **Yang BELUM ikut teruji di
   sini**: jalur lewat endpoint `POST .../signals/collect`, database (skrip
   ini murni memanggil fungsi, tanpa Postgres sama sekali — Docker tidak
   tersedia di sandbox sesi ini), dan jaringan keluar dari Render sendiri ke
   penerbit (kemungkinan besar sama, tapi belum dicoba dari Render). Pipeline
   ingestion (`normalize_text`, `detect_language`, `dedupe`) dan sentiment
   (`sentiment.score`) dijalankan di atas ke-215 item nyata itu tanpa satu
   pun exception — lihat poin 5 di bawah untuk apa yang ditemukan dari situ.

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

   **Langkah kecil ke arah itu diambil 2026-09-02 — BUKAN pengganti langkah di
   atas.** `sentiment.score()` dijalankan apa adanya atas 215 item nyata dari
   poin 2 di atas (judul+ringkasan media Indonesia sungguhan, bukan kalimat
   buatan tim). Temuannya:
   - **79.5% abstain** (171/215) — jauh lebih tinggi daripada kesan yang bisa
     didapat dari 52 kalimat set evaluasi, yang memang ditulis supaya
     mengandung kata leksikon. Ini angka baru yang sebelumnya tidak ada:
     leksikon ini tidak punya dasar untuk menilai SEBAGIAN BESAR judul berita
     nyata, dan itu ditampilkan sebagai abstain, bukan netral (sesuai desain
     modul) — tapi proporsinya sebesar ini baru terlihat sekarang.
   - Dari 44 yang ternilai, saya (satu penilai, membaca manual — **ini bukan
     evaluasi berlabel formal**, jangan disamakan mutunya dengan
     `sentiment_eval.py`) menemukan pola kesalahan konkret, bukan sekadar
     "kurang akurat":
     - **Kata "asal"** (arti "berasal dari") salah terbaca sebagai "ceroboh"
       dan memicu skor negatif pada 2 dari 2 kemunculannya di sampel ini
       (mis. "aktor **asal** Inggris Raya"). **Sudah diperbaiki** — dihapus
       dari `_NEGATIVE` di `app/services/sentiment.py` dengan komentar
       penjelas di kode, ditambah tes regresi
       `test_asal_negara_tidak_lagi_dianggap_negatif`. Diverifikasi tidak
       menurunkan mutu di set evaluasi 52 kalimat (macro-F1 & akurasi tetap
       di atas lantai 0.80 yang ditetapkan tes) — kata itu tidak muncul sama
       sekali di `sentiment_eval.py:LABELED`, jadi tidak ada trade-off yang
       terukur, hanya perbaikan bersih.
     - **Nama program berulang membanjiri skor positif tanpa sentimen baru**:
       6 dari 40 sampel yang dibaca adalah judul BERBEDA tentang program yang
       SAMA ("Apresiasi Pemerintah Daerah Berprestasi"), semua bernilai
       positif tinggi hanya karena kata "apresiasi" ada di NAMA programnya —
       bukan karena tiap artikel menyatakan sikap positif sendiri.
       `ingestion.dedupe` tidak menangkap ini (teks sekitarnya cukup berbeda
       untuk lolos ambang Jaccard 0.82). **Belum diperbaiki** — ini
       keterbatasan struktural leksikon kata-tunggal terhadap nama
       proper/judul program berulang, bukan bug satu kata seperti "asal", di
       luar cakupan perbaikan cepat yang bisa diverifikasi aman di sesi ini.
     - **Sarkasme dan eskalasi krisis tetap tidak terbaca** — persis batas
       yang sudah diakui docstring modul sejak awal, sekarang ada contoh
       nyatanya: judul bernada skeptis "Jujur Janggal! Trump Yakin Ekonomi AS
       Tembus 20%" bernilai +0.75 (matched "jujur", "optimis" secara
       harfiah), dan berita jumlah korban meninggal Ebola yang bertambah
       bernilai +0.4 (matched "meningkat"). Tidak diperbaiki — ini bukan bug,
       ini batas metode leksikon yang sudah didokumentasikan sejak awal;
       memperbaikinya butuh model, bukan kamus kata.
   - **Ini tetap bukan pengganti "ukur ulang terhadap sampel berlabel"** yang
     diminta di atas paragraf ini — itu butuh label dari penilai yang
     independen dari yang membangun sistemnya, idealnya lebih dari satu
     penilai dan mengerti domain proyek sungguhan, atas sampel yang diambil
     secara sistematis. Yang dilakukan di sini satu penilai, tidak
     sistematis, sekali baca — nilainya untuk menunjukkan JENIS kesalahan
     yang ada di data lapangan, bukan mengukur SEBERAPA SERING itu terjadi.

---

## Langkah berikutnya yang paling masuk akal

Berurutan, dari yang paling murah dan paling menaikkan kepercayaan:

1. **Verifikasi Phase 2/3 terhadap production.** Semua kodenya sudah di
   `main`; yang kurang cuma menjalankannya di sana.
2. **Aktifkan `ANTHROPIC_API_KEY` di Render**, lalu verifikasi Executive Brief
   dan Copilot menghasilkan jawaban yang masuk akal dan tidak memuat klaim di
   luar fakta yang dikirim.
3. ~~**Sambungkan satu konektor sungguhan** — RSS paling murah, tidak butuh
   kunci — dan lihat apakah pipeline bertahan pada data lapangan yang
   berantakan.~~ — **dikerjakan sebagian 2026-09-02**, lihat poin 2 di bagian
   "Yang BELUM diverifikasi" di atas. Bertahan (tidak ada exception atas 215
   item nyata); yang belum: lewat endpoint asli + Postgres + dari Render
   sendiri.
4. **Ukur ulang akurasi sentimen** terhadap sampel berlabel dari data nyata
   itu. Ini yang menentukan apakah seluruh lapisan sinyal layak dipakai untuk
   keputusan, atau baru layak untuk eksplorasi. **Langkah kecil, bukan
   pengganti, diambil 2026-09-02** — lihat poin 5 di bagian "Yang BELUM
   diverifikasi": 1 bug leksikon nyata ditemukan+diperbaiki ("asal"), 1
   keterbatasan struktural dicatat (nama program berulang), abstain rate
   79.5% terukur untuk pertama kalinya di data nyata. Yang sebenarnya
   diminta poin ini — sampel berlabel sistematis dari penilai independen —
   masih belum ada.
5. Baru setelah itu: gelombang survei kedua (membuka forecast), lalu Phase 4
   dengan keputusan-keputusan yang sudah diambil lebih dulu.
