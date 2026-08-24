import { PageHeader } from "@/components/PageHeader";
import { InsufficientData } from "@/components/Provenance";
import { ForecastSimulator } from "@/components/ForecastSimulator";
import { api, type Metric } from "@/lib/api";
import { runWhatIf } from "./actions";

export const dynamic = "force-dynamic";

export default async function ForecastPage() {
  const projectId = process.env.DEMO_PROJECT_ID!;
  const index = await api<{ index: Metric }>(`/projects/${projectId}/opinion/index`);

  if (index.index.value === null) {
    return (
      <>
        <PageHeader kicker="Forecast & Simulator" title="Persepsi Kebijakan Nasional 2026" />
        <div className="body">
          <InsufficientData reason="Indeks belum bisa diterbitkan, forecast butuh baseline yang valid." />
        </div>
      </>
    );
  }

  const baseline = index.index.value;
  const initial = await runWhatIf(projectId, baseline, {});
  if (!initial.ok) {
    return (
      <>
        <PageHeader kicker="Forecast & Simulator" title="Persepsi Kebijakan Nasional 2026" />
        <div className="body">
          <InsufficientData reason={initial.error} />
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader kicker="Forecast & Simulator" title="Persepsi Kebijakan Nasional 2026" />
      <div className="body">
        <ForecastSimulator projectId={projectId} baseline={baseline} initial={initial.result} />
      </div>
    </>
  );
}
