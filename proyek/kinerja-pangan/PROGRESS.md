# Kinerja komunikasi enam lembaga pangan — penilaian dari data publik

Proyek platform: **"PANGAN - KINERJA AKUN RESMI (YouTube)"** (`/kinerja`, `/kinerja/analisis`).
Berbeda dari proyek percakapan "PENGUNDURAN DIRI GIBRAN" (`proyek/gibran-mundur-youtube/`); yang
dipakai bersama hanya kunci YouTube Data API.

Kerangka indikator: `docs/kerangka-kinerja-komunikasi-pemerintah.md` (model `gcp-rancangan-1`,
belum divalidasi).

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

## Berikutnya (data publik, belum dikerjakan)

1. **C3 keselarasan**: pasangkan pernyataan resmi Kemenko Pangan dan tiap lembaga per isu, dua
   pengode, di `/kinerja/analisis?bagian=selaras`.
2. **C4 kecepatan respons**: butuh percakapan publik tentang isu pangan di proyek ini (sekarang
   nol, jadi tidak ada hari lonjakan).
3. **Pengodean isi** unggahan YouTube (A9–A18) dengan dua pengode untuk deskripsi isi dan alpha.
4. Instagram/TikTok/X dari tampilan publik akan menambah O4, O6, O9.
