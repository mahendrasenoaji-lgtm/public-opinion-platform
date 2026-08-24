# Status Deployment

Ditulis 2026-08-20 setelah sesi verifikasi end-to-end + deploy pertama.
Update 2026-08-24 (sesi panjang, 6 commit ke main): CORS_ORIGINS
diselesaikan, slider bobot Opinion Index diverifikasi live, gerbang
`SITE_PASSWORD` didokumentasikan, login user asli dibangun (menggantikan
`DEMO_ACCESS_TOKEN`), bug RLS di `/auth/login|register|refresh`
diperbaiki, dan Phase 1 dikeraskan: `ruff check app tests` + `mypy
app/services app/ai` bersih 100%, CI (GitHub Actions) terpasang dan
hijau. Lihat bagian "Pengerasan Phase 1" di bawah untuk detail lengkap.
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
- user demo: `user@publicopinion.id` (`user_id` = `23843249-5249-4911-94c8-b609c117fa39`, role `RESEARCH_DIRECTOR`) — email & password_hash **diganti 2026-08-24** dari `direktur@demo.id`/placeholder ke email sekarang + argon2 asli, atas permintaan pengguna. Login lewat form `/masuk` sudah diverifikasi jalan (lihat bagian "Login asli" di bawah — sempat gagal duluan gara-gara bug RLS di `/auth/login`, sudah diperbaiki). Password plaintext-nya sengaja tidak ditulis di sini (repo public) — ada di password manager pengguna; kalau perlu reset lagi, jalankan `UPDATE users SET email = ..., password_hash = ... WHERE email = 'user@publicopinion.id'` dengan hash dari `argon2.PasswordHasher().hash(...)` (lib yang sama dipakai `apps/api/app/services/auth.py`).

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

## ✅ Login asli — selesai 2026-08-24

`DEMO_ACCESS_TOKEN`/`NEXT_PUBLIC_DEMO_ACCESS_TOKEN` diganti sesi cookie
httpOnly. Ringkasannya (detail desain lengkap ada di riwayat sesi, bukan di
sini — cari kalau perlu):

- Halaman login: `/masuk` (email+password) — **beda** dari `/login` yang
  dipakai gerbang `SITE_PASSWORD` di atas. Route handler:
  `/api/session/login`, `/api/session/logout`.
- Cookie `pop_session` (access token) + `pop_refresh` (refresh token),
  httpOnly, `maxAge` mengikuti klaim `exp` token masing-masing.
  `lib/api.ts` baca cookie ini lewat `next/headers` — cuma bisa dipanggil
  dari konteks server (Server Component/Action/Route Handler), bukan dari
  client langsung.
- `middleware.ts` sekarang dua lapis: cek `SITE_PASSWORD` dulu (tidak
  diubah), baru cek sesi `pop_session` ada & belum expired (cek cepat,
  **tanpa** verifikasi tanda tangan — bukan batas keamanan, cuma
  convenience redirect ke `/masuk`). Batas keamanan sungguhan tetap di
  FastAPI (`decode_token` verifikasi HS256 penuh) + RLS Postgres.
- **Sengaja tidak ada auto-refresh token** di iterasi ini — kalau access
  token expired, `api()` dapat 401 dari backend lalu redirect ke `/masuk`,
  user login ulang manual. `ACCESS_TOKEN_MINUTES=43200` (30 hari) di Render
  bikin ini jarang kejadian untuk skala kuliah. Endpoint
  `/v1/auth/refresh` sudah ada di backend kalau nanti mau dikeraskan.
  `refresh_token_days` default 14 (lebih pendek dari access token 30
  hari — pengaturan yang sudah ada sebelum sesi ini, FYI kalau mau
  diselaraskan nanti).
- `WeightEditor.tsx` (client component, satu-satunya yang tadinya panggil
  `api()` langsung dari browser) sekarang lewat Server Action
  `saveOpinionWeights()` di `app/(dashboard)/opinion-index/actions.ts`.
- **Tidak ada env var Vercel baru** yang dibutuhkan (sengaja — lihat
  keputusan desain "middleware convenience check" di atas, tidak perlu
  `JWT_SECRET` disinkronkan ke Vercel).
- `DEMO_ACCESS_TOKEN`/`NEXT_PUBLIC_DEMO_ACCESS_TOKEN` di Vercel jadi tidak
  terpakai lagi — aman dihapus kapan saja, tidak memblokir apa pun.
- Password demo user diganti dari placeholder ke argon2 asli — lihat
  catatan di atas.
- Tidak ada halaman registrasi (di luar cakupan — org/user diprovisikan
  manual).

**Dua bug infrastruktur ditemukan & diperbaiki di sesi yang sama, keduanya
baru ketahuan karena baru sekarang ada yang benar-benar coba jalur login
end-to-end:**

1. **Vercel Root Directory kosong.** Project Settings → Build and
   Deployment → Root Directory ternyata kosong (bukan `apps/web`), bikin
   dua deploy berturut-turut gagal (`Couldn't find any 'pages' or 'app'
   directory`, lalu `No Next.js version detected`). Sudah diisi `apps/web`
   dan disimpan. Kalau ini kosong lagi entah kenapa di masa depan, itu
   sebabnya build tiba-tiba gagal padahal kode lokal build mulus.
