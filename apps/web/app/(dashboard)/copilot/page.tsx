import { Info } from "lucide-react";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData } from "@/components/Provenance";
import { apiOrNullLenient } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";
import { AskForm } from "./AskForm";
import type { AskResponse } from "./actions";

export const dynamic = "force-dynamic";

export default async function CopilotPage() {
  const { id: projectId, name, is_demo: isDemo } = await getCurrentProject();
  const history = (await apiOrNullLenient<AskResponse[]>(`/projects/${projectId}/copilot/history`)) ?? [];

  return (
    <>
      <PageHeader kicker="AI Copilot" title={name} isDemo={isDemo} />
      <div className="body">
        <Panel kicker="Tanya data proyek" title="Ajukan pertanyaan">
          <AskForm projectId={projectId} />

          <p className="note">
            <Info size={13} />
            Copilot hanya membaca data <b>agregat</b> proyek — index dan dimensinya,
            segmen, tema, dan ringkasan sinyal. Ia tidak pernah membaca tulisan
            individual siapa pun, jadi ia tidak bisa mengutip apa yang orang katakan
            persis. Itu batasan yang disengaja: bukti yang hanya bisa ditunjukkan
            dengan menunjuk satu orang tidak boleh dipakai sebagai bukti.
          </p>
        </Panel>

        <Panel kicker="Jejak" title="Pertanyaan yang pernah dijawab">
          {history.length === 0 ? (
            <InsufficientData reason="Belum ada pertanyaan yang dijawab untuk proyek ini." />
          ) : (
            <div className="narrs">
              {history.map((h) => (
                <div key={h.id} className="narr">
                  <div className="narr-head">
                    <span className="narr-t">{h.payload.jawaban.slice(0, 110)}…</span>
                    <span className="narr-v mono">{h.model_version}</span>
                  </div>
                  <div className="narr-meta mono" style={{ marginTop: 6 }}>
                    {h.evidence.length} bukti · keyakinan {h.confidence} · tinjauan{" "}
                    {h.human_review}
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="note">
            <Info size={13} />
            Setiap jawaban tercatat di <span className="mono">ai_outputs</span> —
            sumber yang sama dengan halaman AI Governance, sehingga jejaknya satu,
            bukan dua catatan yang bisa berbeda.
          </p>
        </Panel>
      </div>
    </>
  );
}
