"use client";

import { useState, useTransition } from "react";
import { Panel } from "./Panel";
import { Provenance } from "./Provenance";
import {
  approveBrief,
  generateBrief,
  type BriefOut,
} from "@/app/(dashboard)/brief/actions";

const SECTIONS: Array<[keyof BriefOut["payload"], string]> = [
  ["apa_yang_terjadi", "Apa yang terjadi"],
  ["mengapa", "Mengapa"],
  ["siapa", "Siapa"],
  ["di_mana", "Di mana"],
  ["apa_berikutnya", "Apa berikutnya"],
  ["yang_perlu_diawasi", "Apa yang perlu diawasi"],
];

const REVIEW_LABEL: Record<BriefOut["human_review"], string> = {
  PENDING: "Menunggu tinjauan",
  APPROVED: "Disetujui",
  REJECTED: "Ditolak",
  NEEDS_REVIEW: "Perlu tinjauan",
};

/**
 * Tombol generate (kalau belum ada brief) + tampilan enam bagian + tombol
 * approve (kalau ada & pengguna punya kapasitas ai_output:approve).
 * Ringkasan ini dibuat AI (R2 CLAUDE.md) — setiap kartu wajib berkaki
 * Provenance, tidak ada pengecualian.
 */
export function BriefGenerator({
  projectId,
  initial,
  canApprove,
}: {
  projectId: string;
  initial: BriefOut | null;
  canApprove: boolean;
}) {
  const [brief, setBrief] = useState(initial);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function onGenerate() {
    setError(null);
    startTransition(async () => {
      const res = await generateBrief(projectId);
      if (res.ok) setBrief(res.brief);
      else setError(res.error);
    });
  }

  function onApprove() {
    if (!brief) return;
    setError(null);
    startTransition(async () => {
      const res = await approveBrief(projectId, brief.id);
      if (res.ok) setBrief(res.brief);
      else setError(res.error);
    });
  }

  if (!brief) {
    return (
      <Panel kicker="Belum ada ringkasan" title="Executive Brief">
        <p style={{ marginBottom: 14 }}>
          Belum ada Executive Brief untuk proyek ini. Ringkasan dibuat oleh model bahasa dari data
          agregat proyek saat ini (index, divergensi sumber, segmen, sebaran wilayah, peristiwa
          terbaru), lalu wajib ditinjau manusia sebelum dipakai resmi.
        </p>
        <button type="button" className="pill pill-ok" style={{ border: 0, cursor: "pointer" }} onClick={onGenerate} disabled={pending}>
          {pending ? "Membuat…" : "Buat ringkasan"}
        </button>
        {error && (
          <p className="err" style={{ marginTop: 10 }}>
            <span className="err-t">{error}</span>
          </p>
        )}
      </Panel>
    );
  }

  return (
    <Panel tone="light">
      <div className="brief">
        <div className="brief-head">
          <div>
            <div className="kicker">
              Executive brief · Dibuat otomatis, {REVIEW_LABEL[brief.human_review].toLowerCase()}
            </div>
            <h1 className="brief-h1">{brief.payload.apa_yang_terjadi}</h1>
          </div>
          <div className="brief-badge">
            {brief.human_review === "APPROVED" && brief.reviewed_at
              ? `Disetujui · ${new Date(brief.reviewed_at).toLocaleDateString("id-ID")}`
              : REVIEW_LABEL[brief.human_review]}
          </div>
        </div>

        <dl className="brief-list">
          {SECTIONS.map(([key, label]) => (
            <div key={key}>
              <dt>{label}</dt>
              <dd>{brief.payload[key]}</dd>
            </div>
          ))}
        </dl>

        <div className="brief-foot">
          Setiap kalimat pada ringkasan ini disusun dari data agregat proyek — lihat bukti di
          bawah. Rekomendasi tindakan (bila ada) adalah opsi; keputusan tetap pada pengambil
          kebijakan.
        </div>

        <Provenance
          method={brief.method}
          confidence={brief.confidence}
          limits={brief.limitations}
        />

        {canApprove && brief.human_review === "PENDING" && (
          <button
            type="button"
            className="pill pill-ok"
            style={{ marginTop: 14, border: 0, cursor: "pointer" }}
            onClick={onApprove}
            disabled={pending}
          >
            {pending ? "Menyetujui…" : "Setujui ringkasan"}
          </button>
        )}
        {error && (
          <p className="err" style={{ marginTop: 10 }}>
            <span className="err-t">{error}</span>
          </p>
        )}
      </div>
    </Panel>
  );
}
