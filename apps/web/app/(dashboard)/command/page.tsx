import { DivergenceBand } from "@/components/DivergenceBand";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { Timeline, type TimelineEvent } from "@/components/Timeline";
import { Info } from "lucide-react";
import { TrendChart } from "@/components/TrendChart";
import { apiOrNull, api, repeatedQuery, type Metric } from "@/lib/api";
import { riskColor } from "@/lib/tokens";
import { getCurrentProject } from "@/lib/currentProject";

export const dynamic = "force-dynamic";

interface Divergence {
  gap: number;
  is_notable: boolean;
  readings: Array<{ source: "SURVEY" | "SOCIAL" | "MEDIA"; value: number; n: number }>;
  explanations: Array<{ factor: string; text: string }>;
}

interface TrendPoint {
  metric: string;
  period_end: string;
  source: string;
  value: number;
}

const TREND_METRICS = ["survey_positive", "social_positive", "media_positive"] as const;
const TREND_SERIES = [
  { key: "survey_positive", label: "Survei", color: "#4DA3FF" },
  { key: "media_positive", label: "Media", color: "#9B8AFB" },
  { key: "social_positive", label: "Sosial", color: "#FF7A45" },
];

interface TopicRow {
  id: string;
  effective_label: string;
  volume: number;
  share_pct: number | null;
  momentum_pct: number | null;
  review_status: string;
}

interface AlertRow {
  key: string;
  label: string;
  direction: string | null;
  latest_value: number;
  latest_period: string;
  z_score: number | null;
  nearby_events: Array<{ label: string; kind: string; occurred_at: string }>;
}

interface AlertsOut {
  alerts: AlertRow[];
  checked: string[];
  insufficient: string[];
  limitations: string[];
}

