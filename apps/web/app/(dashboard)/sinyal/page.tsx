import { Info } from "lucide-react";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { SOURCE } from "@/lib/tokens";
import { api, apiOrNull, type Metric, type SignalSource } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";

export const dynamic = "force-dynamic";

interface SignalSummary {
  volume: Metric;
  sentiment: Metric;
  distinct_authors: number;
  concentration_top10: number;
  source_mix: Record<string, number>;
  period_start: string;
  period_end: string;
  limitations: string[];
}

interface TrendPoint {
  day: string;
  volume: number;
  sentiment: number | null;
  scored: number;
}

interface ClassMetrics {
  precision: number;
  recall: number;
  f1: number;
  support: number;
}

interface SentimentQuality {
  model_version: string;
  n: number;
  accuracy: number;
  accuracy_scored_only: number;
  macro_f1: number;
  abstain_rate: number;
  abstain_by_class: Record<string, number>;
  per_class: Record<string, ClassMetrics>;
  caveat: string;
}

interface SourceRow {
  id: string;
  connector: string;
  source: SignalSource;
  config: Record<string, string>;
  is_active: boolean;
  last_sync_at: string | null;
}

interface ConnectorRow {
  key: string;
  label: string;
  source: SignalSource;
  requires_credential: string | null;
  credential_configured: boolean;
  config_fields: string[];
  notes: string;
}

const pct = (v: number) => `${Math.round(v * 100)}%`;

