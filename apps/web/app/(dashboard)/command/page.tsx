import { DivergenceBand } from "@/components/DivergenceBand";
import { Provenance, InsufficientData } from "@/components/Provenance";
import { api, type Metric } from "@/lib/api";

export const dynamic = "force-dynamic";

interface Divergence {
  gap: number;
  is_notable: boolean;
  readings: Array<{ source: "SURVEY" | "SOCIAL" | "MEDIA"; value: number; n: number }>;
  explanations: Array<{ factor: string; text: string }>;
}

export default async function CommandCenter() {
  const projectId = process.env.DEMO_PROJECT_ID!;

  const [index, divergence] = await Promise.all([
    api<{ index: Metric; limitations: string[] }>(`/projects/${projectId}/opinion/index`),
    api<Divergence>(`/projects/${projectId}/opinion/divergence`),
  ]);

  return (
    <div className="body">
      <section className="stat-row">
        <div className="stat stat-big">
          <div className="kicker">{index.index.label}</div>
          {index.index.insufficient_data || index.index.value === null ? (
            <InsufficientData reason={index.index.note ?? "Sampel di bawah ambang publikasi."} />
          ) : (
            <>
              <div className="stat-v">
                {index.index.value.toFixed(1)}<span className="stat-u">/100</span>
              </div>
              <Provenance
                method={index.index.method}
                n={index.index.effective_n ?? "—"}
                ci={
                  index.index.ci_low !== null
                    ? `${index.index.ci_low}–${index.index.ci_high}`
                    : undefined
                }
                confidence="Tinggi"
                limits={index.limitations[0] ?? "Berlaku untuk periode pengukuran ini saja."}
              />
            </>
          )}
        </div>
      </section>

      <DivergenceBand
        readings={divergence.readings}
        gap={divergence.gap}
        explanationLead={
          divergence.explanations[0]?.text ??
          "Selisih antar sumber masih dalam rentang wajar untuk instrumen yang berbeda."
        }
      />
    </div>
  );
}
