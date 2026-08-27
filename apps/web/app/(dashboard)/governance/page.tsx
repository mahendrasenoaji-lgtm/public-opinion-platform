import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData } from "@/components/Provenance";
import { api } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";

export const dynamic = "force-dynamic";

interface AIOutputRow {
  id: string;
  kind: string;
  model_version: string;
  method: string;
  confidence: "LOW" | "MEDIUM" | "HIGH";
  human_review: "PENDING" | "APPROVED" | "REJECTED" | "NEEDS_REVIEW";
  created_at: string;
}

interface DataQualityRow {
  dataset: string;
  completeness: number;
  duplicate: number;
  response_qual: number;
  consistency: number;
  sample_balance: number;
  metadata_score: number;
  overall: number;
  computed_at: string;
}

const KIND_LABEL: Record<string, string> = {
  executive_brief: "Ringkasan eksekutif",
};

const REVIEW_LABEL: Record<AIOutputRow["human_review"], string> = {
  PENDING: "Menunggu", APPROVED: "Disetujui", REJECTED: "Ditolak", NEEDS_REVIEW: "Perlu tinjauan",
};

export default async function GovernancePage() {
  const { id: projectId, name: projectName, is_demo: isDemo } = await getCurrentProject();
  const [aiOutputs, dataQuality] = await Promise.all([
    api<AIOutputRow[]>(`/projects/${projectId}/governance/ai-outputs`),
    api<DataQualityRow[]>(`/projects/${projectId}/governance/data-quality`),
  ]);

  const dq = dataQuality[0];
  const dqRows: Array<[string, number]> = dq
    ? [
        ["Kelengkapan", dq.completeness],
        ["Duplikat", dq.duplicate],
        ["Kualitas respons", dq.response_qual],
        ["Konsistensi", dq.consistency],
        ["Keseimbangan sampel", dq.sample_balance],
        ["Metadata", dq.metadata_score],
      ]
    : [];

  return (
    <>
      <PageHeader kicker="AI Governance" title={projectName} isDemo={isDemo} />
      <div className="body">
        <Panel kicker="Wajib pada setiap keluaran AI" title="Jejak keputusan model">
          {aiOutputs.length === 0 ? (
            <InsufficientData reason="Belum ada keluaran AI yang tercatat untuk proyek ini." />
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>Keluaran</th>
                  <th>Model</th>
                  <th>Metode</th>
                  <th>Confidence</th>
                  <th>Tinjauan</th>
                </tr>
              </thead>
              <tbody>
                {aiOutputs.map((o) => (
                  <tr key={o.id}>
                    <td className="strong">{KIND_LABEL[o.kind] ?? o.kind}</td>
                    <td className="mono">{o.model_version}</td>
                    <td className="dim">{o.method}</td>
                    <td>{o.confidence}</td>
                    <td>
                      <span
                        className={"pill " + (o.human_review === "APPROVED" ? "pill-ok" : "pill-warn")}
                      >
                        {REVIEW_LABEL[o.human_review]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <div className="grid-2">
          <Panel kicker="Privasi" title="Yang tidak dilakukan platform ini">
            <ul className="nolist">
              <li>Tidak menyimpan identitas responden bersama jawabannya.</li>
              <li>
                Tidak menyimpulkan agama, etnisitas, orientasi, atau afiliasi politik individu.
              </li>
              <li>
                Tidak menyatakan akun tertentu mengendalikan opini publik — hanya estimasi
                pengaruh disertai metode.
              </li>
              <li>Tidak mengambil keputusan otomatis yang berdampak pada individu.</li>
              <li>Tidak memperlakukan sentiment media sosial sebagai representasi populasi.</li>
            </ul>
          </Panel>
          <Panel kicker="Kualitas data" title="Data Quality Score">
            {dqRows.length === 0 ? (
              <InsufficientData reason="Belum ada skor kualitas data untuk proyek ini." />
            ) : (
              <div className="dq">
                {dqRows.map(([label, value]) => (
                  <div key={label} className="dq-row">
                    <span>{label}</span>
                    <div className="bar100">
                      <div
                        style={{
                          width: `${value}%`,
                          background:
                            value >= 90 ? "var(--pos)" : value >= 80 ? "var(--warn)" : "var(--neg)",
                        }}
                      />
                    </div>
                    <b>{value}</b>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}
