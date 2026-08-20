# Status Deployment

Ditulis 2026-08-20 setelah sesi verifikasi end-to-end + deploy pertama.
Dokumen ini adalah sumber kebenaran untuk sesi berikutnya — jangan andalkan
riwayat chat, chat lama tidak ikut ter-clone.

## Live sekarang

| Layer | Platform | URL | Status |
|---|---|---|---|
| Frontend | Vercel (`alwayslearn` org) | https://public-opinion-platform.vercel.app | Live, build hijau |
| Backend | Render (free tier) | https://pop-api-ptug.onrender.com | Live (`/health` OK) |
| Database | Supabase (`ALWAYSLEARN` org, project `uvqzxkabrsnaeeeefjzq`) | — | Live, schema+RLS+seed diterapkan |
| Repo | GitHub | https://github.com/mahendrasenoaji-lgtm/public-opinion-platform | Public |

Org demo yang sudah di-seed di Supabase:
- `org_id` = `19a872b1-1a32-49d6-a168-c46d8b4eb79b`
- `project_id` = `0a06b813-a1ec-4bba-8de1-38e06b2ac2f1`
- user demo: `direktur@demo.id` (`user_id` = `23843249-5249-4911-94c8-b609c117fa39`), password_hash sengaja placeholder — tidak bisa login lewat form, token dibuat manual lewat `create_access_token()`.

## ⚠️ Langkah berikutnya yang BELUM selesai (paling prioritas)

**CORS_ORIGINS di Render belum di-set.** Backend menolak request dari
`https://public-opinion-platform.vercel.app` dengan "Disallowed CORS origin".
Akibatnya: halaman render (GET, server-side) sudah jalan sempurna, tapi
slider bobot di Opinion Index (PUT dari browser) masih gagal.

Perbaikannya satu baris — buka **Render → pop-api → Environment**, tambah:
```
CORS_ORIGINS=["https://public-opinion-platform.vercel.app","http://localhost:3000"]
```
Render auto-redeploy (~1-2 menit) setelah disimpan. Verifikasi dengan:
```bash
curl -X OPTIONS "https://pop-api-ptug.onrender.com/v1/projects/0a06b813-a1ec-4bba-8de1-38e06b2ac2f1/opinion/weights" \
  -H "Origin: https://public-opinion-platform.vercel.app" \
  -H "Access-Control-Request-Method: PUT" -i
```
Harus `200`, bukan `400 Bad Request` / "Disallowed CORS origin".

## Yang sudah diverifikasi live (bukan cuma "harusnya jalan")

- `db/seed.py` dijalankan langsung ke Supabase — 780 responden, 102 metric
  snapshot, 6 timeline event
- `POST /surveys/{id}/weights/compute` (raking pasca-stratifikasi) dijalankan
  terhadap 780 responden nyata di database lokal (bukan Supabase — lihat
  catatan di bawah), bobot tersimpan benar
- Command Center + Opinion Index dirender live dari Vercel, ambil data dari
  Render, yang ambil data dari Supabase — rantai penuh, bukan potongan
- `test_tenant_isolation.py` lulus untuk pertama kalinya di database lokal
  (RLS + role `pop_app`, bukan superuser)

**Belum diverifikasi di Supabase secara spesifik** (baru di database Docker
lokal): endpoint weighting compute, endpoint trend/timeline dengan data
Supabase yang sebenarnya (baru dicek index & divergence). Kemungkinan besar
sama-sama jalan karena schema & RLS identik, tapi belum benar-benar dicoba.

## Kredensial (JANGAN commit ke repo — ini dicatat di luar git sengaja)

Tersimpan di `.env` (root, lokal) dan `apps/web/.env.local` (lokal) —
keduanya gitignored. Kalau sesi baru butuh menyentuh Supabase/Render/Vercel
lagi dan tidak punya akses ke file lokal itu, kredensial berikut perlu
diminta ulang dari pengguna atau di-generate ulang:

- Supabase DB password (superuser `postgres`) — pengguna yang generate lewat
  dashboard, tidak dicatat di sini
- `pop_app` role password di Supabase — dibuat khusus untuk deployment ini
  (BUKAN `change-me` default di `db/rls.sql`, itu cuma untuk `docker-compose`
  lokal)
