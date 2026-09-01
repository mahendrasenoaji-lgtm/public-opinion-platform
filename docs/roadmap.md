# Roadmap

Kerjakan berurutan. Setiap fase selesai berarti: berjalan, teruji, dan
terdokumentasi — bukan sekadar ada di UI.

Dokumen ini daftar centang per fase. Untuk status jujur per komponen —
seberapa jauh sesuatu sudah dibuktikan bekerja, dan apa yang menahan yang
belum — lihat [progress.md](progress.md).

## Phase 1 — fondasi

- [x] Skema database + RLS
- [x] `services/poi.py` + tes
- [x] `services/sampling.py` + tes
- [x] `services/quality.py` + tes
- [x] `services/divergence.py` + tes
- [x] `services/forecast.py` + tes
- [x] `services/risk.py` + tes (termasuk `polarization`)
- [x] `ai/envelope.py` + tes
- [x] SQLAlchemy 2.0 async models (mirror schema.sql lengkap)
- [x] Auth: JWT + refresh + argon2 + `services/auth.py` + tes
- [x] RBAC 8 peran + 4 kapabilitas eksplisit (`deps.py`)
- [x] CRUD organization / project + versioning bobot POI + audit log
- [x] Survey builder: 9 tipe pertanyaan, reorder, delete
- [x] Ingest respons + quality assessment otomatis (speeding, straight-lining)
- [x] Repository layer: `_load_dimensions` dan `_load_signal_readings` dari `metric_snapshots`
- [x] Forecast what-if endpoint (`POST /forecast/what-if`)
- [x] `services/weighting.py` — raking (pasca-stratifikasi multi-variabel) + tes
- [x] Endpoint `POST /surveys/{id}/weights/compute` — hitung & simpan bobot
- [x] Endpoint `GET /opinion/trend` dan `GET /opinion/timeline`
- [x] Frontend: Command Center (POI, Divergence Band, tren, timeline)
- [x] Frontend: Opinion Index (slider bobot interaktif, tren POI)

**Definisi selesai Phase 1:** seorang peneliti bisa membuat proyek, menyusun
kuesioner, memasukkan data, dan melihat POI dengan interval kepercayaan yang
benar — tanpa satu pun angka tampil tanpa sumber dan metode. **Tercapai.**

Catatan cakupan Command Center: "Isu yang paling dibicarakan" dan "Peringatan
aktif" di prototipe butuh topic modeling dan anomaly detection (Phase 2/3) —
sengaja belum dirender di Next.js supaya tidak ada kartu tanpa data nyata di
baliknya (CLAUDE.md §8). Prototipe (`design-reference/`) tetap menampilkannya
sebagai data sintetis untuk keperluan presentasi/kuliah.

**Diverifikasi end-to-end (2026-08-20)** dengan Docker Desktop + Postgres
nyata: `db/seed.py` → API asli → Next.js asli di browser, termasuk
`test_tenant_isolation.py` yang berjalan untuk pertama kalinya. Verifikasi
ini menemukan dan memperbaiki 7 bug yang mustahil terlihat tanpa Postgres
sungguhan:

1. `db/schema.sql` memakai tipe `citext` tanpa `CREATE EXTENSION "citext"`.
2. `deps.py::tenant_session` — `SET LOCAL app.current_org = :org` dengan bind
   parameter: Postgres tidak menerima parameter pada `SET`. **Ini di jalur
   isolasi tenant produksi — mematahkan hampir semua endpoint bertenant.**
   Diperbaiki dengan `SELECT set_config('app.current_org', :org, true)`.
3. Bug yang sama di `db/seed.py` dan `tests/test_tenant_isolation.py`.
4. `MetricSnapshot.source` dipetakan sebagai `String`, padahal kolomnya
   `signal_source` (enum Postgres native) — `WHERE source = 'SURVEY'` gagal
   dengan "operator does not exist". Diperbaiki dengan `sqlalchemy.Enum`.
5. `_load_signal_readings` membaca metric `"poi"` lintas empat source,
   padahal POI cuma pernah punya source SURVEY — perbandingan tiga sinyal
   sebenarnya ada di metric `survey_positive`/`social_positive`/
   `media_positive`. Bug konseptual di repository layer, bukan di seed.
6. `AuditLog.ip` dipetakan `Text`, padahal kolomnya `inet` — import `INET`
   sudah ada di file itu tapi tidak dipakai.
7. `db/seed.py` tidak mengisi `effective_n` untuk snapshot SOCIAL/MEDIA,
   sehingga Provenance menampilkan "n: 0" yang menyesatkan (melanggar R1).

Juga ditemukan, TIDAK diperbaiki (dormant, tidak ada kode yang menulis ke
`ai_outputs` sama sekali sehingga tidak bisa diuji): `AIOutput.confidence`
dan `AIOutput.human_review` kemungkinan besar punya bug yang sama dengan #4
(dipetakan `String`, kolom aslinya `confidence_band`/`review_status`).
Perbaiki begitu Phase 2 mulai menulis ke tabel ini.

Frontend belum punya halaman login/sesi (di luar cakupan Phase 1) — server
component memakai token demo lewat env var (`DEMO_ACCESS_TOKEN`), komponen
client (slider bobot) lewat `NEXT_PUBLIC_DEMO_ACCESS_TOKEN`. Keduanya cuma
untuk dev/demo lokal, ditandai TODO di `lib/api.ts`. Ganti dengan sesi
cookie httpOnly sebelum ada halaman publik.

