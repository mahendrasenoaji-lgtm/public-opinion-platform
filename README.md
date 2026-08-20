# AI Public Opinion Platform

Platform intelligence opini publik untuk konteks Indonesia. Menggabungkan survei
probabilistik, percakapan media sosial, dan liputan media menjadi satu lapisan
analisis — lalu menjelaskan mengapa ketiganya sering tidak sepakat.

> Kalau Anda agen yang akan menulis kode di repo ini, baca **[CLAUDE.md](CLAUDE.md)**
> lebih dulu. File itu memuat aturan yang mengikat, bukan sekadar deskripsi.

**Live:** [public-opinion-platform.vercel.app](https://public-opinion-platform.vercel.app)
(Vercel → Render → Supabase). Status deploy lengkap, langkah yang belum
selesai, dan kredensial mana yang butuh di-refresh: **[docs/deployment-status.md](docs/deployment-status.md)**.

## Yang membedakan platform ini

Dashboard survei menampilkan hasil. Platform ini menjawab pertanyaan yang
biasanya tidak dijawab siapa pun:

- Survei bilang 68% positif, media sosial bilang 41%. **Mana yang benar?**
  Jawabannya: keduanya, untuk populasi yang berbeda. Platform ini menampilkan
  selisih itu sebagai objek utama, lengkap dengan penjelasan mengapa.
- Setiap angka membawa sumber, metode, sampel efektif, interval kepercayaan, dan
  batasannya. Tidak ada angka telanjang.
- Setiap keluaran AI dibungkus kontrak yang menolak divalidasi kalau buktinya
  kosong, kalau ia mengklaim sebab-akibat tanpa desain pembanding, atau kalau ia
  memberi keyakinan tinggi pada data yang self-selected.
- Skor wilayah tidak diterbitkan kalau sampelnya di bawah 250. Yang muncul:
  "data tidak cukup", bukan angka dengan interval selebar apa pun.

## Menjalankan secara lokal

```bash
cp .env.example .env          # isi JWT_SECRET
docker compose up -d db redis opensearch
make db                       # schema + row level security
make seed                     # data demo sintetis
make api                      # http://localhost:8000/docs
make web                      # http://localhost:3000
```

Tes logika domain berjalan tanpa database:

```bash
cd apps/api && python -m pytest tests/test_poi.py tests/test_sampling.py tests/test_envelope.py -q
```

Tes isolasi tenant memerlukan database dan sengaja memakai peran `pop_app`,
bukan superuser — superuser mengabaikan RLS dan akan membuat tesnya lulus palsu.

## Struktur

```
apps/api        FastAPI + SQLAlchemy 2.0 async + Pydantic v2
apps/web        Next.js 15 App Router + TypeScript
  design-reference/prototype.jsx   prototipe visual yang disetujui
db              schema.sql, rls.sql, seed.py
docs            arsitektur, model data, governance, roadmap
```

## Status

Fondasi arsitektural selesai; fitur dibangun bertahap.

| Bagian | Status |
|---|---|
| Skema database + RLS multi-tenant | Selesai |
| `services/poi.py` — indeks komposit | Selesai, teruji |
| `services/sampling.py` — sampling engine | Selesai, teruji |
| `services/quality.py` — kualitas respons | Selesai, teruji |
| `services/divergence.py` — pembeda utama | Selesai, teruji |
| `services/forecast.py` — forecast + what-if | Selesai, teruji |
| `services/risk.py` — risk score + polarisasi | Selesai, teruji |
| `ai/envelope.py` — kontrak keluaran AI | Selesai, teruji |
| `ai/provider.py` — abstraksi LLM | Selesai |
| SQLAlchemy 2.0 models (mirror schema.sql) | Selesai |
| Auth JWT + refresh + argon2 | Selesai, teruji |
| RBAC 8 peran + kapabilitas eksplisit | Selesai |
| CRUD organization / project + audit log | Selesai |
| Survey builder — 9 tipe pertanyaan | Selesai |
| Ingest respons + quality assessment | Selesai |
| Repository layer (opinion index + divergence) | Selesai |
| Forecast what-if + risk + polarization endpoints | Selesai |
| `services/weighting.py` — bobot pasca-stratifikasi (raking) | Selesai, teruji |
| Frontend — Command Center, Opinion Index (Next.js) | Selesai, **diverifikasi live** dengan data nyata |
| Frontend — 7 halaman sisanya (Consistency, Narrative, dst.) | Prototipe selesai, di luar cakupan Phase 1 |

Phase 1 selesai menurut definisinya sendiri di `docs/roadmap.md`, dan sudah
diverifikasi end-to-end dengan Postgres nyata (bukan cuma lulus tanpa
database) — 7 bug ditemukan dan diperbaiki dalam proses itu, detail lengkap
di `docs/roadmap.md`.

Urutan pengerjaan ada di `docs/roadmap.md`.

## Batas yang sudah diputuskan

Platform ini tidak menginferensi atribut sensitif individu, tidak menyimpan
identitas responden bersama jawabannya, tidak menyatakan akun tertentu
mengendalikan opini publik, tidak menyimpulkan kecurangan (hanya menandai untuk
ditinjau manusia), dan tidak memperlakukan sentiment media sosial sebagai
representasi populasi.

Ini keputusan produk. Detailnya di `docs/ai-governance.md`.

## Data demo

Seluruh isi `db/seed.py` adalah **data sintetis**. Angka, provinsi, narasi, dan
segmen dibuat untuk demonstrasi dan tidak mewakili opini publik Indonesia yang
sebenarnya. Setiap tampilan yang berjalan di atasnya menampilkan penanda
"Demo data sintetis".
