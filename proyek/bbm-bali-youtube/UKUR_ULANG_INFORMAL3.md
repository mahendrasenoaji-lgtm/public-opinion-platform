# Ukur ulang: kamus bahasa daerah `informal-3` (8 Nov 2026)

Pemicu: pemilik proyek membuka Excel dan menemukan komentar yang jelas negatif berlabel abstain
("heran.. makhluk rendahan ber-IQ primata model begitu kok bisa jadi gubernur. cuih menjijikan.").
Permintaannya: lengkapi kamus dengan bahasa daerah/kesukuan, karena komentar ditulis dalam banyak
bahasa dan tiap bahasa punya arti sendiri.

Catatan: komentar contoh itu sudah terbaca negatif sejak informal-2 ("menjijikan" → jijik). Excel
yang dibuka masih berlabel informal-1 (sengaja tidak ditimpa 6 Nov). Excel sekarang dibuat ulang.

## Apa yang berubah

- Modul baru `apps/api/app/services/regional.py`: kata bermuatan per bahasa (Jawa, Sunda, Bali,
  Betawi/Jakarta, Minang, Batak/Medan, Melayu, Banjar, Palembang, Bugis/Makassar,
  Manado/Maluku/Papua, Madura, Sasak, plus Indonesia cakap), lengkap dengan arti. Negator, larangan,
  dan penguat daerah ("ora", "teu", "tusing", "dak", "ojo", "tenan", "kali", "bes") dipetakan ke
  padanannya lewat normalisasi, sehingga "ora becus" dibaca seperti "tidak becus".
- `EXCLUDED`: kata yang artinya berbeda antarbahasa, tidak dinilai sama sekali, dengan alasan per kata.
  Contoh: "sing" (Bali 'tidak', Jawa 'yang'), "seng" (Ambon 'tidak', Jawa Timur 'yang'), "ambek"
  (Sunda 'marah', Jawa Timur 'dengan'), "goreng" (Sunda 'jelek'), "aja" (Jawa 'jangan', cakap 'saja').
- Ragam baku (liputan media) tidak bergeser: `lexicon-id-1` tetap.
- Excel: kolom baru "Kata penanda (bobot)" dan "Bahasa kata penanda", sheet baru "Kamus daerah".

## Hasil (36.319 komentar BBM Bali)

| | informal-2 | informal-3 |
|---|---|---|
| Komentar tidak dinilai (abstain) | 17.727 (48,8%) | 16.965 (46,7%) |
| Negatif di antara yang dinilai | 69,8% | 71,2% |
| Label sama pada 18.592 yang sudah dinilai | | 98,7% |
| Label manual negatif (sampel 400) yang masih abstain | 208 dari 279 | 198 dari 279 |
| Evaluasi lapangan MBG (belahan uji) abstain / akurasi / F1 makro | 26,3% / 0,569 / 0,618 | sama persis |

**Presisi komentar yang baru dinilai.** 100 komentar unik acak (seed 20261108, di luar sampel 400)
yang abstain di informal-2 dan dinilai informal-3, dilabeli tanpa melihat skor alat
(`sampel_buta_100_informal3.csv`; pelabel: Claude, satu orang, bukan penutur asli semua bahasa):
dari yang alat beri label **negatif, 95,6% benar (86/90; Wilson 95%: 89–98%)**.

Label **positif** buruk pada percobaan pertama (1 dari 8 benar), sehingga empat kata positif
dikeluarkan: "seneng" dan "demen" (di data hampir selalu tuduhan: "seneng lihat rakyat menderita"),
"merakyat" (tuntutan: "coba sedikit merakyat"), "cakep" (menilai benda). "rusuh" juga dikeluarkan:
21% kemunculannya bernegasi ("warga Bali tidak rusuh").

Perubahan label pada komentar yang sudah dinilai: positif → netral 112 (kebanyakan karena "rasis":
"azab daerah yang suka rasis" dulu positif karena "suka"), netral → negatif 80, negatif → positif 9
(pertanyaan retoris dengan negator daerah: "apa kaga malu", "kok dak dicopot" — kelemahan lama aturan
negasi yang juga berlaku untuk "tidak").

## Jujurnya: kenapa abstain hanya turun 2 poin

Kamus bahasa daerah menangkap makian dan kata nilai yang jelas, tapi sebagian besar komentar yang
masih abstain tidak memuat kata seperti itu. Isinya kalimat biasa yang maknanya negatif dari
konteks ("gubernur suruh jaga sendiri SPBU-nya"), sindiran, pertanyaan retoris, atau kiasan
("ber-IQ primata"). Itu batas metode kamus mana pun, bukan kekurangan entri. 60 dari 153 kata
daerah tidak muncul sama sekali di data ini; bahasa di luar Bali/Jawa baru teruji kalau ada proyek
dari daerahnya.

Perkiraan proporsi negatif yang jujur tetap dari sampel manual (sekitar 67%, 64–70%), bukan dari
alat.

## Belum dilakukan

- Platform (Vercel) masih informal-2 sampai PR ini digabung dan komentar SOCIAL dinilai ulang
  (rescore otomatis mengenali versi baru).
- Laporan HTML/PDF/PPTX masih angka informal-2.
- Pelabel kedua, terutama penutur asli Bali/Jawa, untuk menguji presisi kata daerah.
- Perbaikan `_modifier`: "harusnya mengayomi, bukan bentak" dan "gak usah lebay" masih membalik
  kata negatif jadi positif.

## Skrip

- `skrip/ukur_ulang_informal3.py` — angka di atas, termasuk per kata: jumlah komentar dan persen terbalik negasi.
- `skrip/ambil_sampel_buta_informal3.py tulis|nilai` — sampel buta.
- `skrip/analyze_bbm.py` — CSV/XLSX baru (label informal-1 lama: `label_informal1_per_komentar.csv`).
