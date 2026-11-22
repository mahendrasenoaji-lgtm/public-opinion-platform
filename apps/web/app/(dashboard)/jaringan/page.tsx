import { cookies } from "next/headers";
import { Download, Info } from "lucide-react";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { NetworkMap, type VizEdge, type VizNode } from "@/components/NetworkMap";
import { SnaAccountTable, type AccountMetricsRow } from "@/components/SnaAccountTable";
import { SOURCE, groupColor } from "@/lib/tokens";
import { apiOrNullLenient } from "@/lib/api";
import { PeriodBar } from "@/components/PeriodBar";
import { decodeJwtPayload, SESSION_COOKIE } from "@/lib/session";
import { parseWindow, windowQuery } from "../sinyal/window";
import { getCurrentProject } from "@/lib/currentProject";

export const dynamic = "force-dynamic";

/** Peran yang boleh mengunduh graf (backend menegakkan hal yang sama). */
const CAN_EXPORT = new Set(["SUPER_ADMIN", "RESEARCH_DIRECTOR", "RESEARCHER", "DATA_ANALYST"]);

interface CommunityRow {
  id: number;
  size: number;
  share: number;
  internal_edges: number;
  external_edges: number;
  density: number;
  top_accounts: string[];
  contents: number;
  scored: number;
  sentiment_mean: number | null;
  negative_share: number | null;
  neutral_share: number | null;
  positive_share: number | null;
  top_terms: [string, number][];
}

interface SnaOut {
  source: "SOCIAL";
  start: string;
  end: string;
  summary: {
    nodes: number;
    original_nodes: number;
    edges: number;
    interactions: number;
    density: number;
    reciprocity: number;
    components: number;
    largest_component_share: number;
    avg_clustering: number | null;
    modularity: number | null;
    communities: number;
  };
  accounts: AccountMetricsRow[];
  communities: CommunityRow[];
  viz_nodes: VizNode[];
  viz_edges: VizEdge[];
  insufficient_data: boolean;
  note: string | null;
  notes: string[];
  method: string;
  limitations: string[];
  min_scored: number;
  computed_at: string;
}

interface BridgesOut {
  accounts: number;
  containers: number;
  comments: number;
  cross_accounts: number;
  cross_share: number;
  top_containers: { container: string; url: string | null; commenters: number; comments: number; shared_share: number }[];
  top_cross_accounts: { author_hash: string; containers: number; comments: number }[];
  overlaps: { a: string; b: string; shared: number; jaccard: number }[];
  insufficient_data: boolean;
  note: string | null;
  method: string;
  limitations: string[];
}

const nf = new Intl.NumberFormat("id-ID");
const wibTime = (iso: string) =>
  new Date(iso).toLocaleString("id-ID", {
    timeZone: "Asia/Jakarta",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }) + " WIB";
const pct = (v: number) => `${(v * 100).toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`;

function containerLabel(c: string): string {
  const [kind, id] = c.split(":");
  return `${kind === "tt" ? "TikTok" : "YouTube"} ${id}`;
}

