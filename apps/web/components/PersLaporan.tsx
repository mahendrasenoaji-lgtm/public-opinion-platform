import { PersDailyCharts } from "@/components/PersCharts";
import { dayLabel, idNum, share, type PersSnapshot, type PersSource } from "@/lib/pers";
import { SOURCE } from "@/lib/tokens";

/**
 * Potongan tampilan snapshot Laporan Percakapan. Dipakai dua kali: sebagai
 * penanda blok di dalam isi artikel (`[[nada]]`, `[[grafik-harian]]`, ...) dan
 * di bagian "Angka di balik artikel ini". Sumber tidak pernah digabung (R1).
 */

const LABELS = [
  ["negatif", "Negatif", "var(--neg)"],
  ["netral", "Netral", "var(--muted-fill)"],
  ["positif", "Positif", "var(--pos)"],
] as const;

export function sourceMeta(source: string) {
  const meta = SOURCE[source as keyof typeof SOURCE];
  return { label: meta?.label ?? source, color: meta?.color ?? "var(--txt2)", meaning: meta?.meaning ?? "" };
}

/** http(s) saja: tautan liputan berasal dari feed, jadi skemanya diperiksa. */
function safeHref(url: string | null | undefined): string | null {
  return url && /^https?:\/\//i.test(url) ? url : null;
}

function signed(n: number | null): string {
  if (n === null) return "data tidak cukup";
  return n.toFixed(2).replace(".", ",").replace("-", "−");
}

/** Lebar batang relatif terhadap baris terbesar, minimal tetap terlihat. */
function Bar({ n, max, color }: { n: number; max: number; color?: string }) {
  const w = max > 0 ? Math.max(2, (n / max) * 100) : 0;
  return (
    <td className="pers-barcell" aria-hidden="true">
      <span style={{ width: `${w}%`, background: color }} />
    </td>
  );
}

