import Link from "next/link";
import type { Route } from "next";
import type { Metadata } from "next";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { parseMarkdown, type Inline } from "@/lib/miniMarkdown";
import { citation, dateLabel, getArticle, share } from "@/lib/pers";
import { SOURCE } from "@/lib/tokens";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const res = await getArticle((await params).slug);
  if (res.state !== "ok") return { title: "Artikel" };
  return { title: res.data.title, description: res.data.summary };
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
  const h = await headers();
  const url = `${h.get("x-forwarded-proto") ?? "https"}://${h.get("host") ?? ""}/pers/${a.slug}`;

  return (
    <main className="pers">
      <p className="pers-meta">
        <Link href={"/pers" as Route}>← Semua artikel</Link>
      </p>
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
      </section>
    </main>
  );
}
