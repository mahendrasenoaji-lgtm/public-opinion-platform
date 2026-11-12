import Link from "next/link";
import type { Route } from "next";
import type { Metadata } from "next";
import { dateLabel, listArticles } from "@/lib/pers";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Publikasi hasil riset",
  description: "Artikel hasil riset opini publik, lengkap dengan metode dan batas tiap angka.",
};

/** Beranda publik: daftar artikel terbit. Tanpa login, baca-saja. */
export default async function PersHome({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const tag = (Array.isArray(sp.tag) ? sp.tag[0] : sp.tag)?.trim() || undefined;
  const res = await listArticles(tag);

  return (
    <main className="pers">
      <header className="pers-head">
        <div className="kicker">Publikasi hasil riset</div>
        <h1>Riset opini publik</h1>
        <p>
          Setiap artikel memuat angka yang dibekukan pada saat ditulis, beserta sumber, metode, dan
          batasnya. Konten warga hanya tampil sebagai agregat.
        </p>
      </header>

      {tag && (
        <p className="pers-meta">
          Tag: <b>{tag}</b> · <Link href={"/pers" as Route}>tampilkan semua</Link>
        </p>
      )}

      {res.state !== "ok" ? (
        <p className="pers-empty">Daftar artikel belum bisa dimuat. Coba lagi nanti.</p>
      ) : res.data.items.length === 0 ? (
        <p className="pers-empty">Belum ada artikel yang terbit.</p>
      ) : (
        <ul className="pers-list">
          {res.data.items.map((a) => (
            <li key={a.slug}>
              <Link href={`/pers/${a.slug}` as Route} className="pers-title">
                {a.title}
              </Link>
              <p>{a.summary}</p>
              <div className="pers-meta">
                {a.author_name} · {dateLabel(a.published_at)}
                {a.tags.map((t) => (
                  <Link key={t} href={`/pers?tag=${t}` as Route} className="pers-tag">
                    {t}
                  </Link>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
