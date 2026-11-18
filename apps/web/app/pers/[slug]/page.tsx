import Link from "next/link";
import type { Route } from "next";
import type { Metadata } from "next";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { PersArticleBody, PersBoard } from "@/components/PersArticleView";
import { PersKinerja } from "@/components/PersKinerja";
import {
  ActorsTable, SourceDaily, SourcePeaks, SourceTone, SourcesTable, TopicsTable, WordsTable, sourceMeta,
} from "@/components/PersLaporan";
import { PersNav } from "@/components/PersNav";
import { PrintButton } from "@/components/PrintButton";
import { citation, dateLabel, getArticle, originOf } from "@/lib/pers";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const res = await getArticle((await params).slug);
  if (res.state !== "ok") return { title: "Artikel" };
  const a = res.data;
  return {
    title: a.title,
    description: a.summary,
    metadataBase: new URL(originOf(await headers())),
    alternates: {
      canonical: `/pers/${a.slug}`,
      types: { "application/rss+xml": "/pers/rss.xml" },
    },
    openGraph: {
      type: "article",
      title: a.title,
      description: a.summary,
      url: `/pers/${a.slug}`,
      siteName: "Riset opini publik",
      locale: "id_ID",
      publishedTime: a.published_at,
      modifiedTime: a.updated_at,
      authors: [a.author_name],
      tags: a.tags,
    },
    twitter: { card: "summary_large_image", title: a.title, description: a.summary },
  };
}

/** Satu artikel terbit dengan angka snapshot, metode, batas, ralat, dan sitasi. */
export default async function PersArticlePage({ params }: Params) {
  const { slug } = await params;
  const res = await getArticle(slug);
  if (res.state === "missing") notFound();
  if (res.state === "unavailable") {
    return (
      <main className="pers">
        <p className="pers-empty">Artikel belum bisa dimuat. Coba lagi nanti.</p>
      </main>
    );
  }
  const a = res.data;
  const report = a.snapshot.report;
  const kinerja = a.snapshot.kind === "kinerja" ? a.snapshot.kinerja : undefined;
  const url = `${originOf(await headers())}/pers/${a.slug}`;

  return (
    <main className="pers">
      <PersNav />
      <article>
        <header className="pers-head">
          <h1>{a.title}</h1>
          <div className="pers-meta">
            {a.author_name} · {dateLabel(a.published_at)}
            {a.version > 1 && ` · versi ${a.version}`}
            {a.tags.map((t) => (
              <Link key={t} href={`/pers?tag=${t}` as Route} className="pers-tag">
                {t}
              </Link>
            ))}
          </div>
          {a.summary && <p>{a.summary}</p>}
        </header>

        <PersBoard snap={a.snapshot} />
        <PersArticleBody body={a.body} snap={a.snapshot} />
      </article>

      <section className="pers-data">
        <h2>Angka di balik artikel ini</h2>
        <p className="pers-meta">
          Periode {a.snapshot.period_start} s.d. {a.snapshot.period_end} ({a.snapshot.timezone}) ·
          dibekukan {dateLabel(a.snapshot.frozen_at)}
        </p>
        {kinerja ? (
          <PersKinerja k={kinerja} />
        ) : (
          <>
        {/* Sumber tidak pernah dijumlahkan: satu baris per sumber (R1). */}
        <SourcesTable sources={report.sources} />
        {report.sources.map((s) => {
          const m = sourceMeta(s.source);
          return (
            <section key={s.source} className="pers-source">
              <h3>
                <span style={{ color: m.color }}>●</span> {m.label}
                <span className="pers-meta"> · {m.meaning}</span>
              </h3>
              <SourceTone s={s} />
              <SourceDaily s={s} />
              <SourcePeaks s={s} />
            </section>
          );
        })}
        <TopicsTable snap={a.snapshot} />
        <ActorsTable snap={a.snapshot} />
        <WordsTable sources={report.sources} />

        {report.methods && Object.keys(report.methods).length > 0 && (
          <>
            <h3>Metode</h3>
            <ul>
              {Object.entries(report.methods).map(([k, v]) => (
                <li key={k}>
                  <b>{k}</b>: {v}
                </li>
              ))}
            </ul>
          </>
        )}

          </>
        )}

        <h3>Batas</h3>
        <ul>
          <li>{a.snapshot.note}</li>
          {(report.limitations ?? []).map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>

        {a.corrections.length > 0 && (
          <>
            <h3>Riwayat ralat</h3>
            <ul>
              {a.corrections.map((c) => (
                <li key={c.version}>
                  Versi {c.version} diganti pada {dateLabel(c.at)}: {c.note}
                </li>
              ))}
            </ul>
          </>
        )}

        <h3>Cara mengutip</h3>
        <p className="pers-cite">{citation(a, url)}</p>

        <h3 className="no-print">Unduh</h3>
        <div className="pers-actions no-print">
          <a className="btn btn-ghost btn-sm" href={`/pers/${a.slug}/data.csv`}>
            Data agregat (CSV)
          </a>
          <a className="btn btn-ghost btn-sm" href={`/pers/${a.slug}/artikel.docx`}>
            Artikel (Word)
          </a>
          <PrintButton />
        </div>
        <p className="pers-meta no-print">
          Berkas CSV hanya memuat hitungan. Teks dan akun penulis konten warga tidak pernah
          disertakan. Cara membaca angkanya: <Link href={"/pers/metodologi" as Route}>Metodologi</Link>.
        </p>
      </section>
    </main>
  );
}
