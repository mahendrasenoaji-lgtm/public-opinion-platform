import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { SOURCE, type SignalSource } from "@/lib/tokens";
import { apiOrNullLenient } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";

export const dynamic = "force-dynamic";

interface DivergenceReading {
  source: SignalSource;
  value: number;
  n: number;
  method: string;
  known_bias: string;
}

interface DivergenceResponse {
  gap: number;
  is_notable: boolean;
  readings: DivergenceReading[];
  explanations: Array<{ factor: string; text: string }>;
  limitations: string[];
}

export default async function ConsistencyPage() {
  const { id: projectId, name: projectName, is_demo: isDemo } = await getCurrentProject();
  // null saat proyek belum punya >=2 sumber sinyal sama sekali (404 backend,
  // lihat lib/api.ts:apiOrNullLenient) -- diperlakukan sama seperti readings kosong,
  // UI di bawah sudah menampilkan InsufficientData untuk kedua kasus itu.
  const divergence = (await apiOrNullLenient<DivergenceResponse>(
    `/projects/${projectId}/opinion/divergence`,
  )) ?? { gap: 0, is_notable: false, readings: [], explanations: [], limitations: [] };

  return (
    <>
      <PageHeader kicker="Signal Consistency" title={projectName} isDemo={isDemo} />
      <div className="body">
        <Panel kicker="Fitur pembeda utama" title="Tiga sumber, tiga jawaban berbeda">
          {divergence.readings.length === 0 ? (
            <InsufficientData reason="Belum cukup sumber sinyal untuk dibandingkan." />
          ) : (
            <>
              <div className="cons">
                {divergence.readings.map((r) => (
                  <div key={r.source} className="cons-row">
                    <div className="cons-label" style={{ color: SOURCE[r.source].color }}>
                      {SOURCE[r.source].label}
                    </div>
                    <div className="cons-bar">
                      <div className="bar100">
                        <div style={{ width: `${r.value}%`, background: SOURCE[r.source].color }} />
                      </div>
                    </div>
                    <div className="cons-v">
                      {r.value}
                      <span className="pct">% positif</span>
                    </div>
                    <div className="cons-n">{r.n.toLocaleString("id-ID")}</div>
                  </div>
                ))}
              </div>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Sumber</th>
                    <th>Metode</th>
                    <th>Sumber bias utama</th>
                  </tr>
                </thead>
                <tbody>
                  {divergence.readings.map((r) => (
                    <tr key={r.source}>
                      <td style={{ color: SOURCE[r.source].color }}>{SOURCE[r.source].label}</td>
                      <td>{r.method}</td>
                      <td className="dim">{r.known_bias}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </Panel>

        <Panel kicker="Pembacaan" title="Mengapa angkanya berbeda">
          {divergence.explanations.length === 0 ? (
            <InsufficientData reason="Selisih antar sumber masih dalam rentang wajar untuk instrumen yang berbeda." />
          ) : (
            <div className="reads">
              {divergence.explanations.map((e) => (
                <div key={e.factor} className="read">
                  <div className="read-t">{e.factor}</div>
                  <div className="read-d">{e.text}</div>
                </div>
              ))}
            </div>
          )}
          <Provenance
            method="Dekomposisi selisih berbasis kondisi terhadap profil tiap sumber"
            confidence="Sedang"
            limits={
              divergence.limitations[0] ??
              "Kontribusi tiap faktor adalah estimasi, bukan dekomposisi varians eksak"
            }
          />
        </Panel>
      </div>
    </>
  );
}
