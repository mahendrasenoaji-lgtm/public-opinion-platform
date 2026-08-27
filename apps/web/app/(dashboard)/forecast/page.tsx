import { PageHeader } from "@/components/PageHeader";
import { InsufficientData } from "@/components/Provenance";
import { ForecastSimulator } from "@/components/ForecastSimulator";
import { apiOrNull, type Metric } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";
import { runWhatIf } from "./actions";

export const dynamic = "force-dynamic";

export default async function ForecastPage() {
  const { id: projectId, name: projectName, is_demo: isDemo } = await getCurrentProject();
  // null kalau proyek belum punya data dimensi POI sama sekali (404
  // backend) -- diperlakukan sama seperti index.value === null di bawah,
  // keduanya berujung "belum ada baseline yang valid untuk forecast".
  const index = await apiOrNull<{ index: Metric }>(`/projects/${projectId}/opinion/index`);

  if (index === null || index.index.value === null) {
    return (
      <>
        <PageHeader kicker="Forecast & Simulator" title={projectName} isDemo={isDemo} />
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
        <PageHeader kicker="Forecast & Simulator" title={projectName} isDemo={isDemo} />
        <div className="body">
          <InsufficientData reason={initial.error} />
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader kicker="Forecast & Simulator" title={projectName} isDemo={isDemo} />
      <div className="body">
        <ForecastSimulator projectId={projectId} baseline={baseline} initial={initial.result} />
      </div>
    </>
  );
}
