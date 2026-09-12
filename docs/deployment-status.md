# Status Deployment

> Dokumen ini riwayat deploy, kredensial, dan catatan per sesi. Untuk status
> ringkas per komponen beserta apa yang belum diverifikasi, lihat
> [progress.md](progress.md).

---

# 🟢 MULAI DARI SINI — serah-terima sesi, 12 September 2026 (sesi kelima)

**Ditulis khusus untuk sesi berikutnya di komputer lain.** Riwayat chat tidak
ikut ter-clone; yang ada cuma repo ini. Baca blok ini lebih dulu, baru
`docs/progress.md`.

## Ringkas: apa yang terjadi di sesi ini (12 September 2026)

**Tidak ada PR terbuka. Tidak ada bug production terbuka.** Empat PR
di-merge hari ini, semuanya sudah diverifikasi terhadap production:

| PR | Isi | Bukti |
|---|---|---|
| [#10](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/10) | User-Agent Wikimedia + teruskan badan respons 403 | `/metrics/collect` dari Render: `502` → `200` dalam ~90 detik, payload identik |
| [#11](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/11) | Dokumentasi penutupan bug 403 | — |
| [#12](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/12) | Sidebar berkelompok + pulihkan URL sumber dari guid feed | Bundel CSS Vercel yang sungguh dilayani; 3 item uji lewat `/signals/ingest` ke Render; halaman `/sinyal` dirender sungguhan |
| [#13](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/13) | Dokumentasi PR #12 | — |

**Dua hal yang paling penting dibawa ke sesi berikutnya**, karena keduanya
mengoreksi kesimpulan yang sebelumnya dianggap benar:

1. **"IP datacenter Render diblokir Wikimedia" itu KELIRU.** Yang salah cuma
   User-Agent-nya. Cara kekeliruannya terjadi juga penting: tabel
   penyelidikannya memvariasikan UA tapi mengukur semuanya dari **satu** IP,
   lalu menarik kesimpulan untuk IP yang lain. Pelajaran umumnya: **menguji
   konektor dari mesin lokal tidak membuktikan konektor itu jalan dari
   production.**
2. **URL item RSS lama tidak pernah hilang — ia ada di kolom sebelah.**
   Keempat feed yang dipakai proyek riset pengguna menulis `<guid>` yang
   persis sama dengan `<link>`, dan `rss.py` menyimpannya ke `external_id`
   sejak awal. Yang tampil "tidak ada URL sumber" sebenarnya bisa dipulihkan
   tanpa menebak apa pun.

Urutan kejadiannya: merge #10 → tunggu Render redeploy → `collect` berhasil →
verifikasi lanjutan (idempotensi, konektor Open-Meteo, rantai collect →
forecast) → dokumentasi (#11) → permintaan pengguna soal sidebar + link
"Sumber asli" → periksa keempat feed RSS aslinya → #12 → verifikasi terhadap
production setelah Render/Vercel redeploy → dokumentasi (#13).

## Keadaan sekarang

**`main` sudah di-merge dan sudah hidup di production.** [PR #9](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/9)
(tema terang + dua konektor deret waktu) di-merge 2026-09-11 16:17 UTC, lalu
**diverifikasi benar-benar tayang**, bukan diasumsikan:

- **Vercel** — diperiksa dari bundel CSS yang sungguh dilayani:
  `--ink:#EDF1F6`, `--panel:#FFFFFF`, `--survey:#0B6FD4` ada; blok
  `[data-theme=dark]` beserta `--ink:#0A1017`/`--survey:#4DA3FF` juga ada
  (tema gelap tetap bisa dipilih); skrip boot `localStorage.getItem("pop-theme")`
  ada di HTML; kelas `.auth-wrap`/`.theme-btn`/`.form-err` ada.
- **Render** — `/v1/metrics/connectors` berubah dari `404` ke `401`, lalu
  dengan akun test membalas kedua konektor lengkap dengan `notes`-nya.

Situs sekarang **bertema terang** dengan tombol Gelap/Terang di bar atas tiap
halaman dashboard, dan punya halaman ke-18: `/deret`.

## ✅ Bug 403 Wikimedia — SELESAI 2026-09-12

`POST /projects/{id}/metrics/collect` dari Render dulu **gagal 502** dengan
`"Wikimedia menolak permintaan (403)"`. [PR #10](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/10)
di-merge 2026-09-12 15:41 UTC dan **memperbaikinya**. Bukti diambil dari
production, bukan dari tes:

| Waktu (UTC) | Build di Render | Hasil `POST /metrics/collect` |
|---|---|---|
| 15:42 | UA lama (sebelum redeploy) | `502` — `"Wikimedia menolak permintaan (403)"` |
| 15:43 | UA baru (setelah redeploy) | **`200`** — `fetched: 30, stored: 30` |

Dua panggilan itu berjarak ~90 detik, dari akun, project, dan payload yang
sama persis. Satu-satunya yang berubah adalah build-nya.

**Hipotesis "IP datacenter Render diblokir" ternyata KELIRU** — dan ini yang
perlu diingat supaya tidak diselidiki ulang. IP Render tidak diblokir: IP yang
sama berhasil begitu User-Agent-nya memuat titik kontak yang bisa dibuka. Yang
terjadi: **UA lama (`contact via platform admin` — bukan kontak apa pun)
diterima dari IP rumahan tapi ditolak dari IP datacenter.** Jadi kebijakan UA
Wikimedia ditegakkan lebih ketat terhadap IP datacenter, bukan diblokir buta.
Pelajaran umumnya: **menguji konektor dari mesin lokal saja tidak membuktikan
konektor itu jalan dari production.**

**Yang masih belum terbukti di lapangan:** perbaikan kedua PR #10 —
meneruskan badan respons Wikimedia apa adanya ke pesan error — belum pernah
terpakai sungguhan, karena setelah UA diperbaiki tidak ada 403 lagi untuk
diteruskan. Jalur itu ada tesnya, tapi belum pernah dipicu production.

**Verifikasi lanjutan yang ikut lolos di sesi yang sama** (semua dari Render
production, akun test yang didaftarkan sendiri lewat `/v1/auth/register`):

- `GET /projects/{id}/metrics` → deret tersimpan benar di Postgres:
  30 observasi, `latest_value: 1207.0`, `is_national: true`.
- `collect` dipanggil **dua kali** → panggilan kedua `stored: 0, replaced: 30`.
  Deret di-*replace*, bukan diduplikasi — idempoten seperti didesain.
- Konektor kedua, `openmeteo_air_quality` (`province_code: 31`) → `200`,
  30 titik PM2.5 DKI Jakarta. **Pertama kalinya konektor ini terbukti jalan
  dari Render**; sebelumnya seluruh jalur `collect` tertutup 403 di atas.
- `GET /forecast/baseline?metric=pageviews_prabowo_subianto` → `200`,
  `insufficient_data: false`, model state-space ter-*fit* dari 30 titik itu,
  lengkap dengan `limitations` yang benar (horizon 90 hari ditandai
  ekstrapolasi karena riwayatnya cuma 29 hari). **Rantai penuh
  collect → Postgres → forecast terbukti dari production**, bukan cuma dari
  Postgres lokal seperti verifikasi 2026-09-11.

Project uji yang dibuat untuk verifikasi ini sudah dihapus dari production
(`DELETE` → 204, `GET` sesudahnya → 404).

## Navigasi dikelompokkan + URL sumber dipulihkan (PR #12, 2026-09-12)

Dua permintaan pengguna setelah melihat mockup Command Center.

**Sidebar** — 17 rute datar jadi empat kelompok: Pengukuran · Sinyal ·
Prediksi · AI & Tata Kelola. Dikelompokkan menurut **apa yang diukur**, bukan
menurut fase pembangunan seperti urutan lama. Jaringan Interaksi karena itu
masuk "Sinyal" walau dibangun di Phase 3 — ia mendeskripsikan siapa membalas
siapa pada data yang ada, tidak memproyeksikan apa pun.

Ikutan yang tidak bisa dipisah: label disamakan dengan mockup, **kicker tiap
halaman ikut diubah** (kalau tidak, satu modul bernama dua), rujukan antar
halaman yang menyebut menu lama diperbarui, dan link footer "Current Trending
Categories" — placeholder yang salah — jadi "Ganti proyek →". Status aktif
akhirnya menyala: `.nav-on` sudah lama ada di `globals.css` tapi tak pernah
terpakai karena layout server component tidak tahu pathname; nav dipindah ke
komponen klien `SideNav`. Padding butir `8px → 6px` karena empat judul
kelompok menambah ~116px. Terukur di peramban: **sidebar penuh butuh 909px**
dan muat tanpa scroll di viewport ≥ itu.

**URL sumber item RSS lama** — baris yang tampil "tidak ada URL sumber"
ternyata URL-nya ada di baris yang sama, di kolom sebelah. Keempat feed yang
dipakai proyek riset pengguna menulis `<guid>` PERSIS sama dengan `<link>`,
diperiksa langsung terhadap feed aslinya 2026-09-12:

| Outlet | `guid` == `link` == URL artikel |
|---|---|
| Antara | ya |
| CNBC Indonesia | ya |
| Republika | ya |
| Sindonews | ya |

`connectors/rss.py` menyimpan guid itu ke `external_id` sejak awal; kolom
`url` baru ada 2026-09-11. `_recover_source_url()` memulihkannya.

**Batas yang menjaga ini tetap pemulihan, bukan tebakan** (dan ada tesnya):
hanya URL absolut `http(s)` yang dipakai — tidak ada yang dirangkai, ditempel
ke domain, atau dicarikan padanan; guid yang bukan URL (id numerik, `tag:`
URI, handle akun) tetap menghasilkan "tidak ada URL sumber"; dan kolom `url`
selalu menang kalau terisi. Ini mengikuti aturan yang sudah tertulis di
docstring endpoint-nya: *"jangan ditebak dari field lain."*

Asalnya dibawa keluar sebagai `source_url_origin` dan **ditandai di UI**
("dari guid feed"), tidak disamarkan jadi seolah tersimpan. **Sengaja tidak
di-backfill** ke tabel: menulis ulang kolom `url` pada data riset yang sudah
ada tidak bisa dibatalkan tanpa jejak, dan hasilnya sama saja dengan
menghitungnya saat baca. Kalau backfill nanti diinginkan, fungsi itu
acuannya.

Satu bug ketahuan dari melihat langsung di peramban, bukan dari tes: `.note`
itu `display:flex`, jadi span penanda yang disisipkan di tengah teks jadi
flex item tersendiri dan terperas jadi kolom sempit. Sudah diperbaiki.

**Diverifikasi terhadap production setelah merge, bukan diasumsikan:**

- **Vercel** — diperiksa dari bundel CSS yang sungguh dilayani: `.nav-grp`,
  `.nav-grp-t`, `padding:6px 9px`, dan `.nav-on` semuanya ada.
- **Render** — tiga item uji diingest lewat `POST /signals/ingest` sungguhan
  ke production, dan ketiga cabang `_recover_source_url` berperilaku persis
  seperti dirancang:

  | Item uji | `url` | `source_url_origin` | Tampil di UI |
  |---|---|---|---|
  | guid = permalink artikel | `null` | `guid_feed` | "Buka sumber ↗" + penanda `dari guid feed` |
  | guid bukan URL | `null` | `null` | "tidak ada URL sumber" |
  | `url` tersimpan sejak ingest | terisi | `kolom_url` | "Buka sumber ↗" tanpa penanda |

- **Tampilan** diperiksa dengan merender halaman `/sinyal` sungguhan terhadap
  API production itu — bukan cuma respons JSON-nya. Ketiga baris tampil benar
  dan catatan kakinya mengalir sebagai satu paragraf.

Project uji sudah dihapus (`DELETE` → 204, `GET` sesudahnya → 404).

## Langkah pertama sesi berikutnya

1. **Tidak ada bug production terbuka.** Mulai langsung dari daftar di bawah.
2. **Keputusan yang menunggu pengguna, bukan wewenang agen**: `SignalSource`
   untuk pengukuran instrumen. Kualitas udara sementara memakai `DIGITAL`
   dengan peringatan di kolom `method`. Yang benar adalah nilai enum baru
   (mis. `SENSOR`), tapi itu butuh `ALTER TYPE signal_source ADD VALUE` di
   Supabase — kelas migrasi yang menjatuhkan tiga halaman production pada
   2026-09-02. Jangan dilakukan diam-diam.
3. **`ANTHROPIC_API_KEY` di Render** — Executive Brief dan Copilot masih
   satu-satunya bagian yang kodenya live tapi belum pernah menghasilkan
   jawaban sungguhan. Sengaja ditaruh paling akhir atas instruksi pengguna.
4. Sisanya lihat "Langkah berikutnya yang paling masuk akal" di
   `docs/progress.md`.

**Yang bisa dikerjakan tanpa menunggu keputusan siapa pun**, kalau pengguna
tidak menyebut prioritas lain:

- **Backfill kolom `url`** dari `external_id` untuk item RSS lama, kalau
  pengguna memang menginginkannya. Sengaja TIDAK dilakukan di PR #12 —
  alasannya di bagian PR #12 di atas. `_recover_source_url()` sudah jadi
  acuannya, tinggal dijalankan sebagai migrasi sekali jalan.
- **Jalur `POST /signals/sources/{id}/collect` untuk RSS** — satu-satunya
  jalur konektor yang belum pernah dipicu dari Render sendiri (`ingest`
  manual sudah teruji). Sekarang risikonya lebih kecil dari yang dikira:
  jaringan keluar Render → penerbit pihak ketiga sudah terbukti lewat
  Wikimedia dan Open-Meteo. Kalau gagal 403, **curigai User-Agent lebih
  dulu**, jangan langsung menyimpulkan IP-nya diblokir (lihat pelajaran
  nomor 1 di kepala dokumen).

## Yang TIDAK perlu dikhawatirkan

- **Tidak ada migrasi tertunda.** PR #9, #10, dan #12 sama-sama nol perubahan
  di `db/`. `main.py` cuma bertambah dua baris pendaftaran router (#9); #10
  cuma menyentuh satu file konektor (`app/connectors/wikipedia.py`); #12
  menambah satu fungsi murni + dua field respons di `routers/signals.py` dan
  tidak menyentuh `models/` maupun `services/`. **Pemulihan URL dihitung saat
  baca, nol tulisan ke tabel.**
- **Data dua project riset pengguna aman.** `KEBAKARAN HUTAN` (157 item) dan
  `MBG AGUSTUS 2026` ada di tabel `mentions`; fitur baru menulis ke
  `metric_snapshots`. Tidak ada jalur baru yang menyentuh `mentions`.
- **Routine harian MBG tetap jalan** sampai 19 September — ia memakai
  `POST /signals/ingest` yang tidak disentuh sesi ini.
- Proyek uji yang dibuat di production selama verifikasi **sudah dihapus**
  (`DELETE` → 204, dikonfirmasi 404).

## Cara menjalankan tes lokal tanpa Docker

Temuan sesi ini: **Docker tidak dibutuhkan** — Postgres 16 sudah terpasang
lewat Homebrew di mesin pengguna dan berjalan di port 5432. Asumsi
"butuh Docker" di sesi-sesi sebelumnya keliru. Dua hal yang perlu diketahui
kalau menyiapkannya lagi:

- `db/schema.sql` baris 8 butuh extension `vector` (pgvector). Tanpa itu,
  `mentions` dan `topics` tidak terbuat dan blok RLS-nya ikut batal
  seluruhnya (blok `DO $$` gagal utuh, bukan sebagian).
- Role `pop` perlu atribut `BYPASSRLS` supaya fungsi `SECURITY DEFINER`
  (`auth_register`) bisa menembus `FORCE ROW LEVEL SECURITY`. Di CI ini
  tidak terlihat karena `pop` adalah superuser kontainer.

Database `pop_test` dan role `pop`/`pop_app` yang dipakai verifikasi sesi
ini **sudah dihapus lagi**; mesin pengguna bersih.

---

Ditulis 2026-08-20 setelah sesi verifikasi end-to-end + deploy pertama.
Update 2026-08-24 (sesi panjang, 11 commit ke main): CORS_ORIGINS
diselesaikan, slider bobot Opinion Index diverifikasi live, gerbang
`SITE_PASSWORD` didokumentasikan, login user asli dibangun (menggantikan
`DEMO_ACCESS_TOKEN`), bug RLS di `/auth/login|register|refresh`
diperbaiki, Phase 1 dikeraskan (`ruff`+`mypy` bersih 100%, CI hijau di
GitHub Actions), lalu **semua 9/9 halaman dashboard** di-port ke Next.js
dengan data asli — 5 halaman data (Consistency/Segments/Narrative/Geo/
Forecast) plus Executive Brief (fitur AI generatif pertama di proyek ini,
LLM + `AIEnvelope` + `ai_outputs`) dan AI Governance. **Executive Brief
kodenya sudah live tapi generate sungguhan BELUM diverifikasi** — nunggu
`ANTHROPIC_API_KEY` aktif di Render (lihat bagian paling bawah untuk
detail & langkah verifikasi lanjutan). Dokumen ini adalah sumber
kebenaran untuk sesi berikutnya — jangan andalkan riwayat chat, chat
lama tidak ikut ter-clone.
Update 2026-08-27: item pertama Phase 3 dikerjakan — **Polarization Index**
(`GET /projects/{id}/risk/polarization`, kartu baru di halaman `/segments`),
dihitung penuh dari data segments Phase 1, bukan data reka-reka. Opinion
Risk Score (skor gabungan 9 komponen) sengaja belum diekspos — lihat bagian
"Polarization Index" di bawah untuk alasannya. Diverifikasi end-to-end di
Postgres Docker lokal, **belum di-push/di-deploy ke production**.
Update 2026-09-01 (sesi panjang, "kerjakan semua yang belum"): **Phase 2 dan
Phase 3 sebagian besar dikerjakan** — konektor modular, pipeline ingestion,
sentiment Indonesia + set evaluasi, topic discovery, AI Copilot RAG, forecast
state-space yang benar-benar di-fit, Opinion Risk Score, influence estimate,
dan Communication Impact (DiD). Backend 115 → 387 tes, enam halaman frontend
baru. **Phase 4 sengaja tidak disentuh** — butuh keputusan penyedia SSO,
penyedia pembayaran, dan komitmen kontrak API publik yang bukan wewenang
agen. Baca bagian "Phase 2 + Phase 3 dikerjakan" di bawah, terutama
sub-bagian "Yang BELUM diverifikasi", sebelum mengklaim apa pun ke pengguna.
Update 2026-09-02 (sesi lanjutan, "kerjakan semua yang belum selesai"):
menutup residual yang tercatat sesi 2026-09-01 — Command Center sekarang
menarik "Isu publik" dan "Peringatan aktif" sungguhan (`services/alerts.py`
baru), verifikasi manusia atas label tema (`topics.review_status`), dan dua
fitur Phase 3 yang sebelumnya sengaja belum ada: **synthetic control**
(alternatif DiD untuk Communication Impact) dan **graf jaringan interaksi**
dari relasi balasan/kutipan X (`services/network.py`, halaman `/jaringan`
baru). Backend 387 → 473 tes. PR #1 (branch
`claude/repo-ini-comparison-ior2z4`, CI hijau) **sudah di-merge ke `main`**
atas persetujuan eksplisit pengguna — Render + Vercel akan redeploy dari
`main` secara otomatis, tapi **migrasi kolom baru ke Supabase (lihat di
bawah) masih perlu langkah manual terpisah** sebelum fitur review label
atau `/jaringan` benar-benar jalan di production. Baca bagian
"Sesi lanjutan Phase 2/3" di bawah.
Update 2026-09-02 (sesi kedua hari yang sama): migrasi Supabase dan
`ANTHROPIC_API_KEY`/`YOUTUBE_API_KEY`/`X_BEARER_TOKEN` di Render masih
menunggu pengguna (butuh kredensial production yang tidak ada di sandbox
agen). Sambil menunggu, dikerjakan yang genuinely bisa tanpa kredensial itu:
konektor RSS ditarik terhadap 5 feed media Indonesia SUNGGUHAN untuk
pertama kalinya (215 item nyata, di luar Postgres/Render — lihat bagian
"Verifikasi RSS sungguhan" di bawah), dan dari situ ketemu + diperbaiki satu
bug leksikon sentimen nyata ("asal" salah dibaca negatif). Phase 4 sengaja
tidak disentuh, sesuai instruksi eksplisit pengguna sesi ini. **PR #2
(fix leksikon) sudah di-merge ke `main`** atas persetujuan eksplisit
pengguna, CI mengonfirmasi 474 tes lulus (lihat bagian "Verifikasi RSS
sungguhan" untuk detail).
Update 2026-09-02 (sesi ketiga hari yang sama — **insiden produksi nyata**):
pengguna melaporkan `/command` menampilkan "Application error: a
server-side exception has occurred" di production, tepat setelah PR #1
redeploy. Akar masalah dikonfirmasi & direproduksi persis secara lokal
(lihat bagian "Fix crash Command Center" di bawah): `GET /topics` dan
`GET /network` butuh kolom yang migrasinya ke Supabase memang belum
diterapkan (dicatat sejak sesi PR #1) — itu gagal 500 di backend, bukan
404, dan `apiOrNull()` di frontend cuma menangkap 404 sehingga error lolos
dan menjatuhkan SELURUH halaman `/command`, `/tema`, dan `/jaringan`.
**PR #4** (mitigasi frontend, `apiOrNullLenient()`) dibuka, CI hijau,
**belum di-merge** — menunggu persetujuan pengguna. **PR #3** (gitignore,
trivial) juga masih terbuka dari sesi sebelumnya, belum di-merge. SQL
migrasi Supabase yang sesungguhnya (perbaikan akar masalah, bukan cuma
mitigasi) sudah disiapkan lengkap di deskripsi PR #4 — masih tugas
pengguna sendiri, butuh kredensial Supabase.

**Update sesi keempat (masih 2026-09-02): kedua PR sudah di-merge**, atas
persetujuan eksplisit pengguna — lihat bagian "Fix crash Command
Center/Tema/Jaringan" di bawah untuk detail merge dan apa yang masih
tersisa (migrasi Supabase).

**Update 2026-09-11 (sesi verifikasi production, dipicu email peringatan
auto-pause Supabase)**: item #1 dari "Langkah berikutnya" di
`docs/progress.md` akhirnya dikerjakan — **migrasi kolom Supabase yang sejak
2026-09-02 cuma "sudah dijalankan tapi belum diverifikasi live" sekarang
dikonfirmasi bekerja di production**, lewat jalur yang sebelumnya selalu
terhalang gerbang `SITE_PASSWORD` (di luar wewenang agen): API backend
publik (`pop-api-ptug.onrender.com`) tidak ikut di-gate — cuma frontend
Next.js yang di-gate — jadi verifikasi dilakukan langsung ke API dengan
akun test yang didaftarkan sendiri lewat `/v1/auth/register` (bukan akun
demo pengguna, tidak butuh kredensial siapa pun). Lihat bagian
"Verifikasi production 2026-09-11" di bawah untuk detail lengkap. Project
test dan datanya **sudah dihapus** setelah verifikasi (`DELETE
/v1/projects/{id}` → 204) — production bersih kembali, cuma tersisa satu
org kosong (`verif-prod-20260911@example.com`) yang tidak punya endpoint
penghapusan sendiri di API ini.

Sesi yang sama juga menutup sebagian item #3 ("ukur ulang akurasi
sentimen"): 445 item nyata (naik dari 385) dari 7 feed RSS, satu bug
leksikon baru ditemukan+diperbaiki (`hebat`, pola sama seperti `asal`) —
lihat "Verifikasi production 2026-09-11" untuk detail dan kenapa `manfaat`
SENGAJA tidak ikut diperbaiki meski juga ditemukan salah pada 1/7 kasus.

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
  **UI-nya dibangun 2026-08-27 — lihat bagian "Registrasi self-service" di
  bawah untuk kenapa itu ternyata bukan sekadar tambah form.**
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

## ✅ 5 dari 7 halaman dashboard sisa — selesai 2026-08-24

Batch pertama porting dari prototipe statis (`design-reference/`) ke
Next.js: **Signal Consistency, Public Segments, Narrative Map, Geographic
Map, Forecast & Simulator**. Semua pakai data asli yang sudah di-seed di
Supabase (6 segments, 4 narratives, 48 metric_snapshots per-provinsi) —
bukan data sintetis prototipe (`design-reference/README.md` sendiri
melarang menyalin data prototipe).

Backend baru: `GET /projects/{id}/segments`, `GET /projects/{id}/narratives`,
`GET /projects/{id}/opinion/geo` (agregasi per provinsi). `POST
/forecast/what-if` dan `GET /opinion/divergence` sudah ada sebelumnya,
tinggal dipakai. Model SQLAlchemy `Narrative` baru ditambah ke
`app/models/measurement.py` (tabel `narratives` sendiri sudah ada dari
schema.sql awal, cuma belum ada mapping-nya).

**Diverifikasi live di production** (bukan cuma lolos build) — termasuk
lewat interaksi nyata di browser, bukan cuma render awal:
- Consistency: 4 penjelasan (`explanations`) yang tampil adalah hasil
  komputasi `services/divergence.py` sungguhan, bukan teks statis
  prototipe.
- Segments: 6 segmen dari seed tampil terurut benar, klik memilih narasi
  di Narrative Map diverifikasi mengubah panel detail (state React jalan).
- **Geo membuktikan gating publikasi CLAUDE.md §3 jalan otomatis dari
  data asli**: 8 dari 16 provinsi (yang share populasinya kecil, jadi
  `effective_n` hasil hitung asli jatuh di bawah 250) tampil "data tidak
  cukup" tanpa perlu skenario buatan — bukan cuma lolos tes unit dengan
  data rekayasa.
- Forecast: slider "Kenaikan harga pangan" ke 6% memicu Server Action
  sungguhan ke `/forecast/what-if`, hasilnya bergeser dari 67.3 ke 63
  (cocok dengan koefisien asli -0.72/% di `services/forecast.py`), bukan
  angka statis.
- Satu bug kosmetik ketahuan & diperbaiki lewat verifikasi ini:
  `Decimal` di `SegmentOut`/`NarrativeOut` ter-serialize JSON sebagai
  string presisi-tetap ("24.00" bukan "24"), diganti ke `float`.

Dua field dari prototipe SENGAJA tidak dipindahkan (bukan lupa) — tidak
ada data nyata yang mendukungnya: "isu teratas" & "perubahan periode" di
Geo (metric_snapshots per provinsi cuma simpan satu periode), dan
"volatilitas" di Segments.

Tes baru: `apps/api/tests/test_dashboard_reads.py` — 4 tes end-to-end HTTP
asli (role `pop_app`, RLS aktif), termasuk kasus inti gating publikasi
provinsi n-rendah.

**2 halaman sisa (Executive Brief, AI Governance) sengaja di luar batch
ini** — beda kelas pekerjaan, butuh keputusan yang belum ditanyakan ke
pengguna: Brief perlu narasi AI-generated (`AIEnvelope` + tulis ke
`ai_outputs`, backend `copilot` masih stub 501/Phase 2); Governance
sebagian bisa dibangun sekarang (Data Quality Score dari
`data_quality_scores` yang sudah seeded) tapi tabel "Jejak keputusan
model AI"-nya kosong sampai ada fitur yang benar-benar menulis ke
`ai_outputs` — terkait langsung dengan keputusan Brief.

## ⚠️ Executive Brief (AI generatif) — kode selesai, generate BELUM diverifikasi live

Fitur AI generatif pertama di proyek ini. User eksplisit minta dibangun
beneran (bukan versi data-saja) — lihat riwayat sesi. Infrastrukturnya
(`app/ai/prompts.py:EXECUTIVE_BRIEF`, `app/ai/agents.py`) sudah ada dari
awal proyek, belum pernah dipakai; sesi ini menambah agent konkret
(`app/ai/brief.py:ExecutiveBriefAgent`), router (`app/routers/brief.py`),
dan 2 halaman baru (`/brief`, `/governance`) — **9/9 halaman dashboard
sekarang lengkap**, definisi selesai Phase 1 di `docs/roadmap.md` tercapai
penuh.

**Bug dorman yang dicurigai sejak 2026-08-20 dikonfirmasi & diperbaiki**:
`AIOutput.confidence`/`human_review` memang punya bug pemetaan yang sama
seperti `MetricSnapshot.source` dulu — `String` biasa padahal kolomnya
`confidence_band`/`review_status` (enum Postgres native). Diperbaiki
dengan pola yang sama (enum lokal + `SAEnum(..., create_type=False)`).
Migrasi **tidak diperlukan** — kolom DB-nya dari awal sudah benar
(`db/schema.sql`), cuma mapping SQLAlchemy-nya yang salah.

**Yang sudah diverifikasi live**: `/brief` menampilkan CTA "Buat
ringkasan" dengan benar (404 ditangani, bukan error), `/governance`
menampilkan Data Quality Score asli dari seed + "belum ada keluaran AI"
yang jujur (bukan bug — memang belum ada yang generate).

**Yang BELUM diverifikasi live**: generate Executive Brief sungguhan.
`get_provider()` (`app/ai/provider.py`) butuh `LLM_PROVIDER=anthropic` +
`ANTHROPIC_API_KEY` valid di Render — kalau belum di-set, endpoint
`POST .../brief/generate` akan balas `503` dengan pesan jelas (bukan
gagal senyap, sudah ditest). **Langkah lanjutan untuk sesi berikutnya**:
1. Konfirmasi `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` aktif di
   Render → pop-api → Environment (tanya user, jangan generate ulang
   API key yang sudah aktif tanpa tanya — sama aturan kredensial seperti
   di bagian atas dokumen ini).
2. Login ke `/brief`, klik "Buat Ringkasan", verifikasi 6 bagian terisi
   masuk akal dan TIDAK memuat klaim yang tidak ada di fakta yang dikirim
   (baca `apps/api/app/routers/brief.py:_gather_facts` untuk tahu fakta
   apa saja yang dikirim — sengaja TIDAK ada klaim delta index spesifik,
   cuma satu periode snapshot yang ada).
3. Approve, cek `/governance` menampilkan baris audit yang baru dibuat.

## ✅ Polarization Index (Phase 3, sebagian) — selesai 2026-08-27

Item pertama dari Phase 3 yang benar-benar dikerjakan. Dipilih karena satu-
satunya bagian Opinion Risk Score (`services/risk.py` — sudah ada & diuji
sejak awal proyek, `tests/test_risk.py` sudah lulus dari dulu, cuma belum
pernah punya router) yang seluruh datanya sudah nyata: `polarization()` cuma
butuh (nama, sentiment, size_pct) per segmen, dan itu sudah ada dari Phase 1
(`segments`, sudah di-seed sejak 2026-08-24).

**Sengaja TIDAK mengerjakan Opinion Risk Score penuh** (9 komponen
berbobot). 5 dari 9 komponennya — `issue_growth`, `influencer_amplification`,
`media_escalation`, `trust_decline`, `approval_decline` — butuh sinyal yang
belum ada: konektor sosial, jaringan influencer, deret waktu tren (Phase 2/3
yang belum dimulai, lihat `docs/roadmap.md`). Mengisi komponen itu dengan
angka reka-reka supaya skornya "lengkap" melanggar CLAUDE.md §3 — semangat
yang sama dengan keputusan sengaja tidak merender "Isu publik" & "Peringatan
aktif" di Command Center. Endpoint risk-score menyusul begitu komponennya
nyata.

Baru: `GET /projects/{id}/risk/polarization` (`app/routers/risk.py`) — baca
`segments`, buang yang `sentiment`-nya NULL (tidak diikutkan sebagai posisi
0 palsu — itu akan diam-diam menyuntikkan sikap "netral" yang tidak pernah
diukur), panggil `services/risk.py:polarization()` yang sudah ada. <2 segmen
bersentimen terukur → `insufficient_data: true` (pola sama dengan gating
n<250 di `/opinion/geo`), bukan skor dari data yang terlalu tipis.
Ditampilkan sebagai kartu "Polarization Index" di halaman `/segments`
(warna ikut `state`: hijau "menuju konsensus", kuning "terfragmentasi",
merah "terpolarisasi").

**Diverifikasi live end-to-end** (bukan cuma lolos tes) — Postgres Docker
lokal (belum ke Supabase, lihat catatan di bawah): daftar org+project baru
lewat `/v1/auth/register` asli, insert 6 segmen dengan angka sama persis
seperti `db/seed.py:SEGMENTS`, panggil endpoint lewat curl (skor 45,
"terfragmentasi" — cocok hitungan manual), lalu jalur penuh lewat browser:
gerbang `SITE_PASSWORD` → login `/masuk` → `/segments` → kartu Polarization
Index tampil benar dengan 6 segmen, skor, state, dan batasan yang benar.

Bug kecil ketahuan & diperbaiki di sesi ini: `email-validator` ada di
`requirements.txt` tapi hilang dari `[project.dependencies]` di
`pyproject.toml` (komentar `requirements.txt` sendiri bilang "dihasilkan
dari pyproject.toml" — jadi ini penyimpangan, bukan disengaja). Tidak
mempengaruhi CI/Render (keduanya install dari `requirements.txt` langsung),
cuma bikin `pip install -e ".[dev]"` lokal gagal import di semua tes
berbasis router (auth, brief, dashboard_reads) — baru ketahuan sesi ini
karena baru sekarang ada yang coba `pip install -e .` dari nol. Diperbaiki
dengan menambah entrinya ke `pyproject.toml`.

Kejanggalan kecil lain ketahuan saat mengerjakan ini: `docs/roadmap.md`
Phase 1 sempat mencentang "Risk score + Polarization endpoint" sebagai
selesai padahal endpoint-nya belum pernah ada (cuma fungsi service-nya) —
sudah diperbaiki jadi mencerminkan kondisi sebenarnya sebelum & sesudah
sesi ini.

Tes baru (4x) di `apps/api/tests/test_dashboard_reads.py`: kosong →
insufficient, 1 segmen → insufficient, 2 kutub dari data DB asli → skor &
state benar, segmen tanpa sentimen diabaikan dari perhitungan (bukan
dianggap 0). `ruff check app tests`, `mypy app/services app/ai`, dan
`npm run typecheck` + `next build` semuanya tetap bersih 100%.

~~**Belum diverifikasi di Supabase produksi** — perubahan ini belum di-push/
di-deploy~~ — **koreksi 2026-09-01**: commit `a27581a` ternyata SUDAH ada di
`origin/main` (dicek dengan `git rev-parse origin/main`; kalimat di atas
ditulis sebelum push di akhir sesi yang sama dan tidak pernah diperbarui
sesudahnya). Yang masih benar: verifikasi manual di browser terhadap Supabase
produksi belum dilakukan, baru di Postgres lokal.

## ✅ Registrasi self-service (`/daftar`) — selesai 2026-08-27

Diminta sebagai "item termudah" dari daftar residual Phase 1 — endpoint
`/auth/register` sudah ada+teruji sejak 2026-08-24, tinggal butuh form.
**Ternyata bukan sekadar tambah form**: SEMUA 9 halaman dashboard
hardcode `process.env.DEMO_PROJECT_ID` di server component-nya
masing-masing — tidak ada UI pemilihan/pembuatan proyek sama sekali,
padahal backend-nya (`GET/POST/PATCH/DELETE /projects`) sudah lengkap
sejak awal. Org yang baru daftar otomatis nol proyek (`auth_register()`
di `db/rls.sql` cuma bikin organizations+users, bukan projects), jadi
kalau langsung diarahkan ke `/command` dia akan mendarat di dashboard
yang mengambil data proyek ORG LAIN (RLS mengosongkan semuanya) —
ditemukan dengan benar-benar mendaftar lewat browser, bukan dari baca
kode. Ditanyakan dulu ke pengguna sebelum lanjut (3 opsi: perluas scope,
batalkan, atau ship apa adanya) — dipilih **perluas scope**.

**Yang dibangun:**
- `app/daftar/page.tsx` + `app/api/session/register/route.ts` — form
  (nama organisasi, slug dengan auto-slugify dari nama, nama lengkap,
  email, password), validasi klien cermin persis
  `schemas/auth.py:RegisterRequest`. Link silang dengan `/masuk`.
- `app/proyek-baru/page.tsx` + `actions.ts` — halaman berdiri sendiri
  (di luar `(dashboard)/layout.tsx`, sengaja: layout itu sendiri butuh
  proyek aktif untuk dirender) yang membuat proyek pertama lewat
  `POST /projects` yang sudah ada, lalu set cookie `pop_project_id`.
- `lib/currentProject.ts` (baru) — `getCurrentProjectId()`/
  `getCurrentProject()`, baca cookie `pop_project_id` kalau ada, fallback
  ke `DEMO_PROJECT_ID` kalau tidak (user demo lama TIDAK terpengaruh sama
  sekali — cookie itu belum pernah diset untuk mereka). **Kesembilan
  halaman dashboard + layout.tsx diganti dari
  `process.env.DEMO_PROJECT_ID!` langsung ke helper ini.**
- `PageHeader.tsx` dapat prop `isDemo` baru — sebelumnya SETIAP halaman
  hardcode judul `"Persepsi Kebijakan Nasional 2026"` dan badge
  `"Data demo sintetis"` apa pun proyeknya. Ketemu pas verifikasi live:
  proyek baru yang asli (non-demo) tetap diberi label "Demo data
  sintetis" — pelanggaran R1 (sumber data harus jujur), bukan cuma
  kosmetik. Sekarang `title`/`isDemo` diisi dari `project.name`/
  `project.is_demo` asli lewat `getCurrentProject()`.
- **Bug kelas baru ketemu & diperbaiki**: 3 halaman (`command`,
  `consistency`, `forecast`, plus `opinion-index`) memanggil
  `/opinion/index` atau `/opinion/divergence` tanpa `try/catch` — kedua
  endpoint itu melempar `404` (bukan `insufficient_data:true`) kalau
  proyek belum punya data dimensi/sinyal SAMA SEKALI. Sebelum proyek bisa
  dibuat lewat UI sendiri, ini tidak pernah kejadian (satu-satunya
  proyek yang ada selalu proyek demo yang di-seed penuh) — begitu
  `/proyek-baru` ada, SETIAP halaman itu langsung jatuh dengan
  "Application error" polos untuk proyek yang benar-benar kosong.
  Diperbaiki dengan `lib/api.ts:apiOrNull()` (baru, wrapper `api()` yang
  mengubah 404 jadi `null`) + tiap halaman merender `InsufficientData`
  yang sesuai alih-alih menjatuhkan Server Component.
- **Bug kedua ketemu & diperbaiki**: `api/session/logout/route.ts` cuma
  menghapus `pop_session`/`pop_refresh`, bukan `pop_project_id` —
  ketahuan pas mencoba login sebagai akun BERBEDA di browser yang sama
  setelah logout: akun kedua (yang punya proyeknya sendiri) malah
  mewarisi cookie proyek akun PERTAMA. RLS mencegah kebocoran DATA (akun
  kedua cuma dapat 404 dari proyek asing → `apiOrNull` → tampil "belum
  ada proyek"), tapi akibatnya akun yang sebenarnya punya proyek sendiri
  terlihat kosong keliru. Sudah diperbaiki, diverifikasi ulang: logout →
  login akun lain → proyeknya sendiri tampil benar.

**Diverifikasi end-to-end live di browser** (bukan cuma lolos tes),
mencakup dua akun berbeda di Postgres Docker lokal yang sama:
1. Daftar org baru → mendarat di "Buat Proyek Pertama" (bukan dashboard
   rusak) → buat proyek → `/command` menampilkan nama proyek asli +
   "Data proyek Anda sendiri" + semua kartu kosong menampilkan
   `InsufficientData` yang benar (bukan crash) di `/command`,
   `/opinion-index`, `/consistency`, `/forecast`, `/segments`, `/brief`.
2. Logout → login akun lain yang SUDAH punya proyek dengan data asli →
   proyeknya sendiri (nama + segments + Polarization Index) tampil
   benar, bukan tercemar cookie akun pertama.

`ruff check app tests`, `mypy app/services app/ai`, `pytest` (115 lulus,
tidak ada yang berubah di backend — perubahan sesi ini murni frontend),
`npm run typecheck`, dan `next build` semuanya bersih 100%.

**Deploy ke production dikonfirmasi 2026-08-27** — push memicu build
Vercel baru (`dpl_J3SETfbxuQEPe4RB7f7VkMQzHKDh`, alias
`public-opinion-platform.vercel.app` mengarah ke situ, output build
mencantumkan route `daftar`) dan CI GitHub Actions hijau penuh. **Belum
dicoba langsung di Supabase produksi** (login manual lewat gerbang
`SITE_PASSWORD` dibutuhkan, di luar kemampuan Claude — lihat aturan
boundary kredensial) — baru diverifikasi end-to-end di Postgres Docker
lokal seperti dijelaskan di atas.

**Batasan yang sengaja belum diselesaikan** (di luar cakupan permintaan
"item termudah"): belum ada halaman edit/hapus proyek meski endpoint
`PATCH`/`DELETE /projects/{id}` sudah ada. ~~Belum ada UI pilih-ganti
proyek~~ — **selesai sesi yang sama, lihat bagian "Project switcher" di
bawah** (ditulis sesudahnya, jadi urutannya kebalik — cek judul, bukan
urutan baca linear kalau bingung).

## ✅ Project switcher (`/proyek`) — selesai 2026-08-27

Kelanjutan langsung dari registrasi self-service di atas — begitu org
bisa punya lebih dari satu proyek (`/proyek-baru` bisa dipakai berkali-
kali, bukan cuma sekali di awal), jelas dibutuhkan UI pilih proyek aktif
mana yang mau dilihat, bukan cuma diset sekali dan macet di situ.

- `app/(dashboard)/proyek/page.tsx` — daftar semua proyek org (`GET
  /projects`, sudah ada sejak awal), baris yang aktif ditandai badge
  "Aktif", baris lain dapat tombol "Aktifkan". Link "+ Buat proyek baru"
  ke `/proyek-baru` (sekarang dipakai dua alur: org baru daftar nol
  proyek, ATAU org lama nambah proyek lain — copy halamannya diubah dari
  "Buat Proyek Pertama" ke "Buat Proyek Baru" supaya tidak salah konteks).
- `app/(dashboard)/proyek/actions.ts` — `activateProject(id)`, action
  ter-bind per baris (`activateProject.bind(null, p.id)`, pola form
  action Next.js untuk daftar dengan satu tombol per item, tanpa client
  component). Validasi ulang lewat `GET /projects/{id}` sebelum menyimpan
  cookie `pop_project_id` — bukan lubang keamanan kalau dilewati (RLS
  tetap menegakkan batas tenant), cuma supaya id yang keliru gagal jelas,
  bukan diam-diam tersimpan.
- Link "Ganti proyek" baru di sidebar (`(dashboard)/layout.tsx`), di
  bawah nama proyek aktif.

**Diverifikasi live end-to-end di browser**: dibuat proyek kedua untuk
org yang sudah punya satu (`Proyek Kedua Verif-Risk` lewat
`POST /projects`), buka `/proyek` → kedua proyek tampil, yang lama
ditandai "Aktif" → klik "Aktifkan" di proyek baru → redirect ke
`/command`, sidebar + semua kartu berubah ke proyek baru (kosong, benar)
→ balik ke `/proyek` → klik "Aktifkan" di proyek lama → data asli
(Polarization Index, 6 segmen) tampil kembali persis seperti semula,
bukan cache basi atau tercampur.

`npm run typecheck` dan `next build` bersih 100%. Backend tidak disentuh
sama sekali sesi ini (`pytest` 115 tetap lulus, dijalankan ulang untuk
memastikan). ~~**Belum di-push/di-deploy ke production.**~~ — **koreksi
2026-09-01**: `a0c2a61` sudah ada di `origin/main`, sama seperti koreksi di
bagian Polarization Index di atas.

## ✅ Edit/hapus proyek di `/proyek` — selesai 2026-08-27

Kelanjutan langsung dari project switcher di atas — endpoint `PATCH` dan
`DELETE /projects/{id}` sudah ada di backend sejak awal, tinggal butuh UI.

- `app/(dashboard)/proyek/ProjectRow.tsx` (client component baru) —
  setiap baris proyek sekarang punya tombol "Ubah nama" dan "Hapus" (di
  samping tombol Aktifkan/badge Aktif yang sudah ada). Proyek demo (`is_demo`)
  tetap read-only — tidak bisa diubah/dihapus.
- **Inline rename**: klik "Ubah nama" → nama jadi input teks → Enter atau
  "Simpan" memanggil `PATCH /projects/{id}` lewat server action
  `renameProject()` → Escape atau "Batal" membatalkan. Validasi sisi klien
  + pesan error dari backend ditampilkan di bawah baris.
- **Hapus dengan konfirmasi ganda**: klik "Hapus" → muncul "Ya, hapus" +
  "Batal" (bukan langsung hapus!) → "Ya, hapus" memanggil
  `DELETE /projects/{id}` lewat server action `deleteProject()`. Kalau proyek
  yang dihapus adalah proyek yang sedang aktif (cookie `pop_project_id`),
  cookie di-clear supaya fallback ke `DEMO_PROJECT_ID`.
- Backend `DELETE` butuh role `RESEARCH_DIRECTOR` — user demo punya role
  ini. Kalau user hanya `RESEARCHER`, backend akan menolak dan pesan error
  tampil di UI.

Build bersih 100% (`npm run typecheck` + `next build`). Backend tidak
disentuh sama sekali.

## ✅ Verifikasi production 2026-09-11 — migrasi Supabase & Phase 2/3 dikonfirmasi live

Dipicu email auto-pause Supabase ("proyek tidak aktif >7 hari, akan
di-pause"). Sambil mengecek itu, ditemukan bahwa item #1 dari
"Langkah berikutnya" (`docs/progress.md`) — verifikasi migrasi kolom
Supabase yang sejak 2026-09-02 "sudah dijalankan tapi belum diverifikasi
live" — masih terbuka, dan **tidak butuh menunggu gerbang `SITE_PASSWORD`
seperti diasumsikan sesi-sesi sebelumnya**: gerbang itu cuma ada di
middleware Next.js (`apps/web/middleware.ts`), API FastAPI-nya sendiri
(`pop-api-ptug.onrender.com`) publik dan bisa diverifikasi langsung.

**Metode**: daftar org+akun test baru lewat `POST /v1/auth/register`
(bukan akun demo pengguna — tidak perlu kredensial siapa pun), bukan
lewat browser/`SITE_PASSWORD`. RLS multi-tenant mencegah akun ini membaca
data org demo (diverifikasi memang begitu), jadi semua pengecekan pakai
project baru yang dibuat sendiri.

**Hasil — kedua endpoint yang dulu 500 karena kolom belum bermigrasi
sekarang 200:**
- `GET /v1/projects/{id}/topics` → `200 []` (dulu 500, kolom
  `reviewed_label`/`review_status`/dst belum ada)
- `GET /v1/projects/{id}/network` → `200` dengan `insufficient_data`
  (dulu 500, kolom `reply_to_hash`/`quote_of_hash`/`conversation_id`
  belum ada)
- `PATCH /v1/projects/{id}/topics/{topic_id}/review` → `200`, **jalur
  TULIS ke kolom migrasi juga dikonfirmasi**, bukan cuma baca

**Data asli diinjeksi lewat endpoint sungguhan untuk pertama kalinya**
(sesi-sesi sebelumnya cuma memanggil fungsi `RSSConnector`/`sentiment.py`
secara lokal tanpa Postgres — gap yang eksplisit dicatat di
`docs/progress.md` poin 2 "Yang BELUM diverifikasi"): 195 artikel nyata
dari 4 feed (Antara, CNBC Indonesia, Republika, Sindonews) dikirim lewat
`POST /v1/projects/{id}/signals/ingest` → `200`, `stored: 195`,
`duplicate_rate: 0.0`. Setelahnya:
- `GET .../signals/summary` → volume 195, sentimen rata-rata 0.044
- `GET .../signals/trend` → agregasi harian benar
- `POST .../topics/discover` → tema ter-cluster dari data asli (bukan
  kosong), label kata kunci masuk akal ("2026 / indonesia / gunung", dst)
- `GET .../risk/score` → `coverage: 0.18`, skor **benar-benar ditahan**
  (null) karena di bawah ambang `MIN_COVERAGE` 60% — gating bekerja
  seperti didesain, bukan dipaksakan tampil
- `GET .../forecast/baseline` → `insufficient_data: true` (POI butuh
  snapshot survei, bukan sinyal media) — benar, bukan bug
- `POST .../copilot/ask` → `409` dengan pesan jelas ("belum punya data
  agregat"), bukan crash
- `GET .../brief/latest` → `404` dengan pesan jelas ("belum ada Executive
  Brief"), bukan crash
- `POST .../impact/analyze` → `422` validasi field wajib, bukan crash

Kesimpulan: **seluruh permukaan API Phase 2/3 sehat di production**, baik
untuk proyek kosong maupun proyek berisi data media asli. Project test
dan datanya dihapus (`DELETE /v1/projects/{id}` → `204`, ikut
terverifikasi) setelah pengecekan selesai — production kembali bersih,
kecuali satu org kosong tanpa data yang tidak sempat dihapus (API ini
tidak punya endpoint hapus organisasi).

**Temuan sentimen (memperluas verifikasi 2026-09-02 dari 385 → 445 item,
5 → 7 feed — nambah CNN Indonesia, Tempo, Media Indonesia):**
- Abstain rate 78.0% (naik tipis dari 79.5%), konsisten dengan temuan
  sebelumnya, sekarang sekaligus dikonfirmasi lewat endpoint ingest asli
  (lihat di atas), bukan cuma panggilan fungsi lokal.
- **Bug baru ditemukan & diperbaiki**: kata `hebat` (leksikon positif,
  bobot 0.9) — 3/3 kemunculannya di 445 item adalah penguat keparahan di
  depan kata negatif ("Kebakaran Hebat Lahap Sekolah, 17 Orang Tewas",
  "Kebakaran hebat melanda kantor PUPR", "Gadis AS Muntah Hebat"), 0/3
  makna pujian. Pola identik "asal" (2026-09-02): kata yang berbalik
  makna total tergantung kata yang mengikutinya. Dihapus dari
  `_POSITIVE` di `app/services/sentiment.py`, tes regresi
  `test_hebat_penguat_keparahan_tidak_lagi_dianggap_positif` ditambahkan,
  tidak muncul sama sekali di `sentiment_eval.py:LABELED` (32 tes
  sentiment lokal tetap hijau, termasuk kelas `TestEvaluasi` yang
  menjaga lantai macro-F1/akurasi 0.80 — **belum dijalankan lewat CI**,
  Docker tidak tersedia di sandbox sesi ini seperti sesi-sesi sebelumnya,
  jadi belum lulus role `pop_app` RLS test suite yang 474 tes; hanya
  32 tes sentiment murni yang tanpa database yang dijalankan lokal).
- **`manfaat` diperiksa juga (7 kemunculan), TIDAK diperbaiki**: 6/7
  benar (genre artikel "manfaat kesehatan X" — konteks positif asli,
  mis. "5 Manfaat Labu Kuning untuk Kesehatan Pencernaan"), cuma 1/7
  salah (BGN "mengeluarkan 1.653 sekolah dari daftar penerima manfaat" —
  soal negasi/pencabutan, bukan makna kata itu sendiri). Berbeda dari
  `hebat`/`asal` yang salah di HAMPIR SEMUA kemunculan, menghapus
  `manfaat` akan merusak lebih banyak kasus benar daripada memperbaiki.
  Didokumentasikan sebagai keterbatasan struktural (leksikon kata-tunggal
  tidak menangani negasi "keluar dari daftar penerima X"), bukan bug
  kata yang aman diperbaiki — konsisten dengan keputusan `meningkat` dan
  `korupsi` di sesi-sesi sebelumnya.
- **Perubahan kode SATU-SATUNYA sesi ini** adalah penghapusan `hebat`
  dari leksikon + tes regresinya. Tidak ada perubahan lain ke
  `services/`, `routers/`, atau schema. Belum di-commit/push — menunggu
  keputusan pengguna (lihat laporan sesi untuk opsi).

**Studi kasus tematik (sore harinya, sesi yang sama): karhutla Kalimantan/
Sumatra — pemicunya jadi konfirmasi nyata dari batasan yang sebelumnya
cuma diverifikasi lokal.** 20 artikel nyata (kurasi manual dari 445 item/
7-10 feed, tema "karhutla"/"kabut asap", termasuk temuan real "Update
Korban Karhutla di Enam Provinsi: 4 Meninggal, 347 Luka-luka") diinjeksi
ke project test terpisah lewat `signals/ingest` sungguhan, lalu dihapus
lagi setelah diperiksa. Hasil:
- `topics/discover`: `n_analysed: 20` (pas ambang minimum, `insufficient_data`
  jadi `false`) tapi **HDBSCAN tetap menghasilkan 0 klaster**
  (`unclustered_pct: 100`). Ini konfirmasi PRODUCTION pertama dari catatan
  `docs/roadmap.md`/sesi 2026-08-27: "24 dokumen di 23 dimensi menghasilkan
  NOL klaster... korpus yang sama di 3 dimensi memisahkan temanya bersih" —
  sebelumnya cuma diverifikasi di Postgres lokal, sekarang terbukti persis
  sama di Supabase produksi dengan data media nyata, bukan data buatan.
- `alerts` (anomaly detection): tetap `insufficient` meski `signals/trend`
  sekarang punya 3 titik hari nyata (2026-08-22 vol 1, 09-10 vol 14, 09-11
  vol 5) — baseline historisnya masih dianggap terlalu tipis untuk z-score.
  Perilaku benar (menahan diri), bukan bug.
- `risk/score`: sama seperti batch 16-item sebelumnya — `coverage: 0.22`
  (skor gabungan ditahan), tapi `issue_growth` dan `media_escalation`
  tetap konsisten `100.0` di kedua ukuran sampel — sinyal itu robust
  terhadap ukuran data, bukan kebetulan sampel kecil.

Tidak ada perubahan kode dari studi kasus ini — murni verifikasi. Detail
percakapan lengkap ada di riwayat chat sesi ini, bukan diulang di sini.

**Yang MASIH belum diverifikasi setelah sesi ini** (supaya tidak
mengklaim lebih dari yang sudah dibuktikan): jalur RSS lewat
`RSSConnector` + endpoint `/signals/collect` terjadwal (sesi ini masih
pakai `parse_feed()` lokal lalu `POST /signals/ingest` manual, sama
seperti pola sesi 2026-09-02, BUKAN memanggil `collect` dengan
`DataSource` konektor RSS terdaftar); konektor YouTube/X (masih butuh
API key); Executive Brief & Copilot dengan LLM sungguhan (masih butuh
`ANTHROPIC_API_KEY` — lihat bagian "Executive Brief" di atas, sengaja
ditunda ke akhir atas instruksi eksplisit pengguna sesi ini).

## 🟡 Phase 4 — item tanpa vendor pihak ketiga (2026-09-11)

Atas instruksi eksplisit pengguna ("no 1, 3, dan 4 kerjakan secara
maksimal"). Tiga dari tujuh item Phase 4 dikerjakan — persis yang tidak
butuh keputusan vendor/akun pihak ketiga (lihat tabel lengkap di
`docs/progress.md` bagian "Phase 4 — enterprise"). **Semua kode di bawah
ini baru diverifikasi lokal (43 tes murni tanpa DB, ruff bersih, mypy
--strict bersih di file baru) — BELUM di-deploy ke Render/Vercel**,
menunggu keputusan pengguna soal commit/push/PR.

### ✅ Report generator PDF (`GET /projects/{id}/reports/summary`)

`app/services/reports.py` (fungsi murni, dites tanpa DB) + 
`app/routers/reports.py`. Cakupan v1 sengaja terbatas ke Segments +
Polarization Index — bukan AIEnvelope (statistik murni, sama seperti
`routers/segments.py`/`routers/risk.py`). Warna kolom Sumber sinkron
dengan token R1 (`apps/web/lib/tokens.ts`).

**Bug ditemukan+diperbaiki lewat verifikasi visual PDF sungguhan** (bukan
cuma "tidak error"): nilai teks panjang di kolom "Nilai" tumpang tindih ke
kolom "Sumber" karena sel tabel `reportlab` diisi string mentah (tidak
word-wrap). Diperbaiki dengan membungkus tiap sel jadi `Paragraph`.
Ketahuan justru karena PDF-nya benar-benar dirender dan dibaca kembali,
bukan diasumsikan benar dari kode.

4 tes di `tests/test_reports.py`, termasuk yang mengecek `insufficient_data`
tidak pernah membocorkan `value` yang seharusnya ditahan (CLAUDE.md §3) —
dites lewat pencarian byte mentah karena `pageCompression=0` sengaja
dimatikan di `build_summary_pdf` supaya PDF-nya bisa dites tanpa parser
terpisah.

### ✅ Rate limiting per tenant (`app/middleware/ratelimit.py`)

In-memory sliding-window per proses, BUKAN Redis/terdistribusi. `redis`
sudah jadi dependency proyek sejak awal (`config.py:redis_url`) tapi tidak
pernah benar-benar dipakai di mana pun — menyambungkannya butuh instance
Redis sungguhan yang belum ter-provisioning di Render, keputusan infra
tersendiri, bukan cuma kode. **Batasan yang harus diketahui**: reset ke nol
tiap restart/redeploy; kalau nanti Render dijalankan >1 instance, limit
efektif jadi (limit × jumlah instance). Cukup untuk kondisi sekarang (Render
free tier, satu instance) tapi WAJIB diganti backend Redis sebelum API
publik beneran dibuka.

Endpoint auth (`/v1/auth/login`, `/v1/auth/register`) dapat limit lebih
ketat (10/menit per IP) karena rawan brute-force/spam — endpoint lain
120/menit per org (atau per IP kalau tidak ada token valid). `/health` dan
dokumentasi API dikecualikan total.

7 tes di `tests/test_middleware.py`: lolos di bawah limit, ditolak 429 di
atas limit (dengan header `Retry-After`), `/health` tidak pernah kena
limit, endpoint ketat tidak memotong jatah endpoint lain, dan dua klien
berbeda (IP berbeda) tidak saling memotong jatah.

**Urutan middleware di `main.py` sengaja diperhatikan**: `CORSMiddleware`
harus paling luar (ditambah PALING TERAKHIR — Starlette membungkus dari
yang terakhir ditambahkan ke luar) supaya respons 429 dari rate limiter
tetap membawa header CORS; kalau tidak, browser akan memblokir frontend
membaca pesan errornya sendiri. Dikonfirmasi lewat `app.user_middleware`
setelah app di-boot penuh.

### ✅ Observability dasar (`app/middleware/observability.py`)

Request ID (UUID4) + log JSON satu baris per request (method, path,
status, duration_ms), dikembalikan juga lewat header `X-Request-ID` di
respons. **Ini BUKAN APM/tracing distribusi** (Datadog/Sentry/Honeycomb/
dst) — itu tetap butuh keputusan vendor + akun pihak ketiga, belum
dikerjakan. Render menangkap stdout sebagai log platform tanpa konfigurasi
tambahan, jadi ini langsung berguna tanpa infra baru.

Sengaja TIDAK mencatat `org_id`/`user_id` di log ini (lihat docstring
modul) — mendekode JWT di middleware berarti dua jalur validasi token yang
bisa berbeda perilaku diam-diam dari `app/deps.py`.

2 tes: header `X-Request-ID` ada di tiap respons, dan berbeda antar-request.

### Sengaja TIDAK dikerjakan: orkestrasi multi-agent penuh

`ai/agents.py:Orchestrator` sudah mendukung banyak agen sekaligus
(`run(agents: list[Agent], ctx)`), tapi `brief.py`/`copilot.py` selalu
memanggilnya dengan satu agen. "Memperluas" ini jadi "beneran multi-agent"
butuh keputusan produk dulu (agen tambahan apa, tugas apa, kenapa) —
membuat agen baru tanpa tujuan konkret cuma supaya kotaknya tercentang
melanggar semangat CLAUDE.md §8 ("kalau ragu, berhenti dan tanya"), beda
kelas dengan tiga item di atas yang implementasinya mekanis begitu tahu
tujuannya (rate limit, log, PDF).

## ✅ PR #5 di-merge + verifikasi pasca-deploy — 2026-09-11 (sesi kedua)

PR #5 di-merge ke `main` (merge commit `8677c55`, bukan squash — docs di repo
merujuk ke commit-commit individualnya). Render dan Vercel auto-deploy; Render
selesai dalam ~40 detik, Vercel build hijau di merge commit.

**Yang dikonfirmasi hidup di production setelah deploy** (semua lewat request
sungguhan ke `pop-api-ptug.onrender.com`, bukan dibaca dari kode):

| Item | Bukti |
|---|---|
| Observability | `X-Request-ID` ada di tiap respons dan berbeda antar-request |
| Report PDF | `GET /projects/{id}/reports/summary` → 200, `application/pdf`, 4406 byte, 1 halaman |
| Isi PDF | Word-wrap benar (fix `Paragraph` bertahan di production), legenda provenance R1 lengkap, polarisasi tampil "data tidak cukup" — bukan angka palsu (CLAUDE.md §3) |
| Rate limiter | 10 `POST /auth/login` lolos, ke-11 → `429` + `Retry-After: 45` |
| CORS di 429 | `access-control-allow-origin` terbawa di respons 429 — klaim urutan middleware terbukti di production, bukan cuma di `app.user_middleware` |
| Exempt & isolasi jatah | `/health` tetap 200 dan `GET /projects` tetap 200 saat login sedang diblokir |
| Frontend | Gerbang `SITE_PASSWORD` redirect normal, build Vercel hijau |

Project test dihapus (`DELETE /projects` → 204, daftar kembali `[]`). Satu org
test kosong tertinggal lagi — API masih belum punya endpoint hapus organisasi.

### Dua bug yang lolos CI dan baru ketahuan di production

Keduanya berasal dari PR #5 sendiri, ditemukan justru karena deploy-nya
diverifikasi dengan request sungguhan alih-alih dianggap beres begitu CI hijau.

**1. `reports/summary` balas 500, bukan 404, untuk proyek yang tidak ada.**
`routers/reports.py` memakai `.scalar_one()` — satu-satunya di seluruh
`app/routers/`. Proyek tidak ada (atau milik tenant lain, disaring RLS jadi nol
baris) → `NoResultFound`, dan `main.py` cuma punya exception handler untuk
`ValueError` → 500. Terbukti live: `reports/summary` → 500 sementara
`segments`/`risk/polarization`/`topics`/`network` dengan UUID acak yang sama
→ 200. Diperbaiki jadi `scalar_one_or_none()` + `HTTPException(404,
"Proyek tidak ditemukan.")`, sesuai konvensi `surveys.py`/`topics.py`/
`signals.py`.

**Kenapa CI tidak menangkapnya**: 4 tes di `tests/test_reports.py` semuanya
menguji fungsi murni `build_summary_pdf`; tidak satu pun memanggil
endpoint-nya. Celah itu ditutup `tests/test_reports_router.py` (3 tes
end-to-end terhadap Postgres role `pop_app`), termasuk kasus lintas-tenant
yang **harus** balas 404 identik dengan "proyek tidak ada" — balasan yang
berbeda akan membocorkan keberadaan proyek milik org lain.

**2. Request yang kena rate limit tidak tercatat di log sama sekali.**
Respons 429 tidak membawa `X-Request-ID`. Sebabnya urutan `add_middleware`:
`RequestLoggingMiddleware` ditambahkan pertama = paling dalam, rate limiter di
luarnya, jadi 429 di-short-circuit sebelum logger sempat jalan — tidak ada
baris log JSON-nya. Ironisnya justru request inilah yang paling perlu terlihat
di log (percobaan brute-force login). Urutan dibalik: rate limiter paling
dalam, logger di tengah, CORS tetap paling luar.

Urutan middleware sekarang dipasang lewat `main.py:install_middleware()` —
fungsi tersendiri supaya bisa dites langsung, bukan tiga baris di ruang modul
yang tidak bisa disentuh tes. `tests/test_middleware.py::TestUrutanMiddleware`
menguji fungsi yang sama persis dipakai `main.py` (bukan menyusun ulang
urutannya di tes — tes yang menduplikasi urutan yang mau dijaganya tidak
menjaga apa pun). **Dibuktikan menangkap regresinya**: urutan sengaja
dibalik ke versi buggy → 2 tes gagal; dikembalikan → 10 hijau lagi.

### Perbaikannya dikonfirmasi live (PR #6, merge commit `a3a1dd2`)

CI PR #6: **492 tes lulus** (486 → +6), `ruff` bersih, `mypy` bersih di 34
file. Tiga tes `test_reports_router.py` lulus terhadap Postgres nyata dengan
role `pop_app` — termasuk kasus lintas-tenant, jadi perbaikan 404 itu terbukti,
bukan cuma "tidak error".

Setelah Render selesai redeploy (sempat 502 sebentar saat restart — transien),
kedua bug diperiksa ulang dengan request sungguhan:

```
GET /projects/{uuid-acak}/reports/summary
  → 404 {"detail":"Proyek tidak ditemukan."}      (sebelumnya 500)

POST /v1/auth/login (request ke-12, jatah habis)
  → 429
    access-control-allow-origin: https://public-opinion-platform.vercel.app
    retry-after: 45
    x-request-id: 2bc25a9e-...                     (sebelumnya tidak ada)
```

Header CORS **tetap** terbawa di 429 — refaktor urutan middleware tidak
merusak jaminan yang sudah diverifikasi sebelumnya. Sweep regresi jalur normal
juga bersih: PDF untuk proyek nyata tetap 200/`application/pdf`/`%PDF`
(4400 byte) dan membawa `X-Request-ID`, `segments`/`risk/polarization`/
`topics`/`network`/`health` semuanya tetap 200. Project test dihapus lagi
(204, daftar kembali `[]`).

**Pelajaran yang layak diingat sesi berikutnya**: dua-duanya lolos CI hijau dan
lolos `mypy --strict`, dan dua-duanya ketahuan dalam hitungan menit begitu
deploy-nya benar-benar diketuk dengan request sungguhan. Pola yang sama persis
dengan bug word-wrap PDF di PR #5 (ketahuan karena PDF-nya dirender dan dibaca,
bukan diasumsikan benar dari kode) dan bug `apiOrNull` 2026-09-02. "CI hijau"
bukan sinonim dari "deploy sehat".

## ✅ Studi kasus karhutla + kolom `url` untuk akuntabilitas riset — 2026-09-11 (sesi ketiga)

Dipicu kebutuhan pengguna: studi kasus penelitian akademis "karhutla
Kalimantan/Sumatra" butuh data yang **keasliannya bisa ditelusuri balik**,
bukan cuma diklaim asli.

**Data dikumpulkan (project pengguna sendiri "kebakaran hutan", BUKAN
project test yang dihapus)**:
- 42 artikel RSS nyata (Antara nasional + 6 edisi regional Kalteng/Kalbar/
  Kaltim/Kalsel/Sumsel/Riau/Jambi, CNBC Indonesia, Republika, Sindonews, CNN
  Indonesia, Tempo, Liputan6) via `POST /signals/ingest` sungguhan.
- 115 komentar YouTube dari 9 video berita resmi (KOMPASTV, tvOneNews,
  Official iNews, SINDOnews, METRO TV, BeritaSatu — semua diverifikasi
  nyata lewat oEmbed publik sebelum didaftarkan) via `POST
  .../sources/{id}/collect` sungguhan, konektor `youtube_api`.
- **Data TIDAK dihapus** — beda dari studi kasus 20-item sebelumnya
  (bagian "Verifikasi production 2026-09-11" di atas) yang memang sengaja
  dihapus karena itu project test sekali-pakai.
- Hasil: `topics/discover` atas 157 item gabungan menemukan **4-9 klaster
  nyata** (beda dari batch 20-item yang 0 klaster) — volume lebih besar
  memang membantu HDBSCAN, konsisten dengan catatan `roadmap.md`
  2026-08-27. Sentimen jadi **terukur untuk pertama kalinya** (0.406,
  `insufficient_data: false`) karena kombinasi MEDIA+SOCIAL melewati
  ambang 30 item bernilai — sebelumnya cuma MEDIA yang nyaris tidak pernah
  cukup banyak per topik sempit.
- **Temuan metodologis yang HARUS didokumentasikan, bukan disembunyikan**:
  satu klaster komentar bertema "sawit" bersentimen 0.75 (positif) yang
  patut dicurigai bias leksikon terhadap sarkasme (komentar warganet
  marah soal sawit penyebab karhutla seringnya bernada sindiran, bukan
  pujian tulus) — pola yang sama persis dengan bug "hebat"/"asal" yang
  sudah ditemukan+diperbaiki di leksikon media sebelumnya, tapi kali ini
  di data SOCIAL dan **belum diverifikasi manual** (API ini sengaja tidak
  punya cara baca komentar mentah satu-satu — sampai sekarang, lihat di
  bawah). Jangan pakai angka 0.75 itu di kesimpulan tanpa spot-check.

**Gap akuntabilitas yang ditemukan lewat kebutuhan riset ini, lalu
diperbaiki**: `RawItem.url` (URL artikel/video) sudah lama ditangkap di
level konektor (`connectors/rss.py`, `connectors/youtube.py`, `connectors/
x.py`) tapi **dibuang total** sebelum sempat tersimpan — `IncomingItem`/
`PreparedMention`/tabel `mentions` tidak pernah punya kolom untuknya. Untuk
RSS, tambal sulam sesi ini menaruh URL di `external_id` (jalan, tapi satu
kolom dipakai dua tujuan). Untuk YouTube, URL-nya benar-benar hilang tanpa
jejak. Dan yang lebih mendasar: **tidak ada satu endpoint pun** di API ini
untuk membuka daftar item mentah satu-satu — cuma ada agregat.

**Diperbaiki dengan benar** (bukan tambal sulam lagi):
- Kolom `url text` ditambah ke tabel `mentions` (`db/schema.sql` + migrasi
  `ALTER TABLE` — lihat langkah migrasi di bawah, BELUM dijalankan ke
  Supabase production sampai pengguna menjalankannya).
- `url` dialirkan penuh: `RawItem` (sudah ada) → `IncomingItem` →
  `PreparedMention` → `Mention` lewat `_store()`. `IngestItem` (unggahan
  manual) juga dapat field `url` opsional baru.
- Endpoint baru `GET /projects/{id}/mentions` — pertama kalinya API ini
  mengembalikan konten mentah, bukan agregat. Filter `source`/`days`,
  paginasi `limit`/`offset`, urut terbaru dulu. `url: null` untuk mention
  lama (sebelum kolom ini ada) atau sumber tanpa URL publik — dibedakan
  eksplisit dari string kosong.
- Frontend: panel baru "Item terbaru (untuk validasi manual)" di halaman
  Signal Monitor (`/sinyal`) — tiap baris punya link "Buka sumber ↗"
  berwarna token sumbernya (R1), atau "tidak ada URL sumber" kalau memang
  tidak ada, bukan link mati.

**Migrasi yang perlu dijalankan pengguna di Supabase SQL editor** (sama
pola dengan migrasi kolom `reviewed_label` dkk sebelumnya):

```sql
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS url text;
```

Sampai ini dijalankan, `GET /projects/{id}/mentions` akan gagal dengan
error kolom tidak ada (500, bukan dikira bug kode) — pola identik dengan
migrasi `topics.reviewed_label` dkk 2026-09-02/09-11. 157 item yang sudah
terlanjur masuk sesi ini (URL RSS numpang di `external_id`, URL YouTube
sudah terlanjur hilang) TIDAK di-backfill otomatis — re-ingest akan
menduplikasi kontennya. Manifest lokal (dikirim ke pengguna lewat
SendUserFile, bukan disimpan di repo) tetap sumber kebenaran untuk 157
item itu; kolom `url` di database baru berlaku penuh untuk data BARU
setelah migrasi dijalankan.

**Tes**: 2 tes murni baru (`test_pipeline.py::TestUrl`) + 5 tes end-to-end
baru (`test_mentions_router.py`, terhadap Postgres role `pop_app`,
termasuk isolasi tenant) — **dikonfirmasi lewat CI PR #7: 499 tes lulus**
(492→499), `ruff` bersih, `mypy --strict` bersih. Frontend `tsc`+`next
build` hijau. Merge ke `main` (`8942a95`), Render+Vercel auto-deploy.

### 🔴 Regresi produksi ditemukan+diperbaiki dalam hitungan menit setelah merge

Begitu deploy live, **`signals/summary` dan `topics/discover` ikut balas
500** — bukan cuma endpoint baru `GET /projects/{id}/mentions` yang
memang diprediksi 500 sampai migrasi dijalankan. Akar masalah: menambah
kolom `url` ke model ORM `Mention` membuat **setiap query yang mengambil
baris `Mention` utuh** (`select(Mention)`, bukan kolom spesifik) ikut
meminta kolom itu — dan Postgres production belum punya kolom itu sampai
migrasi dijalankan. Terkena: `signals.py` (summary, mentions baru),
`topics.py` (discover, 2 tempat), `risk.py` (score). Tidak terkena:
`signals/trend`, `reports/summary` — keduanya query kolom spesifik lewat
`func.avg()`/dst, bukan `select(Mention)`.

**Pelajaran untuk sesi berikutnya**: menambah kolom ke model ORM SQLAlchemy
punya efek samping GLOBAL ke semua query full-entity di tabel itu, bukan
cuma ke endpoint yang sengaja memakai kolom barunya — beda dari menambah
field baru di skema Pydantic (yang scope-nya lokal ke endpoint itu saja).
Deploy kode + migrasi DB idealnya satu paket atomik untuk perubahan model
ORM; kalau terpisah (seperti pola migrasi manual Supabase di proyek ini),
window antara deploy-kode dan migrasi-DB adalah window downtime nyata
untuk SEMUA fitur yang menyentuh tabel itu, bukan cuma fitur barunya.

**Diperbaiki**: migrasi `ALTER TABLE mentions ADD COLUMN IF NOT EXISTS url
text;` dijalankan pengguna sendiri di Supabase SQL editor (dipandu lewat
Claude in Chrome — navigasi dan pengetikan SQL oleh agen, klik "Run" oleh
pengguna, karena itu mengubah database production). Berlaku instan, tidak
perlu redeploy. Semua endpoint yang tadi 500 (`signals/summary`,
`topics/discover`, `risk/score`, `GET .../mentions`) dikonfirmasi 200
setelah migrasi, dicek dengan request sungguhan bukan diasumsikan.

`GET /projects/{id}/mentions` diverifikasi mengembalikan data nyata: 40/42
artikel RSS punya `url: null` tapi `external_id` tetap URL (tambal sulam
sesi sebelum ini), item baru ke depan akan punya keduanya. Panel "Item
terbaru (untuk validasi manual)" di `/sinyal` dikonfirmasi live di browser
— "tidak ada URL sumber" tampil benar untuk item lama, bukan link mati.

## ✅ Project baru "MBG AGUSTUS 2026" + akumulasi harian otomatis — 2026-09-11 (masih sesi ketiga)

Project riset kedua pengguna sendiri (setelah "KEBAKARAN HUTAN"), dibuat
lewat UI (`/proyek-baru`) untuk studi kasus program nasional Makan Bergizi
Gratis (MBG). **Ini BUKAN bagian dari kode/deploy platform** — tidak ada
satu baris pun berubah di repo untuk pekerjaan ini, jadi dicatat di sini
murni supaya sesi berikutnya tahu ada apa, bukan karena menyentuh
`apps/api`/`apps/web`.

**Skrip ingest RSS** (`ingest_mbg.py`, disalin dari `ingest_karhutla.py`
sesi kedua — lihat manifest provenance yang sudah dikirim ke pengguna,
bukan disimpan di repo): filter kata kunci `makan bergizi gratis|\bmbg\b|
badan gizi nasional|\bbgn\b` (bukan "gizi" sendirian — terlalu umum, bisa
nyasar berita kesehatan/pangan yang tidak menyinggung program ini). 15 feed
RSS yang sama dengan studi karhutla. Percobaan pertama (manual, sesi ini):
**10 artikel asli tersimpan** — mencakup liputan kritis (keracunan di
beberapa daerah, dugaan korupsi Kejagung, 1.653 sekolah dicoret) dan
bantahan hoaks, bukan cuma pemberitaan positif pemerintah. `url` tersimpan
proper (bukan tambal sulam `external_id`) karena kolom sungguhan sudah ada
sejak PR #7 di atas.

**Akumulasi harian 7 hari** — dijalankan lewat `RemoteTrigger` (routine
cloud Claude Code, **bukan cron job di repo/Render/Vercel**), sesuai
permintaan pengguna: "Jalankan skrip ini lagi tiap hari... supaya jendela
waktu terkumpul dari waktu terbit asli tiap hari — bukan direkonstruksi
belakangan". Dipilih **7 rutinitas `run_once_at` terpisah** (bukan satu
`cron_expression` berulang) supaya otomatis nonaktif sendiri setelah 7 kali
jalan — tidak ada yang perlu diingat untuk dimatikan manual setelah
seminggu:

| # | Jalan (WIB / UTC) | Routine ID |
|---|---|---|
| 1 | 12 Sep 08:00 / 01:00 | `trig_01BGxoi5SR2KMSEMU1r9LQL4` |
| 2 | 13 Sep 08:00 / 01:00 | `trig_014B6ng883QqT4wYHQ7Cd13s` |
| 3 | 14 Sep 08:00 / 01:00 | `trig_01HQy7RJBoLHmdRJLRApjAKT` |
| 4 | 15 Sep 08:00 / 01:00 | `trig_01VDauEVZhrTk35djwzuuMr9` |
| 5 | 16 Sep 08:00 / 01:00 | `trig_01JxK81kgD8FJarbBwuoWK31` |
| 6 | 17 Sep 08:00 / 01:00 | `trig_0113P9wofQbwEw1jui8jfktP` |
| 7 | 18 Sep 08:00 / 01:00 | `trig_0111pPT7yjpoYnqA9o2fxkoR` |
| 8 | 19 Sep 08:00 / 01:00 | `trig_016J9Po9ehvj9Y9kcvQ8ymG8` (ditambah belakangan, atas permintaan pengguna) |

Tiap rutinitas menulis ulang skrip lengkap dari nol di sandbox cloud
ephemeral-nya sendiri (di-tempel penuh di prompt routine, bukan clone repo
— agen cloud tidak punya akses ke scratchpad sesi lokal), lalu memanggil
`POST /signals/ingest` dengan token akses pengguna (JWT, berlaku sampai
~11 Oktober 2026 — cukup untuk seluruh jendela 7 hari). Cek status/hasil:
`claude.ai/code/routines`.

**Yang perlu diketahui sesi berikutnya**: kolom `url` di database tetap
bergantung migrasi yang sama dengan bagian di atas — kalau project ini
dibuat sebelum migrasi dijalankan, ingest pertama akan gagal 500. Sudah
tidak masalah untuk pengguna ini (migrasi sudah jalan), tapi relevan kalau
pola ini diulang untuk project riset baru di Supabase lain.

## ✅ Fix tombol "Aktifkan" proyek tidak refresh — PR #8, di-merge 2026-09-11 (masih sesi ketiga)

Ketahuan lewat laporan pengguna sungguhan setelah pakai project switcher
untuk pindah dari "MBG AGUSTUS 2026" balik ke "KEBAKARAN HUTAN": *"datanya
tidak tampil"*. Data di server dicek dulu (bukan diasumsikan hilang) —
utuh, 157 item, `200 OK`. Baru setelah itu dicurigai bug frontend.

Akar masalah: `handleActivate()` di `ProjectRow.tsx` satu-satunya handler
yang tidak memanggil `router.refresh()`/`router.push()` setelah action-nya
selesai — `handleSave` (rename) dan `handleDelete` di file yang sama sudah
benar sejak awal. Cookie `pop_project_id` memang berubah di server, tapi
halaman `/proyek` sendiri tidak menampilkan status "Aktif" terbaru tanpa
reload manual.

**Catatan jujur soal cakupan fix**: Next.js 15.5.23 (terpasang) secara
default tidak nge-cache halaman `force-dynamic` di client, jadi navigasi
baru lewat `<Link>` semestinya selalu ambil data segar terlepas dari bug
ini. Penyebab paling mungkin untuk laporan pengguna spesifik itu kemungkinan
besar tab dashboard yang sudah terbuka *sebelum* klik "Aktifkan" — itu
butuh reload manual, tidak ada mekanisme cross-tab yang bisa memperbaikinya
dari kode. Dikonfirmasi pengguna: reload manual menampilkan data yang
benar. Fix ini tetap menutup satu asimetri nyata di `/proyek` sendiri.

Tidak ada tes otomatis baru — perubahan satu baris di client action
handler. `tsc`+`next build` hijau, CI PR #8 hijau (backend+frontend+Vercel).

## ✅ Redesain tema terang + dua konektor deret publik — PR #9, di-merge & LIVE 2026-09-11 (sesi keempat)

Dipicu permintaan pengguna: sebuah tangkapan layar dashboard Sprout Social
("saya suka dashboard seperti ini, lebih mudah menganalisa") plus "carikan
API publik yang free atau mudah digunakan dalam dashboard ini".

### Bagian 1 — sistem tema, bukan sekadar ganti warna

Seluruh `apps/web/app/globals.css` ditulis ulang di atas satu blok token.
Aturan barunya tercatat di komentar kepala file: **tidak ada literal warna di
bawah blok token.** Sebelumnya ada ~30 hex tersebar langsung di selector
(`#080D13`, `#16202C`, `#43566E`, `#22303F`, dst.) yang membuat file itu
secara praktis tidak bisa di-retema.

- Tema terang jadi **default**; tema gelap (palet lama, persis) jadi pilihan
  lewat tombol di bar atas (`components/ThemeToggle.tsx`).
- **`prefers-color-scheme` SENGAJA tidak dipakai.** Kalau dipakai, pengguna
  bersistem gelap tidak akan pernah melihat desain terang yang justru diminta
  tanpa mengubah setelan OS-nya. Preferensi disimpan di `localStorage` dan
  dipasang lewat skrip inline di `app/layout.tsx` sebelum cat pertama —
  tanpa itu halaman berkedip dari terang ke gelap tiap muat.
- **Warna sumber R1 nilainya berubah, perannya tidak.** `#4DA3FF` hanya
  mencapai rasio kontras 2.3:1 di atas putih (gagal WCAG AA), jadi tema
  terang memakai `#0B6FD4` (4.9:1); jingga `#FF7A45`→`#C2481B`, ungu
  `#9B8AFB`→`#5D45D1`. "Biru = survei" tetap berlaku di kedua tema.
- `.stat-row` sekarang satu kartu yang dibagi garis rambut (pola dari
  referensi Sprout), memakai `repeat(auto-fit,minmax(190px,1fr))` + `gap:1px`
  di atas background garis. Dipilih begitu karena jumlah ubin berbeda-beda
  per halaman (command 1, jaringan 2, sinyal/risiko/pengaruh 4) — grid
  4-kolom tetap akan meninggalkan sel kosong besar. **Tidak ada TSX yang
  diubah untuk ini.**
- `.insufficient` naik kelas dari teks abu-abu jadi pita peringatan. Keadaan
  "data tidak cukup" adalah pembeda produk (CLAUDE.md §8), bukan kegagalan
  render — tapi tampilan lamanya persis seperti bug.

**Tiga bug nyata ketemu saat mengerjakan ini, bukan dicari:**

1. **`var(--bg2, #1a2332)` di `ProjectRow.tsx` merujuk token yang tidak
   pernah ada.** `--bg2` tidak terdefinisi di mana pun, jadi nilai fallback
   gelap itulah yang selalu dipakai — termasuk kalau temanya diganti.
   Ketahuan karena baru sekarang ada yang menyisir seluruh literal warna.
2. **Recharts membeku di tema gelap.** `TrendChart.tsx` dan
   `ForecastSimulator.tsx` menyuntikkan hex ke `stroke`/`fill`. Yang paling
   halus: `ForecastSimulator` memakai `fill="#0A1017"` untuk MEMOTONG pita
   bawah — trik yang hanya benar kalau nilainya sama persis dengan latar
   panel. Di tema terang itu akan menggambar balok hitam di tengah grafik.
   Sekarang `var(--panel)`. Recharts meneruskan nilai ini apa adanya ke
   atribut SVG, dan `var()` sah di sana.
3. **Empat halaman form (`/masuk`, `/login`, `/daftar`, `/proyek-baru`)
   seluruhnya buta tema** — `#ccc`, `#111`, `#888`, `#c0392b` inline, tidak
   pernah ikut tema mana pun. Sekarang pakai kelas `.auth-*`/`.field`/`.btn`.

`lib/tokens.ts` sekarang mengembalikan `var(--...)` alih-alih hex; hex-nya
pindah ke field `hex` untuk konteks yang tidak bisa membaca CSS custom
property (kanvas, ekspor gambar). `rankColor()` dipindah ke sana dari
`GeoExplorer.tsx` supaya ikut bertema.

`npm run typecheck` dan `next build` hijau.

### Bagian 2 — API publik: enam diuji, empat dipakai

Diuji langsung ke endpoint produksinya, bukan dari dokumentasi vendor:

| API | Kunci | Hasil uji |
|---|---|---|
| Wikimedia Pageviews | tidak perlu | ✅ 200, data id.wikipedia nyata |
| Open-Meteo Air Quality | tidak perlu | ✅ 200, PM2.5 per koordinat |
| BMKG Data Terbuka | tidak perlu | ✅ 200, gempa + koordinat |
| NASA FIRMS | gratis, daftar email | ⚠️ 401 tanpa kunci |
| BPS Web API | gratis, daftar | belum diuji |
| GDELT Doc API | tidak perlu | ❌ ditolak, batas laju 1 req/5 detik |

**GDELT tidak direkomendasikan.** Ia menolak permintaan berulang dari alamat
bersama dengan pesan batas laju, konsisten di beberapa percobaan berjarak.

### Bagian 3 — abstraksi baru: konektor DERET, bukan konektor KONTEN

`app/connectors/metrics.py` (baru) sejajar dengan `base.py`, bukan
turunannya. Alasannya bukan kerapian: `base.Connector` mengembalikan
`RawItem` (konten) yang lalu di-dedup dan dinilai sentimennya. Tampilan
halaman harian bukan konten. Memaksanya lewat `RawItem` akan salah di tiga
tempat sekaligus — `sentiment.score()` menilai string buatan seperti "142
tampilan" seolah pernyataan seseorang, `ingestion.dedupe()` menganggap hari
berangka mirip sebagai duplikat, dan tabel `mentions` terisi baris yang
bukan sebutan siapa pun.

Jadi `RawObservation` → `metric_snapshots`, tabel yang memang untuk itu dan
yang sudah dibaca `/forecast/baseline` serta `/opinion/trend`. **Tidak ada
satu pun modul lama yang diubah untuk mendukung ini** — ketiganya sudah
metrik-agnostik.

`RawObservation.__post_init__` menolak nilai di atas 99.999 (batas
`NUMERIC(8,3)`) alih-alih memotong diam-diam: deret yang terpotong di
puncaknya akan terbaca sebagai plateau yang tidak pernah terjadi.

**Baru:**
- `app/connectors/wikipedia.py` — Wikimedia Pageviews, `source=DIGITAL`
- `app/connectors/openmeteo.py` — PM2.5 per ibu kota provinsi, 20 provinsi
- `app/routers/metrics.py` — `GET /metrics/connectors`,
  `GET /projects/{id}/metrics`, `POST /projects/{id}/metrics/collect`
- `apps/web/app/(dashboard)/deret/` — halaman dashboard ke-18

### Yang SENGAJA tidak dilakukan, dan alasannya

**Open-Meteo TIDAK mengisi `geographic_spread`** — dan klaim awal ke pengguna
di sesi ini bahwa ia akan mengisinya adalah **salah, sudah dikoreksi**.
Komponen itu menghitung berapa provinsi yang PERCAKAPANNYA tersebar
(`routers/risk.py`: provinsi berbeda di antara mention bergeotag resmi).
Udara buruk di 12 provinsi bukan percakapan tersebar di 12 provinsi.
Mengisinya dari sini akan mengubah arti skor risiko diam-diam. Komponen itu
tetap kosong sampai ada mention yang benar-benar bergeotag.

Yang benar-benar dibuka Open-Meteo: lapisan per-provinsi dengan georeferensi
ASLI (koordinat terukur, bukan provinsi ditebak dari teks), yang memenuhi
syarat CLAUDE.md §6 untuk MapLibre — **untuk lapisan kualitas udaranya
sendiri, bukan untuk skor opini per provinsi.**

**`source=DIGITAL` untuk kualitas udara adalah kompromi yang perlu ditinjau
pengguna.** Tidak ada nilai `SignalSource` yang pas — enum-nya SURVEY /
SOCIAL / MEDIA / DIGITAL, dan pengukuran instrumen bukan salah satunya;
DIGITAL ("perilaku terukur") paling dekat tapi tetap meleset, kualitas udara
bukan perilaku. Yang benar secara desain adalah nilai enum baru (mis.
`SENSOR`), tapi itu butuh `ALTER TYPE signal_source ADD VALUE` di Supabase —
migrasi manual yang, persis kelas ini, menjatuhkan tiga halaman production
pada 2026-09-02. Tidak dilakukan diam-diam. Sampai diputuskan, setiap baris
membawa peringatan "pengukuran instrumen, BUKAN opini" di kolom `method`
yang ikut tampil di UI.

**Koordinat 18 provinsi sisanya tidak ditebak.** Yang masuk hanya 20 yang
kodenya dan ibu kotanya bisa dipastikan: 16 provinsi `db/seed.py` + 4
provinsi inti karhutla (Jambi, Kalbar, Kalteng, Kalsel). Provinsi hasil
pemekaran 2022 di Papua sengaja dilewati — koordinat salah akan tersimpan
sebagai georeferensi "asli", dan itu kesalahan paling mahal di modul ini.
Tes `test_koordinat_berada_di_kotak_indonesia` menjaga terhadap lintang/bujur
tertukar.

### Verifikasi

**49 tes baru, semuanya lulus lokal**, `ruff check app tests` bersih.
Keduanya parsing murni tanpa jaringan, sesuai CLAUDE.md §4.

**Diuji terhadap payload produksi sungguhan** (bukan hanya fixture):

- Wikipedia `Badan_Gizi_Nasional` di id.wikipedia, 1 Agu – 10 Sep 2026 →
  **41 pengamatan harian**, min 55 / maks 146, enam hari terakhir
  94 · 81 · 106 · 120 · 142 · 84.
- Open-Meteo Palangka Raya (Kalteng, `62`), 5–10 Sep 2026 → 6 hari, masing-
  masing dari 24 jam penuh. **PM2.5 210–526 µg/m³** — level berbahaya, dan
  konsisten dengan karhutla yang sedang berlangsung.

**Model forecast benar-benar di-fit atas deret nyata itu** (bukan
disimpulkan dari ambangnya): 1 pengamatan → `insufficient_data=True`;
41 pengamatan → `insufficient_data=False`, model "state-space (level lokal
+ tren), di-fit pada riwayat proyek", baseline 84.0, span 40 hari. Interval
di horizon 90 melebar ke ±480 dan `limitations` menyebut sendiri bahwa
bagian itu ekstrapolasi — gating berperilaku benar di data lapangan.

**391 tes lulus** setelah statsmodels terpasang (seluruh suite yang tidak
butuh database, termasuk `test_timeseries` dan `test_forecast` yang
sebelumnya terhalang dependensi).

**Satu bug ketemu dari pengecekan boot aplikasi, bukan dari tes:**
`routers/metrics.py` mengimpor `Role` dari `app.models.user` — modul yang
tidak ada (yang benar `app.deps`). `ruff` tidak menangkapnya (bukan
pelanggaran lint) dan tes konektor juga tidak (tidak mengimpor router).
Yang menangkapnya adalah `from app.main import app` — pengingat bahwa
"tes hijau" dan "aplikasi bisa menyala" adalah dua hal berbeda. Sudah
diperbaiki; `app.openapi()` sekarang mencantumkan ketiga endpoint baru
(total 58 endpoint terdaftar).

**Jahitan penuh diverifikasi terhadap Postgres sungguhan.** Docker memang
tidak ada di sandbox, tapi ternyata **Postgres 16 sudah berjalan langsung di
mesin pengguna** (Homebrew, port 5432) — jadi asumsi "butuh Docker" dari
sesi-sesi sebelumnya keliru. Database `pop_test` sementara dibuat, schema +
RLS diterapkan, lalu dijalankan lewat HTTP asli (httpx + ASGITransport)
dengan role `pop_app` dan `FORCE ROW LEVEL SECURITY` aktif:

```
4. forecast SEBELUM  → insufficient=True,  n=0
5. collect           → 200, fetched=60 stored=60, 2026-07-13..2026-09-10
6. collect ULANG     → stored=0 replaced=60        ← idempoten
7. GET /metrics      → n=60, national=true, latest=84.0
8. forecast SESUDAH  → insufficient=False, n=60, span=59 hari
                       model = state-space (level lokal + tren)
9. isolasi tenant    → org lain baca deret ini: 200 []
10. DELETE proyek    → 204, 60 baris metric_snapshots ikut terhapus
```

Dua hal terbukti di luar yang direncanakan: **idempotensi** (tarik ulang
rentang yang sama tidak menggandakan baris — kalau menggandakan,
`timeseries.fit()` akan melihat dua pengamatan di tanggal yang sama dan
lebar intervalnya mengecil palsu) dan **isolasi tenant** untuk ketiga
endpoint baru.

Dua catatan jujur tentang lingkungan verifikasi:

1. **`mentions` dan `topics` tidak ikut terbuat** — Postgres lokal tidak
   punya extension `vector`, dan `db/schema.sql` baris 8 membutuhkannya.
   Fitur ini tidak menyentuh kedua tabel itu, dan CI memakai
   `pgvector/pgvector:pg16` sehingga suite penuh tetap berjalan dengan
   keduanya ada.
2. **Role `pop` lokal perlu `BYPASSRLS`** supaya fungsi `SECURITY DEFINER`
   (`auth_register`) bisa menembus `FORCE ROW LEVEL SECURITY` di
   `organizations`. Di CI hal ini tidak terlihat karena `pop` adalah
   superuser kontainer (`POSTGRES_USER: pop`), dan superuser melewati RLS
   secara otomatis. Bukan perbedaan perilaku aplikasi — perbedaan
   provisioning. Relevan kalau nanti ada yang menyiapkan Postgres lokal
   tanpa Docker.

**Database `pop_test` beserta role `pop`/`pop_app` sudah dihapus lagi**
setelah verifikasi; mesin pengguna kembali seperti semula. Untuk
membuatnya ulang: `make test-db` (butuh `ADMIN_DATABASE_URL`).

**CI PR #9 hijau penuh** — backend (suite lengkap, role `pop_app`, RLS
aktif), frontend, dan Vercel preview. Jadi 49 tes baru itu **sudah
terkonfirmasi CI**, bukan cuma lokal.

### Di-merge dan diverifikasi tayang — 2026-09-11 16:17 UTC

Di-merge atas persetujuan eksplisit pengguna, lalu **diperiksa benar-benar
hidup**, bukan diasumsikan karena CI hijau:

- **Vercel** — diperiksa dari bundel CSS yang sungguh dilayani (bukan dari
  build lokal): `--ink:#EDF1F6`, `--panel:#FFFFFF`, `--survey:#0B6FD4` ada;
  `[data-theme=dark]` beserta `--ink:#0A1017`/`--survey:#4DA3FF` juga ada,
  jadi tema gelap tetap bisa dipilih; skrip boot
  `localStorage.getItem("pop-theme")` ada di HTML `/login`; kelas
  `.auth-wrap`/`.theme-btn`/`.form-err`/`.btn-ghost` ada.

  Catatan kecil supaya tidak membingungkan sesi berikutnya: minifier
  menghapus tanda kutip, jadi yang tampak di bundel adalah
  `[data-theme=dark]`, bukan `[data-theme="dark"]`. Dan kemunculan
  `#080D13` di bundel BUKAN literal warna yang tertinggal — itu nilai token
  `--nav-bg` di dalam blok tema gelap, persis seperti seharusnya.

- **Render** — `/v1/metrics/connectors` berubah `404` → `401`, lalu dengan
  akun test yang didaftarkan sendiri membalas kedua konektor lengkap dengan
  `notes` metodologisnya. Proyek uji yang dibuat untuk ini **sudah dihapus**
  (`DELETE` → 204, dikonfirmasi 404).

**Satu bug production ditemukan dari verifikasi ini** — sudah **selesai
2026-09-12**; lihat bagian "Wikimedia menolak Render dengan 403" di bawah,
dan blok "MULAI DARI SINI" di kepala dokumen ini.

## ✅ Wikimedia menolak Render dengan 403 — SELESAI, PR #10 di-merge 2026-09-12

> **Bagian ini adalah riwayat penyelidikannya.** Kesimpulan akhirnya ada di
> ujung bagian ini — dan salah satu hipotesis di tengah terbukti KELIRU, jadi
> jangan berhenti membaca di tengah.

Ditemukan saat memverifikasi PR #9 di production, bukan dari tes:
`POST /projects/{id}/metrics/collect` membalas **502** dengan
`"Wikimedia menolak permintaan (403)"`. Jalur yang sama lulus dari mesin
lokal beberapa menit sebelumnya.

**Diselidiki dulu sebelum menambal.** Tiga varian diuji terhadap endpoint
Wikimedia yang sama dari mesin lokal:

| User-Agent | Hasil |
|---|---|
| UA lama konektor | **200** |
| tanpa UA sama sekali | 403 — "Please set a user-agent and respect our robot policy https://w.wiki/4wJS" |
| UA dengan URL kontak | **200** |

Artinya **UA lama bukan penyebabnya** dari IP rumahan. Hipotesis terkuat saat
itu: alamat IP datacenter Render kena kebijakan robot Wikimedia — pesan 403
Wikimedia sendiri menyebut `phabricator T400119`.

> **Hipotesis itu ternyata salah** — lihat "Hasil sesudah merge" di bawah.
> Kekeliruannya bisa dilacak: seluruh tabel di atas diukur dari **satu** IP
> (mesin lokal), lalu kesimpulannya ditarik untuk IP yang lain (Render).
> Variabel yang berubah antara "berhasil" dan "gagal" sebenarnya ada dua —
> UA *dan* IP — tapi cuma satu yang divariasikan.

[PR #10](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/10)
berisi dua perbaikan yang berguna terlepas dari akar masalahnya:

1. **User-Agent memuat titik kontak yang benar-benar bisa dibuka** (URL repo
   ini). Kebijakan Wikimedia meminta pemanggil otomatis menyebut diri DAN
   menyertakan kontak; versi lama menulis "contact via platform admin", yang
   bukan kontak apa pun. Tetap BUKAN string peramban — menyamar dilarang di
   `connectors/base.py`.
2. **Badan respons Wikimedia diteruskan apa adanya** ke `ConnectorError`,
   bukan cuma kode statusnya. Ini yang akan menjawab pertanyaannya: pesan
   lama tidak memberi satu pun petunjuk apakah 403-nya soal UA, kebijakan
   robot, atau IP — padahal Wikimedia menjelaskannya sendiri di badan
   respons lengkap dengan tautan kebijakan.

### Hasil sesudah merge (2026-09-12)

PR #10 di-merge **15:41 UTC**. Render redeploy sendiri. Dua panggilan
`POST /projects/{id}/metrics/collect` dilakukan dari akun test, project, dan
payload yang identik (`wikipedia_pageviews`, `id.wikipedia`,
`Prabowo Subianto`, 30 hari), berjarak ~90 detik:

| Waktu (UTC) | Build | Hasil |
|---|---|---|
| 15:42 | UA lama, redeploy belum masuk | `502` — `"Wikimedia menolak permintaan (403)"` |
| 15:43 | UA baru | **`200`** — `fetched: 30, stored: 30` |

**Perbaikan #1 (User-Agent) yang menyelesaikannya.** Hipotesis IP datacenter
keliru: IP Render tidak diblokir — IP yang sama berhasil begitu UA-nya memuat
titik kontak yang bisa dibuka. Yang sebenarnya terjadi: **UA lama diterima
dari IP rumahan tapi ditolak dari IP datacenter.** Kebijakan UA Wikimedia
ditegakkan lebih ketat terhadap IP datacenter, bukan diblokir buta. Pola
"tarik dari mesin lokal lalu kirim lewat endpoint" tidak jadi diperlukan.

**Perbaikan #2 (meneruskan badan respons) belum terpakai di lapangan** — dan
itu sengaja dicatat, bukan dianggap terbukti. Setelah UA diperbaiki tidak ada
403 lagi untuk diteruskan, jadi jalur itu belum pernah dipicu production.
Nilainya sekarang bersifat pencegahan untuk kegagalan berikutnya.

**Verifikasi lanjutan yang ikut lolos**, semuanya dari Render production:

- `GET /projects/{id}/metrics` → 30 observasi, `latest_value: 1207.0`,
  `is_national: true`. Data benar-benar mendarat di Postgres, bukan cuma
  respons 200.
- `collect` dipanggil ulang → `stored: 0, replaced: 30`. Idempoten: deret
  di-*replace*, tidak diduplikasi.
- `openmeteo_air_quality` (`province_code: 31`) → `200`, 30 titik PM2.5 DKI
  Jakarta. **Pertama kalinya konektor ini terbukti jalan dari Render** —
  sebelumnya seluruh jalur `collect` tertutup oleh 403 di atas, jadi ia
  "tidak terpengaruh" secara teori tapi tetap belum pernah dibuktikan.
- `GET /forecast/baseline?metric=pageviews_prabowo_subianto` → `200`,
  `insufficient_data: false`, model state-space ter-*fit* dari 30 titik itu,
  dan `limitations` menandai horizon 90 hari sebagai ekstrapolasi karena
  riwayatnya cuma 29 hari. **Rantai penuh collect → Postgres → forecast
  terbukti dari production**, bukan cuma dari Postgres lokal.

Project uji untuk verifikasi ini sudah dihapus (`DELETE` → 204, `GET`
sesudahnya → 404).

**Pelajaran yang layak dibawa ke konektor berikutnya:** menguji konektor dari
mesin lokal saja tidak membuktikan konektor itu jalan dari production. Kalau
sebuah konektor baru gagal 403 dari Render, curigai User-Agent lebih dulu
sebelum menyimpulkan IP-nya diblokir.

Yang tidak terpengaruh sama sekali sepanjang insiden ini: seluruh tampilan
tema terang, dan kedua project riset pengguna.

## Yang masih kurang (di luar langkah CORS di atas)

### Residual Phase 1
- ~~2 halaman dashboard tersisa~~ — **selesai**, lihat bagian "Executive
  Brief" di atas. 9/9 halaman dashboard sudah di-port.
- ~~`/auth/register` tidak punya UI~~ — **selesai 2026-08-27**, lihat
  bagian "Registrasi self-service" di atas.
- ~~Belum ada project switcher~~ — **selesai 2026-08-27**, lihat bagian
  "Project switcher" di atas.
- ~~Belum ada UI edit/hapus proyek~~ — **selesai 2026-08-27**, lihat
  bagian "Edit/hapus proyek" di atas.
- ~~"Isu publik" dan "Peringatan aktif" sengaja tidak dirender di Command
  Center~~ — **selesai 2026-09-02**, lihat bagian "Sesi lanjutan Phase 2/3"
  di bawah. `services/alerts.py` (anomaly detection z-score) sekarang ada,
  dan Command Center menariknya bersama topic discovery.
- ~~**Bug dorman belum diperbaiki**: `AIOutput.confidence` dan
  `AIOutput.human_review`~~ — **sudah diperbaiki**, ternyata di sesi
  2026-08-27 bersama Executive Brief (lihat bagian "Executive Brief" di atas
  yang mencatatnya). Daftar residual ini yang tidak ikut diperbarui.
  Diverifikasi ulang 2026-09-01: `models/governance.py` memakai
  `SAEnum(..., create_type=False)` untuk kedua kolom, dan baris `ai_outputs`
  yang ditulis Copilot terbaca kembali dengan benar lewat tes
  `test_copilot_router.py::test_jawaban_tercatat_di_ai_outputs`.

### Infrastruktur & operasional
- Render free tier: server tidur setelah 15 menit tidak dipakai, request
  pertama setelah itu lambat 30-60 detik.
- Belum ada custom domain — masih `.vercel.app` dan `.onrender.com`.
- ~~Belum ada CI~~ — selesai 2026-08-24, lihat bagian "Pengerasan Phase 1"
  di atas.

### Phase 2 & 3 — sebagian besar selesai 2026-09-01
Lihat bagian "Phase 2 + Phase 3 dikerjakan" di bawah. `docs/roadmap.md` memuat
status per-item beserta apa yang SENGAJA belum dikerjakan dan alasannya.

### Phase 4 — enterprise (belum dimulai)
Multi-agent orchestration, SSO/SAML/MFA, API publik + webhook, report
generator (PDF/DOCX/PPTX/XLSX), billing, observability (tracing, evaluasi
model, deteksi drift).

Sengaja tidak disentuh, bukan kehabisan waktu: fase ini butuh keputusan yang
bukan wewenang agen — penyedia identitas untuk SSO, penyedia pembayaran untuk
billing, dan komitmen kontrak API publik yang tidak bisa ditarik lagi setelah
ada yang memakainya. Sesuai CLAUDE.md §8, lebih baik berhenti dan bertanya.


## ✅ Phase 2 + Phase 3 dikerjakan — 2026-09-01

Sesi panjang atas instruksi "kerjakan semua yang belum". Backend dari 115 ke
387 tes, paket `app/connectors/` baru, enam halaman frontend baru.

### Yang dibangun

| Bagian | Berkas inti |
|---|---|
| Model sinyal | `app/models/signal.py` (Mention, Topic, DataSource) |
| Pipeline ingestion | `app/services/ingestion.py`, `app/services/pipeline.py` |
| Sentiment Indonesia | `app/services/sentiment.py` + `sentiment_eval.py` |
| Konektor | `app/connectors/` — RSS, YouTube, X, unggahan manual |
| Topic discovery | `app/services/topics.py` |
| Copilot RAG | `app/ai/retrieval.py`, `app/ai/copilot.py` |
| Forecast state-space | `app/services/timeseries.py` |
| Opinion Risk Score | `app/services/risk.py:partial_risk_score()` |
| Influence estimate | `app/services/influence.py` |
| Communication Impact | `app/services/impact.py` |
| Frontend | `/sinyal`, `/tema`, `/copilot`, `/risiko`, `/pengaruh`, `/dampak` |

### Keputusan yang perlu diketahui sesi berikutnya

**Topic discovery memakai TF-IDF, bukan embedding.** Roadmap menulis
"embedding -> HDBSCAN -> label LLM"; yang dijalankan TF-IDF -> LSA -> HDBSCAN
-> label kata kunci, dan `method` mengembalikan yang benar-benar dipakai.
Belum ada provider embedding yang dikonfigurasi. Titik penggantinya satu
fungsi (`_vectorize`); **label metodenya WAJIB ikut berubah di commit yang
sama** saat itu diganti, kalau tidak metadata berbohong (R1).

**Dimensi LSA diikat ke ukuran korpus.** 24 dokumen di 23 dimensi
menghasilkan NOL klaster (kepadatan menguap di dimensi tinggi); korpus yang
sama di 3 dimensi memisahkan temanya bersih. Jangan menaikkan
`SVD_COMPONENTS` tanpa memperhitungkan `DOCUMENTS_PER_COMPONENT`.

**Risk score memakai `partial_risk_score()`, bukan `risk_score()`.** Yang
kedua tetap ada dan tetap menolak tanpa komponen lengkap. Yang pertama
menghitung dari komponen yang tersedia, menolak di bawah cakupan bobot 60%,
dan selalu mengembalikan `coverage`. Jangan menurunkan `MIN_COVERAGE` supaya
kartunya terisi.

**Skala komponen risiko belum dikalibrasi.** `SENTIMENT_DROP_AT_FULL_RISK`,
`GROWTH_PCT_AT_FULL_RISK`, dan `POINT_DECLINE_AT_FULL_RISK` adalah penilaian
tim, bukan hasil kalibrasi terhadap krisis nyata. Karena itu skornya untuk
membandingkan periode atau proyek berskala sama, bukan ambang absolut — dan
kalimat itu tampil di UI, bukan cuma di kode.

**Communication Impact menolak tanpa pembanding, tanpa jalan pintas.**
`NoControlGroup` bukan kekakuan yang bisa dilonggarkan nanti: ia satu-satunya
penjaga antara platform ini dan klaim kausal yang tidak bisa
dipertanggungjawabkan. `AIEnvelope._has_causal_design()` mengizinkan bahasa
kausal justru karena modul ini ada.

**Env var baru: `AUTHOR_HASH_SALT`.** Kosong = diturunkan dari `JWT_SECRET`
lewat HMAC berpemisah domain, supaya deployment berjalan tidak mendadak gagal
ingest karena ada env var baru. Kalau mau diset eksplisit, **setel sekali di
awal**: menggantinya setelah ada data membuat akun yang sama terhitung
sebagai dua akun berbeda sebelum dan sesudah pergantian. `YOUTUBE_API_KEY`
dan `X_BEARER_TOKEN` juga baru; keduanya opsional, konektornya membalas 503
yang menyebut nama env var-nya kalau kosong.

### Dua bug yang ketahuan lewat verifikasi, bukan lewat build

1. **Keadaan awal `useActionState` sempat diekspor dari modul `"use server"`.**
   Modul itu hanya boleh mengekspor fungsi async; objeknya sampai ke client
   sebagai `undefined` dan `/dampak` jatuh dengan "Cannot read properties of
   undefined". **`next build` dan `tsc --noEmit` sama-sama hijau untuk kode
   itu.** Ketahuan hanya karena halamannya benar-benar dibuka di browser.
   Catatan pencegahnya sekarang ada di ketiga `actions.ts`.
2. **`zip(dates, dates[1:], strict=True)`** di `timeseries.py` — `strict=True`
   menuntut panjang sama, padahal `dates[1:]` memang satu lebih pendek.
   Ketahuan lewat tes.

### Yang diverifikasi, dan bagaimana

Postgres 16 + pgvector lokal (cluster `initdb` sendiri di kontainer sesi,
bukan Docker — Docker tidak jalan di sana), API asli lewat uvicorn, Next.js
hasil `next build` asli, dan Chromium lewat Playwright:

- **387 tes hijau** dengan role `pop_app` (RLS aktif, BUKAN superuser),
  termasuk tes isolasi tenant baru untuk mentions, data_sources, topics,
  riwayat copilot, risk score, influence, dan impact.
- `ruff check app tests` dan `mypy app/services app/ai app/connectors` bersih
  100%. `npm run typecheck` + `next build` bersih.
- 160 konten percakapan dimasukkan lewat `POST /signals/ingest` sungguhan ->
  14 tema ditemukan (10.6% tidak terpetakan) -> skor risiko 62 "High" dengan
  cakupan 78% dan 3 komponen dilaporkan hilang -> 25 akun, 20 diperingkat.
- Keenam halaman baru dibuka di browser setelah melewati gerbang
  `SITE_PASSWORD` dan login user asli. Tombol "Temukan tema" benar-benar
  menulis dan melaporkan porsi yang tidak terpetakan; Copilot menolak bersih
  saat provider belum siap (bukan Application error); form dampak menolak
  tanpa pembanding dengan alasan lengkap.

### Yang BELUM diverifikasi — baca ini sebelum mengklaim apa pun ke pengguna

- **Tidak ada satu pun yang diuji terhadap Supabase produksi.** Seluruh
  verifikasi di atas memakai Postgres lokal di kontainer sesi. Langkah
  lanjutan: tunggu Render + Vercel redeploy setelah push, lalu ulangi
  pemeriksaan manual terhadap production (butuh login `SITE_PASSWORD`, yang
  di luar kemampuan Claude — lihat aturan boundary kredensial di atas).
- **Konektor RSS/YouTube/X belum pernah menarik data sungguhan.** Yang dites
  adalah parsing responsnya (fungsi murni) dan penanganan kredensial kosong.
  Menarik sungguhan butuh kunci di Render, dan untuk RSS butuh jaringan
  keluar dari Render ke penerbitnya.
- **Copilot belum pernah menjawab dengan LLM sungguhan.** Jalur suksesnya
  diuji lewat provider tiruan yang mengembalikan JSON valid — yang terbukti
  adalah pipa di sekelilingnya (envelope tersusun benar, baris `ai_outputs`
  tertulis dan terbaca kembali), BUKAN mutu jawaban model. Sama seperti
  Executive Brief, ini menunggu `ANTHROPIC_API_KEY` aktif di Render.
- **Forecast state-space belum pernah di-fit pada data produksi.** Seed
  Supabase hanya punya satu snapshot per metrik, jadi `/forecast/baseline`
  akan membalas `insufficient_data` di sana sampai ada gelombang kedua. Itu
  perilaku yang benar, bukan bug.
- **Akurasi sentimen yang tampil di `/sinyal` adalah batas ATAS.** Ia diukur
  pada 52 kalimat yang ditulis tim pengembang, bukan pada percakapan proyek
  mana pun. Sebelum dipakai untuk keputusan, ukur ulang terhadap sampel
  berlabel dari data proyek itu sendiri.

## ✅ Sesi lanjutan Phase 2/3 — selesai 2026-09-02

Kelanjutan langsung sesi 2026-09-01, dengan instruksi yang sama: "kerjakan
semua yang belum selesai, lakukan yang terbaik". Enam pekerjaan yang di sesi
sebelumnya tercatat sengaja belum dikerjakan atau baru separuh jalan, semua
ditutup di sesi ini. Enam commit, semua di branch
`claude/repo-ini-comparison-ior2z4` (PR #1), CI hijau di keenamnya.

### Yang dibangun

| Bagian | Berkas inti |
|---|---|
| Command Center: Isu publik + Peringatan aktif | `app/(dashboard)/command/page.tsx` menarik `/topics` dan `/alerts` yang sudah ada |
| Anomaly detection (baru) | `app/services/alerts.py`, `app/routers/alerts.py` — `GET .../alerts` |
| Verifikasi manusia atas label tema (baru) | kolom `topics.reviewed_label`/`review_status`, `PATCH .../topics/{id}/review`, `ReviewTopic.tsx` |
| Synthetic control (baru, Communication Impact) | `services/impact.py:synthetic_control()`, `POST .../impact/synthetic-control`, panel kedua di `/dampak` |
| Graf jaringan interaksi (baru) | `services/network.py`, `GET .../network`, halaman `/jaringan` baru; `connectors/x.py` mengekstrak `referenced_tweets` |
| `lib/api.ts` — bugfix nyata | 422 dari validasi Pydantic (array objek) tidak lagi tampil sebagai `[object Object]` |

### Keputusan yang perlu diketahui sesi berikutnya

**Anomaly detection adalah z-score terhadap baseline historis DERET SENDIRI,
bukan deteksi krisis.** `services/alerts.py` membandingkan titik terakhir
suatu deret (volume/sentimen harian, snapshot metrik) dengan rata-rata dan
simpangan baku titik-titik sebelumnya di deret yang SAMA. Kalau baseline-nya
nyaris rata (SD ~0), z-score meledak jadi tak berarti — ada fallback ke
ambang perubahan relatif untuk kasus itu. `method` dan `limitations`
eksplisit menyebut ini BUKAN penilaian krisis. `MIN_BASELINE_POINTS=4`:
deret yang lebih pendek dari itu dilaporkan "belum bisa diperiksa", beda
dari "diperiksa, tidak ada penyimpangan" — dua keadaan itu tidak boleh
disamakan di UI.

**`topics.review_status` memakai ULANG tipe Postgres `review_status`** yang
tadinya cuma untuk `ai_outputs.human_review` (lihat sesi 2026-08-27). Kolom
baru: `reviewed_label`, `review_status`, `reviewed_by`, `reviewed_at`. Label
asli (`label`, dari kata kunci TF-IDF) TIDAK PERNAH ditimpa — yang disunting
manusia disimpan terpisah supaya keduanya bisa dibandingkan.
`effective_label()` cuma mengganti label yang ditampilkan kalau
`review_status == APPROVED`; ditolak atau masih pending tetap menampilkan
label asli. **Migrasi kolom ini BELUM diterapkan ke Supabase production**
(lihat di bawah).

**Synthetic control (Abadie, Diamond & Hainmueller) butuh periode
pra-perlakuan LEBIH BANYAK dari jumlah donor**, bukan sekadar donor yang
banyak. Kalau tidak, kecocokan pra-perlakuan bisa sempurna secara trivial
(derajat kebebasan cukup untuk overfit) tanpa berarti apa-apa —
`MIN_DONORS=5` menjamin itu, bukan angka sembarang. Signifikansinya dari uji
permutasi placebo (leave-one-out pada donor) → `rank_p_value`, secara
eksplisit BUKAN p-value parametrik — jangan pernah dilabeli "p-value" polos
di UI mana pun nanti.

**Graf jaringan SELALU sebagian, dan itu bukan cacat yang bisa
diperbaiki.** Ia cuma memuat relasi antar akun yang KEDUANYA muncul sebagai
penulis dalam data yang berhasil diambil konektor. Akun yang dibalas tapi
tidak ikut terambil (di luar jendela pencarian X, di luar kueri) tidak
tercatat sebagai nol — tidak tercatat sama sekali. `MIN_ACCOUNTS=10`,
`MIN_EDGES=15`. Tidak menyimpulkan koordinasi atau kendali atas opini
(CLAUDE.md §3) — istilahnya "posisi struktural", bukan "pengaruh".
**Migrasi kolom `mentions.reply_to_hash`/`quote_of_hash`/`conversation_id`
juga BELUM diterapkan ke Supabase production.**

**Lingkungan sesi ini sempat benar-benar kosong** — kontainer baru tanpa
role/database Postgres sama sekali (bukan sekadar server yang mati). Role
`pop`/`pop_app` dan tiga database (`pop`, `pop_test`, `pop_ci`) dibangun
ulang dari `db/schema.sql` + `db/rls.sql` sebelum satu pun tes bisa
dijalankan. Ini fakta lingkungan sesi, bukan sesuatu yang rusak di produk —
dicatat di sini supaya sesi berikutnya tidak bingung kalau mengalami hal
yang sama.

### Bug ditemukan lewat verifikasi browser, bukan lewat build

**`lib/api.ts` menampilkan `[object Object]` untuk error validasi
Pydantic.** `HTTPException(422, "pesan")` dari kode aplikasi mengembalikan
`detail` berupa string, tapi 422 dari validasi Pydantic BAWAAN (mis. daftar
donor kurang dari minimum) mengembalikan `detail` berupa ARRAY objek
`{msg, loc, ...}`. `ApiError` lama menelan itu lewat
`Array.prototype.toString()` → `"[object Object]"`, tidak berarti apa-apa
bagi pengguna. `tsc --noEmit` dan `next build` sama-sama hijau untuk kode
lama — ketahuan hanya karena mencoba jalur penolakan (donor < 5) sungguhan
di browser. `detailToMessage()` sekarang menyusun pesan dari field `msg`
tiap item.

### Yang diverifikasi, dan bagaimana

- **473 tes backend hijau** (387 → 473; 86 baru) dengan role `pop_app`, RLS
  aktif, BUKAN superuser. `ruff check app tests` dan
  `mypy app/services app/ai app/connectors` bersih 100%.
- `npm run typecheck` + `next build` bersih untuk kedua halaman baru
  (`/dampak` dengan panel synthetic control, `/jaringan` baru).
- **Empat halaman diverifikasi lewat browser sungguhan (Playwright)**
  terhadap API asli (uvicorn) + Postgres lokal asli, bukan cuma build
  hijau: Command Center (kartu Isu publik + Peringatan aktif, tombol
  "Tinjau label" → "Setujui"), `/dampak` (jalur sukses synthetic control
  dengan bobot donor & efek yang cocok dengan perhitungan tangan, DAN jalur
  penolakan donor < 5), `/jaringan` (jalur data cukup dengan hash + in-degree
  yang benar, DAN jalur data tidak cukup).
- CI GitHub Actions hijau di keenam push sesi ini; PR #1 `mergeable_state:
  clean`, tanpa review thread yang belum diselesaikan.

### Yang BELUM diverifikasi

- ~~Belum di-merge ke `main`~~ — **PR #1 sudah di-merge ke `main`
  (commit `ad6a3f0`)** atas persetujuan eksplisit pengguna. Semua
  verifikasi di atas tetap memakai Postgres lokal kontainer sesi, bukan
  Supabase — merge memicu redeploy Render+Vercel dari `main`, tapi belum
  ada pemeriksaan manual pasca-deploy terhadap production sungguhan (butuh
  login `SITE_PASSWORD`, di luar kemampuan agen).
- **Migrasi skema untuk kolom baru BELUM diterapkan ke Supabase**: kolom
  review topics (sesi ini) dan kolom relasi balasan/kutipan mentions (sesi
  ini). `db/schema.sql` sudah memuat keduanya untuk instalasi baru, tapi
  tabel yang sudah ada di Supabase butuh `ALTER TABLE ... ADD COLUMN IF NOT
  EXISTS ...` manual per kolom sebelum fitur review label atau `/jaringan`
  bisa dipakai di production.
- **Konektor X masih belum pernah menarik data sungguhan** (sama seperti
  sesi 2026-09-01) — parsing `referenced_tweets`/`conversation_id` yang baru
  ditambahkan sesi ini teruji lewat payload buatan (fungsi murni), bukan
  lewat panggilan API X asli. Butuh `X_BEARER_TOKEN` di Render.

## ✅ Verifikasi RSS sungguhan + perbaikan leksikon sentimen — 2026-09-02 (sesi kedua)

Instruksi pengguna: kerjakan migrasi Supabase dan env var Render sendiri
(butuh kredensial production); sambil menunggu, agen mengerjakan apa pun
yang genuinely bisa dikerjakan tanpa kredensial itu, dan tidak menyentuh
Phase 4 tanpa bertanya. Sandbox sesi ini **tidak punya Docker/Postgres yang
jalan** (Docker Desktop terpasang tapi daemon-nya mati, WSL "Stopped") dan
**tidak punya akses ke Supabase/Render/Vercel** — jadi verifikasi di sesi
ini murni terhadap jaringan publik + fungsi murni lokal, bukan terhadap
database atau deployment mana pun.

### Yang dikerjakan

**Konektor RSS ditarik terhadap feed sungguhan untuk pertama kalinya.**
`RSSConnector().fetch()` — kode produksi apa adanya, dipanggil lewat skrip
mandiri di venv Python terisolasi (dependency minimal: sqlalchemy,
pydantic-settings, asyncpg, httpx — cukup untuk mengimpor modulnya tanpa
menyalakan seluruh aplikasi) — dipakai untuk menarik 5 feed media Indonesia:
Antara News, CNN Indonesia, Tempo, Republika, CNBC Indonesia. 215 dari 250
item diambil berhasil. Dua kandidat URL yang dicoba lebih dulu (Kompas,
Detik) ternyata 404/gagal koneksi — bukan bug konektor, URL feednya memang
sudah pindah/mati (dicoba beberapa varian URL, semuanya gagal) — jadi
diganti dengan Republika + CNBC Indonesia yang terbukti masih hidup.
Konektor menangani kedua kegagalan itu dengan bersih (`ConnectorError` yang
bisa dibaca, bukan crash).

Ke-215 item nyata itu lalu dijalankan lewat pipeline ingestion+sentiment
ASLI (`app/services/ingestion.py`, `app/services/sentiment.py` — tidak
ditulis ulang, dipanggil langsung): `normalize_text`, `detect_language`,
`dedupe` (MinHash+LSH), `sentiment.score`. Tidak ada satu exception pun atas
data lapangan yang beragam (5 struktur feed berbeda, judul+ringkasan dari
gaya penulisan berbeda-beda). Deteksi bahasa: 200-202/215 "id" (angka
berubah antar dua kali jalan karena feednya LIVE — artikel baru masuk,
lama keluar dari jendela top-50, bukan karena kode berubah). Dedup: 0
duplikat exact/near di antara 215 item (feed berbeda outlet, wajar tidak
ada salinan).

**Bug leksikon sentimen nyata ditemukan lewat data lapangan, bukan lewat
52 kalimat set evaluasi tim.** Dari 44 item yang ternilai (sentiment
abstain 79.5% — 171/215, jauh lebih tinggi dari kesan yang mungkin didapat
dari set evaluasi), 40 dibaca manual satu-per-satu (bukan evaluasi
berlabel formal — satu penilai, sekali baca, bukan pengganti langkah
"ukur ulang terhadap sampel berlabel" yang sudah dicatat sejak sesi
2026-09-01). Ditemukan: kata **"asal"** (arti "berasal dari") ada di
leksikon negatif (arti "asal-asalan"/ceroboh) dengan bobot -0.5, dan di
sampel ini memicu skor negatif salah pada 2 dari 2 kemunculannya — keduanya
konstruksi kebangsaan yang netral sepenuhnya ("aktor **asal** Inggris
Raya", "aktris **asal** Korea Selatan"), bukan sekali pun dalam arti
ceroboh.

**Diperbaiki**: entri `"asal": 0.5` dihapus dari `_NEGATIVE` di
`app/services/sentiment.py`, dengan komentar penjelas alasannya langsung di
kode (supaya tidak ditambahkan lagi tanpa konteks ini). Tokenizer memisah
tanda hubung (`normalize_text` membuang non-word char), jadi "asal-asalan"
pun pecah jadi token "asal" + "asalan" terpisah — entri tunggal ini memang
tidak bisa membedakan kedua makna tanpa konteks kata di sekitarnya, di luar
kemampuan leksikon kata-tunggal. Tes regresi baru:
`test_asal_negara_tidak_lagi_dianggap_negatif` di
`apps/api/tests/test_sentiment.py` (kelas baru `TestKataAmbigu`).

**Diverifikasi tidak menurunkan mutu di set evaluasi 52 kalimat**: kata
"asal" tidak muncul sama sekali di `sentiment_eval.py:LABELED`, jadi
`evaluate(LABELED)` tidak terpengaruh sama sekali oleh perubahan ini — bukan
trade-off yang harus ditimbang, murni perbaikan bersih. Dikonfirmasi lokal
(`tests/test_sentiment.py` — 31 tes, semuanya lulus, sebelum dan sesudah
perubahan) dan `tests/test_ingestion.py` + `tests/test_connectors.py` (86
tes murni tanpa DB total, semuanya lulus) di venv terisolasi tanpa Postgres
sama sekali — modul-modul ini murni (CLAUDE.md §4), jadi tidak butuh
database untuk dites. `ruff check` dan `mypy --strict` bersih untuk
`app/services/sentiment.py`.

**Dua temuan lain dicatat, sengaja TIDAK diperbaiki** (di luar cakupan yang
bisa diverifikasi aman tanpa risiko regresi baru):
1. Judul-judul berbeda tentang program pemerintah yang sama ("Apresiasi
   Pemerintah Daerah Berprestasi") membanjiri skor positif hanya karena kata
   "apresiasi" ada di NAMA program itu, bukan karena tiap artikel menyatakan
   sikap sendiri — keterbatasan struktural leksikon kata-tunggal terhadap
   nama proper berulang, bukan bug satu kata yang bisa dihapus seperti
   "asal".
2. Sarkasme dan eskalasi krisis (jumlah korban meninggal yang bertambah)
   tetap tidak terbaca benar — persis batas yang sudah diakui docstring
   modul sejak awal proyek, sekarang ada contoh konkretnya dari data nyata.

Detail lengkap (215 item, 44 skor, alasan tiap keputusan) ada di
`docs/progress.md` bagian "Yang BELUM diverifikasi" poin 2 dan 5 — dokumen
ini sengaja tidak mengulang semuanya supaya tidak ada dua sumber kebenaran
yang bisa berbeda.

### Yang sudah dikonfirmasi lewat CI (bukan cuma lokal)

**473 → 474 tes backend dikonfirmasi hijau lewat CI GitHub Actions**
([run `33590975725`](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/actions/runs/33590975725),
dipicu oleh [PR #2](https://github.com/mahendrasenoaji-lgtm/public-opinion-platform/pull/2)) —
`474 passed` terhadap Postgres asli (image `pgvector/pgvector:pg16`, role
`pop_app`, RLS aktif, bukan superuser), bukan cuma lokal tanpa DB. `ruff` dan
`mypy --strict` (`app/services app/ai app/connectors`) juga bersih di CI
yang sama. Frontend (`typecheck` + `next build`) juga hijau, meski tidak ada
kode frontend yang disentuh sesi ini — dijalankan karena satu PR memicu
kedua job. Lokal (venv tanpa Postgres, Docker tidak tersedia di sandbox
sesi ini) sebelumnya hanya sempat memverifikasi 87 tes murni tanpa DB
(`test_sentiment.py`, `test_ingestion.py`, `test_connectors.py`) — CI di
atas adalah verifikasi PERTAMA yang mencakup seluruh 474 tes untuk
perubahan sesi ini.

### Yang BELUM diverifikasi dari pekerjaan sesi ini

- Tarikan RSS ini terjadi di luar aplikasi sepenuhnya (skrip mandiri, bukan
  lewat `POST .../signals/collect`, bukan lewat Postgres, bukan dari
  Render). Jalur endpoint asli + database + dari Render sendiri ke
  penerbit masih belum diuji terpisah.
- Migrasi kolom Supabase dan env var Render (`ANTHROPIC_API_KEY` dkk.) —
  seperti diminta pengguna di awal sesi ini — **tetap belum dikerjakan**,
  itu memang eksplisit tugas pengguna sendiri, bukan residual yang
  terlewat.

Update 2026-09-02 (sesi keempat hari yang sama): pengguna mengonfirmasi
lewat prompt sesi ini bahwa PR #3 dan #4 belum di-merge sendiri. Diminta
konfirmasi eksplisit ("Merge keduanya sekarang"), lalu **PR #4 dan PR #3
di-merge ke `main`** (`gh pr merge --squash --delete-branch`, commit
`a3e9462` dan `3e082a8`). Render + Vercel akan redeploy `main` otomatis —
**mitigasi crash sudah di jalur deploy**, tapi migrasi kolom Supabase
(SQL lengkap di bagian "Fix crash Command Center" di bawah) **masih
tugas pengguna**, sesuai batas kredensial yang sama seperti sebelumnya.
Verifikasi production sungguhan (login `SITE_PASSWORD` manual) juga masih
menunggu pengguna. Sisa waktu sesi ini dipakai untuk kerja yang genuinely
bisa tanpa kredensial itu — lihat update berikutnya kalau ada.
Update 2026-09-02 (masih sesi keempat): **migrasi kolom Supabase
dijalankan pengguna** lewat SQL Editor dashboard Supabase (project
`publicopinion`, org `ALWAYSLEARN`, branch `main PRODUCTION`) — SQL
persis seperti di deskripsi PR #4 (lihat bagian "Fix crash Command
Center/Tema/Jaringan" di bawah), hasil `Success. No rows returned`.
Pengguna login Supabase sendiri lewat Chrome; Claude membuka tab ke SQL
Editor yang benar dan membaca hasilnya via screenshot (teks query yang
tereksekusi dicocokkan baris demi baris dengan yang diminta — sama), tapi
**tidak mengetik SQL-nya sendiri** — classifier izin Claude Code menolak
aksi `cmd+a` dan `type` di halaman itu (kemungkinan karena tergolong
perubahan skema database production), jadi pengguna yang paste+klik Run
manual. Kolom `topics.reviewed_label`/`review_status`/`reviewed_by`/
`reviewed_at` dan `mentions.reply_to_hash`/`quote_of_hash`/
`conversation_id` + dua index sekarang seharusnya ada di Supabase
production. **Belum diverifikasi lewat aplikasi sungguhan** (butuh login
`SITE_PASSWORD` + `/masuk` manual pengguna ke `/command`, `/tema`,
`/jaringan`) — itu langkah berikutnya.

## ✅ Fix crash Command Center/Tema/Jaringan — PR #4, di-merge 2026-09-02 (sesi keempat)

Insiden production nyata, dilaporkan pengguna langsung: membuka
`https://public-opinion-platform.vercel.app/command` menampilkan
```
Application error: a server-side exception has occurred while loading
public-opinion-platform.vercel.app (see the server logs for more information).
Digest: 548418512
```

**Akar masalah** (dikonfirmasi, bukan dugaan): `GET /projects/{id}/topics`
mengambil kolom `topics.review_status`/`reviewed_label`/`reviewed_by`/
`reviewed_at` (ditambahkan sesi PR #1), dan `GET /projects/{id}/network`
mengambil `mentions.reply_to_hash`/`quote_of_hash`/`conversation_id`.
**Migrasi kolom-kolom ini ke Supabase production belum diterapkan** — sudah
dicatat sejak sesi PR #1 (lihat "Yang BELUM diverifikasi" di atas), tapi
belum ada yang menyadari bahwa absennya migrasi itu tidak cuma membuat
FITUR review-label/network tidak berfungsi, melainkan menjatuhkan
**seluruh** `/command` (juga `/tema` dan `/jaringan`, endpoint yang sama).
Query gagal 500 (kolom tidak ada di tabel Supabase), bukan 404, dan
`apiOrNull()` di `apps/web/lib/api.ts` cuma menangkap 404 — 500 lolos dan
menjatuhkan seluruh Server Component.

**Diagnosis dikonfirmasi dengan reproduksi lokal, bukan cuma membaca
kode**: backend tiruan (Node `http` polos, bukan FastAPI sungguhan) dibuat
untuk membalas 500 persis seperti kolom hilang, lalu Next.js production
build (`next start`) dijalankan lokal dengan cookie sesi buatan sendiri
(HMAC gerbang `SITE_PASSWORD` dihitung manual dengan `SESSION_SECRET`
lokal, JWT `pop_session` bentuk-valid tanpa perlu tanda tangan asli —
middleware cuma cek `exp`, bukan verifikasi signature, lihat
`lib/session.ts`). Error yang muncul **identik kata demi kata** dengan
laporan pengguna. Baru setelah itu perbaikan diterapkan dan diverifikasi
ulang: ketiga halaman merender "Data tidak cukup" alih-alih crash.

**Perbaikan (PR #4, mitigasi frontend)**: `apiOrNullLenient()` baru di
`lib/api.ts` — menangkap SEMUA `ApiError`, bukan cuma 404 seperti
`apiOrNull()`. Dipakai di `/command` (`/topics` & `/alerts`), `/tema`
(`/topics`), `/jaringan` (`/network`). CI hijau (`typecheck`+`next build`
+ backend 474 tes semuanya lulus, tidak ada kode backend yang diubah).
**Di-merge ke `main` 2026-09-02 (sesi keempat)** — atas persetujuan
eksplisit pengguna, commit `a3e9462`. Render + Vercel redeploy otomatis
dari `main`; mitigasi ada di jalur deploy begitu redeploy selesai.

**Ini mitigasi, BUKAN perbaikan akar masalah.** SQL migrasi sesungguhnya
(sudah ditulis lengkap di deskripsi PR #4, siap copy-paste ke Supabase SQL
Editor):

```sql
ALTER TABLE topics ADD COLUMN IF NOT EXISTS reviewed_label text;
ALTER TABLE topics ADD COLUMN IF NOT EXISTS review_status review_status NOT NULL DEFAULT 'PENDING';
ALTER TABLE topics ADD COLUMN IF NOT EXISTS reviewed_by uuid REFERENCES users(id);
ALTER TABLE topics ADD COLUMN IF NOT EXISTS reviewed_at timestamptz;

ALTER TABLE mentions ADD COLUMN IF NOT EXISTS reply_to_hash text;
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS quote_of_hash text;
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS conversation_id text;

CREATE INDEX IF NOT EXISTS mentions_project_reply_to_hash_idx
  ON mentions (project_id, reply_to_hash) WHERE reply_to_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS mentions_project_quote_of_hash_idx
  ON mentions (project_id, quote_of_hash) WHERE quote_of_hash IS NOT NULL;
```

Tipe `review_status` seharusnya sudah ada (dipakai `ai_outputs.human_review`
sejak 2026-08-24/27) — kalau muncul error "type review_status does not
exist", jalankan dulu
`CREATE TYPE review_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'NEEDS_REVIEW');`
sebelum baris `ALTER TABLE topics ADD COLUMN review_status ...` di atas.
Setelah migrasi ini dijalankan, fitur review label dan network graph baru
benar-benar berfungsi dengan data nyata — PR #4 sendiri cuma mencegah
crash, tidak mengaktifkan fiturnya.

**Update: migrasi SQL di atas sudah dijalankan pengguna** (2026-09-02,
sesi keempat, lihat update di bagian atas dokumen ini) — `Success. No
rows returned` di Supabase SQL Editor, query tereksekusi dicocokkan
persis dengan yang diminta. Kolom-kolom di atas seharusnya sudah ada di
Supabase production sekarang.

**Sesi berikutnya**: verifikasi production sungguhan (login
`SITE_PASSWORD` + `/masuk` manual oleh pengguna) masih **belum
dilakukan** — itu satu-satunya langkah tersisa untuk mengonfirmasi (a)
`/command`/`/tema`/`/jaringan` tidak lagi crash, dan (b) fitur
review-label + network graph benar-benar menampilkan data, bukan cuma
"data tidak cukup".

## ✅ Verifikasi RSS ronde kedua (sampel lebih besar) — 2026-09-02 (sesi keempat)

Instruksi pengguna: sambil menunggu verifikasi production, kerjakan
"langkah 2" (hal genuinely bisa dikerjakan tanpa kredensial) secara
maksimal. Diplih: perluas verifikasi RSS+sentimen sesi kedua (215 item,
5 feed) dengan sampel baru yang lebih besar, untuk mencari bug leksikon
lain seperti "asal".

### Yang dikerjakan

Skrip mandiri baru (pola identik sesi sebelumnya — venv terisolasi tanpa
Postgres, `RSSConnector().fetch()` dan `services/ingestion.py`,
`services/sentiment.py` dipanggil langsung apa adanya, tidak ditulis
ulang) menarik **11 kandidat feed**: 5 yang sudah terbukti hidup sesi lalu
(Antara, CNN Indonesia, Tempo, Republika, CNBC Indonesia) plus 6 kandidat
baru (Liputan6, Sindonews, Bisnis.com, Kontan, Media Indonesia,
Suara.com).

**7/11 hidup** — 385 item mentah, lebih besar dari 215 item sesi lalu:
- Ke-5 feed lama tetap hidup. Catatan kecil: Antara News gagal sekali
  ("Server disconnected") lalu berhasil di percobaan berikutnya — bukti
  kongkret kegagalan TRANSIEN, bukan cuma feed mati permanen seperti
  Kompas/Detik sesi lalu. Menguatkan catatan `connectors/rss.py` soal
  feed yang rapuh.
- **2 kandidat baru terbukti hidup**: Sindonews (30 item), Media Indonesia
  (80 item) — bisa ditambahkan ke daftar feed produksi kalau nanti mau
  diperluas.
- **4 kandidat gagal**, dicatat biar tidak perlu dicoba ulang: Liputan6
  (404 — URL RSS lama sudah tidak berlaku), Bisnis.com (403/404,
  tidak konsisten antar percobaan), Kontan (XML tidak well-formed —
  kemungkinan encoding/entity rusak dari sisi penerbit), Suara.com
  (koneksi gagal total, bukan HTTP error).

Pipeline ingestion+sentiment ASLI dijalankan atas 385 item: 0 exception,
362/385 (94%) terdeteksi bahasa Indonesia, 0 duplikat (wajar, 7 outlet
berbeda), abstain 301/385 (78.2% — konsisten dengan 79.5% sesi lalu, beda
tipis karena feed LIVE). 84 item ternilai dibaca manual, plus token
`matched` diperiksa lewat REPL untuk ~15 item ekstrem/mencurigakan yang
tidak langsung jelas benar-salahnya (bukan cuma menyimpulkan dari
judulnya).

### Hasil: TIDAK ada bug leksikon baru yang aman diperbaiki

Berbeda dari sesi lalu ("asal"), ronde ini **tidak menemukan kata tunggal
yang bisa dihapus/diperbaiki tanpa risiko regresi** — dicatat apa adanya,
bukan dipaksakan supaya kelihatan ada progres (CLAUDE.md §8). Tiga
temuan konkret:

1. **Kata "meningkat" (bobot positif 0.4) salah pada konteks krisis —
   dikonfirmasi lagi dengan contoh BARU, bukan cuma Ebola sesi lalu.**
   "Aktivitas Gunung Sinabung Meningkat-Warga Mengungsi, Awas Bencana
   Baru" bernilai **+0.40 positif** (matched: `meningkat`), padahal ini
   berita evakuasi akibat erupsi gunung berapi — jelas negatif. Kejadian
   sama pada "Wamen ESDM ... Subsidi Energi Bisa Meningkat Rp300
   Triliun" (+0.40, subsidi membengkak = buruk secara fiskal, bukan
   baik). **Tidak diperbaiki** — "meningkat" tetap positif di sebagian
   besar konteks lain (ekonomi tumbuh, kepuasan naik), menghapusnya akan
   merusak lebih banyak klasifikasi benar daripada memperbaiki. Ini batas
   leksikon-kata-tunggal yang sudah diakui docstring modul, sekarang ada
   dua contoh nyata dari topik berbeda (kesehatan/Ebola sesi lalu,
   bencana alam sesi ini).

2. **Kata "korupsi"/"korup" (bobot negatif 0.9) mendominasi berita
   ANTI-korupsi jadi salah arah.** "RUU Perampasan Aset Momentum Perkuat
   Pemberantasan Korupsi" (-0.90, matched 2x `korupsi`) dan "Negara Kaya
   Minyak Ngamuk Digerogoti Koruptor, Sita Aset Rp 17,7 T" (-0.90) —
   keduanya berita tentang UPAYA memberantas korupsi (RUU baru, aset
   hasil korupsi disita), bukan tentang korupsi terjadi, tapi skornya
   sama negatifnya seolah itu berita korupsi baru. **Tidak diperbaiki**
   — "korupsi" negatif itu sendiri benar; masalahnya ada di konteks
   "melawan X" vs "X terjadi", yang butuh pemahaman kalimat penuh, bukan
   kamus kata. Sama persis kelas masalah dengan sarkasme yang sudah
   dicatat sesi lalu.

3. **Kata "sulit" (bobot negatif 0.6) salah pada satu kalimat idiomatik,
   BUKAN kandidat perbaikan seperti "asal".** "Gita Bhebhita sulit tahan
   tawa saat satu adegan..." (-0.60) — "sulit tahan tawa" adalah idiom
   untuk "lucu sekali", bukan kesulitan sungguhan, jadi entertainment
   yang netral/positif salah terbaca negatif. **Sengaja tidak
   diperbaiki, beda alasan dari "asal"**: pada sampel ini "sulit" juga
   benar dipakai pada "Berwajah Sulit Dikenali" (jasad tanpa identitas —
   memang negatif), dan "sulit"/"susah" adalah salah satu penanda
   kesulitan paling umum di seluruh leksikon — kebalikan dari "asal"
   yang nyaris tidak punya kegunaan sah sebagai kata negatif. Menghapus
   "sulit" akan merusak jauh lebih banyak klasifikasi benar daripada
   memperbaiki satu idiom langka.

**Yang justru terkonfirmasi jalan dengan benar** (supaya tidak semua
temuan kedengaran negatif): "berhasil" pada "Penyelundupan ... Berhasil
Digagalkan" (+0.80, benar — penggagalan penyelundupan itu berita baik),
"sukses" pada dua berita berbeda (+0.80, benar), "membaik" pada berita
kondisi santri keracunan yang membaik (+0.70, benar), "cepat" pada 4
judul berbeda soal respons cepat pemerintah (+0.40..+0.55, benar — cepat
menangani krisis itu genuinely positif meski krisisnya sendiri negatif),
"tolak"/"menolak" pada dua berita politik luar negeri (-0.80, benar).
Leksikon ini bekerja sebagaimana mestinya pada mayoritas kasus yang
diperiksa — temuan di atas adalah pengecualian yang didokumentasikan,
bukan indikasi leksikonnya rusak.

### Kesimpulan untuk `docs/progress.md`

Poin 5 di "Yang BELUM diverifikasi" (akurasi sentimen adalah batas ATAS,
perlu diukur ulang terhadap sampel berlabel sistematis dari penilai
independen) **tetap berlaku, sekarang dengan sampel dua kali lebih besar
menguatkan kesimpulan yang sama**: leksikon kata-tunggal punya batas
struktural yang jelas (kata ambigu konteks, framing "melawan X" vs "X
terjadi", idiom) yang sudah dua sesi berturut-turut ditemukan tanpa
kandidat perbaikan aman baru selain "asal". Ini bukan kegagalan mencari
— ini bukti bahwa perbaikan lanjutan butuh metode berbeda (model, bukan
kamus), sesuai yang sudah diakui sejak awal modul ini ditulis.

## ✅ Audit crash seluruh sidebar + perbaikan sistemik — 2026-09-02 (masih sesi keempat)

Pengguna melaporkan lewat screenshot: "masih banyak yang belum bisa
diklik" di sidebar. Ditanya dua kali untuk klarifikasi — pertama soal
tampilan (garis bawah default browser di item nav, sudah diperbaiki
terpisah, lihat commit `427e704`), lalu dikonfirmasi pengguna SUDAH
mencoba klik dan memang gagal. Diminta cek semua link.

### Audit statis: kelas bug PR #4 ternyata bukan cuma di 3 halaman

Baca kode ke-14 halaman dashboard satu per satu. `apiOrNull()` HANYA
menangkap 404 (lihat `lib/api.ts`) — 6 halaman ternyata memanggil `api()`
POLOS tanpa penanganan error sama sekali: `/geo`, `/narrative`,
`/governance`, `/segments`, `/proyek`, plus panggilan trend/timeline di
`/command` dan `/opinion-index`. Semuanya akan menjatuhkan SELURUH
halaman kalau backend membalas error apa pun (bukan cuma skenario kolom
belum bermigrasi yang memicu insiden PR #4 — bisa juga DB blip, timeout,
dll).

### Perbaikan PERTAMA salah — ketahuan lewat verifikasi, bukan baca kode

Iterasi pertama mengganti `api()` -> `apiOrNull()` di 6 halaman itu.
**Salah** — `apiOrNull()` cuma menangkap 404, PERSIS bug yang sama
dengan yang coba diperbaiki (insiden PR #4 itu sendiri 500, bukan 404).
Ketahuan lewat verifikasi lokal sungguhan, bukan asumsi:

1. `next build && next start` lokal, `NEXT_PUBLIC_API_URL` menunjuk ke
   backend tiruan Node `http` polos yang membalas 500 untuk SEMUA
   endpoint.
2. Cookie gerbang `pop_gate_session` dibuat manual pakai `SESSION_SECRET`
   lokal (HMAC sama seperti `lib/auth.ts`) dan cookie sesi `pop_session`
   JWT bentuk-valid tanpa tanda tangan asli (middleware cuma cek `exp`,
   bukan verifikasi signature — pola sama dengan verifikasi PR #4
   sebelumnya).
3. Ke-17 rute dashboard diminta lewat klien HTTP Node (bukan `curl` —
   tidak tersedia di sandbox sesi ini), dicek status code + isi body.

Hasil ronde pertama (setelah "perbaikan" apiOrNull): SEMUA 6 halaman
yang baru diubah **masih 500**, body HTML `id="__next_error__"` — masih
crash persis seperti sebelum "diperbaiki". Root cause: `apiOrNull` bukan
`apiOrNullLenient`.

### Perbaikan BENAR: apiOrNullLenient di semua 15 halaman

Diperbaiki ulang — SEMUA panggilan `api()`/`apiOrNull()` untuk baca data
awal halaman (bukan Server Action hasil submit form, itu beda kategori
sesuai dokumentasi `apiOrNullLenient`) diganti `apiOrNullLenient()`.
Ternyata ini bukan cuma 6 halaman yang tadi salah — SEMUA 9 halaman lain
yang sudah pakai `apiOrNull` (consistency, copilot, dampak, forecast,
pengaruh, risiko, sinyal, opinion-index, brief) punya kerentanan SAMA
persis, cuma belum pernah dilaporkan sebagai insiden. Total 15 halaman
diubah dalam satu commit (`33d026b`).

**Diverifikasi ulang dua kali** dengan server lokal yang sama:
- Backend tiruan 500-untuk-semua: **ke-17 rute HTTP 200**, tidak ada
  `__next_error__` sama sekali.
- Backend tiruan 404-untuk-semua (simulasi proyek baru kosong lewat
  `/proyek-baru`): **ke-17 rute HTTP 200** juga, semua menampilkan
  "data tidak cukup"/"belum ada" alih-alih crash.

`typecheck` + `next build` bersih di kedua iterasi.

### Yang BELUM diverifikasi dari perbaikan ini

- Ini murni tes backend TIRUAN (500/404 buatan), bukan Supabase/Render
  sungguhan. Backend production sekarang (pasca migrasi) kemungkinan
  besar tidak membalas 500 untuk endpoint-endpoint ini — tapi
  kerentanannya tetap ada untuk masa depan (DB blip, migrasi
  berikutnya yang lupa diterapkan, dll). Perbaikan ini pencegahan,
  bukan bukti ada bug production AKTIF hari ini di 6 halaman yang
  ditemukan lewat audit statis (beda dengan /topics & /network yang
  memang terbukti aktif gagal).
- **Belum ketahuan apakah keluhan awal pengguna ("belum bisa diklik")
  memang disebabkan hal ini** — bisa jadi murni soal tampilan (garis
  bawah, sudah diperbaiki terpisah) atau memang backend production
  sempat 500 di jendela waktu tertentu (mis. sebelum migrasi Supabase
  dijalankan hari ini). Pengguna belum sempat konfirmasi link mana
  spesifiknya. Perlu diverifikasi ulang dengan pengguna langsung
  mencoba lagi di production.

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
