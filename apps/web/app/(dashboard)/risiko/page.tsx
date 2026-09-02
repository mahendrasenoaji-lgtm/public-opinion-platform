import { Info } from "lucide-react";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { riskColor } from "@/lib/tokens";
import { apiOrNullLenient } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";

export const dynamic = "force-dynamic";

interface RiskComponent {
  key: string;
  label: string;
  value: number | null;
  weight: number;
  available: boolean;
  reason_missing: string | null;
}

interface RiskScore {
  score: number | null;
  band: string | null;
  coverage: number;
  components: RiskComponent[];
  missing: string[];
  top_contributors: string[];
  method: string;
  insufficient_data: boolean;
  note: string | null;
  limitations: string[];
}

const pct = (v: number) => `${Math.round(v * 100)}%`;

export default async function RisikoPage() {
  const { id: projectId, name, is_demo: isDemo } = await getCurrentProject();
  const risk = await apiOrNullLenient<RiskScore>(`/projects/${projectId}/risk/score`);

  const tersedia = risk?.components.filter((c) => c.available) ?? [];
  const hilang = risk?.components.filter((c) => !c.available) ?? [];

  return (
    <>
      <PageHeader kicker="Opinion Risk Score" title={name} isDemo={isDemo} />
      <div className="body">
        <section className="stat-row">
          <div className="stat stat-big">
            <div className="kicker">Skor risiko</div>
            {!risk || risk.score === null ? (
              <InsufficientData
                reason={risk?.note ?? "Belum ada data yang cukup untuk menghitung skor."}
              />
            ) : (
              <>
                <div className="stat-v" style={{ color: riskColor(risk.score) }}>
                  {risk.score}
                  <span className="stat-u">/100 · {risk.band}</span>
                </div>
                <Provenance
                  method={risk.method}
                  n={`${tersedia.length}/9 komponen`}
                  confidence={risk.coverage >= 0.9 ? "Sedang" : "Rendah"}
                  limits={risk.limitations[0] ?? ""}
                />
              </>
            )}
          </div>

          <div className="stat">
            <div className="kicker">Cakupan bobot</div>
            <div
              className="stat-v"
              style={{ color: (risk?.coverage ?? 0) >= 0.9 ? "var(--pos)" : "var(--warn)" }}
            >
              {pct(risk?.coverage ?? 0)}
            </div>
            {/* Cakupan bukan metadata pelengkap: skor 62 dari 95% bobot dan 62
                dari 61% bobot adalah dua pernyataan berbeda, dan keduanya harus
                terbaca berbeda di layar. */}
            <div className="proj-s" style={{ marginTop: 6 }}>
              Bagian bobot risiko yang benar-benar punya data
            </div>
          </div>

          <div className="stat">
            <div className="kicker">Komponen tanpa data</div>
            <div className="stat-v">{hilang.length}</div>
            <div className="proj-s" style={{ marginTop: 6 }}>
              Dikeluarkan dari hitungan, tidak diisi nol
            </div>
          </div>

          <div className="stat">
            <div className="kicker">Penyumbang teratas</div>
            <ul className="nolist" style={{ marginTop: 8 }}>
              {(risk?.top_contributors ?? []).map((c) => (
                <li key={c}>{c}</li>
              ))}
              {(risk?.top_contributors ?? []).length === 0 && <li>—</li>}
            </ul>
          </div>
        </section>

        <div className="grid-2">
          <Panel kicker="Terhitung" title="Komponen yang punya data">
            {tersedia.length === 0 ? (
              <InsufficientData reason="Belum ada satu pun komponen yang bisa dihitung." />
            ) : (
              <div className="dq">
                {tersedia.map((c) => (
                  <div key={c.key} className="dq-row">
                    <span>{c.label}</span>
                    <div className="bar100">
                      <div
                        style={{
                          width: `${c.value ?? 0}%`,
                          background: riskColor(c.value ?? 0),
                        }}
                      />
                    </div>
                    <b>{Math.round(c.value ?? 0)}</b>
                  </div>
                ))}
              </div>
            )}
            <p className="note">
              <Info size={13} />
              Bobot tiap komponen dinormalisasi ulang atas komponen yang tersedia.
              Normalisasi itu memperlakukan komponen yang hilang seolah berperilaku
              seperti rata-rata yang ada — sebuah asumsi, bukan pengukuran.
            </p>
          </Panel>

          <Panel kicker="Belum terhitung" title="Komponen tanpa data">
            {hilang.length === 0 ? (
              <p className="proj-s">Semua komponen punya data.</p>
            ) : (
              <div className="narrs">
                {hilang.map((c) => (
                  <div key={c.key} className="narr">
                    <div className="narr-head">
                      <span className="narr-t">{c.label}</span>
                      <span className="narr-v mono">bobot {(c.weight * 100).toFixed(0)}%</span>
                    </div>
                    <div className="narr-meta" style={{ marginTop: 6, color: "var(--txt2)" }}>
                      {c.reason_missing}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>

        <Panel kicker="Batasan" title="Apa yang skor ini tidak katakan">
          <ul className="nolist">
            {(risk?.limitations ?? []).map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </Panel>
      </div>
    </>
  );
}
