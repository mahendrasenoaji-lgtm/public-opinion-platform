"use client";

import { SOURCE, type SignalSource } from "@/lib/tokens";
import { Provenance } from "./Provenance";

/**
 * Elemen tanda tangan platform.
 *
 * Menempatkan survei, media sosial, dan media pada satu skala 0-100 dan
 * menjadikan selisihnya sebagai objek utama, bukan catatan kaki. Inilah
 * pertanyaan yang tidak dijawab dashboard survei biasa: kenapa angkanya beda.
 */
export function DivergenceBand({
  readings,
  gap,
  explanationLead,
}: {
  readings: Array<{ source: SignalSource; value: number; n: number }>;
  gap: number;
  explanationLead: string;
}) {
  const sorted = [...readings].sort((a, b) => a.value - b.value);
  if (sorted.length === 0) return null;
  const lo = sorted[0]!.value;
  const hi = sorted[sorted.length - 1]!.value;

  return (
    <section className="dvg">
      <header className="dvg-head">
        <div>
          <div className="kicker">One opinion — multiple signals</div>
          <h2 className="panel-title">Sinyal opini tidak sepakat</h2>
        </div>
        <div className="dvg-gap">
          <div className="dvg-gap-n">{gap}</div>
          <div className="kicker">poin selisih</div>
        </div>
      </header>

      <div className="dvg-track" role="img"
           aria-label={sorted.map((r) => `${SOURCE[r.source].label} ${r.value}`).join(", ")}>
        <div className="dvg-span" style={{ left: `${lo}%`, width: `${hi - lo}%` }} />
        {sorted.map((r, i) => (
          <div key={r.source} className="dvg-mark" style={{ left: `${r.value}%` }}>
            <div className="dvg-stem" style={{ background: SOURCE[r.source].color, height: 26 + i * 16 }} />
            <div className="dvg-dot" style={{ background: SOURCE[r.source].color }} />
            <div className="dvg-tag" style={{ bottom: 34 + i * 16, borderColor: SOURCE[r.source].color }}>
              <span style={{ color: SOURCE[r.source].color }}>{SOURCE[r.source].label}</span> {r.value}
            </div>
          </div>
        ))}
        <div className="dvg-scale"><span>0</span><span>50</span><span>100</span></div>
      </div>

      <p className="dvg-read">{explanationLead}</p>

      <Provenance
        method="Survei CATI multistage + agregasi API platform"
        n={readings.map((r) => r.n.toLocaleString("id-ID")).join(" / ")}
        confidence="Sedang"
        limits="Sosial tidak representatif populasi dan tidak dapat dibobot ke populasi nasional"
      />
    </section>
  );
}
