# Kinerja komunikasi enam lembaga pangan — penilaian dari data publik

Proyek platform: **"PANGAN - KINERJA AKUN RESMI (YouTube)"** (`/kinerja`, `/kinerja/analisis`).
Berbeda dari proyek percakapan "PENGUNDURAN DIRI GIBRAN" (`proyek/gibran-mundur-youtube/`); yang
dipakai bersama hanya kunci YouTube Data API.

Kerangka indikator: `docs/kerangka-kinerja-komunikasi-pemerintah.md` (model `gcp-rancangan-1`,
belum divalidasi).

## 🟢 19 Nov 2026: artikel kinerja TERBIT (versi 1)

- Atas keputusan pemilik ("terbitkan sekarang apa adanya"): `/pers/seberapa-jauh-kinerja-komunikasi-enam-lembaga-pangan-bisa-dinilai-dari-data-publ-e7f344`,
  terbit 19 Nov 09.52 WIB. C3 dan uji kesepakatan pengodean isi dinyatakan tertunda di teks.
- **Ralat (versi 2) nanti**, setelah peneliti mengode worksheet C3 (18 pasangan) dan lembar pengode 1 (min. 20 unggahan):
  masukkan kode tertutup pengode 2, hitung C3 BGN + Kementan dan alpha, perbarui bagian C3 dan "Isi unggahan".

## 19 Nov 2026 (siang): sampel C3 diperluas

- Pernyataan Kemenko Pangan 1–24 Agu dibaca dari halaman daftar `kemenkopangan.go.id/berita/6/{offset}` (offset per 7
  butir): +27 butir, kini 63 total / 55 dalam periode (`data/kemenko_pangan_berita.csv`).
- 9 kandidat pasangan baru; 1 dikeluarkan (harga beras/SPHP: isu tidak sama). Worksheet pengode 1
  `data/c3_lembar_pengode1.csv` kini **18 pasangan**: BGN 5, Kementan 5, Bapanas 4, KLH 2, KKP 1, Kemenhut 1.
  **BGN dan Kementan mencapai ambang 5** — C3 keduanya bisa diskor setelah kedua lembar dikode.
- Kode pengode 2 untuk 8 pasangan baru ditambahkan ke `data_lokal/c3_kode_pengode2_TERTUTUP.json` (Mac saja, tetap
  tertutup sampai peneliti mengode). Paragraf C3 di draf `d0f1ddb9` diperbarui.

## 🟢 19 Nov 2026: draf artikel kinerja Menunggu tinjauan

- Keenam kanal YouTube diambil ulang di `/kinerja` (111 hari, sejak 1 Agu): Kementan 100 video (27 baru), Kemenhut 10 (3),
  KKP 17 (2), KLH 43 (7), Bapanas 18 (5), BGN 20 (5). 164 unggahan jatuh di 1 Agu–31 Okt.
- Lembar pengode 2 dilengkapi: 49 unggahan baru (7 sudah punya kode lokal tapi belum tersimpan, 42 dikode dari judul +
  deskripsi lewat YouTube API). Kini **208/208**; salinan lokal `data_lokal/kode_isi_pengode2.json`.
