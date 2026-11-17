import type { Metadata } from "next";
import { PersNav } from "@/components/PersNav";

export const metadata: Metadata = {
  title: "Metodologi",
  description: "Cara angka di setiap artikel dihitung, seberapa tepat, dan apa yang tidak bisa diklaim.",
};

/**
 * Halaman metodologi. Semua angka ketepatan di sini adalah hasil ukur yang
 * tercatat di repo (docs/progress.md, proyek/bbm-bali-youtube/UKUR_ULANG_INFORMAL4.md).
 * Bila penilai sentimen diganti, angka di halaman ini harus diukur ulang, bukan disalin.
 */
export default function Metodologi() {
  return (
    <main className="pers">
      <PersNav />
      <header className="pers-head">
        <div className="kicker">Publikasi hasil riset</div>
        <h1>Metodologi</h1>
        <p>
          Cara angka di setiap artikel dihitung, seberapa tepat alat ukurnya, dan apa yang tidak
          bisa disimpulkan dari angka itu.
        </p>
      </header>

      <div className="pers-prose">
        <h2>Tiga sumber, tidak pernah dijumlahkan</h2>
        <ul>
          <li>
            <b>Survei</b>: sampel probabilistik. Hanya sumber ini yang bisa digeneralisasi ke
            populasi.
          </li>
          <li>
            <b>Percakapan sosial</b>: komentar publik, misalnya di YouTube. Orang yang berkomentar
            memilih sendiri untuk bersuara, jadi angkanya menggambarkan percakapan, bukan
            penduduk.
          </li>
          <li>
            <b>Liputan media</b>: judul dan ringkasan berita. Ini mencerminkan pilihan redaksi,
            bukan pendapat pembaca.
          </li>
        </ul>
        <p>
          Setiap angka di artikel menyebut sumbernya. Angka dari sumber yang berbeda tidak
          dirata-rata dan tidak dijumlah menjadi satu angka.
        </p>

        <h2>Angka dibekukan</h2>
        <p>
          Saat sebuah artikel ditulis, angka untuk periode yang dibahas disalin dan dibekukan.
          Angka di artikel tidak berubah walaupun data di sistem dinilai ulang dengan kamus yang
          lebih baru. Bila ada kekeliruan, artikel diralat: versinya naik dan catatan ralatnya
          tampil di kaki artikel.
        </p>

        <h2>Cara sentimen dinilai</h2>
        <p>
          Sentimen dinilai dengan kamus kata dan pola frasa, bukan dengan model bahasa. Komentar
          dinilai dengan kamus ragam cakap yang mencakup singkatan, kata gaul, 13 bahasa daerah,
          dan 20 pola frasa. Berita dinilai dengan kamus ragam baku. Konten yang tidak memuat kata
          bermuatan yang dikenali <b>tidak dinilai</b>. Konten itu dilaporkan sebagai tidak
          dinilai, tidak dihitung netral.
        </p>

        <h2>Seberapa tepat</h2>
        <div style={{ overflowX: "auto" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th scope="col">Yang diukur</th>
                <th scope="col">Data uji</th>
                <th scope="col">Hasil</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Komentar, kamus ragam cakap</td>
                <td>209 komentar YouTube berlabel manual (belahan uji dari 440)</td>
                <td>26,3% tidak dinilai; akurasi 0,569; macro F1 0,618</td>
              </tr>
              <tr>
                <td>Label negatif pada komentar</td>
                <td>100 komentar acak yang dinilai negatif, dibaca ulang</td>
                <td>95 dari 100 benar (rentang Wilson 89 sampai 98%)</td>
              </tr>
              <tr>
                <td>Judul berita, kamus ragam baku</td>
                <td>160 judul berita nyata</td>
                <td>78,1% tidak dinilai; dari yang dinilai, 0,457 benar</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          Data uji dilabeli oleh satu pelabel dengan bantuan asisten AI, bukan oleh dua pelabel
          manusia yang bekerja terpisah. Angka di atas karena itu batas atas yang optimistis.
          Ketepatan untuk berita rendah, sehingga nada liputan media sebaiknya dibaca sebagai
          petunjuk kasar.
        </p>

        <h2>Ambang tampil</h2>
        <ul>
          <li>Rata-rata dan porsi sentimen harian ditahan bila konten bernilai kurang dari 30.</li>
          <li>
            Lonjakan adalah hari dengan volume minimal 1,5 kali median volume harian sumber itu.
          </li>
          <li>Skor survei per provinsi ditahan bila responden kurang dari 250.</li>
        </ul>
        <p>Bila data tidak cukup, artikel menulis &quot;data tidak cukup&quot;, bukan angka.</p>

        <h2>Yang tidak bisa diklaim</h2>
        <ul>
          <li>
            <b>Nada bukan sikap.</b> Komentar bernada positif bisa memuji pengkritik sebuah
            kebijakan. Sindiran dan pertanyaan retoris sering terbaca keliru.
          </li>
          <li>
            <b>Bukan suara penduduk.</b> Porsi komentar negatif tidak sama dengan porsi warga
            yang menolak.
          </li>
          <li>
            <b>Bukan sebab-akibat.</b> Liputan yang terbit pada hari lonjakan dilaporkan sebagai
            kebersamaan waktu. Artikel memakai kata &quot;berkaitan dengan&quot;, bukan
            &quot;menyebabkan&quot;.
          </li>
          <li>
            <b>Tidak ada penilaian akun.</b> Artikel tidak menyebut akun warga dan tidak menyatakan
            akun mana pun mengendalikan opini.
          </li>
        </ul>

        <h2>Privasi</h2>
        <p>
          Teks dan tautan komentar warga tidak disimpan di artikel dan tidak ada di berkas unduhan.
          Yang terbit hanya hitungan. Yang disebut namanya hanya lembaga dan media, lewat judul
          berita yang memang diterbitkan redaksi.
        </p>
      </div>
    </main>
  );
}
