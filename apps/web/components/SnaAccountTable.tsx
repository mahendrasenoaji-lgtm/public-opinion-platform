"use client";

import { useState } from "react";
import { groupColor } from "@/lib/tokens";

export interface AccountMetricsRow {
  author_hash: string;
  in_degree: number;
  out_degree: number;
  partners: number;
  betweenness: number | null;
  closeness: number | null;
  pagerank: number;
  eigenvector: number | null;
  community: number;
}

type Key = "pagerank" | "in_degree" | "out_degree" | "partners" | "betweenness" | "closeness" | "eigenvector";

const COLUMNS: { key: Key; label: string; hint: string }[] = [
  { key: "in_degree", label: "Dibalas/dikutip", hint: "In-degree berbobot: berapa kali akun ini dibalas atau dikutip" },
  { key: "out_degree", label: "Membalas", hint: "Out-degree berbobot: berapa kali akun ini membalas atau mengutip" },
  { key: "partners", label: "Mitra", hint: "Akun berbeda yang terhubung langsung (dua arah)" },
  { key: "betweenness", label: "Betweenness", hint: "Seberapa sering akun berada di jalur terpendek antar-akun lain (peran penghubung)" },
  { key: "closeness", label: "Closeness", hint: "Seberapa dekat akun ke akun lain dalam graf (Wasserman-Faust)" },
  { key: "pagerank", label: "PageRank", hint: "Dibalas oleh akun yang juga banyak dibalas" },
  { key: "eigenvector", label: "Eigenvector", hint: "Terhubung dengan akun yang juga banyak terhubung" },
];

const nf = new Intl.NumberFormat("id-ID");
const fmt = (k: Key, v: number | null) =>
  v === null ? "–" : k === "in_degree" || k === "out_degree" || k === "partners" ? nf.format(v) : v.toFixed(4);

export function SnaAccountTable({ rows }: { rows: AccountMetricsRow[] }) {
  const [sort, setSort] = useState<Key>("pagerank");
  const [all, setAll] = useState(false);
  const sorted = [...rows].sort((a, b) => (b[sort] ?? -1) - (a[sort] ?? -1));
  const shown = all ? sorted : sorted.slice(0, 20);
  const peak = Math.max(...rows.map((r) => r[sort] ?? 0), 1e-9);

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="tbl">
        <thead>
          <tr>
            <th>Akun (hash)</th>
            <th>Kom.</th>
            {COLUMNS.map((c) => (
              <th key={c.key} title={c.hint}>
                <button
                  type="button"
                  className="sort-btn"
                  aria-pressed={sort === c.key}
                  onClick={() => setSort(c.key)}
                >
                  {c.label}
                  {sort === c.key ? " ↓" : ""}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={r.author_hash}>
              <td className="mono">{r.author_hash.slice(0, 12)}…</td>
              <td>
                <span className="nm-swatch" style={{ background: groupColor(r.community) }} />
                {r.community ? `K${r.community}` : "–"}
              </td>
              {COLUMNS.map((c) => (
                <td key={c.key} className="mono">
                  {c.key === sort ? (
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <div className="bar100" style={{ flex: 1, minWidth: 40 }}>
                        <div style={{ width: `${((r[c.key] ?? 0) / peak) * 100}%`, background: "var(--txt2)" }} />
                      </div>
                      {fmt(c.key, r[c.key])}
                    </div>
                  ) : (
                    fmt(c.key, r[c.key])
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 20 && (
        <button type="button" className="btn btn-ghost btn-sm" style={{ marginTop: 8 }} onClick={() => setAll(!all)}>
          {all ? "Tampilkan 20 teratas" : `Tampilkan semua (${rows.length})`}
        </button>
      )}
    </div>
  );
}
