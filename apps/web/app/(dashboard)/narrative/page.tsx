import { PageHeader } from "@/components/PageHeader";
import { InsufficientData } from "@/components/Provenance";
import { NarrativeExplorer, type NarrativeItem } from "@/components/NarrativeExplorer";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function NarrativePage() {
  const projectId = process.env.DEMO_PROJECT_ID!;
  const narratives = await api<NarrativeItem[]>(`/projects/${projectId}/narratives`);

  return (
    <>
      <PageHeader kicker="Narrative Map" title="Persepsi Kebijakan Nasional 2026" />
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
