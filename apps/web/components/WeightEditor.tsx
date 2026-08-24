"use client";

import { useMemo, useState, useTransition } from "react";
import { SOURCE, type SignalSource } from "@/lib/tokens";
import { saveOpinionWeights } from "@/app/(dashboard)/opinion-index/actions";

export interface WeightDim {
  key: string;
  label: string;
  score: number;
  weight: number;
  source: SignalSource;
  note: string;
}

/**
 * Slider bobot dimensi POI. Menghitung ulang POI secara lokal untuk umpan
 * balik instan saat digeser (matematikanya sama dengan services/poi.py:
 * rata-rata tertimbang skor yang sudah ada — tidak menghitung ulang CI atau
 * sampel efektif, itu tetap wewenang server). Baru dikirim ke server dan
 * dicatat di audit log saat pengguna menekan "Simpan bobot".
 */
export function WeightEditor({
  projectId,
  initialDims,
}: {
  projectId: string;
  initialDims: WeightDim[];
}) {
  const [dims, setDims] = useState(initialDims);
  const [saved, setSaved] = useState(true);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const totalW = dims.reduce((a, d) => a + d.weight, 0) || 1;
  const previewPoi = useMemo(
    () => dims.reduce((a, d) => a + d.score * (d.weight / totalW), 0),
    [dims, totalW],
  );

  function setWeight(key: string, weight: number) {
    setDims((prev) => prev.map((d) => (d.key === key ? { ...d, weight } : d)));
    setSaved(false);
  }

  function save() {
    setError(null);
    startTransition(async () => {
      const result = await saveOpinionWeights(
        projectId,
        Object.fromEntries(dims.map((d) => [d.key, d.weight])),
      );
      if (result.ok) setSaved(true);
      else setError(result.error);
    });
  }

  return (
    <div className="poi-wrap">
      <div>
        <div className="poi-n">{previewPoi.toFixed(1)}</div>
        <div className="poi-scale">/ 100 {!saved && <span className="pill pill-sim">PRATINJAU</span>}</div>
        <div className="poi-meta">
          <div>
            <b>Status</b> {saved ? "Bobot tersimpan" : "Belum disimpan — geser untuk pratinjau"}
          </div>
        </div>
        <button
          type="button"
          className="pill pill-ok"
          style={{ marginTop: 12, cursor: "pointer", border: 0 }}
          onClick={save}
          disabled={saved || pending}
        >
          {pending ? "Menyimpan…" : "Simpan bobot"}
        </button>
        {error && <p className="err" style={{ marginTop: 10 }}><span className="err-t">{error}</span></p>}
      </div>

      <div className="poi-dims">
        {dims.map((d) => (
          <div key={d.key} className="dim">
            <div className="dim-head">
              <span className="dim-src" style={{ background: SOURCE[d.source].color }} />
              <span className="dim-label">{d.label}</span>
              <span className="dim-score">{d.score}</span>
            </div>
            <div className="bar100">
              <div style={{ width: `${d.score}%`, background: SOURCE[d.source].color, opacity: 0.45 }} />
            </div>
            <div className="dim-w">
              <input
                type="range"
                min={0}
                max={40}
                value={d.weight}
                onChange={(e) => setWeight(d.key, Number(e.target.value))}
                aria-label={`Bobot ${d.label}`}
              />
              <span className="dim-wv">{Math.round((d.weight / totalW) * 100)}%</span>
            </div>
            <div className="dim-note">{d.note}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
