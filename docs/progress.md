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
| Tes backend | **474 + 12 baru** (role `pop_app`, RLS aktif — bukan superuser; 473→474 dikonfirmasi via CI [PR #2](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/2). 12 tes baru 2026-09-11 — `test_reports.py` (4), `test_middleware.py` (7), `test_sentiment.py` (+1) — semuanya murni/tanpa DB, dijalankan lokal (43/43 hijau termasuk yang lama); **belum dikonfirmasi lewat CI penuh terhadap role `pop_app`**, Docker tidak tersedia di sandbox sesi ini, sama seperti sesi-sesi sebelumnya) |
| Endpoint API | 60 (+1 — `GET /projects/{id}/reports/summary`, 2026-09-11) |
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

## Phase 4 — enterprise · **DIMULAI SEBAGIAN (2026-09-11)**

Empat item pertama (SSO, MFA wajib, billing, API publik) tetap **belum
disentuh** — keputusan vendor/kebijakan yang bukan wewenang agen. Tiga item
lain yang TIDAK butuh vendor pihak ketiga **mulai dikerjakan** sesi
2026-09-11, atas instruksi eksplisit pengguna ("kerjakan no 1, 3, dan 4
secara maksimal").

| Item | Status |
|---|---|
| SSO / SAML / SCIM | Belum disentuh — penyedia identitas mana yang dipakai adalah keputusan organisasi |
| MFA wajib | Belum disentuh — kolom `users.mfa_secret` sudah ada di schema; alur enrolmen dan pemulihan butuh keputusan kebijakan |
| Billing + kredit survei/data/AI | Belum disentuh — penyedia pembayaran mana, dan model harga apa |
| API publik + webhook | Belum disentuh — kontrak API publik tidak bisa ditarik lagi setelah ada yang memakainya |
| ✅ Report generator PDF | **Selesai v1** — `GET /projects/{id}/reports/summary`, cakupan Segments + Polarization Index. Lihat `docs/deployment-status.md` bagian "Phase 4 — item tanpa vendor pihak ketiga (2026-09-11)". DOCX/PPTX/XLSX belum ada permintaan konkret soal formatnya, belum dikerjakan. |
| ✅ Rate limiting per tenant | **Versi minimal selesai** — in-memory per-proses, BUKAN Redis/terdistribusi (batasannya didokumentasikan di `app/middleware/ratelimit.py`, harus diganti sebelum API publik/skala horizontal beneran ada). |
| ✅ Observability dasar | **Selesai** — request ID + log JSON per request (`app/middleware/observability.py`). Ini BUKAN APM/tracing distribusi (Datadog/Sentry/dst) — itu tetap butuh keputusan vendor, belum dikerjakan. |
| Orkestrasi multi-agent penuh | **Sengaja tidak disentuh** — `ai/agents.py:Orchestrator` SUDAH mendukung banyak agen sekaligus (`run(agents: list[Agent], ctx)`), tapi kedua pemanggilnya (`brief.py`, `copilot.py`) selalu mengirim satu agen. Memperluas ini jadi "beneran multi-agent" butuh keputusan desain (agen apa, tugas apa, kenapa) yang bukan wewenang agen untuk diputuskan sendiri tanpa digunakan siapa pun dulu — beda kelas dengan tiga item di atas yang implementasinya mekanis begitu tahu tujuannya. |

Empat item pertama tetap butuh keputusan yang bukan wewenang agen. Sesuai
CLAUDE.md §8, lebih baik berhenti dan bertanya daripada memilih sendiri lalu
mengunci proyek ke pilihan itu.

---

## Yang BELUM diverifikasi — baca sebelum mengandalkan angka mana pun

Ini bagian terpenting dari dokumen ini.

1. ~~**Tidak ada satu pun fitur Phase 2/3 yang diuji terhadap Supabase
   produksi.**~~ — **ditutup 2026-09-11.** Ternyata verifikasi TIDAK butuh
   login `SITE_PASSWORD` seperti diasumsikan di bawah — gerbang itu cuma di
   middleware Next.js, API FastAPI publik (`pop-api-ptug.onrender.com`) bisa
   diverifikasi langsung lewat akun test yang didaftarkan sendiri lewat
   `/v1/auth/register`. Detail lengkap di `docs/deployment-status.md` bagian
   "Verifikasi production 2026-09-11". Ringkas: `GET /topics` dan
   `GET /network` (dulu 500) sekarang `200`; `PATCH /topics/{id}/review`
   (jalur TULIS ke kolom migrasi) juga `200`; 195 artikel media asli
   diinjeksi lewat `POST /signals/ingest` sungguhan lalu `topics/discover`,
   `risk/score`, `forecast/baseline`, `copilot/ask`, `brief/latest`,
   `impact/analyze` semua diverifikasi berperilaku benar (bukan cuma "tidak
   500" — gating `insufficient_data`/`coverage` juga bekerja seperti
   didesain). Project test dihapus lagi setelahnya, production bersih.

   Isi asli catatan ini (sebelum ditutup), untuk konteks sejarah:

   **Migrasi skema belum diterapkan ke Supabase** untuk dua perubahan Phase 3
   terakhir — kolom `topics.reviewed_label`/`review_status`/`reviewed_by`/
   `reviewed_at`, dan `mentions.reply_to_hash`/`quote_of_hash`/
   `conversation_id`. `db/schema.sql` sudah memuatnya di definisi
   `CREATE TABLE`, tapi itu cuma berlaku untuk instalasi baru — tabel yang
   sudah ada di Supabase butuh `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...`
   manual per kolom (persis seperti yang dijalankan ke Postgres lokal sesi
   ini) sebelum fitur review label atau `/jaringan` bisa dipakai di
   production.

   **Update 2026-09-02, sesi ketiga hari yang sama — ini bukan lagi risiko
   teoretis, sudah jadi insiden production nyata.** Absennya migrasi ini
   TIDAK cuma membuat fitur review-label/network tidak berfungsi — ia
   menjatuhkan SELURUH halaman `/command`, `/tema`, dan `/jaringan` dengan
   "Application error: a server-side exception has occurred", karena
   `GET /topics`/`GET /network` gagal 500 (kolom tidak ada), dan
   `apiOrNull()` di frontend cuma menangkap 404. Mitigasi frontend
   (`apiOrNullLenient()`, PR #4) **sudah di-merge ke `main`** (sesi keempat,
   2026-09-02) — begitu Render+Vercel selesai redeploy dari `main`, ketiga
   halaman akan menampilkan "data tidak cukup" alih-alih crash, TAPI itu
   tetap bukan pengganti migrasi ini, yang masih perlu dijalankan manual.
   SQL lengkapnya ada di deskripsi PR #4 dan di `docs/deployment-status.md`
   bagian "Fix crash Command Center/Tema/Jaringan". **Migrasi kolom
   Supabase sudah dijalankan pengguna** (2026-09-02, sesi keempat) —
   `Success. No rows returned` di SQL Editor.

2. **Konektor YouTube dan X belum pernah menarik data sungguhan** — butuh
   kunci API yang tidak tersedia di sandbox mana pun sejauh ini. **RSS
   sekarang sudah, sebagian** (2026-09-02): `RSSConnector().fetch()` — kode
   produksi apa adanya, tidak ditulis ulang — dipakai lewat skrip mandiri di
   venv terisolasi untuk menarik 5 feed media Indonesia sungguhan (Antara,
   CNN Indonesia, Tempo, Republika, CNBC Indonesia), menghasilkan 215 item
   nyata. Dua URL feed yang dicoba pertama kali (Kompas, Detik) ternyata
   404/mati — bukti kecil bahwa URL RSS memang rapuh dan berubah, persis
   seperti disinggung di `connectors/rss.py`. **Update 2026-09-11**: jalur
   lewat endpoint sungguhan dan database production **sekarang teruji** —
   195 item nyata (4 feed, ditarik ulang hari ini) dikirim lewat
   `POST /v1/signals/ingest` ke `pop-api-ptug.onrender.com` sungguhan
   (bukan panggilan fungsi lokal), tersimpan di Supabase, dan berhasil
   diagregasi lewat `signals/summary`, `signals/trend`, `topics/discover`.
   Jadi jaringan keluar dari Render ke Postgres/Supabase **teruji**; yang
   **masih belum teruji** cuma jalur `POST .../signals/sources/{id}/collect`
   (konektor RSS terdaftar sebagai `DataSource` + jaringan Render → penerbit
   RSS langsung) — sesi ini masih menarik feed dari mesin lokal lalu
   mengirim hasilnya lewat `ingest`, bukan memicu `collect` dari Render
   sendiri. Detail lengkap di `docs/deployment-status.md` bagian
   "Verifikasi production 2026-09-11". Pipeline
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

   **Ronde kedua diambil 2026-09-02 (sesi keempat) — sampel dua kali lebih
   besar, KESIMPULAN SAMA, tidak dipaksakan jadi "progres" palsu.** 385
   item mentah (naik dari 215) dari 7 feed hidup (naik dari 5 — Sindonews
   dan Media Indonesia terbukti hidup, 4 kandidat lain terbukti mati/rusak),
   84 judul ternilai dibaca manual + token `matched` diperiksa untuk item
   ekstrem. **Tidak ada bug leksikon baru yang aman diperbaiki** seperti
   "asal" — tiga temuan baru, semuanya batas struktural yang sudah
   diketahui, bukan bug baru: (1) "meningkat" salah pada konteks bencana
   (Gunung Sinabung, +0.40 padahal berita evakuasi) — versi baru dari
   temuan Ebola sesi lalu, kelas masalah sama; (2) "korupsi" mendominasi
   berita ANTI-korupsi jadi salah arah (RUU Perampasan Aset, -0.90 padahal
   berita positif upaya pemberantasan); (3) "sulit" salah pada satu idiom
   entertainment ("sulit tahan tawa" = lucu, bukan sulit) — sengaja TIDAK
   dihapus dari leksikon karena juga benar dipakai di sampel yang sama
   (jasad "sulit dikenali"), beda dengan "asal" yang nyaris tidak punya
   kegunaan sah sebagai kata negatif. Detail lengkap + token yang cocok
   untuk tiap temuan ada di `docs/deployment-status.md` bagian "Verifikasi
   RSS ronde kedua". Kesimpulannya: leksikon kata-tunggal sudah dekat
   batas perbaikan amannya — perbaikan lanjutan yang berarti butuh model,
   bukan kamus kata, persis seperti diakui docstring modul sejak awal.

   **Ronde ketiga diambil 2026-09-11 (sesi verifikasi production) — sampel
   naik ke 445 item (7 feed, nambah CNN Indonesia/Tempo/Media Indonesia),
   KALI INI ADA satu bug baru yang aman diperbaiki.** `hebat` (leksikon
   positif, 0.9) — 3/3 kemunculan adalah penguat keparahan di depan kata
   negatif ("Kebakaran Hebat Lahap Sekolah, 17 Orang Tewas", "Kebakaran
   hebat melanda kantor PUPR", "Gadis AS Muntah Hebat"), 0/3 makna pujian —
   pola identik "asal", **dihapus dari leksikon** (bukan cuma dicatat).
   `manfaat` juga diperiksa (7 kemunculan) tapi SENGAJA tidak diperbaiki:
   6/7 benar (genre artikel "manfaat kesehatan X"), cuma 1/7 salah karena
   negasi/pencabutan ("dikeluarkan dari daftar penerima manfaat") — beda
   kelas dengan `hebat`/`asal` yang salah di hampir semua kemunculan.
   Detail lengkap di `docs/deployment-status.md` bagian "Verifikasi
   production 2026-09-11". Abstain rate 78.0%, konsisten dengan ronde 1-2.

6. **15 dari 17 halaman dashboard rentan crash "Application error" pada
   error backend APA PUN — ditemukan+diperbaiki 2026-09-02 (sesi
   keempat), atas laporan pengguna "banyak yang belum bisa diklik".**
   Insiden PR #4 (500 dari kolom belum bermigrasi menjatuhkan
   `/command`/`/tema`/`/jaringan`) ternyata cuma tiga contoh dari kelas
   bug yang jauh lebih luas — 6 halaman lain pakai `api()` polos tanpa
   penanganan error sama sekali, dan 9 halaman lagi yang sudah pakai
   `apiOrNull()` ternyata SAMA rentannya (`apiOrNull` cuma menangkap
   404, bukan 500 — persis kesalahan yang sempat dibuat ulang di
   perbaikan PERTAMA sesi ini, ketahuan lewat verifikasi lokal
   sungguhan dengan backend tiruan, bukan asumsi). Diperbaiki dengan
   `apiOrNullLenient()` (menangkap SEMUA `ApiError`) di seluruh 15
   halaman, diverifikasi dua kali (backend tiruan 500-untuk-semua DAN
   404-untuk-semua) — ke-17 halaman sekarang konsisten HTTP 200 dengan
   degradasi "data tidak cukup". **Yang belum diverifikasi**: apakah
   keluhan awal pengguna memang disebabkan ini (belum dikonfirmasi link
   spesifik mana yang gagal, dan tes ini pakai backend tiruan, bukan
   Supabase/Render sungguhan) — lihat `docs/deployment-status.md`
   bagian "Audit crash seluruh sidebar" untuk detail lengkap.

---

## Langkah berikutnya yang paling masuk akal

Berurutan, dari yang paling murah dan paling menaikkan kepercayaan:

1. ~~**Verifikasi Phase 2/3 terhadap production.**~~ — **selesai
   2026-09-11**, lihat `docs/deployment-status.md` bagian "Verifikasi
   production 2026-09-11". Ternyata tidak perlu menunggu apa pun — bisa
   langsung lewat API publik dengan akun test sendiri.
2. **Aktifkan `ANTHROPIC_API_KEY` di Render**, lalu verifikasi Executive Brief
   dan Copilot menghasilkan jawaban yang masuk akal dan tidak memuat klaim di
   luar fakta yang dikirim. **Sengaja ditunda ke urutan TERAKHIR** atas
   instruksi eksplisit pengguna sesi 2026-09-11 (dikerjakan setelah poin 1/3/4
   di sini, bukan sebelumnya).
3. ~~**Sambungkan satu konektor sungguhan** — RSS paling murah, tidak butuh
   kunci — dan lihat apakah pipeline bertahan pada data lapangan yang
   berantakan.~~ — **selesai 2026-09-11**: 195 item nyata dikirim lewat
   `POST /signals/ingest` sungguhan ke production (bukan panggilan fungsi
   lokal), tersimpan, teragregasi, ter-cluster jadi topics. Sisa yang belum:
   memicu `collect` dari Render sendiri lewat `DataSource` konektor RSS
   terdaftar (bukan cuma `ingest` manual) — beda kelas, bukan penghalang
   berarti.
4. **Ukur ulang akurasi sentimen** terhadap sampel berlabel dari data nyata
   itu. Ini yang menentukan apakah seluruh lapisan sinyal layak dipakai untuk
   keputusan, atau baru layak untuk eksplorasi. **Tiga ronde langkah kecil
   diambil (2026-09-02 x2, 2026-09-11 x1), bukan pengganti langkah ini** —
   lihat poin 5 di bagian "Yang BELUM diverifikasi": ronde 1 (215 item)
   menemukan+memperbaiki "asal"; ronde 2 (385 item) tidak menemukan bug baru
   yang aman diperbaiki; **ronde 3 (445 item, 2026-09-11) menemukan+
   memperbaiki satu lagi ("hebat", pola sama seperti "asal")** — jadi titik
   jenuhnya belum semutlak yang disimpulkan ronde 2, tapi masih dalam
   kategori "perbaikan kecil dari perluasan sampel", bukan lompatan mutu.
   `manfaat` diperiksa di ronde 3 dan SENGAJA tidak diperbaiki (6/7 kasus
   benar). **Kesimpulan tetap sama seperti ronde 2**: perbaikan akurasi yang
   BERARTI (bukan cuma nambah satu-dua kata per ronde) tetap butuh (a)
   sampel berlabel sistematis dari penilai independen, atau (b) metode
   berbasis model — dua-duanya di luar yang bisa diselesaikan lewat ronde
   pull-RSS-dan-baca-manual lagi.
5. **Gelombang survei kedua (membuka forecast)** — **masih di luar wewenang
   agen**: butuh respons manusia sungguhan, tidak bisa difabrikasi tanpa
   melanggar R1 (data sintetis tidak boleh disajikan sebagai hasil survei
   nyata). Ini murni tugas pengumpulan data pengguna/institusi, bukan
   tugas rekayasa.
6. **Phase 4** — lihat tabel di bagian "Phase 4 — enterprise" di atas.
   Empat item pertama (SSO, MFA wajib, billing, API publik) tetap butuh
   keputusan vendor/kebijakan yang bukan wewenang agen, dan — di luar
   keputusan itu — melibatkan pembuatan akun pihak ketiga (identity
   provider, payment provider) yang juga di luar batas yang boleh
   dilakukan agen atas nama pengguna tanpa persetujuan eksplisit per
   platform. Tiga item sisanya (rate limiting, report generator,
   observability dasar, orkestrasi multi-agent) **tidak butuh keputusan
   vendor** — lihat `docs/deployment-status.md` bagian "Phase 4 — item yang
   tidak butuh vendor pihak ketiga (2026-09-11)" untuk apa yang mulai
   dikerjakan.