export function SourcesTable({ sources }: { sources: PersSource[] }) {
  if (sources.length === 0) return <p className="pers-empty">Tidak ada data pada periode ini.</p>;
  return (
    <div className="pers-tbl-wrap">
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
          {sources.map((s) => {
            const m = sourceMeta(s.source);
            return (
              <tr key={s.source}>
                <td>
                  <span style={{ color: m.color }}>●</span> {m.label}
                  <div className="proj-s">{m.meaning}</div>
                </td>
                <td className="mono">{idNum(s.n)}</td>
                <td className="mono">{idNum(s.scored)}</td>
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
  );
}

export function SourceTone({ s, titled = false }: { s: PersSource; titled?: boolean }) {
  if (s.scored <= 0) return null;
  const m = sourceMeta(s.source);
  const unscored = s.n - s.scored;
  return (
    <figure className="pers-fig">
      <figcaption>
        Nada {idNum(s.scored)} konten yang bernilai sentimen{titled ? ` (${m.label})` : ""}
      </figcaption>
      <div
        className="pers-stack"
        role="img"
        aria-label={LABELS.map(([k, name]) => `${name} ${share(s.labels, k, s.scored)}`).join(", ")}
      >
        {LABELS.map(([k, name, color]) =>
          (s.labels[k] ?? 0) > 0 ? (
            <span
              key={k}
              title={`${name}: ${idNum(s.labels[k])} konten (${share(s.labels, k, s.scored)})`}
              style={{ flexGrow: s.labels[k], background: color }}
            />
          ) : null,
        )}
      </div>
      <div className="pers-legend">
        {LABELS.map(([k, name, color]) => (
          <span key={k}>
            <i style={{ background: color }} /> {name} <b className="mono">{share(s.labels, k, s.scored)}</b>
          </span>
        ))}
      </div>
      {unscored > 0 && (
        <p className="pers-meta">
          {idNum(unscored)} konten lain ({((unscored / s.n) * 100).toFixed(1).replace(".", ",")}%) tidak dinilai
          karena tidak memuat kata bermuatan yang dikenali. Konten itu tidak dihitung netral.
        </p>
      )}
    </figure>
  );
}

export function SourceDaily({ s, withTable = true }: { s: PersSource; withTable?: boolean }) {
  if (!s.days || s.days.length < 2) return null;
  const m = sourceMeta(s.source);
  return (
    <>
      <PersDailyCharts days={s.days} color={m.color} sourceLabel={m.label} />
      {withTable && (
        <details className="pers-details">
          <summary>Lihat angka per hari sebagai tabel</summary>
          <div className="pers-tbl-wrap">
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
                    <td className="mono">{idNum(d.volume)}</td>
                    <td className="mono">{idNum(d.scored)}</td>
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
      )}
    </>
  );
}

export function SourcePeaks({ s }: { s: PersSource }) {
  return (
    <>
      {(s.peaks ?? []).map((p) => {
        const news = p.same_day_media.filter((m) => m.text);
        return (
          <div key={p.day} className="pers-peak">
            <b>{dayLabel(p.day)}</b>: {idNum(p.volume)} konten
            {p.is_spike && p.ratio !== null
              ? `, ${String(p.ratio).replace(".", ",")} kali median harian (lonjakan)`
              : " (hari teramai, bukan lonjakan)"}
            {news.length > 0 && (
              <>
                <div className="pers-meta">Liputan yang terbit pada hari yang sama (kebersamaan waktu, bukan sebab):</div>
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
    </>
  );
}

export function TopicsTable({ snap }: { snap: PersSnapshot }) {
  const topics = snap.report.topics ?? [];
  if (topics.length === 0) return null;
  const bySource = [...new Set(topics.map((t) => t.source))];
  return (
    <>
      {bySource.map((src) => {
        const rows = topics.filter((t) => t.source === src).sort((a, b) => b.n - a.n);
        const max = rows[0]?.n ?? 0;
        const m = sourceMeta(src);
        return (
          <figure key={src} className="pers-fig">
            <figcaption>Tema yang dibicarakan ({m.label}); satu konten bisa masuk lebih dari satu tema</figcaption>
            <div className="pers-tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th scope="col">Tema</th>
                    <th scope="col" className="num">Konten</th>
                    <th scope="col" aria-hidden="true" />
                    <th scope="col" className="num">Nada rata-rata</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((t) => (
                    <tr key={t.label}>
                      <td>{t.label}</td>
                      <td className="mono num">{idNum(t.n)}</td>
                      <Bar n={t.n} max={max} color={m.color} />
                      <td className="mono num">{signed(t.sentiment)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </figure>
        );
      })}
    </>
  );
}

export function ActorsTable({ snap }: { snap: PersSnapshot }) {
  const groups = (snap.actors ?? []).filter((g) => g.actors.length > 0);
  if (groups.length === 0) return null;
  return (
    <>
      {groups.map((g) => {
        const m = sourceMeta(g.source);
        const max = g.actors[0]?.n ?? 0;
        return (
          <figure key={g.source} className="pers-fig">
            <figcaption>
              Tokoh yang paling sering disebut ({m.label})
              {g.n_total ? `; ${idNum(g.n_with_actor)} dari ${idNum(g.n_total)} konten menyebut setidaknya satu tokoh` : ""}
            </figcaption>
            <div className="pers-tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th scope="col">Tokoh</th>
                    <th scope="col" className="num">Konten</th>
                    <th scope="col" aria-hidden="true" />
                    <th scope="col" className="num">Nada konten yang menyebutnya</th>
                  </tr>
                </thead>
                <tbody>
                  {g.actors.map((a) => (
                    <tr key={a.name}>
                      <td>{a.name}</td>
                      <td className="mono num">{idNum(a.n)}</td>
                      <Bar n={a.n} max={max} color={m.color} />
                      <td className="mono num">{signed(a.sentiment)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </figure>
        );
      })}
    </>
  );
}

export function WordsTable({ sources }: { sources: PersSource[] }) {
  const withWords = sources.filter((s) => s.words && s.words.length > 0);
  if (withWords.length === 0) return null;
  return (
    <>
      {withWords.map((s) => {
        const m = sourceMeta(s.source);
        const words = (s.words ?? []).slice(0, 12);
        const max = words[0]?.[1] ?? 0;
        return (
          <figure key={s.source} className="pers-fig">
            <figcaption>Kata terbanyak ({m.label})</figcaption>
            <div className="pers-tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th scope="col">Kata</th>
                    <th scope="col" className="num">Muncul</th>
                    <th scope="col" aria-hidden="true" />
                  </tr>
                </thead>
                <tbody>
                  {words.map(([w, n]) => (
                    <tr key={w}>
                      <td>{w}</td>
                      <td className="mono num">{idNum(n)}</td>
                      <Bar n={n} max={max} color={m.color} />
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </figure>
        );
      })}
    </>
  );
}
