"use client";

import { useState } from "react";
import { Delta } from "./Delta";
import { Panel } from "./Panel";
import { Provenance } from "./Provenance";
import { SOURCE, type SignalSource } from "@/lib/tokens";

export interface NarrativeItem {
  id: string;
  code: string;
  statement: string;
  origin_source: SignalSource;
  volume_pct: number;
  momentum_7d: number;
  sentiment: number | null;
  media_pickup: number;
  unclustered_pct: number;
}

/** Daftar narasi + panel detail narasi terpilih. Cuma memilih, tidak menulis. */
export function NarrativeExplorer({ narratives }: { narratives: NarrativeItem[] }) {
  const [sel, setSel] = useState(narratives[0]);
  if (!sel) return null;

  return (
    <div className="grid-2">
      <Panel kicker="Narasi yang beredar" title="Narrative Map">
        <div className="narrs">
          {narratives.map((n) => (
            <button
              key={n.id}
              type="button"
              className={"narr" + (sel.id === n.id ? " narr-on" : "")}
              onClick={() => setSel(n)}
            >
              <div className="narr-head">
                <span className="narr-id">{n.code}</span>
                <span className="narr-t">{n.statement}</span>
                <span className="narr-v">{n.volume_pct}%</span>
              </div>
              <div className="bar100">
                <div
                  style={{
                    width: `${Math.min(100, n.volume_pct * 2)}%`,
                    background: (n.sentiment ?? 0) < 0 ? "var(--neg)" : "var(--pos)",
                  }}
                />
              </div>
              <div className="narr-meta">
                <span>
                  momentum <Delta value={n.momentum_7d} />
                </span>
                <span style={{ color: SOURCE[n.origin_source].color }}>
                  asal {SOURCE[n.origin_source].label}
                </span>
                <span className="dim">pickup media {n.media_pickup}</span>
              </div>
            </button>
          ))}
        </div>
      </Panel>

      <Panel kicker={`Narasi ${sel.code}`} title={sel.statement}>
        <div className="kv">
          <div>
            <span>Volume</span>
            <b>{sel.volume_pct}% dari percakapan</b>
          </div>
          <div>
            <span>Momentum 7 hari</span>
            <b>
              {sel.momentum_7d > 0 ? "+" : ""}
              {sel.momentum_7d} poin
            </b>
          </div>
          <div>
            <span>Sentiment</span>
            <b>{sel.sentiment !== null ? `${sel.sentiment > 0 ? "+" : ""}${sel.sentiment}` : "—"}</b>
          </div>
          <div>
            <span>Titik asal</span>
            <b>{SOURCE[sel.origin_source].label}</b>
          </div>
          <div>
            <span>Pickup media</span>
            <b>{sel.media_pickup} artikel</b>
          </div>
          <div>
            <span>Tidak terklaster</span>
            <b>{sel.unclustered_pct}%</b>
          </div>
        </div>
        <Provenance
          method="Embedding + clustering HDBSCAN, pelabelan narasi diverifikasi manusia"
          confidence="Sedang"
          limits={`Batas antar-narasi tidak selalu tegas; ${sel.unclustered_pct}% mention tidak terklaster`}
        />
      </Panel>
    </div>
  );
}
