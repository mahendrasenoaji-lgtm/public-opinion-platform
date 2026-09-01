"use client";

import { useActionState } from "react";
import { Provenance } from "@/components/Provenance";
import { SOURCE, type SignalSource } from "@/lib/tokens";
import { askCopilot, type AskState } from "./actions";

// Didefinisikan di sini, bukan di actions.ts — modul "use server" hanya boleh
// mengekspor fungsi async. Lihat catatan di dampak/actions.ts.
const AWAL: AskState = { answer: null, error: null, question: "" };

const CONFIDENCE_ID: Record<string, string> = {
  LOW: "Rendah",
  MEDIUM: "Sedang",
  HIGH: "Tinggi",
};

export function AskForm({ projectId }: { projectId: string }) {
  // isPending dari useActionState (React 19), bukan useFormStatus — lihat
  // catatan yang sama di tema/DiscoverButton.tsx.
  const [state, action, isPending] = useActionState(askCopilot, AWAL);
  const answer = state.answer;

  return (
    <>
      <form action={action} style={{ display: "flex", gap: 10 }}>
        <input type="hidden" name="projectId" value={projectId} />
        <input
          name="question"
          defaultValue={state.question}
          placeholder="mis. Bagaimana sentimen percakapan sosial dibanding hasil survei?"
          style={{
            flex: 1,
            background: "var(--panel2)",
            border: "1px solid var(--line)",
            borderRadius: 3,
            padding: "8px 12px",
            color: "var(--txt)",
            fontSize: 13,
          }}
        />
        <button
          type="submit"
          disabled={isPending}
          style={{
            background: "var(--panel2)",
            border: "1px solid var(--line)",
            borderRadius: 3,
            padding: "8px 16px",
            color: "var(--txt)",
            cursor: isPending ? "wait" : "pointer",
            fontSize: 13,
          }}
        >
          {isPending ? "Menyusun jawaban…" : "Tanya"}
        </button>
      </form>

      {state.error && (
        <div className="insufficient" style={{ marginTop: 16 }}>
          <div className="insufficient-t">Tidak bisa dijawab</div>
          <div className="insufficient-d">{state.error}</div>
        </div>
      )}

      {answer && (
        <div style={{ marginTop: 18 }}>
          {answer.payload.data_tidak_tersedia && (
            <div className="pill pill-warn" style={{ display: "inline-block", marginBottom: 10 }}>
              data tidak tersedia untuk pertanyaan ini
            </div>
          )}

          <p style={{ fontSize: 14, lineHeight: 1.65, margin: "0 0 16px" }}>
            {answer.payload.jawaban}
          </p>

          <h3 className="kicker">Bukti yang dipakai</h3>
          <div className="narrs" style={{ marginTop: 8 }}>
            {answer.evidence.map((e, i) => {
              const meta = SOURCE[e.source as SignalSource];
              return (
                <div key={`${e.label}-${i}`} className="narr">
                  <div className="narr-head">
                    <span className="narr-t">{e.label}</span>
                    <span className="pill" style={{ color: meta?.color }}>
                      {meta?.label ?? e.source}
                    </span>
                  </div>
                  {e.n !== null && (
                    <div className="narr-meta mono" style={{ marginTop: 4 }}>
                      n = {e.n}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {Object.keys(answer.matched_terms).length > 0 && (
            <p className="proj-s" style={{ marginTop: 12 }}>
              {/* Kata yang cocok ditampilkan supaya pengguna yang bertanya
                  kenapa suatu bukti dipakai bisa ditunjukkan jawabannya —
                  pemilihannya pencocokan kata kunci, bukan pemahaman makna. */}
              Kartu dipilih karena kata:{" "}
              <span className="mono">
                {Object.entries(answer.matched_terms)
                  .map(([k, terms]) => `${k} (${terms.join(", ")})`)
                  .join(" · ")}
              </span>
            </p>
          )}

          <Provenance
            method={answer.method}
            n={`${answer.cards_used}/${answer.cards_considered} kartu fakta`}
            confidence={CONFIDENCE_ID[answer.confidence] ?? answer.confidence}
            limits={answer.limitations}
          />
        </div>
      )}
    </>
  );
}
