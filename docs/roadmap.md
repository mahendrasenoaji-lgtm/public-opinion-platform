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
- [x] Forecast what-if endpoint + Risk score + Polarization endpoint
- [ ] Bobot pasca-stratifikasi (perhitungan; ingest sudah menyimpan weight)
- [ ] Frontend: Command Center, Opinion Index

**Definisi selesai Phase 1:** seorang peneliti bisa membuat proyek, menyusun
kuesioner, memasukkan data, dan melihat POI dengan interval kepercayaan yang
benar — tanpa satu pun angka tampil tanpa sumber dan metode.

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
- [ ] Opinion Risk Score + Polarization Index (`services/risk.py` sudah ada)
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
