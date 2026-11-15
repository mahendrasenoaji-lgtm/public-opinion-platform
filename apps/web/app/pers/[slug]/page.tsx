import Link from "next/link";
import type { Route } from "next";
import type { Metadata } from "next";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { parseMarkdown, type Inline } from "@/lib/miniMarkdown";
import { PersDailyCharts } from "@/components/PersCharts";
import { PersNav } from "@/components/PersNav";
import { PrintButton } from "@/components/PrintButton";
import { citation, dateLabel, dayLabel, getArticle, originOf, share } from "@/lib/pers";
import { SOURCE } from "@/lib/tokens";

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

const LABELS = [
  ["negatif", "Negatif", "var(--neg)"],
  ["netral", "Netral", "var(--muted-fill)"],
  ["positif", "Positif", "var(--pos)"],
] as const;

/** http(s) saja: tautan liputan berasal dari feed, jadi skemanya diperiksa. */
function safeHref(url: string | null | undefined): string | null {
  return url && /^https?:\/\//i.test(url) ? url : null;
}

function Text({ inline }: { inline: Inline[] }) {
  return <>{inline.map((p, i) => (p.bold ? <b key={i}>{p.text}</b> : <span key={i}>{p.text}</span>))}</>;
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

        <div className="pers-body">
          {parseMarkdown(a.body).map((b, i) =>
            b.type === "ul" ? (
              <ul key={i}>
                {b.items.map((item, j) => (
                  <li key={j}>
                    <Text inline={item} />
                  </li>
                ))}
              </ul>
            ) : b.type === "h2" ? (
              <h2 key={i}>
                <Text inline={b.inline} />
              </h2>
            ) : b.type === "h3" ? (
              <h3 key={i}>
                <Text inline={b.inline} />
              </h3>
            ) : (
              <p key={i}>
                <Text inline={b.inline} />
              </p>
            ),
          )}
        </div>
      </article>

      <section className="pers-data">
        <h2>Angka di balik artikel ini</h2>
        <p className="pers-meta">
          Periode {a.snapshot.period_start} s.d. {a.snapshot.period_end} ({a.snapshot.timezone}) ·
          dibekukan {dateLabel(a.snapshot.frozen_at)}
        </p>
        {/* Sumber tidak pernah dijumlahkan: satu baris per sumber (R1). */}
        <div style={{ overflowX: "auto" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th scope="col">Sumber</th>
                <th scope="col">Konten</th>
                <th scope="col">Bernilai sentimen</th>
                <th scope="col">Negatif</th>
                <th scope="col">Netral</th>
                <th scope="col">Positif</th>
              </tr>
            </thead>
            <tbody>
              {report.sources.map((s) => {
                const meta = SOURCE[s.source as keyof typeof SOURCE];
                return (
                  <tr key={s.source}>
                    <td>
                      <span style={{ color: meta?.color }}>●</span> {meta?.label ?? s.source}
                      <div className="proj-s">{meta?.meaning}</div>
                    </td>
                    <td className="mono">{s.n.toLocaleString("id-ID")}</td>
                    <td className="mono">{s.scored.toLocaleString("id-ID")}</td>
                    {(["negatif", "netral", "positif"] as const).map((k) => (
                      <td key={k} className="mono">
                        {share(s.labels, k, s.scored) ?? "data tidak cukup"}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {report.sources.length === 0 && <p className="pers-empty">Tidak ada data pada periode ini.</p>}

        {report.sources.map((s) => {
          const meta = SOURCE[s.source as keyof typeof SOURCE];
          const label = meta?.label ?? s.source;
          const unscored = s.n - s.scored;
          return (
            <section key={s.source} className="pers-source">
              <h3>
                <span style={{ color: meta?.color }}>●</span> {label}
                <span className="pers-meta"> · {meta?.meaning}</span>
              </h3>

              {s.scored > 0 && (
                <figure>
                  <figcaption>
                    Nada {s.scored.toLocaleString("id-ID")} konten yang bernilai sentimen
                  </figcaption>
                  <div className="pers-stack" role="img" aria-label={LABELS.map(([k, name]) => `${name} ${share(s.labels, k, s.scored)}`).join(", ")}>
                    {LABELS.map(([k, name, color]) =>
                      (s.labels[k] ?? 0) > 0 ? (
                        <span
                          key={k}
                          title={`${name}: ${(s.labels[k] ?? 0).toLocaleString("id-ID")} konten (${share(s.labels, k, s.scored)})`}
                          style={{ flexGrow: s.labels[k], background: color }}
                        />
                      ) : null,
                    )}
                  </div>
                  <div className="pers-legend">
                    {LABELS.map(([k, name, color]) => (
                      <span key={k}>
                        <i style={{ background: color }} /> {name}{" "}
                        <b className="mono">{share(s.labels, k, s.scored)}</b>
                      </span>
                    ))}
                  </div>
                  {unscored > 0 && (
                    <p className="pers-meta">
                      {unscored.toLocaleString("id-ID")} konten lain (
                      {((unscored / s.n) * 100).toFixed(1).replace(".", ",")}%) tidak dinilai karena
                      tidak memuat kata bermuatan yang dikenali. Konten itu tidak dihitung netral.
                    </p>
                  )}
                </figure>
              )}

              {s.days && s.days.length > 1 && (
                <>
                  <PersDailyCharts days={s.days} color={meta?.color ?? "var(--txt2)"} sourceLabel={label} />
                  <details className="pers-details">
                    <summary>Lihat angka per hari sebagai tabel</summary>
                    <div style={{ overflowX: "auto" }}>
                      <table className="tbl">
                        <thead>
                          <tr>
                            <th scope="col">Hari</th>
                            <th scope="col">Konten</th>
                            <th scope="col">Bernilai sentimen</th>
                            <th scope="col">Porsi negatif</th>
                          </tr>
                        </thead>
                        <tbody>
                          {s.days.map((d) => (
                            <tr key={d.day}>
                              <td>{dayLabel(d.day)}</td>
                              <td className="mono">{d.volume.toLocaleString("id-ID")}</td>
                              <td className="mono">{d.scored.toLocaleString("id-ID")}</td>
                              <td className="mono">
                                {d.negative_share === null
                                  ? "data tidak cukup"
                                  : `${(d.negative_share * 100).toFixed(1).replace(".", ",")}%`}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
                </>
              )}

              {(s.peaks ?? []).map((p) => {
                const news = p.same_day_media.filter((m) => m.text);
                return (
                  <div key={p.day} className="pers-peak">
                    <b>{dayLabel(p.day)}</b>: {p.volume.toLocaleString("id-ID")} konten
                    {p.is_spike && p.ratio !== null
                      ? `, ${String(p.ratio).replace(".", ",")} kali median harian (lonjakan)`
                      : " (hari teramai, bukan lonjakan)"}
                    {news.length > 0 && (
                      <>
                        <div className="pers-meta">
                          Liputan yang terbit pada hari yang sama (kebersamaan waktu, bukan sebab):
                        </div>
                        <ul>
                          {news.map((m, i) => {
                            const href = safeHref(m.source_url);
                            return (
                              <li key={i}>
                                {href ? (
                                  <a href={href} rel="noopener noreferrer nofollow">
                                    {m.text}
                                  </a>
                                ) : (
                                  m.text
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      </>
                    )}
                  </div>
                );
              })}
            </section>
          );
        })}

        {report.sources.map((s) =>
          s.words && s.words.length > 0 ? (
            <p key={s.source} className="pers-meta">
              Kata terbanyak ({SOURCE[s.source as keyof typeof SOURCE]?.label ?? s.source}):{" "}
              {s.words.slice(0, 12).map(([w, n]) => `${w} (${n.toLocaleString("id-ID")})`).join(", ")}
            </p>
          ) : null,
        )}

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
