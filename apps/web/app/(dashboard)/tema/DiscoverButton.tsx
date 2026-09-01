"use client";

import { useActionState } from "react";
import { discoverTopics, type DiscoverState } from "./actions";

const AWAL: DiscoverState = { ok: false, message: null };

const BUTTON: React.CSSProperties = {
  background: "var(--panel2)",
  border: "1px solid var(--line)",
  borderRadius: 3,
  padding: "6px 12px",
  cursor: "pointer",
  fontSize: 12,
};

/**
 * Pemicu penemuan tema.
 *
 * Client component karena butuh status "sedang berjalan" — klasterisasi pada
 * korpus besar tidak instan, dan tombol yang diam selama beberapa detik akan
 * ditekan berkali-kali.
 */
export function DiscoverButton({ projectId }: { projectId: string }) {
  // isPending dari useActionState (React 19) — bukan useFormStatus, supaya
  // tidak perlu menambah @types/react-dom hanya untuk satu tombol.
  const [state, action, isPending] = useActionState(discoverTopics, AWAL);

  return (
    <div style={{ textAlign: "right" }}>
      <form action={action}>
        <input type="hidden" name="projectId" value={projectId} />
        <button type="submit" className="nav-i" disabled={isPending} style={BUTTON}>
          {isPending ? "Menghitung…" : "Temukan tema"}
        </button>
      </form>
      {state.message && (
        <div
          className="proj-s"
          style={{ marginTop: 6, maxWidth: 320, color: state.ok ? "var(--txt2)" : "var(--warn)" }}
        >
          {state.message}
        </div>
      )}
    </div>
  );
}
