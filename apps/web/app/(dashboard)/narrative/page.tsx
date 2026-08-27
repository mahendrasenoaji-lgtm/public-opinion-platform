import { PageHeader } from "@/components/PageHeader";
import { InsufficientData } from "@/components/Provenance";
import { NarrativeExplorer, type NarrativeItem } from "@/components/NarrativeExplorer";
import { api } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";

export const dynamic = "force-dynamic";

export default async function NarrativePage() {
  const { id: projectId, name: projectName, is_demo: isDemo } = await getCurrentProject();
  const narratives = await api<NarrativeItem[]>(`/projects/${projectId}/narratives`);

  return (
    <>
      <PageHeader kicker="Narrative Map" title={projectName} isDemo={isDemo} />
      <div className="body">
        {narratives.length === 0 ? (
          <InsufficientData reason="Belum ada narasi terdeteksi untuk proyek ini." />
        ) : (
          <NarrativeExplorer narratives={narratives} />
        )}
      </div>
    </>
  );
}
