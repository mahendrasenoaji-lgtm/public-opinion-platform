"use client";

import { useState, useTransition } from "react";
import {
  correctSentiment,
  type SentimentLabel,
} from "@/app/(dashboard)/sinyal/actions";

const LABELS: [SentimentLabel, string][] = [
  ["negatif", "Negatif"],
  ["netral", "Netral"],
  ["positif", "Positif"],
];

function labelOf(value: number | null): SentimentLabel | null {
  if (value === null) return null;
  // Ambang yang sama dengan services/sentiment.py (POSITIVE/NEGATIVE_THRESHOLD).
  if (value > 0.15) return "positif";
  if (value < -0.15) return "negatif";
  return "netral";
}

/**
 * Skor sentimen satu konten + kontrol koreksi manual.
 *
 * Yang ditetapkan manusia adalah LABEL (negatif/netral/positif), bukan angka.
 * Konten yang sudah dikoreksi ditandai "manual" dan bisa dibatalkan, yang
 * mengembalikannya ke skor penilai otomatis terkini.
 */
export function SentimentCorrector({
  projectId,
  mentionId,
  sentiment,
  manual,
  canEdit,
}: {
  projectId: string;
  mentionId: string;
  sentiment: number | null;
  manual: boolean;
  canEdit: boolean;
}) {
  const [state, setState] = useState({ sentiment, manual });
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();
  const current = labelOf(state.sentiment);

  function apply(label: SentimentLabel | null) {
    setError("");
    startTransition(async () => {
      const res = await correctSentiment(projectId, mentionId, label);
      if (!res.ok) {
        setError(res.error);
        return;
      }
      setState({ sentiment: res.result.sentiment, manual: res.result.sentiment_manual });
    });
  }

  return (
    <div className="corr">
      <span className="mono corr-v">
        {state.sentiment === null
          ? "tidak dinilai"
          : `${state.sentiment > 0 ? "+" : ""}${state.sentiment.toFixed(2)}`}
        {state.manual && <span className="pill pill-ok corr-tag">manual</span>}
      </span>
      {canEdit && (
        <span className="corr-btns">
          {LABELS.map(([label, text]) => (
            <button
              key={label}
              type="button"
              className={"btn btn-ghost btn-sm" + (state.manual && current === label ? " corr-on" : "")}
              aria-pressed={state.manual && current === label}
              disabled={pending}
              onClick={() => apply(label)}
              title={`Tetapkan label ${text.toLowerCase()} (koreksi manual)`}
            >
              {text}
            </button>
          ))}
          {state.manual && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={pending}
              onClick={() => apply(null)}
              title="Batalkan koreksi; kembali ke skor penilai otomatis"
            >
              Batal
            </button>
          )}
        </span>
      )}
      {error && (
        <span className="form-err" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
