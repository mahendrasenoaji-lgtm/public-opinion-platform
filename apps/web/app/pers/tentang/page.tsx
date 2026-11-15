import Link from "next/link";
import type { Route } from "next";
import type { Metadata } from "next";
import { PersNav } from "@/components/PersNav";

export const metadata: Metadata = {
  title: "Tentang",
  description: "Apa itu Riset opini publik, siapa yang menerbitkan, dan cara mengutipnya.",
};

export default function Tentang() {
  return (
    <main className="pers">
      <PersNav />
      <header className="pers-head">
        <div className="kicker">Publikasi hasil riset</div>
        <h1>Tentang</h1>
      </header>

      <div className="pers-prose">
        <p>
          Riset opini publik menerbitkan hasil pembacaan percakapan publik, liputan media, dan
          survei tentang isu kebijakan di Indonesia. Setiap artikel memuat angka yang dibekukan,
          sumbernya, cara menghitungnya, dan batasnya.
        </p>

        <h2>Cara artikel terbit</h2>
        <ul>
          <li>Peneliti menyusun draf dari data satu periode yang tetap.</li>
          <li>Draf ditinjau orang lain sebelum terbit.</li>
          <li>Hanya direktur riset yang menerbitkan.</li>
          <li>
            Artikel yang sudah terbit tidak dihapus dan tidak diubah diam-diam. Perubahan dicatat
            sebagai ralat dengan nomor versi.
          </li>
        </ul>

        <h2>Yang tidak kami lakukan</h2>
        <ul>
          <li>Menyebut atau menilai akun warga.</li>
          <li>Menebak agama, etnis, kesehatan, atau pilihan politik seseorang.</li>
          <li>Menyatakan sebab-akibat dari data pengamatan.</li>
          <li>Menampilkan angka bila datanya tidak cukup.</li>
        </ul>

        <h2>Mengutip dan memakai data</h2>
        <p>
          Setiap artikel menyediakan saran sitasi, berkas data agregat (CSV), dan versi Word.
          Sebutkan nomor versi bila artikel pernah diralat. Penjelasan angka ada di halaman{" "}
          <Link href={"/pers/metodologi" as Route}>Metodologi</Link>. Artikel baru bisa diikuti
          lewat <a href="/pers/rss.xml">feed RSS</a>.
        </p>
      </div>
    </main>
  );
}