export default async function SinyalPage() {
  const { id: projectId, name, is_demo: isDemo } = await getCurrentProject();

  const [summary, trend, quality, sources, connectors] = await Promise.all([
    apiOrNull<SignalSummary>(`/projects/${projectId}/signals/summary`),
    apiOrNull<TrendPoint[]>(`/projects/${projectId}/signals/trend`),
    api<SentimentQuality>(`/projects/${projectId}/signals/sentiment-quality`),
    apiOrNull<SourceRow[]>(`/projects/${projectId}/signals/sources`),
    api<ConnectorRow[]>(`/signals/connectors`),
  ]);

  const volume = summary?.volume.value ?? 0;
  // Warna mengikuti sumber yang dominan, bukan estetika (R1).
  const tone = SOURCE[summary?.volume.source ?? "SOCIAL"].color;
  const withVolume = (trend ?? []).filter((p) => p.volume > 0);
  const peak = Math.max(1, ...withVolume.map((p) => p.volume));

  return (
    <>
      <PageHeader kicker="Signal Monitor" title={name} isDemo={isDemo} />
      <div className="body">
        <section className="stat-row">
          <div className="stat stat-big">
            <div className="kicker">Volume percakapan</div>
            <div className="stat-v" style={{ color: tone }}>
              {volume.toLocaleString("id-ID")}
              <span className="stat-u">konten</span>
            </div>
            {summary && (
              <Provenance
                method={summary.volume.method}
                n={summary.volume.effective_n ?? 0}
                confidence="Tinggi"
                limits="Hitungan konten unik setelah deduplikasi, bukan jumlah orang."
              />
            )}
          </div>

          <div className="stat">
            <div className="kicker">Sentimen rata-rata</div>
            {!summary || summary.sentiment.value === null ? (
              <InsufficientData
                reason={
                  summary?.sentiment.note ??
                  "Belum ada percakapan yang masuk untuk proyek ini."
                }
              />
            ) : (
              <>
                <div className="stat-v" style={{ color: tone }}>
                  {summary.sentiment.value > 0 ? "+" : ""}
                  {summary.sentiment.value.toFixed(2)}
                  <span className="stat-u">/ 1.00</span>
                </div>
                <Provenance
                  method={summary.sentiment.method}
                  n={summary.sentiment.effective_n ?? 0}
                  confidence="Rendah"
                  limits="Self-selected. Bukan sentimen publik, melainkan sentimen yang menulis."
                />
              </>
            )}
          </div>

          <div className="stat">
            <div className="kicker">Akun berbeda</div>
            <div className="stat-v">{(summary?.distinct_authors ?? 0).toLocaleString("id-ID")}</div>
            <div className="proj-s" style={{ marginTop: 6 }}>
              Identitas di-hash, tidak pernah disimpan apa adanya
            </div>
          </div>

          <div className="stat">
            <div className="kicker">Porsi 10 akun teratas</div>
            <div className="stat-v">{pct(summary?.concentration_top10 ?? 0)}</div>
            <div className="proj-s" style={{ marginTop: 6 }}>
              Deskripsi sebaran, bukan indikasi koordinasi
            </div>
          </div>
        </section>

        <div className="grid-2">
          <Panel kicker="Volume harian" title="Tren percakapan">
            {withVolume.length === 0 ? (
              <InsufficientData reason="Belum ada percakapan pada periode ini." />
            ) : (
              <div className="dq">
                {withVolume.slice(-14).map((p) => (
                  <div key={p.day} className="dq-row">
                    <span className="mono">{p.day}</span>
                    <div className="bar100">
                      <div style={{ width: `${(p.volume / peak) * 100}%`, background: tone }} />
                    </div>
                    <b>{p.volume}</b>
                  </div>
                ))}
              </div>
            )}
            <p className="note">
              <Info size={13} />
              Hari tanpa konten bernilai sentimen tidak ditampilkan sebagai netral —
              ia memang tidak terukur, dan nol akan terbaca sebagai pengukuran.
            </p>
          </Panel>

          <Panel kicker="Komposisi" title="Sumber sinyal">
            {!summary || Object.keys(summary.source_mix).length === 0 ? (
              <InsufficientData reason="Belum ada sinyal yang masuk." />
            ) : (
              <div className="dq">
                {Object.entries(summary.source_mix).map(([src, count]) => {
                  const meta = SOURCE[src as SignalSource];
                  const share = (count / Math.max(1, volume)) * 100;
                  return (
                    <div key={src} className="dq-row">
                      <span>
                        <span className="pill" style={{ color: meta.color }}>{meta.label}</span>
                      </span>
                      <div className="bar100">
                        <div style={{ width: `${share}%`, background: meta.color }} />
                      </div>
                      <b>{count}</b>
                    </div>
                  );
                })}
              </div>
            )}
            {summary && (
              <ul className="nolist" style={{ marginTop: 14 }}>
                {summary.limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <Panel
          kicker="Mutu pengukuran"
          title="Akurasi leksikon sentimen"
          right={<span className="pill pill-warn">{quality.model_version}</span>}
        >
          {/* docs/roadmap.md mensyaratkan akurasi sentimen dilaporkan di UI
              sebelum fitur ini dipakai di proyek nyata. Ini pemenuhannya. */}
          <div className="fc-out">
            <div>
              <span className="kicker">Macro F1</span>
              <b>{quality.macro_f1.toFixed(3)}</b>
            </div>
            <div>
              <span className="kicker">Akurasi (yang dinilai)</span>
              <b>{quality.accuracy_scored_only.toFixed(3)}</b>
            </div>
            <div>
              <span className="kicker">Akurasi (ketat)</span>
              <b>{quality.accuracy.toFixed(3)}</b>
            </div>
            <div>
              <span className="kicker">Tidak dinilai</span>
              <b>{pct(quality.abstain_rate)}</b>
            </div>
          </div>

          <table className="tbl" style={{ marginTop: 18 }}>
            <thead>
              <tr>
                <th>Kelas</th>
                <th>Presisi</th>
                <th>Recall</th>
                <th>F1</th>
                <th>Tidak dinilai</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(quality.per_class).map(([kelas, m]) => (
                <tr key={kelas}>
                  <td style={{ textTransform: "capitalize" }}>{kelas}</td>
                  <td className="mono">{m.precision.toFixed(3)}</td>
                  <td className="mono">{m.recall.toFixed(3)}</td>
                  <td className="mono">{m.f1.toFixed(3)}</td>
                  <td className="mono">{quality.abstain_by_class[kelas] ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <p className="note">
            <Info size={13} />
            {quality.caveat}
          </p>
        </Panel>

        <Panel kicker="Pengaturan" title="Sumber data terdaftar">
          {!sources || sources.length === 0 ? (
            <InsufficientData reason="Belum ada sumber data yang didaftarkan untuk proyek ini." />
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>Konektor</th>
                  <th>Sumber</th>
                  <th>Konfigurasi</th>
                  <th>Sinkron terakhir</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((s) => (
                  <tr key={s.id}>
                    <td>{s.connector}</td>
                    <td>
                      <span className="pill" style={{ color: SOURCE[s.source].color }}>
                        {SOURCE[s.source].label}
                      </span>
                    </td>
                    <td className="mono">
                      {Object.entries(s.config)
                        .map(([k, v]) => `${k}=${v}`)
                        .join(" ") || "—"}
                    </td>
                    <td className="mono">{s.last_sync_at?.slice(0, 16).replace("T", " ") ?? "belum pernah"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3 className="kicker" style={{ marginTop: 22 }}>Konektor yang tersedia</h3>
          <table className="tbl" style={{ marginTop: 8 }}>
            <thead>
              <tr>
                <th>Konektor</th>
                <th>Sumber</th>
                <th>Kredensial</th>
                <th>Batasan sumber</th>
              </tr>
            </thead>
            <tbody>
              {connectors.map((c) => (
                <tr key={c.key}>
                  <td>{c.label}</td>
                  <td>
                    <span className="pill" style={{ color: SOURCE[c.source].color }}>
                      {SOURCE[c.source].label}
                    </span>
                  </td>
                  <td>
                    {c.requires_credential === null ? (
                      <span className="pill pill-ok">tidak perlu</span>
                    ) : c.credential_configured ? (
                      <span className="pill pill-ok">{c.requires_credential} aktif</span>
                    ) : (
                      <span className="pill pill-warn">{c.requires_credential} belum diset</span>
                    )}
                  </td>
                  <td style={{ color: "var(--txt2)" }}>{c.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>
    </>
  );
}
