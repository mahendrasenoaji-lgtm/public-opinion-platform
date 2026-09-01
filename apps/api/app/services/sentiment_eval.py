"""Set evaluasi berlabel manual untuk `services/sentiment.py`.

`docs/roadmap.md` mensyaratkan set ini ada SEBELUM sentiment dinyalakan di
proyek nyata, dan akurasinya dilaporkan di UI. File ini memenuhi syarat
pertama; `GET /projects/{id}/signals/sentiment-quality` memenuhi yang kedua.

## Apa yang set ini bisa dan tidak bisa buktikan

Kalimat di bawah ditulis oleh tim pengembang dengan meniru bentuk komentar
publik Indonesia tentang kebijakan. Itu berarti:

- **Bisa** membuktikan leksikon berperilaku seperti yang dimaksudkan: negasi
  membalik, penguat memperkuat, kalimat faktual tidak dipaksa berlabel.
- **Bisa** menangkap regresi — kalau seseorang mengubah leksikon dan angkanya
  jatuh, ada yang rusak.
- **TIDAK bisa** memperkirakan akurasi pada percakapan sungguhan. Kalimat yang
  ditulis sendiri selalu lebih rapi, lebih pendek, dan lebih jelas
  polaritasnya daripada yang ditemukan di lapangan. Angka dari set ini adalah
  batas ATAS, bukan perkiraan.

Kasus yang sengaja dimasukkan walaupun diketahui akan gagal (sarkasme, ironi,
kalimat campuran) ditandai dengan komentar. Menghapusnya akan menaikkan
akurasi tanpa membuat alatnya lebih baik — itu menipu diri sendiri.

Bahasa Indonesia sehari-hari di media sosial banyak memakai bentuk tidak baku;
sebagian ada di sini karena memang begitu bentuk datanya.
"""

from __future__ import annotations

#: (teks, label_benar). Label: "positif" | "netral" | "negatif".
LABELED: list[tuple[str, str]] = [
    # ---------------------------------------------------------- positif ----
    ("Programnya sangat membantu keluarga kami yang penghasilannya pas-pasan", "positif"),
    ("Saya puas dengan pelayanan di kantor kecamatan sekarang, cepat dan ramah", "positif"),
    ("Kebijakan ini adil untuk warga kecil, saya mendukung penuh", "positif"),
    ("Alhamdulillah bantuan sudah cair, lega rasanya", "positif"),
    ("Petugasnya profesional dan transparan soal biaya", "positif"),
    ("Hasilnya bagus sekali, jauh lebih baik dari tahun lalu", "positif"),
    ("Saya apresiasi langkah pemerintah daerah yang responsif kali ini", "positif"),
    ("Prosesnya mudah dan lancar, tidak berbelit seperti dulu", "positif"),
    ("Harganya jadi terjangkau buat warga, ini solutif", "positif"),
    ("Bangga dengan capaian ini, semoga terus membaik", "positif"),
    ("Saya setuju dengan arah kebijakannya, sudah tepat sasaran", "positif"),
    ("Pelayanan online-nya efektif, hemat waktu banget", "positif"),
    # negasi yang membalik ke positif
    ("Ternyata tidak susah kok mengurusnya, saya salah duga", "positif"),
    ("Sistemnya sama sekali tidak ribet, malah cepat", "positif"),
    # penguat
    ("Mantap sekali kerja timnya, salut", "positif"),
    ("Bantuan pangan ini benar benar bermanfaat untuk warga terdampak", "positif"),

    # ---------------------------------------------------------- negatif ----
    ("Pelayanannya buruk sekali, saya kecewa berat", "negatif"),
    ("Sudah tiga bulan tidak ada kejelasan, ini mengecewakan", "negatif"),
    ("Kebijakan ini memberatkan rakyat kecil", "negatif"),
    ("Harga kebutuhan pokok makin mahal, hidup makin susah", "negatif"),
    ("Prosesnya berbelit dan lambat, bikin kesal", "negatif"),
    ("Saya menolak rencana ini, tidak adil buat warga sini", "negatif"),
    ("Anggarannya diduga dikorupsi, warga marah", "negatif"),
    ("Datanya kacau, banyak yang tidak terdaftar padahal berhak", "negatif"),
    ("Saya khawatir dampaknya ke pedagang kecil", "negatif"),
    ("Percuma saja lapor, tidak pernah ditanggapi", "negatif"),
    ("Aturan barunya rumit dan membebani UMKM", "negatif"),
    ("Petugasnya abai, dibiarkan antre berjam-jam", "negatif"),
    ("Saya pesimis target ini tercapai, terlalu jauh dari kenyataan", "negatif"),
    ("Warga resah karena informasinya simpang siur", "negatif"),
    # negasi yang membalik ke negatif
    ("Pelayanannya tidak bagus, malah bikin bingung", "negatif"),
    ("Hasilnya kurang memuaskan buat saya", "negatif"),
    ("Sistem barunya nggak membantu sama sekali", "negatif"),

    # ----------------------------------------------------------- netral ----
    ("Rapat koordinasi dijadwalkan hari Kamis pukul sembilan pagi", "netral"),
    ("Pendaftaran dibuka mulai tanggal satu sampai lima belas bulan depan", "netral"),
    ("Ada tiga syarat dokumen yang harus dilampirkan", "netral"),
    ("Kantornya pindah ke gedung sebelah mulai minggu ini", "netral"),
    ("Jumlah penerima tahap kedua berbeda dengan tahap pertama", "netral"),
    ("Sosialisasi dilakukan di dua belas kecamatan", "netral"),
    ("Saya sedang menunggu pengumuman hasil verifikasi", "netral"),
    ("Formulirnya bisa diunduh di situs resmi", "netral"),
    ("Apakah ada yang sudah menerima pemberitahuan?", "netral"),
    ("Anggarannya bersumber dari APBD tahun berjalan", "netral"),
    ("Programnya berjalan sejak dua tahun lalu", "netral"),
    ("Ini pengumuman resmi dari dinas terkait", "netral"),
    # campuran: dua sisi seimbang, jawaban yang benar memang di tengah
    ("Pelayanannya cepat tapi biayanya mahal", "netral"),
    ("Programnya bagus, sayangnya sosialisasinya kurang", "netral"),

    # ------------------------------------------- kasus sukar (disengaja) ----
    # Sarkasme: leksikon akan membacanya positif. Dibiarkan supaya kegagalan
    # ini ikut terhitung, bukan disembunyikan dari laporan akurasi.
    ("Bagus sekali, sudah bayar pajak malah jalannya rusak parah", "negatif"),
    ("Mantap, antre dari subuh cuma untuk disuruh pulang", "negatif"),
    # Ironi halus tanpa kata bermuatan sama sekali — akan abstain.
    ("Sudah dijanjikan sejak lima tahun lalu, sampai sekarang begitu saja", "negatif"),
    # Kata negatif dipakai dalam kalimat yang justru memuji pemberantasannya.
    # Leksikon tidak punya cara membedakan ini; kegagalan yang jujur.
    ("Pemberantasan korupsi tahun ini berhasil, saya apresiasi", "positif"),
    # Kata "demo" netral dalam konteks berita, bermuatan dalam konteks opini.
    ("Demo berlangsung di depan kantor gubernur sejak pagi", "netral"),
]
