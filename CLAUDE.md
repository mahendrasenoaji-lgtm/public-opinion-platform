# CLAUDE.md — Panduan kerja untuk agen di repo ini

Baca file ini seluruhnya sebelum menulis kode. File ini berisi aturan yang tidak
boleh dilanggar, bukan sekadar deskripsi proyek.

## 1. Apa yang sedang dibangun

**AI Public Opinion Platform** — platform intelligence yang menggabungkan survei
probabilistik, percakapan media sosial, dan liputan media menjadi satu lapisan
"public opinion intelligence" untuk pemerintah, BUMN, konsultan, dan lembaga riset
di Indonesia.

Ini **bukan** aplikasi survei. Aplikasi survei menampilkan hasil. Platform ini
menjelaskan *mengapa* hasilnya berbeda antar sumber, siapa yang terpengaruh, ke
mana arahnya, dan apa batas dari setiap klaim.

Bahasa antarmuka: **Bahasa Indonesia**. Nama modul boleh Inggris (Command Center,
Opinion Index). Kode, komentar, dan nama variabel: Inggris.

## 2. Tiga aturan arsitektural yang tidak bisa dinegosiasikan

Kalau sebuah pull request melanggar salah satu dari ini, ia salah — sekalipun
fiturnya jalan.

### R1 — Setiap metrik membawa provenance-nya

Tidak ada angka yang beredar di sistem tanpa `source` (`SURVEY` / `SOCIAL` /
`MEDIA` / `DIGITAL`) dan `method`. Angka survei probabilistik dan sentiment media
sosial **tidak pernah** dirata-rata begitu saja menjadi satu angka tanpa label.

Di frontend, warna menandai sumber, bukan estetika:

| Sumber | Token | Hex | Arti |
|---|---|---|---|
| Survei probabilistik | `--survey` | `#4DA3FF` | Bisa digeneralisasi ke populasi |
| Percakapan sosial | `--social` | `#FF7A45` | Self-selected, tidak representatif |
| Liputan media | `--media` | `#9B8AFB` | Agenda redaksi, bukan opini pembaca |

Jangan pakai warna ini untuk hal lain. Jangan tambahkan warna sumber baru tanpa
menambah enum `SignalSource` di backend.

### R2 — Setiap keluaran AI dibungkus `AIEnvelope`

Lihat `apps/api/app/ai/envelope.py`. Endpoint apa pun yang mengembalikan hasil
LLM harus mengembalikan `AIEnvelope[T]`, yang wajib berisi:

`evidence` (referensi data agregat) · `method` · `confidence` · `limitations` ·
`model_version` · `human_review`

Ini bukan dekorasi. `AIEnvelope` menolak divalidasi kalau `evidence` kosong atau
`limitations` kosong. Kalau Anda tergoda membuat jalan pintas untuk melewatinya,
itu tandanya fitur tersebut memang tidak boleh ada.

Di UI, envelope ini dirender sebagai komponen `<Provenance />` di kaki setiap
kartu. Tidak ada kartu insight tanpa kaki.

### R3 — Isolasi tenant di lapisan database, bukan di lapisan aplikasi

Postgres Row Level Security aktif di semua tabel bertenant. Setiap request
menyetel `SET LOCAL app.current_org = '<uuid>'` di dalam transaksi
(`apps/api/app/deps.py`). Jangan pernah menambahkan filter `WHERE org_id = ...`
secara manual sebagai pengganti RLS, dan jangan pernah memakai koneksi superuser
untuk query aplikasi.

Tes `apps/api/tests/test_tenant_isolation.py` harus tetap hijau. Kalau Anda
menambah tabel bertenant, tambahkan kebijakan RLS-nya di `db/rls.sql` **di commit
yang sama**.

## 3. Batas etis yang sudah diputuskan

Ini keputusan produk, bukan preferensi. Jangan diimplementasikan ulang.

- Jangan menginferensi agama, etnisitas, orientasi seksual, kondisi kesehatan,
  atau afiliasi politik individu. Segmentasi hanya dari variabel yang dikumpulkan
  dengan consent.
- Jangan pernah menyatakan akun tertentu "mengendalikan" opini. Istilah yang
  dipakai: *influence estimate*, selalu dengan metodenya.
- Jangan menyatakan kausalitas dari data observasional. Kata yang dipakai:
  *berkaitan dengan*, *kemungkinan terkait*. Klaim kausal hanya boleh keluar dari
  modul Communication Impact yang punya desain pembanding.
- Jangan menyimpan identitas responden bersama jawabannya. Tabel `respondents`
  dan `responses` dipisah; PII hidup di `respondent_identities` dengan retensi
  terpisah dan akses terbatas.
- Jangan menandai fraud. Sistem hanya memberi `quality_flag` untuk ditinjau
  manusia.