export default async function JaringanPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const win = parseWindow(await searchParams);
  const { id: projectId, name, is_demo: isDemo } = await getCurrentProject();
  const q = windowQuery(win);
  const [data, bridges] = await Promise.all([
    apiOrNullLenient<SnaOut>(`/projects/${projectId}/network/sna${q}`),
    apiOrNullLenient<BridgesOut>(`/projects/${projectId}/network/bridges${q}`),
  ]);
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  const role = token ? decodeJwtPayload(token)?.role : undefined;
  const canExport = typeof role === "string" && CAN_EXPORT.has(role);
  const exportQuery = (format: string) => {
    const p = new URLSearchParams({ format });
    if (win.start && win.end) {
      p.set("dari", win.start);
      p.set("sampai", win.end);
    }
    return `/jaringan/ekspor?${p.toString()}`;
  };
  const s = data?.summary;
  const ready = data && !data.insufficient_data;
  const social = SOURCE.SOCIAL;

  return (
    <>
      <PageHeader kicker="Jaringan Interaksi (SNA)" title={name} isDemo={isDemo} />
      <div className="body">
        <PeriodBar win={win} />
        {data?.computed_at && (
          <p className="field-hint" style={{ margin: "-4px 0 12px" }}>
            Dihitung {wibTime(data.computed_at)}. Graf besar butuh beberapa detik, jadi hasilnya
            disimpan hingga 10 menit; konten yang baru masuk tampil sesudahnya.
          </p>
        )}

        {/* Kata yang dipakai di halaman ini: "posisi struktural", bukan
            "pengaruh", "kendali", atau "buzzer" — CLAUDE.md §3. */}
        <section className="stat-row">
          <div className="stat">
            <div className="kicker">Akun dalam graf</div>
            <div className="stat-v">{nf.format(s?.nodes ?? 0)}</div>
            {s && s.original_nodes > s.nodes && (
              <div className="field-hint">dari {nf.format(s.original_nodes)} (dipangkas)</div>
            )}
          </div>
          <div className="stat">
            <div className="kicker">Relasi antar-akun</div>
            <div className="stat-v">{nf.format(s?.edges ?? 0)}</div>
            <div className="field-hint">{nf.format(s?.interactions ?? 0)} interaksi</div>
          </div>
          <div className="stat">
            <div className="kicker">Komunitas</div>
            <div className="stat-v">{nf.format(s?.communities ?? 0)}</div>
            <div className="field-hint">
              modularity {s?.modularity != null ? s.modularity.toFixed(3) : "–"}
            </div>
          </div>
          <div className="stat">
            <div className="kicker">Density</div>
            <div className="stat-v">{s ? s.density.toFixed(4) : "–"}</div>
            <div className="field-hint">resiprositas {s ? pct(s.reciprocity) : "–"}</div>
          </div>
          <div className="stat">
            <div className="kicker">Komponen terbesar</div>
            <div className="stat-v">{s ? pct(s.largest_component_share) : "–"}</div>
            <div className="field-hint">
              {nf.format(s?.components ?? 0)} komponen · klaster{" "}
              {s?.avg_clustering != null ? s.avg_clustering.toFixed(3) : "–"}
            </div>
          </div>
        </section>

        <Panel kicker="Peta jaringan" title="Akun dan relasi balas-membalas">
          {!ready ? (
            <InsufficientData
              reason={
                data?.note ??
                "Belum ada relasi balasan/kutipan pada periode ini. Relasi datang dari balasan komentar YouTube (Tarik tema) atau X."
              }
            />
          ) : (
            <>
              <NetworkMap
                nodes={data.viz_nodes}
                edges={data.viz_edges}
                communities={data.communities.map((c) => ({ id: c.id, size: c.size }))}
              />
              <Provenance
                method={data.method}
                n={data.summary.edges}
                confidence="Rendah"
                limits={data.limitations[0] ?? ""}
              />
            </>
          )}
        </Panel>

        {ready && (
          <Panel kicker="Sentralitas · posisi struktural" title="Aktor kunci">
            <SnaAccountTable rows={data.accounts} />
            <p className="note">
              <Info size={13} />
              Tabel memuat gabungan akun teratas untuk tiap ukuran; klik judul kolom untuk
              mengurutkan. Angka tinggi berarti posisi menonjol dalam graf yang teramati, bukan
              pengaruh kausal, kendali atas opini, atau tanda akun terkoordinasi.
            </p>
            {data.notes.length > 0 && (
              <ul className="nolist field-hint" style={{ marginTop: 6 }}>
                {data.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            )}
          </Panel>
        )}

        {ready && data.communities.length > 0 && (
          <Panel kicker="Deteksi komunitas · Louvain" title="Komunitas dan narasinya">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
              {data.communities.map((c) => (
                <div key={c.id} className="read">
                  <div className="read-t">
                    <span className="nm-swatch" style={{ background: groupColor(c.id) }} />K{c.id} ·{" "}
                    {nf.format(c.size)} akun ({pct(c.share)})
                  </div>
                  <div className="read-d">
                    Density {c.density.toFixed(3)} · relasi dalam {nf.format(c.internal_edges)} · ke luar{" "}
                    {nf.format(c.external_edges)}
                  </div>
                  <div className="read-d" style={{ marginTop: 6 }}>
                    <span className="pill" style={{ color: social.color }}>{social.label}</span>{" "}
                    {c.sentiment_mean != null &&
                    c.negative_share != null &&
                    c.neutral_share != null &&
                    c.positive_share != null ? (
                      <>
                        nada rata-rata {c.sentiment_mean.toFixed(2)} · negatif {pct(c.negative_share)} ·
                        netral {pct(c.neutral_share)} · positif {pct(c.positive_share)} (n{" "}
                        {nf.format(c.scored)})
                      </>
                    ) : (
                      <>
                        nada: data tidak cukup ({nf.format(c.scored)} dari minimal{" "}
                        {data.min_scored} konten bernilai)
                      </>
                    )}
                  </div>
                  {c.top_terms.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
                      {c.top_terms.map(([w, n]) => (
                        <span key={w} className="chip">
                          {w}
                          <b>{n}</b>
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="field-hint" style={{ marginTop: 6 }}>
                    Akun teratas: {c.top_accounts.map((a) => `${a.slice(0, 8)}…`).join(", ")}
                  </div>
                </div>
              ))}
            </div>
            <p className="note">
              <Info size={13} />
              Komunitas = kelompok akun yang lebih rapat berinteraksi satu sama lain daripada dengan
              akun lain; bukan kelompok ideologis atau organisasi. Nada mengukur teks, bukan sikap,
              dan baru ditampilkan dari {data.min_scored} konten bernilai. Kata dominan dihitung
              dari konten akun paling aktif di tiap komunitas.
            </p>
          </Panel>
        )}

        <Panel kicker="Graf akun–unggahan" title="Unggahan dan akun penghubung">
          {!bridges || bridges.insufficient_data ? (
            <InsufficientData reason={bridges?.note ?? "Belum ada komentar dari beberapa unggahan pada periode ini."} />
          ) : (
            <>
              <section className="stat-row" style={{ marginBottom: 12 }}>
                <div className="stat">
                  <div className="kicker">Unggahan</div>
                  <div className="stat-v">{nf.format(bridges.containers)}</div>
                </div>
                <div className="stat">
                  <div className="kicker">Akun berkomentar</div>
                  <div className="stat-v">{nf.format(bridges.accounts)}</div>
                </div>
                <div className="stat">
                  <div className="kicker">Akun lintas unggahan</div>
                  <div className="stat-v">{nf.format(bridges.cross_accounts)}</div>
                  <div className="field-hint">{pct(bridges.cross_share)} dari akun</div>
                </div>
              </section>
              <div style={{ overflowX: "auto" }}>
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Unggahan</th>
                      <th>Akun berkomentar</th>
                      <th>Komentar</th>
                      <th>Akunnya juga di unggahan lain</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bridges.top_containers.map((c) => (
                      <tr key={c.container}>
                        <td>
                          {c.url ? (
                            <a href={c.url} target="_blank" rel="noreferrer">
                              {containerLabel(c.container)} ↗
                            </a>
                          ) : (
                            containerLabel(c.container)
                          )}
                        </td>
                        <td className="mono">{nf.format(c.commenters)}</td>
                        <td className="mono">{nf.format(c.comments)}</td>
                        <td className="mono">{pct(c.shared_share)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {bridges.overlaps.length > 0 && (
                <>
                  <h4 style={{ margin: "16px 0 6px" }}>Tumpang-tindih komentator antar-unggahan</h4>
                  <div style={{ overflowX: "auto" }}>
                    <table className="tbl">
                      <thead>
                        <tr>
                          <th>Unggahan A</th>
                          <th>Unggahan B</th>
                          <th>Akun yang sama</th>
                          <th>Jaccard</th>
                        </tr>
                      </thead>
                      <tbody>
                        {bridges.overlaps.slice(0, 10).map((o) => (
                          <tr key={`${o.a}-${o.b}`}>
                            <td>{containerLabel(o.a)}</td>
                            <td>{containerLabel(o.b)}</td>
                            <td className="mono">{nf.format(o.shared)}</td>
                            <td className="mono">{o.jaccard.toFixed(3)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              {bridges.top_cross_accounts.length > 0 && (
                <p className="field-hint" style={{ marginTop: 10 }}>
                  Akun dengan unggahan terbanyak:{" "}
                  {bridges.top_cross_accounts
                    .slice(0, 8)
                    .map((a) => `${a.author_hash.slice(0, 8)}… (${a.containers} unggahan)`)
                    .join(", ")}
                </p>
              )}
              <Provenance
                method={bridges.method}
                n={bridges.comments}
                confidence="Rendah"
                limits={bridges.limitations.join(" ")}
              />
            </>
          )}
        </Panel>

        <Panel kicker="Ekspor" title="Buka di Gephi">
          {canExport ? (
            <>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <a className="btn btn-sm" href={exportQuery("gexf")}>
                  <Download size={13} /> GEXF (Gephi)
                </a>
                <a className="btn btn-ghost btn-sm" href={exportQuery("nodes")}>
                  <Download size={13} /> CSV simpul
                </a>
                <a className="btn btn-ghost btn-sm" href={exportQuery("edges")}>
                  <Download size={13} /> CSV relasi
                </a>
              </div>
              <p className="field-hint" style={{ marginTop: 8 }}>
                Berisi seluruh graf periode ini: hash akun, nomor komunitas, dan jumlah relasi, tanpa
                teks konten dan tanpa nama akun. Setiap unduhan tercatat di audit log.
              </p>
            </>
          ) : (
            <p className="field-hint">
              Ekspor graf hanya untuk peran Data Analyst ke atas (dan tercatat di audit log).
            </p>
          )}
        </Panel>

        <Panel kicker="Batasan" title="Apa yang graf ini tidak katakan">
          <ul className="nolist">
            {(data?.limitations ?? []).map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </Panel>
      </div>
    </>
  );
}
