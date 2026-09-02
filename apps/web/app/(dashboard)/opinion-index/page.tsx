import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { TrendChart } from "@/components/TrendChart";
import { WeightEditor, type WeightDim } from "@/components/WeightEditor";
import { apiOrNullLenient, repeatedQuery, type Metric, type SignalSource } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";

export const dynamic = "force-dynamic";

interface IndexResponse {
  index: Metric;
  dimensions: Metric[];
  weights: Record<string, number>;
  limitations: string[];
}

interface TrendPoint {
  metric: string;
  period_end: string;
  source: string;
  value: number;
}

/** Deskripsi tiap dimensi POI — teks presentasi, bukan data dari server. */
const DIM_NOTES: Record<string, string> = {
  sentiment: "Agregat sentiment lintas kanal",
  approval: "Item approval, survei probabilistik",
  trust: "Indeks kepercayaan institusi",
  satisfaction: "Kepuasan layanan publik",
  issue_perception: "Persepsi terhadap isu dominan",
  confidence: "Keyakinan terhadap arah kebijakan",
};

// Bentuk fallback saat proyek belum punya data dimensi POI sama sekali
// (404 backend, lihat lib/api.ts:apiOrNull) -- insufficient_data:true di
// sini membuat JSX di bawah otomatis merender InsufficientData lewat jalur
// yang sama seperti "di bawah ambang publikasi", tidak perlu cabang baru.
const EMPTY_INDEX: IndexResponse = {
  index: {
    key: "poi",
    label: "Public Opinion Index",
    value: null,
    unit: "index",
    source: "SURVEY",
    method: "—",
    ci_low: null,
    ci_high: null,
    effective_n: null,
    insufficient_data: true,
    note: "Proyek ini belum punya data dimensi POI sama sekali.",
  },
  dimensions: [],
  weights: {},
  limitations: [],
};

export default async function IndexPage() {
  const { id: projectId, name: projectName, is_demo: isDemo } = await getCurrentProject();

  // apiOrNullLenient, bukan api/apiOrNull polos: error backend APA PUN
  // (bukan cuma "belum ada data" 404) tidak boleh menjatuhkan seluruh
  // halaman -- lihat catatan yang sama di /command untuk /topics & /alerts.
  const [index, trend] = await Promise.all([
    apiOrNullLenient<IndexResponse>(`/projects/${projectId}/opinion/index`),
    apiOrNullLenient<TrendPoint[]>(
      `/projects/${projectId}/opinion/trend${repeatedQuery({ metrics: ["poi"], limit: 12 })}`,
    ),
  ]).then(([idx, tr]) => [idx ?? EMPTY_INDEX, tr ?? []] as const);

  const dims: WeightDim[] = index.dimensions.map((d) => ({
    key: d.key,
    label: d.label,
    score: d.value ?? 0,
    weight: index.weights[d.key] ?? 0,
    source: d.source as SignalSource,
    note: DIM_NOTES[d.key] ?? "",
  }));

  return (
    <>
      <PageHeader kicker="Opinion Index" title={projectName} isDemo={isDemo} />
      <div className="body">
        <Panel kicker="Indeks komposit — bobot dapat dikonfigurasi per proyek" title="Public Opinion Index">
          {index.index.insufficient_data || index.index.value === null ? (
            <InsufficientData reason={index.index.note ?? "Sampel di bawah ambang publikasi."} />
          ) : (
            <>
              <WeightEditor projectId={projectId} initialDims={dims} />
              <Provenance
                method={index.index.method}
                n={index.index.effective_n ?? "—"}
                ci={index.index.ci_low !== null ? `${index.index.ci_low}–${index.index.ci_high}` : undefined}
                confidence="Tinggi"
                limits={index.limitations[0] ?? "Berlaku untuk periode pengukuran ini saja."}
              />
            </>
          )}
        </Panel>

        <Panel kicker="Jejak indeks" title="POI 12 minggu">
          {trend.length > 0 ? (
            <TrendChart
              points={trend}
              series={[{ key: "poi", label: "POI", color: "#4DA3FF" }]}
              domain={[65, 80]}
              height={200}
            />
          ) : (
            <InsufficientData reason="Belum ada riwayat POI untuk proyek ini." />
          )}
        </Panel>
      </div>
    </>
  );
}
