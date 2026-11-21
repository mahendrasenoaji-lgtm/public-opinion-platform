"use client";

import { useMemo, useState } from "react";
import { groupColor } from "@/lib/tokens";

export interface VizNode {
  id: string;
  x: number;
  y: number;
  community: number;
  pagerank: number;
  in_degree: number;
  out_degree: number;
}

export interface VizEdge {
  source: string;
  target: string;
  weight: number;
}

const W = 1000;
const H = 620;
const PAD = 28;
const nf = new Intl.NumberFormat("id-ID");

/**
 * Peta jaringan: posisi sudah dihitung server (services/sna.py, force-directed
 * dengan seed tetap), jadi tidak ada pustaka graf di peramban dan petanya sama
 * setiap kali dibuka. Warna = komunitas (bukan sumber, lihat GROUP di
 * lib/tokens.ts); ukuran = PageRank. Klik simpul untuk menyorot tetangganya.
 */
export function NetworkMap({
  nodes,
  edges,
  communities,
}: {
  nodes: VizNode[];
  edges: VizEdge[];
  communities: { id: number; size: number }[];
}) {
  const [hover, setHover] = useState<VizNode | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [hidden, setHidden] = useState<Set<number>>(new Set());

  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const maxPr = Math.max(...nodes.map((n) => n.pagerank), 1e-9);
  const maxW = Math.max(...edges.map((e) => e.weight), 1);
  const neighbors = useMemo(() => {
    if (!selected) return null;
    const s = new Set<string>([selected]);
    for (const e of edges) {
      if (e.source === selected) s.add(e.target);
      if (e.target === selected) s.add(e.source);
    }
    return s;
  }, [selected, edges]);

  const px = (v: number) => PAD + v * (W - 2 * PAD);
  const py = (v: number) => PAD + v * (H - 2 * PAD);
  const radius = (n: VizNode) => 3 + Math.sqrt(n.pagerank / maxPr) * 13;
  const visible = (n: VizNode) => !hidden.has(n.community);

  function toggle(id: number) {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div style={{ position: "relative" }}>
      <div className="nm-legend" role="group" aria-label="Saring komunitas">
        {communities.map((c) => (
          <button
            key={c.id}
            type="button"
            className={hidden.has(c.id) ? "btn btn-ghost btn-sm" : "btn btn-sm btn-ghost"}
            aria-pressed={!hidden.has(c.id)}
            style={{ opacity: hidden.has(c.id) ? 0.45 : 1 }}
            onClick={() => toggle(c.id)}
          >
            <span className="nm-swatch" style={{ background: groupColor(c.id) }} />K{c.id} ·{" "}
            {nf.format(c.size)} akun
          </button>
        ))}
        <span className="field-hint" style={{ alignSelf: "center" }}>
          <span className="nm-swatch" style={{ background: "var(--txt3)" }} />
          abu-abu = komunitas kecil/lainnya
        </span>
      </div>

      <svg
        className="netmap"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Peta jaringan ${nodes.length} akun teratas dan ${edges.length} relasi di antara mereka`}
        onClick={() => setSelected(null)}
      >
        <g>
          {edges.map((e) => {
            const a = byId.get(e.source);
            const b = byId.get(e.target);
            if (!a || !b || !visible(a) || !visible(b)) return null;
            const lit = !neighbors || (neighbors.has(a.id) && neighbors.has(b.id) &&
              (a.id === selected || b.id === selected));
            return (
              <line
                key={`${e.source}-${e.target}`}
                className="nm-edge"
                x1={px(a.x)}
                y1={py(a.y)}
                x2={px(b.x)}
                y2={py(b.y)}
                strokeWidth={0.6 + (e.weight / maxW) * 2.4}
                strokeOpacity={lit ? 0.18 + (e.weight / maxW) * 0.5 : 0.04}
              />
            );
          })}
        </g>
        <g>
          {nodes.filter(visible).map((n) => {
            const dim = neighbors && !neighbors.has(n.id);
            return (
              <circle
                key={n.id}
                className="nm-node"
                cx={px(n.x)}
                cy={py(n.y)}
                r={radius(n)}
                fill={groupColor(n.community)}
                fillOpacity={dim ? 0.15 : 0.9}
                onMouseEnter={() => setHover(n)}
                onMouseLeave={() => setHover(null)}
                onClick={(ev) => {
                  ev.stopPropagation();
                  setSelected((cur) => (cur === n.id ? null : n.id));
                }}
              >
                <title>{`${n.id.slice(0, 12)}… · K${n.community || "–"}`}</title>
              </circle>
            );
          })}
        </g>
      </svg>

      {hover && (
        <div
          className="nm-tip"
          style={{
            left: `${(px(hover.x) / W) * 100}%`,
            top: `${(py(hover.y) / H) * 100}%`,
            transform: "translate(12px, -50%)",
          }}
        >
          <div className="mono">{hover.id.slice(0, 16)}…</div>
          <div>Komunitas: {hover.community ? `K${hover.community}` : "lainnya"}</div>
          <div>
            Dibalas/dikutip {nf.format(hover.in_degree)} · membalas {nf.format(hover.out_degree)}
          </div>
          <div>PageRank {hover.pagerank.toFixed(4)}</div>
        </div>
      )}
      <p className="field-hint" style={{ marginTop: 6 }}>
        Klik simpul untuk menyorot akun yang terhubung langsung; klik latar untuk kembali. Peta
        hanya memuat akun teratas; angka lengkapnya ada di tabel aktor di bawah.
      </p>
    </div>
  );
}
