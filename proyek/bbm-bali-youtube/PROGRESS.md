# Kelangkaan BBM Bali — komentar YouTube 11–20 Okt 2026

Folder `proyek/bbm-bali-youtube/` di repo **publik** `public-opinion-platform` (atas pilihan pengguna,
5 Nov 2026: semua file termasuk teks komentar masuk repo publik; nama akun sudah di-hash). Isinya: data
komentar YouTube, laporan, dan skrip pengolahnya. Data yang sama juga ada di database platform.
Dibuat 5 Nov 2026 dalam satu sesi Claude Code. Ringkasan percakapannya ada di bawah supaya
pekerjaan bisa dilanjutkan di komputer lain tanpa riwayat chat.

## 🟢 Mulai dari sini

1. Komputer lain: `cd ~/Documents/public-opinion-platform && git pull` → buka folder ini.
2. Sebelum kerja: `git pull`. Sesudah kerja: commit + push (lewat PR, seperti bagian lain repo).
3. Status: **SELESAI.** Tidak ada pekerjaan yang menggantung. Pilihan lanjutan ada di bagian
   "Kalau mau dilanjutkan".

## Permintaan pengguna (urut)

1. "Cek repo public opinion, lalu buatkan mengenai kelangkaan BBM di Bali, hanya untuk komentar
   YouTube saja, tidak perlu pemberitaan media. Tarik data komentar dengan kurun 10 hari dari awal
   krisis BBM hingga solusi dari pemerintah, sumber komentarnya diberikan linknya juga."
2. "Buatkan PDF dari artifact BBM Bali YouTube. Lalu akun yang berkomentar apakah bisa dideteksi
   akun organik atau buzzer?"
3. "Simpan percakapan dan progress di repo supaya dapat saya kerjakan di komputer lain." (file ini)
4. "Jadikan satu dengan public opinion seperti proyek yang lain" → dipilih: semua file ke repo publik ini.

## Keputusan yang diambil

| Hal | Keputusan | Alasan |
|---|---|---|
| Jendela waktu | **11 Okt 00:00 – 20 Okt 23:59 WITA** | Antrean mulai 11–12 Okt; 19 Okt Bahlil + Koster menyatakan pasokan normal (cadangan 15 hari, ganjil-genap diperpanjang). +1 hari penutup. |
| Cara ambil | Skrip sendiri, **YouTube Data API v3 resmi** | `collect-all` di platform hanya menarik komentar TERBARU (order=time, 100/video, UI 2 hari) → rentang lampau tak terjangkau. |
| Kunci API | `YOUTUBE_API_KEY` disalin dari env Render `pop-api` (izin pengguna) | Tidak disimpan di repo mana pun. Di komputer lain: ambil lagi dari Render → pop-api → Environment. |
| Masuk platform | Ya (pilihan pengguna) → PR #43 di public-opinion-platform | Panel "Unggah data (JSON)" di `/sinyal` memanggil endpoint lama `POST /signals/ingest`. |
| Identitas akun | Nama akun **tidak disimpan**, diganti hash 12 karakter | Aturan CLAUDE.md §3 repo platform. |
| Buzzer | **Tidak** melabeli akun tertentu; hanya indikator agregat | Aturan platform: tidak menandai fraud / "mengendalikan opini". |

## Hasil

- 527 video (judul menyebut Bali + BBM/SPBU/Pertamina), 458 punya komentar dalam jendela.
- **36.319 komentar + balasan**, 22.803 akun berbeda; 425 komentar sesudah 20 Okt dibuang.
- Puncak **15 Okt (11.916 komentar, 33%)** — hari video Gubernur Koster diprotes petugas SPBU beredar.
  11 Okt nol karena video krisis pertama baru terbit 12 Okt.