## Phase 2 — sinyal

- [x] Konektor modular — RSS (media, tanpa kunci), YouTube Data API v3, X API
      v2, unggahan manual. `app/connectors/`, batas legal di `base.py`.
      Meta/TikTok belum: keduanya butuh akses resmi yang belum dimiliki.
- [x] Pipeline ingestion: dedup (MinHash+LSH), deteksi bahasa, hash author.
      **Belum di worker terpisah** — `POST .../collect` jalan sinkron di dalam
      permintaan, dengan batas `limit` supaya di bawah timeout. Pengumpulan
      terjadwal berskala besar masih perlu worker.
- [x] Sentiment + emotion (leksikon Indonesia; set evaluasi 52 kalimat
      berlabel manual, akurasi dilaporkan lewat
      `GET .../signals/sentiment-quality` dan tampil di `/sinyal`)
- [x] Topic discovery — **TF-IDF → LSA → HDBSCAN → label kata kunci**, BUKAN
      embedding → HDBSCAN → label LLM seperti tertulis semula. Belum ada
      provider embedding yang dikonfigurasi, dan `method` mengembalikan yang
      benar-benar dipakai. Verifikasi manusia atas label belum ada.
- [x] Narrative map + momentum (momentum dari volume per periode;
      `services/topics.py:momentum()`)
- [x] Media monitoring lewat RSS. **Stance tingkat artikel belum** — yang ada
      baru volume dan sentimen leksikon atas judul+ringkasan.
- [ ] Peta geografis (MapLibre, hanya untuk data bergeoreferensi) — belum ada
      sumber bergeoreferensi asli, jadi masih grid provinsi seperti prototipe.
      Provinsi TIDAK diinferensi dari isi teks; lihat `services/ingestion.py`.
- [x] AI Copilot berbasis RAG atas data agregat (`app/ai/retrieval.py`,
      `app/ai/copilot.py`). Retrieval-nya pencocokan kata kunci atas kartu
      fakta agregat — bukan pencarian semantik, dan bukan atas tabel mentions.

**Perhatian:** sentiment berbahasa Indonesia adalah bagian yang paling mudah
salah. Sediakan set evaluasi berlabel manual sebelum menyalakan fitur ini di
proyek nyata, dan laporkan akurasinya di UI. — **Dipenuhi**, dengan catatan
yang harus ikut dibaca: set evaluasi itu ditulis tim pengembang, bukan sampel
acak dari percakapan proyek mana pun. Angkanya (macro-F1 0.902, akurasi 0.897
di antara yang dinilai, abstain 25%) adalah batas ATAS. Sebelum dipakai untuk
keputusan di sebuah proyek, ukur ulang terhadap sampel berlabel dari data
proyek itu sendiri.

## Phase 3 — prediksi

- [x] Estimasi model forecast state-space (`services/timeseries.py`,
      `UnobservedComponents` di-fit pada riwayat `metric_snapshots`).
      **Belum di worker terpisah** — di-fit saat permintaan datang. Untuk
      jumlah pengamatan yang ada sekarang itu cepat; ia perlu pindah ke worker
      begitu riwayatnya panjang atau proyeknya banyak.
- [x] What-If simulator, sekarang di atas baseline yang di-fit. Kalau riwayat
      belum cukup, hasilnya ditandai `fitted: false` dan model-nya bernama
      "lebar interval bawaan (belum ada model terpasang)".
- [x] Polarization Index (`GET /projects/{id}/risk/polarization`, selesai
      2026-08-27 — lihat `docs/deployment-status.md`)
- [x] Opinion Risk Score gabungan 9 komponen (`GET .../risk/score`). Delapan
      komponen dihitung dari data nyata; `geographic_spread` butuh geotag
      resmi yang jarang ada. Skor tidak diterbitkan di bawah cakupan bobot
      60%, dan `coverage` selalu ikut ditampilkan.
- [x] Influencer network dengan istilah *influence estimate*
      (`services/influence.py`, `GET .../influence`). Yang diukur porsi
      percakapan dan keterlibatan — keterpaparan, bukan pengaruh kausal.
      **Graf jaringan antar-akun belum ada**: data yang tersimpan tidak
      memuat relasi balasan/kutipan antar-akun.
- [x] Communication Impact dengan desain pembanding wajib
      (`services/impact.py`, difference-in-differences).
      `NoControlGroup` menolak menghitung tanpa kelompok pembanding, tanpa
      jalan pintas. Synthetic control belum ada.

## Phase 4 — enterprise (belum dimulai)

- [ ] Orkestrasi multi-agent penuh — `app/ai/agents.py:Orchestrator` sudah ada
      dan dipakai Brief + Copilot, tapi baru menjalankan satu agen berurutan
- [ ] SSO/SAML, SCIM, MFA wajib (kolom `users.mfa_secret` sudah ada di schema,
      belum ada kode yang memakainya)
- [ ] API publik + webhooks + rate limiting per tenant
- [ ] Report generator: PDF, DOCX, PPTX, XLSX
- [ ] Billing: subscription + kredit survei/data/AI
- [ ] Observability: tracing, evaluasi keluaran model, deteksi drift

Fase ini butuh keputusan yang bukan wewenang agen: penyedia identitas mana
untuk SSO, penyedia pembayaran mana untuk billing, dan komitmen kontrak API
publik yang tidak bisa ditarik lagi setelah ada yang memakainya. Jangan
dikerjakan tanpa keputusan itu diambil lebih dulu.
