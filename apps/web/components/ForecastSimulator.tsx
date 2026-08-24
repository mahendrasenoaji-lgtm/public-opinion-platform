"use client";

import { useEffect, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Delta } from "./Delta";
import { Panel } from "./Panel";
import { Provenance } from "./Provenance";
import { runWhatIf, type WhatIfResult } from "@/app/(dashboard)/forecast/actions";

const chartAxis = { stroke: "#41526B", fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" };
const tipStyle = {
  background: "#0D141D", border: "1px solid #22303F", borderRadius: 2,
  fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: "#E6EDF6",
};

const DRIVERS = [
  {
    key: "food_price",
    label: "Kenaikan harga pangan",
    unit: "%",
    hint: "Setiap 1% kenaikan diasosiasikan dengan penurunan indeks pada horizon 30 hari",
  },
  {
    key: "comms_intensity",
    label: "Intensitas komunikasi publik",
    unit: " unit",
    hint: "Efek positif terhadap indeks, melandai setelah titik jenuh",
  },
  {
    key: "negative_coverage",
    label: "Eskalasi liputan negatif",
    unit: " unit",
    hint: "Memperlebar ketidakpastian, bukan hanya menurunkan rata-rata",
  },
] as const;

export function ForecastSimulator({
  projectId,
  baseline,
  initial,
}: {
  projectId: string;
  baseline: number;
  initial: WhatIfResult;
}) {
  const [values, setValues] = useState<Record<string, number>>({
    food_price: 0,
    comms_intensity: 0,
    negative_coverage: 0,
  });
  const [result, setResult] = useState<WhatIfResult>(initial);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function setDriver(key: string, v: number) {
    const next = { ...values, [key]: v };
    setValues(next);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setPending(true);
      setError(null);
      const scenario = Object.fromEntries(Object.entries(next).filter(([, val]) => val !== 0));
      const res = await runWhatIf(projectId, baseline, scenario);
      setPending(false);
      if (res.ok) setResult(res.result);
      else setError(res.error);
    }, 400);
  }

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
  }, []);

  const active = Object.values(values).some((v) => v !== 0);
  const end = result.points[result.points.length - 1];
  const chartData = result.points.map((p) => ({
    d: `H+${p.horizon_days}`,
    exp: p.expected,
    low: p.pi_low,
    high: p.pi_high,
  }));

  return (
    <>
      <Panel
        kicker="Proyeksi model, bukan kepastian"
        title="Opinion Forecast"
        right={active && <span className="pill pill-sim">SIMULASI AKTIF</span>}
      >
        <div className="chart">
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={chartData} margin={{ top: 6, right: 8, left: -22, bottom: 0 }}>
              <CartesianGrid stroke="#1A2532" vertical={false} />
              <XAxis dataKey="d" {...chartAxis} tickLine={false} axisLine={{ stroke: "#1F2B3C" }} />
              <YAxis domain={["auto", "auto"]} {...chartAxis} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tipStyle} />
              <Area type="monotone" dataKey="high" stroke="none" fill="#4DA3FF" fillOpacity={0.14} name="Batas atas" />
              <Area type="monotone" dataKey="low" stroke="none" fill="#0A1017" fillOpacity={1} name="Batas bawah" />
              <Line type="monotone" dataKey="exp" stroke="#4DA3FF" strokeWidth={2.5} dot={false} name="Ekspektasi" />
              <ReferenceLine y={baseline} stroke="#41526B" strokeDasharray="3 3" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="fc-out">
          <div>
            <span className="kicker">Sekarang</span>
            <b>{baseline.toFixed(1)}</b>
          </div>
          <div>
            <span className="kicker">Ekspektasi H+{end?.horizon_days ?? "—"}</span>
            <b>{end?.expected ?? "—"}</b>
          </div>
          <div>
            <span className="kicker">Rentang</span>
            <b>
              {end?.pi_low} – {end?.pi_high}
            </b>
          </div>
          <div>
            <span className="kicker">Perubahan</span>
            <b>{end && <Delta value={+(end.expected - baseline).toFixed(1)} />}</b>
          </div>
        </div>
      </Panel>

      <Panel kicker="What-if" title="Uji skenario">
        <div className="sliders">
          {DRIVERS.map((d) => (
            <div key={d.key} className="slider">
              <div className="slider-top">
                <label htmlFor={d.key}>{d.label}</label>
                <span className="slider-v">
                  {values[d.key]}
                  {d.unit}
                </span>
              </div>
              <input
                id={d.key}
                type="range"
                min={0}
                max={10}
                value={values[d.key]}
                onChange={(e) => setDriver(d.key, Number(e.target.value))}
              />
              <div className="slider-h">{d.hint}</div>
            </div>
          ))}
        </div>
        <div className="sim-out">
          <div className="sim-t">{pending ? "Menghitung ulang…" : "Hasil simulasi"}</div>
          {error && <p className="sim-warn">{error}</p>}
          <p>
            Skenario ini memproyeksikan indeks berada di sekitar <b>{end?.expected}</b> pada H+
            {end?.horizon_days}, dengan rentang <b>{end?.pi_low}–{end?.pi_high}</b>.
          </p>
          <p className="sim-warn">
            Angka di atas adalah keluaran simulasi berdasarkan koefisien historis, bukan prediksi
            yang dijamin dan bukan dasar tunggal untuk pengambilan keputusan.
          </p>
        </div>
        <Provenance
          method={result.model}
          ci={`Interval prediksi ${Math.round(result.pi_level * 100)}%`}
          confidence="Sedang"
          limits={result.limitations[0] ?? "Koefisien diestimasi historis; tidak valid untuk skenario ekstrem"}
        />
      </Panel>
    </>
  );
}