- Sentimen (penilai platform `lexicon-id-1+informal-1`): 58% abstain; dari yang dinilai 63% negatif;
  rata-rata −0,2 s.d. −0,27 tiap hari. Sarkasme sering terbaca positif (komentar teratas "hebat nih
  Gubenur" dinilai positif).
- Tema: pemerintah daerah 6.194 komentar > antrean 5.446 > pemerintah pusat 4.222 > Pertamina 2.711.
- **Buzzer/organik** (agregat): 74% akun berkomentar sekali; 20 akun teraktif = 1,8% komentar;
  **0** teks kembar (≥30 huruf) dari ≥3 akun; 3 teks kembar dari 2 akun (pesan menenangkan "stok bbm
  aman"); 104 akun mengulang teks sama ≥3× (1.001 komentar, ±3%); 32 akun ≥10 komentar/jam;
  19 akun di ≥20 video. Kesimpulan: dominan organik; sekelompok kecil akun pengulang layak dibaca
  manual, belum cukup disebut buzzer.

## Di mana hasilnya

| Apa | Lokasi |
|---|---|
| Laporan online (privat, bagikan lewat Share) | https://claude.ai/artifact/WFPjyhn1CKxprVTMjVX1qQ (versi 2) |
| Laporan PDF (9 hlm, link bisa diklik) | `laporan_bbm_bali_youtube.pdf` |
| Laporan HTML (sumber PDF) | `laporan.html` |
| Excel (sheet Komentar / Video / Harian / Metode) | `komentar_youtube_bbm_bali_11-20okt2026.xlsx` |
| CSV satu baris per komentar + link | `komentar_youtube_bbm_bali_11-20okt2026.csv` |
| Data mentah API | `raw_youtube_api.json` |
| Statistik untuk laporan | `stats.json` |
| File unggahan platform | `unggah_platform_bbm_bali.json` (36.319 item, connector `youtube_api`, source SOCIAL) |
| Platform | proyek **"KELANGKAAN BBM BALI (YouTube 11-20 Okt 2026)"** di public-opinion-platform.vercel.app → 35.772 konten unik (547 teks kembar dibuang dedup), sentimen −0,24 (n 15.105), 22.704 akun |

Link per komentar: `https://www.youtube.com/watch?v=<video_id>&lc=<comment_id>`.

## Menjalankan ulang

```bash
cd ~/Documents/public-opinion-platform/proyek/bbm-bali-youtube
export YOUTUBE_API_KEY=...            # dari Render → pop-api → Environment
python3 -I skrip/collect_bbm.py raw_youtube_api.json        # ±30 menit, ±3.200 unit kuota
python3 -m venv .venv && .venv/bin/pip install openpyxl
.venv/bin/python skrip/analyze_bbm.py raw_youtube_api.json .  # ±20 menit (Excel lambat)
python3 skrip/build_report.py stats.json laporan.html
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --no-pdf-header-footer \
  --print-to-pdf=laporan_bbm_bali_youtube.pdf "file://$PWD/laporan.html"
```

`analyze_bbm.py` memakai penilai sentimen dari `apps/api` di repo yang sama; bisa diganti lewat env
`POP_API_DIR`.
Catatan: menjalankan ulang `collect` hari ini bisa memberi angka sedikit berbeda (komentar dihapus,
video baru terindeks). Indikator buzzer dihitung dengan skrip sekali pakai di sesi; angkanya tertulis
di laporan dan di atas.

## Hal yang perlu diketahui

- Unggah ke platform sempat 2× "Bad Gateway" dan 1× "Service Unavailable" dari Render; diulang dari
  titik berhenti, aman karena `ON CONFLICT DO NOTHING`. Unggah ±5 detik per 300 item.
- Dashboard platform memakai jendela relatif dari hari ini (bawaan 30 hari) → data Okt keluar dari
  tampilan bawaan sekitar **19 Nov 2026**. Data tetap tersimpan.
- Sesi login platform di Chrome bisa kedaluwarsa; login dilakukan pengguna sendiri.
- Unggah file lewat alat Chrome dibatasi 10 MB → file unggahan dipecah dua.

## Kalau mau dilanjutkan

1. **Pemeriksaan akun lebih dalam:** tarik ulang `authorChannelId` untuk ±150 akun paling aktif, lalu
   `channels.list` (tanggal kanal dibuat, jumlah video/subscriber). Kuota kecil. Tetap tanpa
   menyebut akun di laporan.
2. Pelabelan manual sampel komentar BBM untuk mengukur akurasi sentimen di isu ini.
3. Perluas jendela (mis. sampai 31 Okt) untuk melihat ekor percakapan sesudah pernyataan "normal".
