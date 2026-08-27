# Roadmap

Kerjakan berurutan. Setiap fase selesai berarti: berjalan, teruji, dan
terdokumentasi — bukan sekadar ada di UI.

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

- [ ] Konektor modular (YouTube, X, Meta, TikTok bila akses resmi tersedia)
- [ ] Pipeline ingestion di worker: dedup, bahasa, embedding
- [ ] Sentiment + emotion (model Indonesia; evaluasi terhadap set berlabel manual)
- [ ] Topic discovery: embedding → HDBSCAN → label LLM → verifikasi manusia
- [ ] Narrative map + momentum
- [ ] Media monitoring + stance tingkat artikel
- [ ] Peta geografis (MapLibre, hanya untuk data bergeoreferensi)
- [ ] AI Copilot berbasis RAG atas data agregat

**Perhatian:** sentiment berbahasa Indonesia adalah bagian yang paling mudah
salah. Sediakan set evaluasi berlabel manual sebelum menyalakan fitur ini di
proyek nyata, dan laporkan akurasinya di UI.

## Phase 3 — prediksi

- [ ] Estimasi model forecast di worker (state-space/SARIMAX)
- [ ] What-If simulator (lapisan API sudah ada di `services/forecast.py`)
- [x] Polarization Index (`GET /projects/{id}/risk/polarization`, selesai
      2026-08-27 — lihat `docs/deployment-status.md`)
- [ ] Opinion Risk Score gabungan 9 komponen (`services/risk.py` sudah ada,
      tapi 5 komponennya butuh sinyal Phase 2 yang belum ada — lihat
      `app/routers/risk.py` untuk daftar lengkapnya)
- [ ] Influencer network dengan istilah *influence estimate*
- [ ] Communication Impact — **wajib** desain pembanding
      (difference-in-differences atau synthetic control). Tanpa itu, modul ini
      tidak boleh menghasilkan klaim efek.

## Phase 4 — enterprise

- [ ] Orkestrasi multi-agent penuh
- [ ] SSO/SAML, SCIM, MFA wajib
- [ ] API publik + webhooks + rate limiting per tenant
- [ ] Report generator: PDF, DOCX, PPTX, XLSX
- [ ] Billing: subscription + kredit survei/data/AI
- [ ] Observability: tracing, evaluasi keluaran model, deteksi drift
