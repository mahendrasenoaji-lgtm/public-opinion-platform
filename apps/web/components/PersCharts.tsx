"use client";

import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { dayLabel, type PersDay } from "@/lib/pers";

const axis = { stroke: "var(--txt3)", fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" };
const tip = {
  background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 6,
  fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: "var(--txt)",
  boxShadow: "var(--shadow)",
};
const num = (n: number) => n.toLocaleString("id-ID");

/**
 * Dua grafik harian untuk SATU sumber (R1: sumber tidak pernah digabung).
 * Volume dan porsi negatif sengaja dua grafik terpisah, masing-masing satu
 * sumbu: satuannya berbeda, dan grafik bersumbu ganda mengundang salah baca.
 * Hari dengan konten bernilai di bawah ambang tampil sebagai celah, bukan nol.
 */
export function PersDailyCharts({
  days,
  color,
  sourceLabel,
}: {
  days: PersDay[];
  color: string;
  sourceLabel: string;
}) {
  const data = days.map((d) => ({
    day: dayLabel(d.day),
    volume: d.volume,
    negative: d.negative_share === null ? null : Math.round(d.negative_share * 1000) / 10,
  }));
  const anyShare = data.some((d) => d.negative !== null);

  return (
    <div className="pers-charts">
      <figure>
        <figcaption>Jumlah konten per hari ({sourceLabel})</figcaption>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }} barCategoryGap="18%">
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="day" {...axis} tickLine={false} axisLine={{ stroke: "var(--line)" }} minTickGap={12} />
            <YAxis {...axis} tickLine={false} axisLine={false} width={48} tickFormatter={num} allowDecimals={false} />
            <Tooltip
              contentStyle={tip}
              cursor={{ fill: "var(--panel3)" }}
              formatter={(v) => [num(Number(v)), "Konten"]}
            />
            <Bar dataKey="volume" fill={color} radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </figure>

      <figure>
        <figcaption>Porsi konten bernada negatif per hari, dari yang bernilai sentimen ({sourceLabel})</figcaption>
        {anyShare ? (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis dataKey="day" {...axis} tickLine={false} axisLine={{ stroke: "var(--line)" }} minTickGap={12} padding={{ left: 24, right: 24 }} />
              <YAxis {...axis} domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickLine={false} axisLine={false} width={48} unit="%" />
              <Tooltip
                contentStyle={tip}
                cursor={{ stroke: "var(--line-2)" }}
                formatter={(v) => [`${String(v).replace(".", ",")}%`, "Negatif"]}
              />
              <Line
                type="linear"
                dataKey="negative"
                stroke={color}
                strokeWidth={2}
                dot={{ r: 4, fill: color, stroke: "var(--panel)", strokeWidth: 2 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <p className="pers-empty">Data tidak cukup: tiap hari punya kurang dari 30 konten bernilai.</p>
        )}
      </figure>
    </div>
  );
}
