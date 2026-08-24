"use client";

import { useState } from "react";
import { Info } from "lucide-react";
import { Panel } from "./Panel";
import { Provenance } from "./Provenance";
import { InsufficientData } from "./Provenance";
import type { Metric } from "@/lib/api";

export interface ProvinceMetrics {
  province_code: string;
  province_name: string;
  poi: Metric;
  trust: Metric;
  approval: Metric;
}

//: Ambang warna mengikuti nilai POI, murni presentasi — bukan sumber R1.
function rankColor(value: number | null): string {
  if (value === null) return "#41526B";
  if (value >= 75) return "#2FBF71";
  if (value >= 70) return "#7FB45C";
  if (value >= 66) return "#F5B301";
  if (value >= 63) return "#EF8A3C";
  return "#EF4B4B";
}

/**
 * Grid provinsi berperingkat — BUKAN peta MapLibre. CLAUDE.md §6: MapLibre
 * cuma dipakai kalau data punya georeferensi asli.
 */
export function GeoExplorer({ provinces }: { provinces: ProvinceMetrics[] }) {
  const ranked = [...provinces].sort((a, b) => (b.poi.value ?? -1) - (a.poi.value ?? -1));
  const [sel, setSel] = useState(ranked[0]);
  if (!sel) return null;

  return (
    <div className="grid-2">
      <Panel kicker="Diurutkan menurut indeks" title="Opini per provinsi">
        <div className="geo">
          {ranked.map((p) => (
            <button
              key={p.province_code}
              type="button"
              className={"geo-t" + (sel.province_code === p.province_code ? " geo-on" : "")}
              onClick={() => setSel(p)}
              style={{ borderLeftColor: rankColor(p.poi.value) }}
            >
              <span className="geo-n">{p.province_name}</span>
              <span className="geo-v" style={{ color: rankColor(p.poi.value) }}>
                {p.poi.value ?? "—"}
              </span>
            </button>
          ))}
        </div>
        <div className="legend">
          <span>Rendah</span>
          {["#EF4B4B", "#EF8A3C", "#F5B301", "#7FB45C", "#2FBF71"].map((c) => (
            <i key={c} style={{ background: c }} />
          ))}
          <span>Tinggi</span>
        </div>
      </Panel>

      <Panel kicker="Detail wilayah" title={sel.province_name}>
        {sel.poi.insufficient_data ? (
          <InsufficientData reason={sel.poi.note ?? "Sampel di bawah ambang publikasi."} />
        ) : (
          <>
            <div className="kv">
              <div>
                <span>Public Opinion Index</span>
                <b>{sel.poi.value}</b>
              </div>
              <div>
                <span>Trust</span>
                <b>{sel.trust.insufficient_data ? "data tidak cukup" : sel.trust.value}</b>
              </div>
              <div>
                <span>Approval</span>
                <b>
                  {sel.approval.insufficient_data ? "data tidak cukup" : `${sel.approval.value}%`}
                </b>
              </div>
              <div>
                <span>Sampel tercapai</span>
                <b>{sel.poi.effective_n}</b>
              </div>
              {sel.poi.ci_low !== null && sel.poi.ci_high !== null && (
                <div>
                  <span>CI 95%</span>
                  <b>
                    {sel.poi.ci_low}–{sel.poi.ci_high}
                  </b>
                </div>
              )}
            </div>
            <p className="note">
              <Info size={13} /> Estimasi provinsi hanya ditampilkan bila sampel tercapai memenuhi
              ambang minimum. Provinsi dengan n di bawah 250 ditandai sebagai data tidak cukup.
            </p>
            <Provenance
              method={sel.poi.method}
              n={sel.poi.effective_n ?? "—"}
              ci={sel.poi.ci_low !== null ? `${sel.poi.ci_low}–${sel.poi.ci_high}` : undefined}
              confidence={(sel.poi.effective_n ?? 0) > 400 ? "Tinggi" : "Sedang"}
              limits="Tidak dapat diturunkan ke tingkat kabupaten/kota tanpa sampel tambahan"
            />
          </>
        )}
      </Panel>
    </div>
  );
}
