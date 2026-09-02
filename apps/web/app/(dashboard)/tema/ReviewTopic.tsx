"use client";

import { useActionState, useState } from "react";
import { reviewTopic, type ReviewState } from "./actions";

// Didefinisikan di sini, bukan di actions.ts — modul "use server" hanya boleh
// mengekspor fungsi async. Lihat catatan yang sama di dampak/actions.ts.
const AWAL: ReviewState = { ok: false, message: null };

const BUTTON: React.CSSProperties = {
  background: "var(--panel2)",
  border: "1px solid var(--line)",
  borderRadius: 3,
  padding: "4px 10px",
  cursor: "pointer",
  fontSize: 11,
};

const REVIEW_LABEL: Record<string, string> = {
  PENDING: "belum ditinjau",
  APPROVED: "disetujui",
  REJECTED: "ditolak",
  NEEDS_REVIEW: "perlu ditinjau ulang",
};

/**
 * Verifikasi manusia atas label kata-kunci satu tema.
 *
 * Sengaja bukan tombol satu-klik: menyunting label adalah klaim interpretatif
 * ("ini yang dimaksud tema ini"), jadi butuh langkah sadar (buka form,
 * ketik/biarkan kosong, baru kirim) — bukan sesuatu yang bisa terjadi tanpa
 * sengaja.
 */
export function ReviewTopic({
  projectId,
  topicId,
  reviewStatus,
  reviewedLabel,
  rawLabel,
}: {
  projectId: string;
  topicId: string;
  reviewStatus: string;
  reviewedLabel: string | null;
  rawLabel: string;
}) {
  const [state, action, isPending] = useActionState(reviewTopic, AWAL);
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState(reviewedLabel ?? "");

  if (!open) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
        <span
          className={
            reviewStatus === "APPROVED"
              ? "pill pill-ok"
              : reviewStatus === "REJECTED"
                ? "pill pill-warn"
                : "pill"
          }
        >
          {REVIEW_LABEL[reviewStatus] ?? reviewStatus}
        </span>
        <button type="button" onClick={() => setOpen(true)} className="nav-i" style={BUTTON}>
          Tinjau label
        </button>
      </div>
    );
  }

  return (
    <form action={action} style={{ marginTop: 8 }}>
      <input type="hidden" name="projectId" value={projectId} />
      <input type="hidden" name="topicId" value={topicId} />
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          name="label"
          placeholder={`Kosongkan untuk menyetujui "${rawLabel}" apa adanya`}
          style={{
            background: "var(--panel2)",
            border: "1px solid var(--line)",
            borderRadius: 3,
            padding: "5px 8px",
            fontSize: 12,
            color: "var(--txt)",
            minWidth: 220,
          }}
        />
        <button
          type="submit"
          name="status"
          value="APPROVED"
          disabled={isPending}
          className="pill pill-ok"
          style={{ ...BUTTON, border: "none" }}
        >
          Setujui
        </button>
        <button
          type="submit"
          name="status"
          value="REJECTED"
          disabled={isPending}
          className="pill pill-warn"
          style={{ ...BUTTON, border: "none" }}
        >
          Tolak
        </button>
        <button
          type="submit"
          name="status"
          value="NEEDS_REVIEW"
          disabled={isPending}
          className="pill"
          style={{ ...BUTTON, border: "none" }}
        >
          Perlu ditinjau ulang
        </button>
        <button type="button" onClick={() => setOpen(false)} className="nav-i" style={BUTTON}>
          Batal
        </button>
      </div>
      {state.message && (
        <div className="proj-s" style={{ marginTop: 4, color: "var(--warn)" }}>
          {state.message}
        </div>
      )}
    </form>
  );
}
