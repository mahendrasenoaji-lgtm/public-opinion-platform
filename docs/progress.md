# Progres

Satu tempat untuk melihat **apa yang sudah jadi, apa yang belum, dan apa yang
menahannya.** Diperbarui 2026-09-16 (sesi ketujuh — K1/K3/K5/K6 dari tabel
"Pengumpulan sinyal terjadwal" dikerjakan; lihat blok "MULAI DARI SINI" di
kepala `docs/deployment-status.md` untuk detail dan bukti).

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
| Tes backend | **548** = 499 dikonfirmasi CI + **49 baru** (konektor deret: Wikipedia 25, Open-Meteo 24). Yang 499 via CI (role `pop_app`, RLS aktif): 486 [PR #5](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/5), 492 [PR #6](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/6), 499 [PR #7](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/7). Yang 49 (konektor deret) **dikonfirmasi CI lewat [PR #9](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/9)** |
| Tes backend (2026-09-15) | **593 lulus lokal** (Postgres 16, role `pop_app`, RLS aktif, schema dengan kolom vector di-shim) setelah PR #15: +21 tes `test_collect_all_router.py`, +~20 tes konektor RSS/kata kunci. **CI PR #15 dan #16 hijau** (pgvector sungguhan) |
| Endpoint API | **68** (+4 pada 2026-09-15: `POST /projects/{id}/signals/collect-all`, `POST`/`GET`/`DELETE /projects/{id}/signals/collector-token`). Sebelumnya 64 (+3 metrics, 2026-09-11) |
| Otomasi terjadwal | **1** — `.github/workflows/collect-signals.yml`, tiap 30 menit (2026-09-15) |
| Halaman dashboard | 18 (9 Phase 1 + 9 Phase 2/3, termasuk `/deret` baru) |
| Konektor | 6 konten (rss, youtube, x, manual) + **2 deret waktu** (wikipedia_pageviews, openmeteo_air_quality), keduanya tanpa kunci API |
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
| `connectors/rss.py` — media monitoring | Teruji parsing + **Live production dari Render (2026-09-15)** | 14/14 feed ditarik dari dalam Render tanpa 403. Sejak PR #15: `keywords` opsional (kata utuh, di-escape), `external_id` = permalink, halaman HTML dilaporkan "bukan feed" |
| `POST .../signals/collect-all` — tarik semua sumber aktif | Teruji (21 tes) + **Live production** | Laporan per sumber: `offered`/`matched`/`coverage_gap`; gagal/crash diisolasi per sumber |
| Token pengumpul `.../signals/collector-token` | Teruji + **Live production** | `type=collector`, satu proyek, dicabut lewat `audit_logs` (tanpa migrasi). Token ini ditolak di `/projects` (401, dicek di production) |
| `.github/workflows/collect-signals.yml` + `.github/scripts/collect_signals.py` | **Live production** (run manual `workflow_dispatch` sukses 2026-09-15 14:43 UTC) | Skripnya sendiri tidak punya tes otomatis — lihat "yang kurang" |
| `connectors/youtube.py` — YouTube Data API v3 | Teruji parsing | Butuh `YOUTUBE_API_KEY` |
| `connectors/x.py` — X API v2 recent search | Teruji parsing | Butuh `X_BEARER_TOKEN` |
| `connectors/manual.py` — unggahan/ekspor vendor | Teruji | Jalur yang benar-benar dipakai sekarang |
| `connectors/metrics.py` — kontrak konektor DERET | Teruji (2026-09-11) | Sejajar dengan `base.py`, bukan turunannya — lihat di bawah |
| `connectors/wikipedia.py` — Wikimedia Pageviews | Teruji (25 tes) + payload produksi asli | Tanpa kunci API. 41 pengamatan harian nyata ditarik & diparse |
| `connectors/openmeteo.py` — PM2.5 per provinsi | Teruji (24 tes) + payload produksi asli | Tanpa kunci API. Kovariat eksogen, BUKAN sinyal opini |
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
asli untuk OPINI. Grid provinsi berperingkat tetap dipakai. Provinsi **tidak**
diinferensi dari isi teks — hasilnya akan dipakai sebagai georeferensi padahal
bukan.

**Berubah sebagian 2026-09-11 (sesi keempat), dan batasnya penting.**
`connectors/openmeteo.py` memberi data yang georeferensinya memang ASLI —
koordinat ibu kota provinsi yang diukur instrumen, bukan ditebak dari teks —
untuk 20 provinsi. Syarat CLAUDE.md §6 terpenuhi **untuk lapisan kualitas
udaranya sendiri**. Itu TIDAK berarti peta skor opini per provinsi boleh
dibangun: opini per provinsi masih datang dari survei yang `achieved_n`-nya
di bawah ambang di separuh provinsi (gating §3 tetap berlaku), dan sebaran
percakapan masih tanpa geotag.

Konsekuensi yang paling gampang salah: **komponen risiko `geographic_spread`
TETAP KOSONG.** Ia menghitung sebaran PERCAKAPAN, bukan sebaran udara buruk.
Mengisinya dari Open-Meteo akan mengubah arti skor risiko diam-diam — dan itu
persis pelanggaran R1 yang paling mahal, karena angkanya akan tampak lengkap.

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
| ✅ Report generator PDF | **Live production** — `GET /projects/{id}/reports/summary`, cakupan Segments + Polarization Index. Diverifikasi setelah deploy: 200, `application/pdf`, word-wrap benar, "data tidak cukup" tidak dipalsukan jadi angka. Bug 500-bukan-404 untuk proyek tidak ada ditemukan pasca-deploy dan diperbaiki ([PR #6](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/6)). DOCX/PPTX/XLSX belum ada permintaan konkret soal formatnya, belum dikerjakan. |
| ✅ Rate limiting per tenant | **Live production** — diverifikasi: 10 login lolos, ke-11 → 429 + `Retry-After`, `/health` tetap lolos, header CORS terbawa di 429. In-memory per-proses, BUKAN Redis/terdistribusi (batasannya didokumentasikan di `app/middleware/ratelimit.py`, harus diganti sebelum API publik/skala horizontal beneran ada). |
| ✅ Observability dasar | **Live production** — `X-Request-ID` diverifikasi ada dan unik per request. Bug "429 tidak ikut tercatat" ditemukan pasca-deploy dan diperbaiki ([PR #6](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/6)). Ini BUKAN APM/tracing distribusi (Datadog/Sentry/dst) — itu tetap butuh keputusan vendor, belum dikerjakan. |
| Orkestrasi multi-agent penuh | **Sengaja tidak disentuh** — `ai/agents.py:Orchestrator` SUDAH mendukung banyak agen sekaligus (`run(agents: list[Agent], ctx)`), tapi kedua pemanggilnya (`brief.py`, `copilot.py`) selalu mengirim satu agen. Memperluas ini jadi "beneran multi-agent" butuh keputusan desain (agen apa, tugas apa, kenapa) yang bukan wewenang agen untuk diputuskan sendiri tanpa digunakan siapa pun dulu — beda kelas dengan tiga item di atas yang implementasinya mekanis begitu tahu tujuannya. |

Empat item pertama tetap butuh keputusan yang bukan wewenang agen. Sesuai
CLAUDE.md §8, lebih baik berhenti dan bertanya daripada memilih sendiri lalu
mengunci proyek ke pilihan itu.

---

## Pengumpulan sinyal terjadwal (2026-09-15, sesi keenam)

Bagian ini ringkasan untuk melanjutkan kerja di komputer lain. Bukti rinci
(log run, angka, tabel feed) ada di blok "🟢 MULAI DARI SINI" di kepala
`docs/deployment-status.md`.

### Apa yang dikerjakan, berurutan

1. **Diagnosis.** Laporan pengguna: "scheduled task pengambilan data jam 8
   gagal 3 hari". Itu routine cloud Claude Code `MBG - Ingest RSS harian`
   (bukan scheduled task Claude Desktop — file lokalnya kosong). Log keempat
   run (12–15 Sep) sama: **ke-15 feed 403 dari jaringan sandbox routine**,
   0 artikel, status routine tetap "SUCCEEDED". Dari Mac pengguna: 200.
2. **Temuan metodologis.** Feed hanya memuat item terbaru: Antara nasional
   ≈1,2 jam, Republika ≈1,3 jam. Run sekali sehari melewatkan sebagian besar
   berita meski tidak diblokir. Feed Kontan ternyata membalas halaman HTML.
3. **PR #15 (API)** — `collect-all`, token pengumpul, pengerasan
   `decode_token` (hanya `type=access`), penyaring `keywords` RSS, identitas
   item = permalink (guid Liputan6 berupa angka), deteksi `coverage_gap`,
   isolasi kegagalan per sumber, skrip pemicu `collect_signals.py`.
4. **Konfigurasi production** — 14 sumber RSS didaftarkan di proyek
   `MBG AGUSTUS 2026` (`c6241a06-2a63-4b61-84d2-f7eb9c558710`) dengan
   `keywords` = `makan bergizi gratis, mbg, badan gizi nasional, bgn`; token
   pengumpul diterbitkan (berlaku s.d. **2027-03-14**); secret
   `POP_COLLECTOR_TOKENS` dan variable `POP_API_BASE` dipasang di repo.
5. **Verifikasi production** — tarik pertama: 14/14 feed OK dari Render,
   6 artikel MBG baru; tarik ulang: `stored_total: 0`; proyek 16 item,
   0 `external_id` ganda.
6. **PR #16** — workflow `collect-signals.yml` (cron `7,37 * * * *`) +
   dokumentasi. File workflow dibuat lewat **editor web GitHub** (token `gh`
   di Mac pengguna tidak punya scope `workflow`). Run manual dari GitHub
   Actions sukses: Render bangun 72 dtk, 14/14 feed OK.
7. **Routine cloud lama 5/7–8/8 dinonaktifkan** (`enabled: false`); 1–4 sudah
   habis sendiri. Database uji lokal (`pop_test`, role `pop`/`pop_app`)
   dihapus lagi dari Postgres Homebrew.

### Yang KURANG / belum dikerjakan — urut dari yang paling berisiko

| # | Hal | Kenapa penting | Cara menyelesaikan |
|---|---|---|---|
| K1 | ~~Jadwal otomatis belum dibuktikan berulang.~~ **Terbukti 2026-09-16, dan hasilnya bermasalah**: 5 run `schedule` dalam ~20,7 jam (harusnya ~41 pada cron 30 menit) — jarak aktual 2,5–5,5 jam. GitHub Actions men-throttle jadwal berfrekuensi tinggi di repo ini. | Antara & Republika (feed ~1 jam) hampir selalu `coverage_gap` karena jaraknya jauh melebihi rentang feed. | **Masih terbuka** — perbaikan butuh pemicu di luar GitHub Actions (cron eksternal memanggil `workflow_dispatch`), yang berarti menyimpan PAT di layanan pihak ketiga: keputusan vendor baru, bukan wewenang agen sendiri. Lihat blok "MULAI DARI SINI" 16 Sep di `deployment-status.md`. |
| K2 | **Data MBG 12–15 Sep hilang permanen.** | Deret harian proyek MBG bolong 4 hari; analisis tren harus menyebutnya. | Tidak bisa dipulihkan dari RSS. Kalau perlu, cari arsip di situs penerbit secara manual dan masukkan lewat `POST /signals/ingest` dengan catatan provenance — jangan diam-diam. |
| K3 | ✅ **Selesai 2026-09-16.** Kedelapan routine cloud MBG dihapus lewat claude.ai/code/routines, diverifikasi lewat `RemoteTrigger list` (tidak ada sisa). | JWT stateless tidak bisa dicabut satu per satu. | **Token akses pengguna lama TETAP sah** (s.d. ~11 Okt 2026) — menghapus routine cuma menghapus jejak plaintext-nya, bukan mencabut tokennya. Rotasi `JWT_SECRET` sengaja belum dilakukan (mematikan semua sesi + token pengumpul aktif) — butuh persetujuan eksplisit pengguna. |
| K4 | **GitHub menonaktifkan jadwal di repo publik setelah 60 hari tanpa aktivitas repo.** | Pengumpulan bisa berhenti diam-diam sekitar pertengahan November bila repo tidak di-commit. | Commit apa pun ke repo sebelum 60 hari, atau aktifkan ulang workflow di tab Actions saat GitHub mengirim email peringatan. |
| K5 | ✅ **Selesai 2026-09-16.** `collect_all` sekarang menulis SATU baris audit per run (ringkasan per sumber di `metadata_`), bukan satu per sumber. Dari ~670 baris/hari menjadi ~48 baris/hari. 593/593 tes lokal lulus, ruff+mypy tanpa regresi. | Supabase free tier terbatas 500 MB; tabel ini tidak pernah dipangkas. | Selesai — `app/routers/signals.py`, param `write_audit` di `_store_fetched`. |
| K6 | ✅ **Selesai 2026-09-16.** UI di `/sinyal`: form tambah sumber (field dinamis per konektor), tombol hapus sumber, "Tarik semua sekarang" dengan hasil per sumber, panel terbitkan/cabut token. Diverifikasi hidup di browser: 50 artikel nyata ditarik dari feed Antara sungguhan lewat tombol baru. | Semua konfigurasi sekarang lewat API (curl). Peneliti non-teknis tidak bisa mengelolanya. | Selesai — `sinyal/actions.ts` + `components/SourceManager.tsx`. Bug nyata ketemu+diperbaiki dalam prosesnya: `lib/api.ts` crash pada respons 204 (DELETE), mematahkan hapus-sumber & cabut-token secara senyap; juga memperbaiki bug identik pra-ada di hapus-proyek. |
| K7 | 🔶 **Diriset 2026-09-17, siap dieksekusi -- butuh token admin produksi yang agen tidak punya.** Domain RSS baru Kontan (`rss.kontan.co.id/...`) dicek langsung: **403 dari CloudFront di semua path & User-Agent** -- bukan cuma butuh URL baru, infrastrukturnya diblokir. `www.kontan.co.id/rss`\|`/feed` cuma halaman HTML navigasi, bukan feed. Diuji 9 kandidat pengganti: **Katadata** (`https://katadata.co.id/rss`, 200, 25 item/~13 jam -- outlet data-bisnis paling sepadan dengan Kontan, publisher baru) direkomendasikan; `finance.detik.com/rss` dan `cnnindonesia.com/ekonomi/rss` juga hidup (200, item lebih banyak) sebagai cadangan. Bisnis.com diblokir Cloudflare ("Just a moment...") di kedua endpoint yang dicoba. | Satu outlet ekonomi hilang dari cakupan MBG. | **Tinggal eksekusi satu request** (RESEARCH_DIRECTOR+ di proyek `MBG AGUSTUS 2026`, `c6241a06-2a63-4b61-84d2-f7eb9c558710`): `POST /projects/c6241a06-2a63-4b61-84d2-f7eb9c558710/signals/sources` body `{"connector": "rss", "config": {"feed_url": "https://katadata.co.id/rss", "keywords": "makan bergizi gratis, mbg, badan gizi nasional, bgn", "label": "Katadata"}}` -- lewat UI `/sinyal` (form K6) atau curl dengan token pengguna. Agen tidak menyimpan kredensial produksi apa pun; percobaan browser automation di sesi ini gagal konek ke Chrome aktif (bukan soal izin, sesi browser tidak tersambung). |
| K8 | **Proyek `KEBAKARAN HUTAN` masih memakai skrip manual** (`ingest_karhutla.py`, di luar repo). | Tidak terkumpul otomatis sama sekali. | Daftarkan sumbernya + `keywords` karhutla, terbitkan token untuk proyek itu, tambahkan token sebagai **baris baru** di secret `POP_COLLECTOR_TOKENS`. |
| K9 | **Skrip `collect_signals.py` tidak punya tes otomatis.** | Salah parsing respons baru ketahuan saat run merah. | Tambah tes kecil dengan server HTTP palsu (stdlib) di CI. |
| K10 | **Jam gratis Render.** Ping tiap 30 menit membuat instance sering bangun (cold start ~72–93 dtk). | 750 jam gratis/bulan dibagi semua layanan free di workspace Render yang sama. | Cek pemakaian di dashboard Render akhir bulan; kalau mepet, kurangi frekuensi untuk feed yang rentangnya panjang, atau pindah plan. |
| K11 | **Mesin pengguna:** pgvector tidak terpasang di Postgres Homebrew; `gh` tanpa scope `workflow`. | Tes lokal butuh schema yang di-shim; mengubah file workflow butuh editor web. | `brew install pgvector` (pastikan untuk postgresql@16) dan `gh auth refresh -h github.com -s workflow`. |

### Cara melanjutkan di komputer lain

1. `git clone https://github.com/mahendrasenoaji-lgtm/public-opinion-platform`
   → baca blok "🟢 MULAI DARI SINI" di `docs/deployment-status.md`, lalu tabel
   K1–K11 di atas.
2. Status jadwal: tab **Actions** di GitHub → "Pengumpulan sinyal terjadwal"
   → buka run terbaru → **Summary** (tabel per sumber).
3. Memicu manual: Actions → workflow itu → **Run workflow**
   (`since_days` bisa diubah, maks 90).
4. Token pengumpul **tidak disimpan di mana pun selain secret GitHub** — tidak
   bisa dibaca ulang. Kalau hilang/perlu diganti: login ke API, `POST
   /v1/projects/{id}/signals/collector-token` (RESEARCH_DIRECTOR), lalu
   perbarui secret `POP_COLLECTOR_TOKENS` (Settings → Secrets and variables
   → Actions). Token lama otomatis mati.
5. Mematikan pengumpulan: Actions → workflow → **Disable workflow**, atau
   `DELETE /v1/projects/{id}/signals/collector-token`.

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
   "Verifikasi production 2026-09-11".
   **Update 2026-09-12**: jaringan keluar dari **Render ke penerbit pihak
   ketiga** sekarang teruji lewat jalur lain — `POST .../metrics/collect`
   berhasil menarik data langsung dari Wikimedia dan Open-Meteo dari dalam
   Render (lihat blok "MULAI DARI SINI"). Jadi yang tersisa untuk RSS bukan
   lagi pertanyaan "apakah Render bisa menjangkau internet luar", melainkan
   khusus jalur `DataSource`-nya. Satu pelajaran dari situ yang **berlaku
   untuk konektor RSS juga**: UA yang diterima dari IP rumahan bisa ditolak
   dari IP datacenter Render. Kalau `sources/{id}/collect` nanti gagal dengan
   403, curigai User-Agent lebih dulu, bukan langsung menyimpulkan IP-nya
   diblokir.
   **Update 2026-09-15 — jalur `DataSource` RSS dari Render TERUJI.** Lewat
   endpoint baru `POST .../signals/collect-all` (PR #15, memakai
   `_fetch_source` yang sama dengan `sources/{id}/collect`): 14 feed
   terdaftar di proyek MBG ditarik **dari dalam Render**, 14/14 berhasil,
   tanpa 403, dengan UA yang sama. 6 artikel MBG tersimpan, tarik ulang
   `stored: 0`. Yang 403 justru sandbox routine cloud Claude, bukan Render —
   lihat blok "MULAI DARI SINI". Pipeline
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

   **Jalan memutar dibangun 2026-09-11 (sesi keempat) — BUKAN pengganti
   gelombang survei kedua.** `timeseries.fit()` menuntut DERET
   (`MIN_OBSERVATIONS = 8`, `MIN_OBSERVATIONS_FOR_TREND = 12`), bukan
   menuntut data survei. Konektor `wikipedia_pageviews` yang baru memberi
   deret harian nyata: tarikan sungguhan untuk artikel "Badan Gizi Nasional"
   di id.wikipedia menghasilkan **41 pengamatan** (1 Agu – 10 Sep 2026), di
   atas kedua ambang itu.

   Yang ini betul-betul menjawab: "apakah modelnya bekerja pada deret nyata,
   bukan hanya pada fixture tes". Yang ini TIDAK menjawab: "ke mana opini
   publik bergerak" — tampilan halaman mengukur PERHATIAN, bukan sikap, dan
   `source`-nya `DIGITAL` justru supaya tidak pernah tertukar dengan survei.
   Gelombang survei kedua tetap satu-satunya jalan untuk mem-forecast POI,
   dan itu tetap tugas pengumpulan data pengguna (lihat poin 5 di "Langkah
   berikutnya").

   **`timeseries.fit()` SUDAH dijalankan atas deret 41-titik itu** (sesi
   keempat, setelah statsmodels terpasang di sandbox) — bukan disimpulkan
   dari ambangnya:

   ```
   1 pengamatan  → insufficient_data=True
                   "Perlu minimal 8 pengamatan historis; tersedia 1."
   41 pengamatan → insufficient_data=False
                   model    = state-space (level lokal + tren), di-fit pada riwayat proyek
                   baseline = 84.0   span = 40 hari   median_step = 1.0 hari
                   expected = {1: 90.82, 7: 89.30, 30: 83.45, 90: 68.19}
                   spread ± = {1: 32.53, 7: 82.03, 30: 203.96, 90: 480.23}
   ```

   Perhatikan `spread` di horizon 90: **±480 di atas baseline 84**. Itu bukan
   kegagalan, itu model yang mengatakan ia tidak tahu — dan `limitations`
   menyebutnya sendiri ("Horizon terjauh (90 hari) melampaui panjang riwayat
   yang tersedia (40 hari). Bagian itu ekstrapolasi, bukan estimasi.").
   Modul ini berperilaku benar pada data lapangan, bukan cuma pada fixture.

   **Jahitan lengkapnya JUGA sudah diverifikasi** — `POST /metrics/collect`
   → `metric_snapshots` → `GET /forecast/baseline`, lewat HTTP asli
   (httpx + ASGITransport) terhadap Postgres 16 lokal dengan role `pop_app`
   dan `FORCE ROW LEVEL SECURITY` aktif, bukan superuser:

   ```
   4. forecast SEBELUM  → insufficient=True,  n=0
                          "Perlu minimal 8 pengamatan historis; tersedia 0."
   5. collect           → 200, fetched=60 stored=60, 2026-07-13..2026-09-10
   6. collect ULANG     → stored=0 replaced=60        ← idempoten
   8. forecast SESUDAH  → insufficient=False, n=60, span=59 hari
                          model = state-space (level lokal + tren)
   9. isolasi tenant    → org lain baca deret ini: 200 []
   10. DELETE proyek    → 204, metric_snapshots ikut terhapus (cascade)
   ```

   Dua hal yang baru terbukti di sini, di luar yang direncanakan:
   **idempotensi** (tarik ulang rentang sama tidak menggandakan baris — kalau
   menggandakan, `timeseries.fit()` akan melihat dua pengamatan di tanggal
   yang sama dan estimasi lebar intervalnya mengecil palsu), dan **isolasi
   tenant** untuk endpoint baru ini.

   **Catatan tentang lingkungan verifikasi**: Postgres lokal tidak punya
   extension `vector`, jadi `mentions` dan `topics` tidak ikut terbuat dan
   RLS untuk keduanya tidak diuji di sini. Fitur ini tidak menyentuh kedua
   tabel itu, dan CI (`pgvector/pgvector:pg16`) menjalankan suite penuh
   dengan keduanya ada — PR #9 hijau.

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

> **Mulai dari sini kalau ini sesi baru.** Yang paling atas dan paling
> konkret per 2026-09-15 ada di blok "🟢 MULAI DARI SINI" di kepala
> `docs/deployment-status.md` — ringkasnya: **pengumpulan RSS proyek MBG kini
> berjalan dari API sendiri** (PR #15, `collect-all` + token pengumpul),
> dipicu GitHub Actions tiap 30 menit, menggantikan routine cloud yang gagal
> 403 empat hari. PR #9 sampai #16 hidup di production. **Yang kurang dari
> pekerjaan itu ada di tabel K1–K11** (bagian "Pengumpulan sinyal
> terjadwal"); daftar di bawah ini untuk platform secara umum.

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
   lokal), tersimpan, teragregasi, ter-cluster jadi topics. Sisa yang dulu
   belum — memicu `collect` dari Render sendiri lewat `DataSource` RSS —
   **selesai 2026-09-15** (PR #15, `collect-all`, terjadwal).
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
   tugas rekayasa. **Konektor `wikipedia_pageviews` (2026-09-11) TIDAK
   menggantikan ini** — lihat poin 4 di bagian "Yang BELUM diverifikasi":
   ia membuka deret untuk menguji modelnya, bukan deret opini.

7. ~~**Jalankan `POST /projects/{id}/metrics/collect` terhadap Postgres
   sungguhan.**~~ — **selesai 2026-09-11 (sesi keempat).** Ternyata tidak
   butuh Docker seperti diasumsikan: Postgres 16 sudah berjalan langsung di
   mesin pengguna. Seluruh jahitan terverifikasi lewat HTTP asli dengan role
   `pop_app` dan RLS aktif, termasuk idempotensi tarik-ulang dan isolasi
   tenant. Lihat poin 4 di bagian "Yang BELUM diverifikasi" untuk hasilnya.

8. **Putuskan `SignalSource` untuk pengukuran instrumen.** Kualitas udara
   sementara memakai `DIGITAL` dengan peringatan di `method`, karena nilai
   enum baru (`SENSOR`) butuh `ALTER TYPE signal_source ADD VALUE` di
   Supabase — kelas migrasi yang pernah menjatuhkan tiga halaman production
   pada 2026-09-02, jadi tidak dilakukan diam-diam. Lihat
   `docs/deployment-status.md` bagian "Redesain tema terang + dua konektor
   deret publik".

9. ~~**Tutup bug 403 Wikimedia terhadap Render.**~~ — **selesai 2026-09-12**.
   PR #10 di-merge, Render redeploy, `/metrics/collect` berubah dari `502`
   ke `200` (`fetched: 30, stored: 30`) dalam ~90 detik dengan payload yang
   sama persis. Halaman `/deret` sekarang benar-benar bisa dipakai dari UI.

   **Hipotesis "IP datacenter Render diblokir" ternyata keliru** — IP-nya
   tidak diblokir; UA lama yang tanpa titik kontak nyata ditolak dari IP
   datacenter padahal diterima dari IP rumahan. Jadi pola "tarik dari mesin
   lokal lalu kirim lewat endpoint" **tidak jadi diperlukan** di sini.
   Bukti lengkapnya (termasuk verifikasi lanjutan: idempotensi `collect`,
   konektor Open-Meteo, dan rantai collect → forecast dari production) ada di
   `docs/deployment-status.md` blok "MULAI DARI SINI".
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
