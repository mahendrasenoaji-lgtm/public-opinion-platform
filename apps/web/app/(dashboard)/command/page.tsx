import { DivergenceBand } from "@/components/DivergenceBand";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { Timeline, type TimelineEvent } from "@/components/Timeline";
import { TrendChart } from "@/components/TrendChart";
import { apiOrNull, api, repeatedQuery, type Metric } from "@/lib/api";
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

export default async function CommandCenter() {
  const { id: projectId, name: projectName, is_demo: isDemo } = await getCurrentProject();

  const [index, divergence, trend, timeline] = await Promise.all([
    apiOrNull<{ index: Metric; limitations: string[] }>(`/projects/${projectId}/opinion/index`),
    apiOrNull<Divergence>(`/projects/${projectId}/opinion/divergence`),
    api<TrendPoint[]>(
      `/projects/${projectId}/opinion/trend${repeatedQuery({ metrics: [...TREND_METRICS], limit: 12 })}`,
    ),
    api<TimelineEvent[]>(`/projects/${projectId}/opinion/timeline${repeatedQuery({ limit: 8 })}`),
  ]);

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

        {/* Isu publik dan peringatan aktif butuh topic modeling dan anomaly
            detection (Phase 2/3, docs/roadmap.md) — belum ditampilkan supaya
            tidak ada kartu tanpa data nyata di baliknya (CLAUDE.md §8). */}
      </div>
    </>
  );
}
