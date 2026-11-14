# Panduan data akun resmi (Instagram, TikTok, X)

Untuk modul Kinerja Komunikasi (`/kinerja`). YouTube diambil otomatis lewat formulir
"Ambil dari kanal YouTube resmi". Instagram, TikTok, dan X **tidak** diambil otomatis:
platform ini hanya memakai API resmi (`apps/api/app/connectors/base.py`), dan ketiga
platform itu tidak membuka data akun lembaga lain tanpa akses khusus. Jalurnya adalah
**unggah berkas** (JSON atau CSV) yang diisi peneliti dari tampilan publik akun resmi.

Diputuskan 15 November 2026 sebagai jalur bawaan karena tidak butuh biaya maupun akses
baru. Bila nanti tersedia ekspor alat pihak ketiga yang sah, atau akses Instagram
Business Discovery lewat akun Business milik organisasi, berkasnya tetap masuk lewat
formulir unggah yang sama.

## 1. Templat

Di `/kinerja` → "Unggah data akun resmi" → **Unduh templat CSV**. Templat hanya berisi
kepala kolom (tanpa baris contoh, supaya contoh tidak ikut tersimpan sebagai data):

```
platform,account,external_id,posted_at,kind,url,caption,likes,comments,shares,views,followers,captured_at,saves,reach,impressions
```

Kolom wajib: `platform` (`instagram`, `tiktok`, `x`, `youtube`), `account`, `external_id`,
`posted_at`. **Angka yang tidak tampil dibiarkan kosong, jangan diisi 0.** Kosong berarti
"tidak terlihat", nol berarti "terlihat dan nilainya nol"; keduanya dihitung berbeda.

## 2. Apa yang tampil publik di tiap platform

| Kolom | Instagram | TikTok | X |
|---|---|---|---|
| `external_id` | kode di URL: `/p/<kode>/` atau `/reel/<kode>/` | angka di URL: `/video/<id>` | angka di URL: `/status/<id>` |
| `likes` | tampil, kecuali disembunyikan pemilik akun → kosong | tampil | tampil |
| `comments` | tampil (jumlah komentar) | tampil | jumlah balasan |
| `shares` | **tidak tampil** → kosong | tampil | jumlah repost (+ kutipan, catat di `caption` bila dipisah) |
| `views` | hanya Reels/video | tampil | tampil |
| `saves` | tidak tampil (hanya insight pemilik) | jumlah simpan tampil publik | jumlah markah tampil publik |
| `followers` | di profil, saat pencatatan | di profil | di profil |
| `reach`, `impressions` | hanya insight pemilik akun | hanya insight pemilik akun | hanya insight pemilik akun |
| `kind` | foto / karusel / reels | video / foto | teks / foto / video |

## 3. Cara mencatat supaya bisa dibandingkan

1. **Catat pada umur unggahan yang sama**, misalnya 7 hari setelah terbit. Angka unggahan
   lama terus bertambah; membandingkan unggahan kemarin dengan unggahan sebulan lalu tidak
   adil. Isi `captured_at` dengan waktu pencatatan.
2. `followers` adalah jumlah pengikut **saat pencatatan**, bukan saat unggahan terbit.
3. `posted_at` dalam ISO 8601 dengan zona waktu, mis. `2026-11-10T09:30:00+07:00`.
4. Satu akun cukup satu nama `account` yang konsisten (pakai handle, mis. `@kemenhut`).
5. Mengunggah ulang baris dengan `platform` + `external_id` yang sama **memperbarui**
   angkanya, tidak menggandakan.

## 4. Akun resmi lembaga pangan (diverifikasi dari situs `.go.id` masing-masing, 14 Nov 2026)

| Lembaga | YouTube | Instagram | TikTok |
|---|---|---|---|
| Kementan | `@kementanri` (ID `UC757MLmzhe5QXlr9yWyHcpQ`) | `kementerianpertanian` | `@kementanri` |
| Kemenhut | `@Kemenhut_RI` | `kemenhut` | tidak dicantumkan di situs |
| KKP | `@KKP_RI` | `kkpgoid` | `@kkp.go.id` |
| KLH/BPLH | `@KLH-BPLH` | `kemenlh_bplh` | tidak dicantumkan di situs |
| Bapanas | `@badanpangannasionalofficial` | `badanpangannasional` | tidak dicantumkan di situs |
| BGN | `@BadanGiziNasional` (dari ppid.bgn.go.id) | `badangizinasional.ri` | `@badan.gizi.nasional.ri` |

"Tidak dicantumkan di situs" berarti alamatnya belum diverifikasi; jangan ditebak.

## 5. Batas

- Hanya pencatatan manual dari tampilan publik, atau ekspor alat yang memakai akses sah.
  Jangan memakai alat yang mengambil data dengan menyamar sebagai peramban atau
  melewati batas platform (lihat `base.py`).
- Angka publik mengukur interaksi, bukan pemahaman atau kepercayaan (indikator C1, C5
  butuh kuesioner).
- Akun resmi lembaga disimpan di `official_posts`, terpisah dari percakapan warga, jadi
  tidak pernah ikut terhitung dalam sentimen publik (CLAUDE.md R1).
