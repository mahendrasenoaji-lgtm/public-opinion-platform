"use client";

import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

//: Chrome grafik lewat CSS custom property, bukan hex. Recharts meneruskan
//: `stroke`/`fill` apa adanya ke atribut SVG, dan var() sah di sana — jadi
//: sumbu, grid, dan tooltip ikut berganti tema tanpa kode kondisional.
const chartAxis = {
  stroke: "var(--txt3)",
  fontSize: 10,
  fontFamily: "'IBM Plex Mono', monospace",
};
const tipStyle = {
  background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 6,
  fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: "var(--txt)",
  boxShadow: "var(--shadow)",
};

export interface TrendSeries {
  key: string;
  label: string;
  color: string;
}

/**
 * Grafik garis multi-seri, dipivot dari baris {period, metric, value} ke
 * satu baris per periode dengan satu kolom per seri — bentuk yang dipakai
 * Recharts. Pemivotan ini bukan logika domain, cuma penyesuaian bentuk data
 * untuk chart, jadi aman dilakukan di komponen client.
 */
export function TrendChart({
  points,
  series,
  domain,
  height = 230,
}: {
  points: Array<{ period_end: string; metric: string; value: number }>;
  series: TrendSeries[];
  domain: [number, number];
  height?: number;
}) {
  const byPeriod = new Map<string, Record<string, number | string>>();
  for (const p of points) {
    const row = byPeriod.get(p.period_end) ?? { period: p.period_end };
    row[p.metric] = p.value;
    byPeriod.set(p.period_end, row);
  }
  const data = [...byPeriod.values()].sort((a, b) =>
    String(a.period).localeCompare(String(b.period)),
  );

  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 6, right: 8, left: -22, bottom: 0 }}>
          <CartesianGrid stroke="var(--line)" vertical={false} />
          <XAxis dataKey="period" {...chartAxis} tickLine={false} axisLine={{ stroke: "var(--line)" }} />
          <YAxis domain={domain} {...chartAxis} tickLine={false} axisLine={false} />
          <Tooltip contentStyle={tipStyle} cursor={{ stroke: "var(--line-2)" }} />
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              stroke={s.color}
              strokeWidth={2}
              dot={false}
              name={s.label}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <div style={{ display: "flex", gap: 16, marginTop: 8, fontFamily: "'IBM Plex Mono',monospace", fontSize: 10 }}>
        {series.map((s) => (
          <span key={s.key} style={{ color: s.color }}>● {s.label}</span>
        ))}
      </div>
    </div>
  );
}