export default async function CommandCenter() {
  const { id: projectId, name: projectName, is_demo: isDemo } = await getCurrentProject();

  const [index, divergence, trend, timeline, topics, alerts] = await Promise.all([
    apiOrNull<{ index: Metric; limitations: string[] }>(`/projects/${projectId}/opinion/index`),
    apiOrNull<Divergence>(`/projects/${projectId}/opinion/divergence`),
    api<TrendPoint[]>(
      `/projects/${projectId}/opinion/trend${repeatedQuery({ metrics: [...TREND_METRICS], limit: 12 })}`,
    ),
    api<TimelineEvent[]>(`/projects/${projectId}/opinion/timeline${repeatedQuery({ limit: 8 })}`),
    // apiOrNull, bukan api: fitur ini belum tentu tersedia di backend yang
    // sedang aktif kalau Vercel naik lebih dulu daripada Render setelah
    // rilis (lihat catatan yang sama di /sinyal).
    apiOrNull<TopicRow[]>(`/projects/${projectId}/topics`),
    apiOrNull<AlertsOut>(`/projects/${projectId}/alerts`),
  ]);
  const topTopics = (topics ?? [])
    .slice()
    .sort((a, b) => b.volume - a.volume)
    .slice(0, 5);

  return (
    <>
      <PageHeader kicker="Command Center" title={projectName} isDemo={isDemo} />
      <div className="body">
        <section className="stat-row">
          <div className="stat stat-big">
            <div className="kicker">{index?.index.label ?? "Public Opinion Index"}</div>
            {index === null ? (
              <InsufficientData reason="Proyek ini belum punya data dimensi POI sama sekali — belum ada survei yang di-ingest." />
            ) : index.index.insufficient_data || index.index.value === null ? (
              <InsufficientData reason={index.index.note ?? "Sampel di bawah ambang publikasi."} />
            ) : (
              <>
                <div className="stat-v">
                  {index.index.value.toFixed(1)}
                  <span className="stat-u">/100</span>
                </div>
                <Provenance
                  method={index.index.method}
                  n={index.index.effective_n ?? "—"}
                  ci={
                    index.index.ci_low !== null
                      ? `${index.index.ci_low}–${index.index.ci_high}`
                      : undefined
                  }
                  confidence="Tinggi"
                  limits={index.limitations[0] ?? "Berlaku untuk periode pengukuran ini saja."}
                />
              </>
            )}
          </div>
        </section>

        {divergence === null ? (
          <Panel kicker="Fitur pembeda utama" title="Signal Consistency">
            <InsufficientData reason="Perlu minimal dua sumber sinyal (survei/sosial/media) untuk dibandingkan." />
          </Panel>
        ) : (
          <DivergenceBand
            readings={divergence.readings}
            gap={divergence.gap}
            explanationLead={
              divergence.explanations[0]?.text ??
              "Selisih antar sumber masih dalam rentang wajar untuk instrumen yang berbeda."
            }
          />
        )}

        <div className="grid-2">
          <Panel kicker={`${trend.length ? "Data tersedia" : "Belum ada data"} · periode terbaru`} title="Pergerakan tiap sinyal">
            {trend.length > 0 ? (
              <>
                <TrendChart points={trend} series={TREND_SERIES} domain={[30, 85]} />
                <Provenance
                  method="Time-series metric_snapshots per gelombang"
                  n={`${new Set(trend.map((p) => p.period_end)).size} periode`}
                  confidence="Tinggi"
                  limits="Nilai per sumber tidak dapat dirata-ratakan menjadi satu angka (CLAUDE.md R1)"
                />
              </>
            ) : (
              <InsufficientData reason="Belum ada snapshot metrik untuk proyek ini." />
            )}
          </Panel>

          <Panel kicker="Rangkaian peristiwa" title="Opinion timeline">
            {timeline.length > 0 ? (
              <Timeline events={timeline} />
            ) : (
              <InsufficientData reason="Belum ada peristiwa tercatat untuk proyek ini." />
            )}
          </Panel>
        </div>

        <div className="grid-2">
          <Panel kicker="Topic Discovery" title="Isu publik">
            {topTopics.length === 0 ? (
              <InsufficientData
                reason={
                  "Belum ada tema yang ditemukan. Masukkan percakapan lewat " +
                  "Signal Monitor lalu jalankan penemuan tema di halaman Topic Discovery."
                }
              />
            ) : (
              <ul className="nolist">
                {topTopics.map((t) => (
                  <li key={t.id}>
                    <b>{t.effective_label}</b>
                    {" — "}
                    {t.volume} konten
                    {t.share_pct !== null && ` (${t.share_pct.toFixed(1)}%)`}
                    {t.review_status === "PENDING" && (
                      <span className="pill pill-warn" style={{ marginLeft: 8 }}>
                        belum ditinjau
                      </span>
                    )}
                    {t.momentum_pct !== null && t.momentum_pct > 50 && (
                      <span className="pill pill-warn" style={{ marginLeft: 8 }}>
                        momentum +{t.momentum_pct.toFixed(0)}%
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <Provenance
              method="TF-IDF + LSA(SVD) + HDBSCAN, label dari kata kunci teratas"
              n={topTopics.reduce((a, t) => a + t.volume, 0)}
              confidence="Rendah"
              limits="Label belum ditinjau manusia adalah gabungan kata kunci, bukan interpretasi terverifikasi."
            />
          </Panel>

          <Panel kicker="Anomaly Detection" title="Peringatan aktif">
            {!alerts || alerts.alerts.length === 0 ? (
              <InsufficientData
                reason={
                  alerts && alerts.checked.length > 0
                    ? "Tidak ada penyimpangan mencolok terdeteksi pada deret yang bisa diperiksa saat ini."
                    : "Belum ada deret dengan riwayat cukup panjang untuk diperiksa."
                }
              />
            ) : (
              <ul className="nolist">
                {alerts.alerts.slice(0, 5).map((a) => (
                  <li key={a.key}>
                    <b style={{ color: riskColor(a.z_score ? Math.min(100, Math.abs(a.z_score) * 25) : 60) }}>
                      {a.label}
                    </b>{" "}
                    {a.direction} di {a.latest_period}
                    {a.z_score !== null && ` (z=${a.z_score})`}
                    {a.nearby_events.length > 0 && (
                      <div className="proj-s" style={{ marginTop: 2 }}>
                        Berdekatan waktu dengan: {a.nearby_events.map((e) => e.label).join(", ")}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <p className="note">
              <Info size={13} />
              {alerts?.limitations[0] ??
                "Deteksi penyimpangan statistik terhadap pola historis, bukan penilaian krisis dan bukan klaim penyebab."}
            </p>
          </Panel>
        </div>
      </div>
    </>
  );
}
