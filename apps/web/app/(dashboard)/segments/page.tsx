import { Info } from "lucide-react";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

interface SegmentOut {
  name: string;
  size_pct: number;
  sentiment: number | null;
  trust: number | null;
  profile: Record<string, string>;
  method: string;
  entropy: number | null;
}

interface PolarizationOut {
  polarization_score: number | null;
  state: string | null;
  method: string;
  segments_used: number;
  insufficient_data: boolean;
  note: string | null;
  limitations: string | null;
}

const POLARIZATION_TONE: Record<string, string> = {
  "menuju konsensus": "var(--pos)",
  terfragmentasi: "var(--warn)",
  terpolarisasi: "var(--neg)",
};

const SEG_COLOR = (sent: number | null) => {
  if (sent === null) return "var(--txt3)";
  if (sent > 30) return "var(--pos)";
  if (sent > 0) return "#5FA98A";
  if (sent > -40) return "var(--warn)";
  return "var(--neg)";
};

export default async function SegmentsPage() {
  const projectId = process.env.DEMO_PROJECT_ID!;
  const [segments, polarization] = await Promise.all([
    api<SegmentOut[]>(`/projects/${projectId}/segments`),
    api<PolarizationOut>(`/projects/${projectId}/risk/polarization`),
  ]);

  return (
    <>
      <PageHeader kicker="Public Segments" title="Persepsi Kebijakan Nasional 2026" />
      <div className="body">
        <section className="stat-row">
          <div className="stat">
            <div className="kicker">Polarization Index</div>
            {polarization.insufficient_data || polarization.polarization_score === null ? (
              <InsufficientData
                reason={polarization.note ?? "Sampel segmen belum cukup untuk dihitung."}
              />
            ) : (
              <>
                <div
                  className="stat-v"
                  style={{ color: POLARIZATION_TONE[polarization.state ?? ""] ?? "var(--txt)" }}
                >
                  {polarization.polarization_score}
                  <span className="stat-u">/100 · {polarization.state}</span>
                </div>
                <Provenance
                  method={polarization.method}
                  n={`${polarization.segments_used} segmen`}
                  confidence="Sedang"
                  limits={polarization.limitations ?? "Mengukur jarak posisi, bukan intensitas permusuhan."}
                />
              </>
            )}
          </div>
        </section>

        <Panel kicker="Enam kelompok, bukan positif/negatif" title="Public Segments">
          {segments.length === 0 ? (
            <InsufficientData reason="Belum ada segmentasi untuk proyek ini." />
          ) : (
            <>
              <div className="segbar">
                {segments.map((s) => (
                  <div
                    key={s.name}
                    className="segbar-seg"
                    style={{ width: `${s.size_pct}%`, background: SEG_COLOR(s.sentiment) }}
                    title={`${s.name} ${s.size_pct}%`}
                  >
                    <span>{s.size_pct}%</span>
                  </div>
                ))}
              </div>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Segmen</th>
                    <th>Ukuran</th>
                    <th>Sentiment</th>
                    <th>Trust</th>
                    <th>Usia inti</th>
                    <th>Wilayah</th>
                    <th>Isu utama</th>
                  </tr>
                </thead>
                <tbody>
                  {segments.map((s) => (
                    <tr key={s.name}>
                      <td className="strong">{s.name}</td>
                      <td>{s.size_pct}%</td>
                      <td className={(s.sentiment ?? 0) < 0 ? "neg" : "pos"}>
                        {s.sentiment !== null
                          ? `${s.sentiment > 0 ? "+" : ""}${s.sentiment}`
                          : "—"}
                      </td>
                      <td>{s.trust ?? "—"}</td>
                      <td>{s.profile.age ?? "—"}</td>
                      <td className="dim">{s.profile.geo ?? "—"}</td>
                      <td className="dim">{s.profile.concern ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="note">
                <Info size={13} /> Segmentasi dibentuk dari respons survei dan variabel demografis
                yang dikumpulkan dengan consent. Platform tidak melakukan inferensi terhadap
                atribut sensitif seperti agama, etnisitas, atau afiliasi politik individu.
              </p>
              <Provenance
                method={segments[0]?.method ?? "latent class analysis"}
                confidence="Tinggi"
                limits={
                  segments[0]?.entropy != null
                    ? `Entropi ${segments[0].entropy} — sebagian responden punya probabilitas keanggotaan ganda`
                    : "Batas antar-segmen bersifat probabilistik, bukan mutually exclusive tegas"
                }
              />
            </>
          )}
        </Panel>
      </div>
    </>
  );
}