2. **`/auth/login` selalu balas 401 apa pun passwordnya.** Query user lewat
   email butuh akses ke tabel `users` SEBELUM org_id-nya diketahui
   (ayam-telur), tapi `get_session()` tidak pernah men-set
   `app.current_org` — jadi kena `FORCE ROW LEVEL SECURITY` dan selalu
   kosong. Diperbaiki dengan fungsi Postgres `SECURITY DEFINER` sempit
   (`auth_lookup_user`, di `db/rls.sql`, migrasi sudah diterapkan manual ke
   Supabase — proyek ini belum punya tooling migrasi otomatis) — **bukan**
   melonggarkan policy `users_tenant` secara umum, itu akan membocorkan
   users lintas tenant untuk semua query tanpa `app.current_org`. Efek
   samping: `last_login_at` sekarang sengaja tidak diupdate lagi (kena RLS
   yang sama, sudah senyap gagal sejak awal — bukan regresi). `/auth/register`
   punya akar masalah identik (INSERT ke `organizations`/`users` tanpa
   org_id) dan **masih belum diperbaiki** — tidak ada UI yang memakainya
   sekarang jadi sengaja dilewati, tapi kalau nanti ada halaman registrasi,
   ingat perbaiki ini dulu.

**Login end-to-end sudah diverifikasi live** (bukan cuma lolos build):
login lewat `/masuk` → redirect ke `/command` → slider bobot Opinion Index
lewat Server Action → simpan → hard reload → nilai bertahan → dikembalikan
ke semula → tombol Keluar → cookie hilang → akses halaman lagi balik ke
`/masuk`. Kredensial demo saat ini: email `user@publicopinion.id` (diganti
dari `direktur@demo.id` atas permintaan pengguna), password ada di
password manager pengguna — lihat cara reset di bagian atas kalau perlu.

## ✅ Pengerasan Phase 1 — selesai 2026-08-24

Atas instruksi eksplisit pengguna ("kerjakan bertahap... sebelum semua
dapat running... akan digunakan secara real time") — bukan inisiatif
sendiri. Urutan mengikuti CLAUDE.md §5 ("jangan lompat ke Phase 2 sebelum
Phase 1 punya tes").

- **`/auth/register` dan `/auth/refresh` diperbaiki** — akar masalah RLS
  identik dengan bug login di atas. Dua fungsi `SECURITY DEFINER` baru
  (`auth_lookup_user_by_id`, `auth_register`) di `db/rls.sql`, migrasi
  sudah diterapkan ke Supabase. `/auth/register` masih tidak punya UI
  (di luar cakupan, sesuai keputusan desain login asli di atas) — jadi
  cuma diverifikasi lewat CI/tes, belum dicoba live ke Supabase produksi
  secara terpisah (beda dengan login+refresh yang sudah, lihat di bawah).
- **`apps/api/tests/test_auth_router.py` baru** — tes end-to-end HTTP asli
  (httpx.AsyncClient) untuk ketiga endpoint auth, terhadap Postgres nyata
  dengan role `pop_app` (RLS aktif, bukan superuser — superuser akan
  membuat tes ini lulus palsu). Kelas tes yang seharusnya menangkap kedua
  bug RLS di atas sebelum sampai production.
- **`ruff check app tests` + `mypy app/services app/ai` bersih 100%** di
  seluruh backend (sebelumnya 96 pelanggaran ruff pra-ada + 6 mypy-strict
  di scope yang CLAUDE.md §6 wajibkan bersih, tidak pernah ketahuan karena
  tidak ada yang menjalankannya otomatis). 6 pelanggaran SENGAJA diberi
  `noqa` eksplisit + alasan di kode, bukan diperbaiki: 5x `UP042`
  (str+Enum di `app/models/*.py` — area yang sudah punya bug dorman
  tercatat soal pemetaan enum Postgres native, tidak diubah tanpa
  verifikasi eksplisit) dan 1x `B017` (exception generik di tes RLS,
  disengaja karena kelas exception driver Postgres bisa beda tergantung
  versi asyncpg/SQLAlchemy).
- **`.github/workflows/ci.yml` baru** — `pytest` (role `pop_app`, RLS
  aktif) + `ruff` + `mypy` untuk backend, `typecheck` + `next build` untuk
  frontend, jalan tiap push/PR ke `main`. **Hijau, sudah diverifikasi**
  (bukan cuma ditulis) — sempat merah 2x di run pertama (89 pelanggaran
  ruff pra-ada yang di atas, lalu `JWT_SECRET` workflow bentrok dengan
  nilai yang di-hardcode `test_auth_service.py`), keduanya diperbaiki dan
  run berikutnya hijau penuh.
- **Makefile target `test-db` baru** — provisioning database `pop_test`
  (schema+RLS) yang sebelumnya langkah manual tidak terdokumentasi di
  mana pun (baru ketahuan sesi ini saat mencoba `make test` dari nol).
- Login + refresh **diverifikasi live lagi terhadap Supabase produksi**
  setelah semua perubahan di atas (bukan cuma lewat CI) — login
  `user@publicopinion.id`, lalu tukar refresh token, keduanya `200`.

**Yang sengaja TIDAK dikerjakan di tahap ini** — di luar "Phase 1 harus
punya tes" dan butuh keputusan/kredensial yang bukan wewenang Claude
sendiri (lihat Phase 2/3/4 di bawah): konektor media sosial, model
forecast nyata, SSO, billing, dll. Kalau ragu diselesaikan diam-diam,
lebih baik berhenti dan tanya — sesuai prinsip CLAUDE.md §8.

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
- Belum ada custom domain — masih `.vercel.app` dan `.onrender.com`.
- ~~Belum ada CI~~ — selesai 2026-08-24, lihat bagian "Pengerasan Phase 1"
  di atas.

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
