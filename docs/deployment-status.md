# Status Deployment

Ditulis 2026-08-20 setelah sesi verifikasi end-to-end + deploy pertama.
Update 2026-08-24: CORS_ORIGINS diselesaikan, slider bobot Opinion Index
diverifikasi live (simpan sungguhan, bukan pratinjau), dan gerbang
`SITE_PASSWORD` (ditambah 2026-08-22 di sesi lain yang tidak tercatat di
sini saat itu) didokumentasikan.
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

## ✅ CORS_ORIGINS — selesai 2026-08-24

`CORS_ORIGINS` sudah di-set di **Render → pop-api → Environment**:
```
CORS_ORIGINS=["https://public-opinion-platform.vercel.app","http://localhost:3000"]
```
Preflight `OPTIONS` terverifikasi `200` dengan
`access-control-allow-origin: https://public-opinion-platform.vercel.app`
(butuh ~1-2 menit redeploy Render sebelum berlaku — percobaan pertama masih
`400` karena redeploy belum selesai, percobaan kedua sukses).

Slider bobot di Opinion Index juga sudah diverifikasi live end-to-end:
geser slider → status "PRATINJAU" (belum tersimpan) → klik "Simpan Bobot" →
status jadi "Bobot tersimpan" → **hard reload (server component, bukan
cache client) → nilai bertahan** → konfirmasi PUT benar-benar menulis ke
Supabase, bukan cuma state React lokal. Diuji dengan mengubah bobot
Sentimen 20%→30% lalu dikembalikan ke nilai semula (20/25/25/12/10/8) di
akhir supaya data demo tidak tertinggal berubah.

## ⚠️ Gerbang `SITE_PASSWORD` — sengaja, tapi belum tercatat sebelumnya

Commit `97c336f` (2026-08-22, sesi terpisah yang tidak tercatat di memori
sesi ini saat itu) menambah site-wide password gate di frontend:
`apps/web/middleware.ts` + `apps/web/lib/auth.ts` — cookie sesi HMAC-SHA256
(`pop_gate_session`, 7 hari), pola yang sama dipakai di situs pre-launch
lain milik pengguna. Env var yang dibutuhkan di Vercel: `SITE_PASSWORD`
(ditandai *Sensitive* — nilainya tidak bisa dilihat ulang lewat dashboard
Vercel setelah disimpan, cuma ada di password manager pengguna) dan
`SESSION_SECRET`. Keduanya sudah terkonfigurasi dan berfungsi (login
terverifikasi 2026-08-24).

Dampak: **situs production sekarang butuh login `SITE_PASSWORD` dulu**
sebelum halaman apa pun bisa diakses — termasuk untuk verifikasi otomatis
sesi mendatang. Kalau perlu browsing terautomasi ke situs ini, sesi harus
login manual dulu (Claude tidak boleh mengetik password walau pengguna
menawarkan memberikannya langsung — lihat aturan boundary kredensial).

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
- Domain telanjang (`/`) redirect ke `/command` — sebelumnya 404 karena
  route App Router tidak punya halaman di root sama sekali (diperbaiki
  commit `db312b7`)
- `PUT .../opinion/weights` (bobot dimensi Opinion Index, beda dengan
  weighting compute raking survei di bawah) — diverifikasi 2026-08-24
  langsung terhadap Supabase produksi lewat slider di browser, termasuk
  hard-reload untuk membuktikan tulisan persisten, bukan cuma state client

**Belum diverifikasi di Supabase secara spesifik** (baru di database Docker
lokal): endpoint weighting compute (raking survei), endpoint trend/timeline
dengan data Supabase yang sebenarnya (baru dicek index & divergence). Kemungkinan besar
sama-sama jalan karena schema & RLS identik, tapi belum benar-benar dicoba.

## Kredensial (SENGAJA tidak ada di repo ini — repo public)

Bukan di file lokal (pengguna kerja lintas komputer, file lokal tidak
portable) dan bukan di git (repo public, commit rahasia = kebocoran).
Disimpan pengguna sendiri di password manager, sudah diberikan lengkap satu
kali lewat chat 2026-08-20. Kalau sesi baru butuh menyentuhnya dan tidak
punya nilainya, **minta ke pengguna** — jangan generate ulang tanpa
ditanya dulu (mengganti `pop_app` password atau `JWT_SECRET` yang sudah
aktif akan mematahkan token yang sedang dipakai user lain / deployment
yang jalan).

Yang perlu diminta kalau dibutuhkan: password Supabase (superuser
`postgres` dan role `pop_app`, dua-duanya beda), `JWT_SECRET` Render,
`DEMO_ACCESS_TOKEN` Vercel. Semuanya juga selalu bisa dilihat ulang oleh
pengguna langsung dari dashboard masing-masing platform (Supabase →
Settings → Database; Render → Environment; Vercel → Project Settings →
Environment Variables) — itu sumber kebenaran yang sebenarnya, bukan
salinan manapun.

`DEMO_ACCESS_TOKEN` / `NEXT_PUBLIC_DEMO_ACCESS_TOKEN` kedaluwarsa
**sekitar 19 September 2026**. Setelah itu, generate ulang dengan
`create_access_token()` (lihat `apps/api/app/services/auth.py`) pakai
`JWT_SECRET` dari Render, lalu `vercel env rm` + `vercel env add` untuk
kedua nama env var itu, redeploy.

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
