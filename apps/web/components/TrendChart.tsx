"use client";

import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const chartAxis = { stroke: "#41526B", fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" };
const tipStyle = {
  background: "#0D141D", border: "1px solid #22303F", borderRadius: 2,
  fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: "#E6EDF6",
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
          <CartesianGrid stroke="#1A2532" vertical={false} />
          <XAxis dataKey="period" {...chartAxis} tickLine={false} axisLine={{ stroke: "#1F2B3C" }} />
          <YAxis domain={domain} {...chartAxis} tickLine={false} axisLine={false} />
          <Tooltip contentStyle={tipStyle} cursor={{ stroke: "#2A3A4D" }} />
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
