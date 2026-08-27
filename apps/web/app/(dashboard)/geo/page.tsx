import { PageHeader } from "@/components/PageHeader";
import { InsufficientData } from "@/components/Provenance";
import { GeoExplorer, type ProvinceMetrics } from "@/components/GeoExplorer";
import { api } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";

export const dynamic = "force-dynamic";

export default async function GeoPage() {
  const { id: projectId, name: projectName, is_demo: isDemo } = await getCurrentProject();
  const provinces = await api<ProvinceMetrics[]>(`/projects/${projectId}/opinion/geo`);

  return (
    <>
      <PageHeader kicker="Geographic Map" title={projectName} isDemo={isDemo} />
      <div className="body">
        {provinces.length === 0 ? (
          <InsufficientData reason="Belum ada data provinsi untuk proyek ini." />
        ) : (
          <GeoExplorer provinces={provinces} />
        )}
      </div>
    </>
  );
}
