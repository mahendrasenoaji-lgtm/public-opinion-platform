import { PageHeader } from "@/components/PageHeader";
import { InsufficientData } from "@/components/Provenance";
import { GeoExplorer, type ProvinceMetrics } from "@/components/GeoExplorer";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function GeoPage() {
  const projectId = process.env.DEMO_PROJECT_ID!;
  const provinces = await api<ProvinceMetrics[]>(`/projects/${projectId}/opinion/geo`);

  return (
    <>
      <PageHeader kicker="Geographic Map" title="Persepsi Kebijakan Nasional 2026" />
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