- `JWT_SECRET` di Render — auto-generated oleh `render.yaml`
  (`generateValue: true`), bisa dilihat di Render → Environment
- `DEMO_ACCESS_TOKEN` / `NEXT_PUBLIC_DEMO_ACCESS_TOKEN` di Vercel — token
  JWT 30 hari untuk user demo di atas, **kedaluwarsa sekitar 19 September
  2026**. Setelah itu, generate ulang dengan `create_access_token()` (lihat
  `apps/api/app/services/auth.py`) pakai `JWT_SECRET` dari Render, lalu
  `vercel env rm` + `vercel env add` untuk kedua nama env var itu, redeploy.

## Yang masih kurang (di luar langkah CORS di atas)

### Residual Phase 1
- **Belum ada halaman login/sesi asli** — `lib/api.ts` pakai token demo
  lewat env var (`DEMO_ACCESS_TOKEN` server, `NEXT_PUBLIC_...` client).
  `NEXT_PUBLIC_*` berarti token itu **terlihat oleh siapa pun** yang buka
  devtools di situs publik. Diterima untuk demo kuliah dengan data sintetis;
  wajib diganti sesi cookie httpOnly sebelum dipakai untuk apa pun yang
  serius.
- Cuma 2 dari 9 halaman dashboard yang di-port ke Next.js (Command Center,
  Opinion Index) — sesuai definisi selesai Phase 1 di `docs/roadmap.md`.
  7 halaman lain (Consistency, Narrative, Segments, Geo, Forecast, Brief,
  Governance) cuma ada di prototipe statis (`design-reference/`).
- "Isu publik" dan "Peringatan aktif" sengaja tidak dirender di Command
  Center — butuh topic modeling & anomaly detection (Phase 2/3) yang belum
  ada.
- **Bug dorman belum diperbaiki**: `AIOutput.confidence` dan
  `AIOutput.human_review` di `models/governance.py` kemungkinan besar punya
  bug yang sama seperti `MetricSnapshot.source` (dipetakan `String`, padahal
  kolomnya enum Postgres native) — tidak bisa diverifikasi karena belum ada
  kode yang menulis ke `ai_outputs` sama sekali. Perbaiki begitu Phase 2
  mulai menulis ke tabel ini.

### Infrastruktur & operasional
- Render free tier: server tidur setelah 15 menit tidak dipakai, request
  pertama setelah itu lambat 30-60 detik.
- Belum ada CI (GitHub Actions) yang menjalankan `pytest`/`ruff`/`mypy`/
  `next build` otomatis tiap push — semua verifikasi sesi ini manual.
- Belum ada custom domain — masih `.vercel.app` dan `.onrender.com`.

### Phase 2 — sinyal (belum dimulai sama sekali)
Konektor sosial (YouTube/X/Meta/TikTok), pipeline ingestion (dedup, bahasa,
embedding), sentiment Indonesia + set evaluasi, topic discovery (embedding →
HDBSCAN → label LLM → verifikasi manusia), narrative map + momentum, media
monitoring, peta geografis (MapLibre — sekarang cuma grid provinsi statis),
AI Copilot RAG.

### Phase 3 — prediksi (belum dimulai)
Model forecast nyata di worker (state-space/SARIMAX — `services/forecast.py`
sudah ada tapi belum ada model yang benar-benar di-fit), influencer network,
Communication Impact (**wajib** desain pembanding, tanpa itu dilarang klaim
efek kausal — lihat CLAUDE.md).

### Phase 4 — enterprise (belum dimulai)
Multi-agent orchestration, SSO/SAML/MFA, API publik + webhook, report
generator (PDF/DOCX/PPTX/XLSX), billing, observability (tracing, evaluasi
model, deteksi drift).

## Arsitektur deploy (untuk referensi)

```
Vercel (Next.js, server components)
  └─> fetch() ke Render (FastAPI)
        └─> asyncpg ke Supabase Postgres (role pop_app, RLS aktif)
```

Config file: `render.yaml` (root repo, Render Blueprint),
`apps/api/requirements.txt` (di-generate dari `pyproject.toml`,
dibutuhkan Render), `apps/web/.env.local` (lokal, tidak commit — isinya
sama dengan env var Vercel).