- Draf `/pers` berjenis kinerja `d0f1ddb9-7399-4aa4-8668-401c9350d250` ("Seberapa jauh kinerja komunikasi enam lembaga
  pangan bisa dinilai dari data publik"), periode 2026-08-01..2026-10-31, teks `artikel_pers_kinerja.md`, pratinjau dicek
  (4 penanda tampil), status **Menunggu tinjauan**. Menerbitkan = keputusan pemilik.
- **Masih milik peneliti:** lembar pengode 1 (min. 20 unggahan) dan worksheet C3. Sesudahnya: masukkan kode C3 tertutup,
  lalu ralat artikel (bagian "Isi unggahan") bila alpha sudah terhitung.

## Keputusan peneliti (17 Nov 2026)

| Hal | Keputusan |
|---|---|
| Lembaga | Kementan, Kemenhut, KKP, KLH/BPLH, Bapanas, BGN (di bawah koordinasi Kemenko Bidang Pangan) |
| Tujuan | Artikel/tesis |
| Data | **Hanya data publik** (tanpa dokumen internal, insight akun, atau survei) |
| Urutan | Skor indikator dulu |
| Periode | **1 Agu – 31 Okt 2026** (tiga bulan). Satu bulan (Okt) hanya memberi 4 akun dengan minimal 5 video (KKP 4 video, Kemenhut 1), dan kerangka 9.3 melarang kuintil di bawah 5 akun. Di platform dicatat sebagai periode `2026-10` dengan keterangan jendela di kolom bukti. |
| Kuintil | Peringkat persentil dibulatkan ke atas: skor = ceil(5 × peringkat / 6), peringkat 1 = terendah |

## Hasil: skor indikator (diisi di `/kinerja`, 17 Nov 2026)

| Lembaga | Kanal | Video | O4 median tayangan | O5 median (suka+komentar)/pelanggan | O8 pertanyaan dibalas |
|---|---|---|---|---|---|
| Kementan | @kementanri | 82 | 2.550,5 → **5** | 0,0433% → **3** | 0/27 → **1** |
| Kemenhut | @kemenhut_ri | 10 | 2.182 → **5** | 0,0934% → **4** | ditahan (9 pertanyaan) |
| KKP | @kkp_ri | 11 | 1.829 → **4** | 0,1986% → **5** | ditahan (2) |
| BGN | @badangizinasional | 18 | 949 → **3** | 0,1971% → **5** | ditahan (18) |
| KLH/BPLH | @klh-bplh | 27 | 869 → **2** | 0,0088% → **1** | ditahan (3) |
| Bapanas | @badanpangannasionalofficial | 16 | 183 → **1** | 0,0349% → **2** | ditahan (2) |

- O4/O5: angka publik saat diambil (17 Nov 2026 22.42 WIB), video terbit 1 Agu–31 Okt; data
  per video di `data/youtube_2026-08_video.csv`, `_09_`, `_10_`; ringkasan per bulan di
  `data/youtube_2026-MM_ringkasan.json`. Dibuat ulang dengan `skrip/youtube_bulanan.py`.
- O5 versi publik tanpa share (YouTube tidak menampilkannya). BGN (0,1971%) dan KKP (0,1986%)
  nyaris sama; beda peringkatnya tidak bermakna.
- O8: dihitung `/kinerja/analisis?bagian=tanggap` pada video yang tercatat di proyek (jendela 90
  hari s.d. 14 Nov 2026); ditahan bila pertanyaan < 20.
- 23–24 indikator lain dicatat **tidak tersedia** dengan alasan (data internal, insight akun,
  survei). **C3 dan C4 sengaja dibiarkan "belum diisi"**: keduanya bisa dari data publik tetapi
  belum dikerjakan (lihat bawah).

## Temuan utama untuk artikel

Dengan data publik saja, **tidak ada satu pun skor dimensi yang terbit**, untuk lembaga mana pun:
Input 0/6, Process 0/7, Output 2–3/9 (22–33%), Outcome 0/6. Aturan model (bagian 9.4) mensyaratkan
cakupan minimal 60% per dimensi. Bahkan bila C3, C4, dan C6 dikerjakan, Outcome paling banyak 3/6
(50%). Artinya kerangka ini tidak bisa menilai lembaga dari luar; yang bisa dilaporkan jujur adalah
**indikator teramati satu per satu**, bukan skor total. Itu temuan tentang keterbukaan data, bukan
tentang mutu komunikasi lembaga (bagian 9.5).

## Situs web resmi (`/kinerja/analisis?bagian=situs`, 17 Nov 2026)

Kemenhut 24 butir, KKP 18, BGN 10, KLH 9 (dibaca server); Bapanas 19 (CSV dari Mac, karena
server Render ditolak situsnya); Kementan 0 (halaman daftar tanpa tanggal; perlu CSV manual).
KLH `/berita` dan `/pengumuman` gagal dibuka dari server maupun dari Mac pada 17 Nov.
Angka 30/90 hari masih batas bawah sampai situs dibaca berkala.

## 18 Nov 2026: C3, C4, pengodean isi, situs Kementan (keputusan peneliti pagi itu)

Keputusan: pengode 1 = peneliti, pengode 2 = Claude (dicatat sebagai pengode AI, bukan manusia independen);
percakapan C4 = komentar YouTube pada video yang menyebut nama lembaga; Kementan dibaca dari halaman artikel
(judul + tanggal saja, maks. 20, `skrip/kementan_artikel.py`).

**Kartu skor sekarang lengkap untuk keenam lembaga (28 indikator, 0 belum diisi).** Kementan 3 berskor / 25 tidak
tersedia; lima lainnya 2 / 26. Tidak ada skor dimensi yang terbit (temuan utama tetap).

- **Situs Kementan:** 20 artikel (12–17 Nov) diunggah sebagai CSV (`data/situs_kementan_2026-11-18.csv`). Keenam situs
  kini punya butir.
- **C3 keselarasan → tidak tersedia untuk semua.** Pernyataan Kemenko Pangan dibaca dari kemenkopangan.go.id (5 halaman
  daftar, 36 butir, 27 dalam Agu–Okt; `data/kemenko_pangan_berita.csv`). 15 kandidat pasangan per isu dengan pernyataan
  lembaga (video YouTube resmi); 5 dikeluarkan karena pernyataan lembaga hanya judul (`data/c3_pasangan_dikeluarkan.csv`).
  Tersisa 10: Kementan 4, BGN 2, KLH 2, Bapanas 1, KKP 1, Kemenhut 0 — semuanya di bawah ambang 5 pasangan per lembaga,
  jadi C3 tidak bisa diskor apa pun hasil kodenya. Catatan teknis: saran skor C3 di platform dihitung atas semua pasangan
  proyek, bukan per lembaga.
  - **Pengode 1 (peneliti) belum mengode.** Lembar kerja tanpa kode: `data/c3_lembar_pengode1.csv`. Kode pengode 2
    disimpan TERTUTUP di Mac (`data_lokal/c3_kode_pengode2_TERTUTUP.json`, tidak di GitHub) karena halaman C3 platform
    menampilkan kode kedua pengode; dimasukkan ke platform sesudah peneliti mengode.
- **C4 kecepatan respons → tidak tersedia untuk semua (keputusan peneliti).** Percakapan: 70.325 komentar dari 360 video
  (`skrip/collect_percakapan.py`, data mentah lokal), lalu video dari kanal lembaga sendiri/unitnya dikeluarkan (komentar
  di sana memuncak karena lembaga mengunggah; contoh: "Hymne Penyuluh" BPPSDMP 53.906 komentar). Hasil fungsi platform
  (`skrip/hitung_c4.py`, `data/c4_per_lembaga.json`):

  | Lembaga | Komentar | Median/hari | Lonjakan | Tak dijawab 72 jam | Median jam | Saran |
  |---|---|---|---|---|---|---|
  | Kementan | 4.881 | 31 | 34 | 1 | 13,4 | 4 |
  | KKP | 2.549 | 6 | 17 | 10 | 25,2 | 1 |
  | Kemenhut | 1.482 | 5 | 20 | 13 | 29,6 | 1 |
  | BGN | 501 | 5 | 22 | 13 | 14,1 | 1 |
  | KLH/BPLH | 414 | 3 | 14 | 5 | 29,2 | 3 |
  | Bapanas | 359 | 2 | 15 | 8 | 35,1 | 1 |

  Tidak dijadikan skor: fungsi platform menghitung unggahan resmi apa pun sebagai tanggapan tanpa cek isi (Kementan
  mengunggah hampir tiap hari), dan percakapan lima lembaga lain terlalu tipis.
- **Pengodean isi (A9–A18):** lembar pengode 2 lengkap di platform, 159/159 unggahan, A9, A11, A12, A14, A15, A16 dari
  judul + deskripsi; A17 dan A18 kosong (video tidak ditonton). Platform menyembunyikan kode pengode lain, jadi peneliti
  bisa mengode lembar 1 tanpa melihat kode Claude. Alpha baru terhitung setelah minimal 20 unggahan dikode ganda.
  Salinan kode lokal: `data_lokal/kode_isi_pengode2.json` (tidak di GitHub, supaya tetap buta).

**Yang tersisa untuk peneliti:** (1) kode lembar 1 di `/kinerja/analisis?bagian=kode` (minimal 20 unggahan untuk alpha);
(2) kode `data/c3_lembar_pengode1.csv` lalu beri tahu Claude untuk memasukkan kode pengode 2.

## Publikasi di /pers (rencana, 18 Nov 2026)

Keputusan pemilik: hasil kinerja diterbitkan di `/pers` dengan sistem yang sama seperti artikel percakapan.
PR #80 menambah draf publikasi berjenis `kinerja` (tombol "Buat draf publikasi" di `/kinerja`): kartu skor,
akun resmi, situs, dan pengodean isi dibekukan; sebaran kode hanya ikut bila alpha >= 0,667.

Urutan sesudah PR #80 dirilis dan lembar pengode 1 + C3 selesai:
1. Ambil ulang keenam kanal YouTube di `/kinerja` dengan rentang 110 hari, supaya unggahan 1 Agu–31 Okt lengkap
   di platform (pengambilan 14 Nov hanya 90 hari, mulai ±16 Agu).
2. Masukkan kode C3 pengode 2 dari `data_lokal/c3_kode_pengode2_TERTUTUP.json`.
3. Buat draf dari `/kinerja`, periode 2026-08-01 s.d. 2026-10-31, tulis isi dengan struktur artikel BBM Bali,
   ajukan tinjauan; menerbitkan tetap keputusan pemilik.

## Berikutnya (data publik, belum dikerjakan; status 17 Nov)

1. **C3 keselarasan**: pasangkan pernyataan resmi Kemenko Pangan dan tiap lembaga per isu, dua
   pengode, di `/kinerja/analisis?bagian=selaras`.
2. **C4 kecepatan respons**: butuh percakapan publik tentang isu pangan di proyek ini (sekarang
   nol, jadi tidak ada hari lonjakan).
3. **Pengodean isi** unggahan YouTube (A9–A18) dengan dua pengode untuk deskripsi isi dan alpha.
4. Instagram/TikTok/X dari tampilan publik akan menambah O4, O6, O9.
