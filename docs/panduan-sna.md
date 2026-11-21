# Panduan membaca halaman Jaringan Interaksi (SNA)

Halaman `/jaringan` sejak 21 November 2026. Kode: `apps/api/app/services/sna.py`
(perhitungan, murni), `apps/api/app/routers/network.py` (`/network/sna`, `/network/bridges`,
`/network/export`), `apps/web/app/(dashboard)/jaringan/`. Tes: `apps/api/tests/test_sna.py`.

## Dari mana grafnya

- **Simpul (node)** = akun, hanya sebagai hash (`author_hash`). Nama akun tidak pernah disimpan.
- **Relasi (edge)** = A membalas atau mengutip B, **hanya bila sumbernya menyatakannya**:
  balasan komentar YouTube (`parentId`) dan reply/quote X. "@nama" di dalam teks tidak dipakai.
- Bobot = berapa kali relasi itu terjadi pada periode.
- Sumber: SOSIAL. TikTok dan Instagram tidak memberi nama akun, jadi tidak membentuk graf.

## Ukuran yang ditampilkan

| Ukuran | Cara membaca | Hati-hati |
|---|---|---|
| Dibalas/dikutip (in-degree) | Berapa kali akun ditanggapi | Satu akun yang membalas 20× ≠ 20 akun; lihat kolom Mitra |
| Membalas (out-degree) | Seberapa aktif akun menanggapi | |
| Mitra | Akun berbeda yang terhubung langsung | |
| Betweenness | Seberapa sering akun berada di jalur terpendek antar-akun lain: peran penghubung antar-kelompok | Diperkirakan dari sampel simpul bila graf besar (dicatat di halaman) |
| Closeness | Seberapa dekat akun ke seluruh akun lain (Wasserman-Faust, adil untuk graf terpecah) | |
| PageRank | Ditanggapi oleh akun yang juga banyak ditanggapi | Urutan bawaan tabel dan ukuran simpul di peta |
| Eigenvector | Terhubung dengan akun yang juga banyak terhubung | Hanya di komponen terbesar; akun lain "–" |
| Density | Porsi relasi yang terjadi dari semua relasi yang mungkin | Graf media sosial selalu sangat jarang (mendekati 0) |
| Resiprositas | Porsi relasi yang dibalas balik | |
| Komponen terbesar | Porsi akun yang saling terhubung dalam satu jaringan | |
| Klaster | Rata-rata koefisien klaster (seberapa sering teman dari teman juga terhubung) | |
| Modularity | Seberapa tegas graf terbagi menjadi komunitas; >0,3 biasanya dianggap struktur komunitas yang jelas | |

**Komunitas** dicari dengan Louvain (resolusi 1, seed 42, graf tak berarah berbobot). Delapan
komunitas terbesar (≥3 akun) diberi warna dan kartu: ukuran, density dalam, relasi ke luar,
**nada SOSIAL** (rata-rata + porsi negatif/netral/positif, baru tampil dari 30 konten bernilai),
dan **kata dominan** dari konten akun paling aktif di komunitas itu.

**Graf akun–unggahan**: siapa berkomentar di video mana (dari URL komentar). Menunjukkan unggahan
dengan komentator terbanyak, akun yang berkomentar di ≥2 unggahan, dan tumpang-tindih komentator
antar-unggahan (Jaccard). Di YouTube ini melengkapi graf balasan, yang hanya mencatat balasan ke
komentar utama.

## Kata yang dipakai (CLAUDE.md §3)

Semua angka adalah **posisi struktural** dalam graf yang teramati. Jangan ditulis sebagai
"akun yang mengendalikan/menggerakkan opini", "buzzer", atau "jaringan terkoordinasi".
Contoh kalimat yang aman: *"Akun X berada pada posisi penghubung (betweenness tertinggi) antara
komunitas K1 dan K3 pada periode ini."*

## Batas teknis

- Graf >25.000 akun dipangkas ke akun dengan interaksi terbanyak (batas memori server 512 MB);
  jumlah semula tampil di kartu "Akun dalam graf".
- Betweenness, eigenvector, dan klaster pada graf >3.000 akun dihitung di inti 3.000 akun
  ber-degree tertinggi; betweenness memakai 250 simpul sumber acak.
- Hasil deterministik (seed tetap): data sama → angka dan peta sama.

## Ekspor ke Gephi

Tombol GEXF / CSV simpul / CSV relasi di bagian bawah halaman (peran Data Analyst ke atas; setiap
unduhan tercatat di audit log). Isinya seluruh graf periode itu: hash akun, nomor komunitas, dan
bobot relasi, tanpa teks konten. Di Gephi: *File → Open* (GEXF), atau *Data Laboratory → Import
Spreadsheet* untuk CSV (simpul dulu, lalu relasi).
