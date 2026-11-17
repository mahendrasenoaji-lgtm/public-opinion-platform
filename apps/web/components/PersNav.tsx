import Link from "next/link";
import type { Route } from "next";

/** Menu situs publikasi. Semua tautan publik, tanpa sesi. */
export function PersNav() {
  return (
    <nav className="pers-nav no-print" aria-label="Menu publikasi">
      <Link href={"/pers" as Route}>Artikel</Link>
      <Link href={"/pers/metodologi" as Route}>Metodologi</Link>
      <Link href={"/pers/tentang" as Route}>Tentang</Link>
      <a href="/pers/rss.xml">RSS</a>
    </nav>
  );
}