- Skor provinsi tidak ditampilkan bila `achieved_n < 250`. Tampilkan
  "data tidak cukup", bukan angka dengan CI lebar.

## 4. Peta repo

```
apps/api/            FastAPI + SQLAlchemy 2.0 async + Pydantic v2
  app/models/        Tabel SQLAlchemy
  app/schemas/       Kontrak Pydantic (yang keluar lewat HTTP)
  app/routers/       Endpoint, tipis — logika ada di services/
  app/services/      Logika domain murni, tanpa I/O, mudah dites
  app/connectors/    Konektor sumber data — SELURUHNYA I/O, karena itu bukan
                     services/. Batas legal yang mengikat ada di base.py
  app/ai/            Abstraksi provider LLM + agen + envelope + retrieval
apps/web/            Next.js 15 App Router + TypeScript + Tailwind
  components/        Panel, Provenance, DivergenceBand, chart wrappers
  lib/tokens.ts      Sumber tunggal token desain (harus cocok dengan R1)
db/schema.sql        DDL
db/rls.sql           Kebijakan Row Level Security
db/seed.py           Data demo sintetis Indonesia
docs/                Keputusan arsitektur, model data, governance, roadmap
```

Aturan lapisan: `routers` boleh memanggil `services`, `connectors`, dan `ai`.
`services` tidak boleh mengimpor `routers`, `connectors`, atau `ai`. Logika
statistik hidup di `services` sebagai fungsi murni supaya bisa dites tanpa
database dan tanpa memanggil LLM.

`connectors` melanggar kemurnian itu dengan sengaja — ia memang bicara ke
jaringan. Yang bisa dites tanpa jaringan (parsing respons) dipisah jadi fungsi
murni di dalam modul konektornya, dan itu yang dites. Jangan menambah konektor
tanpa membaca batas legal di `app/connectors/base.py` lebih dulu.

## 5. Urutan pengerjaan

Kerjakan berurutan. Jangan lompat ke Phase 2 sebelum Phase 1 punya tes.

**Phase 1 — fondasi (kerjakan ini dulu)**
1. `docker compose up` jalan; migrasi + seed berhasil
2. Auth (JWT, refresh, MFA opsional) + RBAC 8 peran
3. CRUD organization / project
4. Survey builder + respondent + response ingest
5. `services/poi.py` — Public Opinion Index dengan bobot configurable
6. `services/sampling.py` — kalkulator ukuran sampel
7. `services/quality.py` — deteksi straight-lining, speeding, inkonsistensi
8. Command Center + Opinion Index di frontend

**Phase 2 — sinyal**
Social listening (konektor modular), media monitoring, topic modeling
(embeddings + HDBSCAN), narrative map, peta geografis, AI Copilot berbasis RAG.

**Phase 3 — prediksi**
Forecast state-space, What-If simulator, opinion risk score, polarization index,
influencer network, communication impact (butuh desain pembanding).

**Phase 4 — enterprise**
Orkestrasi multi-agent, SSO/SAML, webhooks, API publik, billing, audit lanjutan.

Detail per fase ada di `docs/roadmap.md`.

## 6. Konvensi

- Python 3.12, `ruff` + `mypy --strict` untuk `app/services` dan `app/ai`.
- SQLAlchemy 2.0 async saja. Tanpa query sinkron.
- Pydantic v2. Skema respons selalu eksplisit; jangan mengembalikan model ORM.
- Frontend: server component sebagai default; `"use client"` hanya untuk yang
  memang interaktif (slider bobot, simulator, pemilih provinsi).
- Charts: Recharts untuk yang standar, ECharts hanya kalau Recharts tidak cukup.
  Peta: MapLibre — **hanya** kalau data punya georeferensi asli. Sampai itu ada,
  pakai grid provinsi berperingkat seperti di prototipe.
- Tes: pytest + httpx AsyncClient. Setiap fungsi di `services/` wajib punya tes
  unit. Setiap endpoint bertenant wajib punya tes isolasi.
- Commit message: `area: ringkas dalam bentuk imperatif`, contoh
  `poi: bobot dimensi dinormalisasi sebelum agregasi`.

## 7. Data demo

Semua yang ada di seed adalah **data sintetis**. Jangan pernah menyajikannya
seolah-olah hasil survei nyata. Setiap dashboard yang berjalan di atas seed harus
menampilkan penanda "Demo data sintetis" (lihat `nav-foot` di prototipe).

## 8. Kalau ragu

Prinsip pemutus: **platform ini lebih baik mengatakan "kami tidak tahu" daripada
memberi angka yang tidak bisa dipertanggungjawabkan.** Ketika ada pilihan antara
tampilan yang mengesankan dan klaim yang jujur, pilih yang jujur. Nilai jual
produk ini justru ada di situ.
