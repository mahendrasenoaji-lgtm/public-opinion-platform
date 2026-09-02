import { PageHeader } from "@/components/PageHeader";
import { InsufficientData } from "@/components/Provenance";
import { GeoExplorer, type ProvinceMetrics } from "@/components/GeoExplorer";
import { apiOrNullLenient } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";

export const dynamic = "force-dynamic";

export default async function GeoPage() {
  const { id: projectId, name: projectName, is_demo: isDemo } = await getCurrentProject();
  // apiOrNullLenient, bukan api polos: satu error backend (mis. kolom belum
  // bermigrasi, DB sempat down) tidak boleh menjatuhkan SELURUH halaman
  // dengan "Application error" -- kelas bug yang sama persis dengan yang
  // sudah diperbaiki di /command, /tema, /jaringan (lihat lib/api.ts).
  const provinces = (await apiOrNullLenient<ProvinceMetrics[]>(`/projects/${projectId}/opinion/geo`)) ?? [];

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
