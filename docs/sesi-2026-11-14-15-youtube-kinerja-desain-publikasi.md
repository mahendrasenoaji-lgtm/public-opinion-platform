# Catatan sesi 14–15 November 2026 — migrasi, YouTube Kinerja, desain, artikel pertama

Ringkasan percakapan supaya pekerjaan bisa dilanjutkan di komputer lain tanpa riwayat chat.
Status terkini selalu di blok "MULAI DARI SINI" dan "Daftar kerja" di
[deployment-status.md](deployment-status.md).

## Mulai di komputer lain

```
git clone https://github.com/mahendrasenoaji-lgtm/public-opinion-platform   # atau git pull
```

Baca `CLAUDE.md`, lalu blok teratas `docs/deployment-status.md`, lalu file ini.
Tidak ada PR terbuka per 15 Nov. Produksi: web `public-opinion-platform.vercel.app`,
API `pop-api-ptug.onrender.com`, DB Supabase proyek `publicopinion` (org ALWAYSLEARN).

## Yang dikerjakan (urut)

| Permintaan pengguna | Hasil |
|---|---|
| "cek repo public opinion" | Repo bersih; PR #58–#60 sudah digabung; dua migrasi belum jalan (API 409). |
| "jalankan migrasi … gunakan claude chrome" | `2026-11-12-kinerja-komunikasi.sql` dan `2026-11-13-publikasi.sql` dijalankan di SQL Editor; RLS true/true; `/kinerja`, `/publikasi`, `/pers` hidup. Ditemukan: kuota **egress** Supabase lewat batas siklus 10 Okt–10 Nov, tenggang sampai **10 Des 2026**. |
| "bisakah mengukur akun resmi Kementan, Kemenhut, KKP, KLH, Bapanas, BGN?" | Bisa sebagian: YouTube otomatis (API resmi), IG/TikTok lewat berkas, X butuh API berbayar; reach/impressions hanya dari pemilik akun. |
| "lanjutkan sampai selesai" | PR #61 (dokumen status) dan **#63** (YouTube di Kinerja: `app/connectors/youtube_channel.py`, `POST /comm-performance/youtube`, formulir di `/kinerja`, migrasi `2026-11-14-kinerja-youtube.sql`). #62 tertutup otomatis saat basisnya dihapus, diganti #63. |
| "ya authorized semuanya" | Merge #61/#63, migrasi YouTube dijalankan. Handle kanal diambil dari situs `.go.id` tiap lembaga; proyek baru **"PANGAN - KINERJA AKUN RESMI (YouTube)"**; 6 kanal diambil (90 hari, maks 200 video). |
| (temuan) | **#64**: engagement rate kecil tampil "0%" → 2 angka penting; backend bulat 4 desimal. **#65**: kontras AA (`--survey` #0A66C3, `--social` #B24219, `--txt3` #696475/#8D97C1), menu kiri tidak terpotong, ubin angka `/kinerja`, `/proyek` di ponsel. **#66**: cetak/PDF selalu palet terang. |
| "kerjakan sampai tuntas, simpan deploy commit" | **#67**: templat CSV + `docs/panduan-data-akun-resmi.md` (IG/TikTok/X = unggah berkas); lima keputusan situs publikasi dicatat di `docs/rencana-situs-publikasi.md` §5. Draf artikel BBM Bali dibuat dan diajukan ke **tinjauan**. **#68**: dokumen status. |

## Data YouTube akun resmi (proyek PANGAN - KINERJA AKUN RESMI, diambil 14 Nov, 90 hari)

| Akun | Video | Pelanggan | Median tayangan | Median suka | Median komentar | ER per pelanggan |
|---|---|---|---|---|---|---|
| `@kementanri` (Kementan) | 73 | 239.000 | 2.451 | 92 | 17 | 0,045% |
| `@kkp_ri` (KKP) | 15 | 99.200 | 2.355 | 111 | 3 | 0,12% |
| `@kemenhut_ri` (Kemenhut) | 7 | 54.100 | 2.316 | 48 | 5 | 0,094% |
| `@badangizinasional` (BGN) | 15 | lihat `/kinerja` | 1.059 | 14 | 9 | 0,22% |
| `@klh-bplh` (KLH/BPLH) | 36 | 171.000 | 820,5 | 9,5 | 0 | 0,0056% |
| `@badanpangannasionalofficial` (Bapanas) | 13 | 7.180 | 210 | 2 | 0 | 0,028% |

Angka tayangan terus bertambah; ambil ulang lewat formulir yang sama untuk memperbarui
(tidak menggandakan). Baris tidak boleh dijumlah atau diperingkat lintas platform.

## Masih terbuka (ringkas; rincian di daftar kerja)

- **Pengguna:** terbitkan artikel BBM Bali (`/publikasi` → Terbitkan; id
  `97271ca0-8e8e-4c22-bb9c-ab9b61806711`, tidak bisa ditarik setelah terbit); kunci
  Anthropic di Render; pelabel manusia kedua; empat pertanyaan modul Kinerja; domain `/pers`;
  anggaran API X.
- **Agen:** grafik interaktif + RSS + gambar OG di `/pers`; ekspor DOCX/PDF + CSV agregat;
  pengodean isi, C3/C4/O8, audit T1–T4; periode tetap di halaman lain; aktor per proyek;
  perbaikan kamus (sindiran, pertanyaan retoris); rescore proyek lain (hati-hati egress).
- **Belum dilihat mata:** `/masuk`, `/daftar` di ponsel; hasil PDF `/laporan`.

## Catatan kerja

- Merge oleh agen kadang ditolak pemeriksa izin Claude Code walau pengguna mengizinkan;
  pengguna bisa merge sendiri atau menambah izin `gh pr merge`.
- SQL Editor Supabase: isi editor lewat `monaco.editor.getModels()[0].setValue(...)`;
  query dengan `DROP` memunculkan dialog "Potential issue detected".
- Berkas lokal yang sengaja TIDAK di GitHub (pilihan pengguna): `presentasi_bbm_bali_youtube_FINAL.pptx`
  dan `skrip/build_pptx_final.js` di `proyek/bbm-bali-youtube/`.
