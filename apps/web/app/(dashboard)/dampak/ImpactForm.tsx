"use client";

import { useActionState } from "react";
import { Provenance } from "@/components/Provenance";
import { analyzeImpact, type ImpactState } from "./actions";

// Didefinisikan di sini, bukan di actions.ts — modul "use server" hanya boleh
// mengekspor fungsi async. Lihat catatan di actions.ts.
const AWAL: ImpactState = {
  result: null,
  error: null,
  input: {
    metric: "approval",
    treated_segment: "",
    control_segment: "",
    pre_period_end: "",
    post_period_end: "",
  },
};

const FIELD: React.CSSProperties = {
  background: "var(--panel2)",
  border: "1px solid var(--line)",
  borderRadius: 3,
  padding: "7px 10px",
  color: "var(--txt)",
  fontSize: 13,
  width: "100%",
};

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "block" }}>
      <span className="kicker">{label}</span>
      <div style={{ marginTop: 5 }}>{children}</div>
      {hint && <div className="proj-s" style={{ marginTop: 4 }}>{hint}</div>}
    </label>
  );
}

export function ImpactForm({ projectId, segments }: { projectId: string; segments: string[] }) {
  // isPending dari useActionState (React 19), bukan useFormStatus — lihat
  // catatan yang sama di tema/DiscoverButton.tsx.
  const [state, action, isPending] = useActionState(analyzeImpact, AWAL);
  const r = state.result;

  return (
    <>
      <form action={action}>
        <input type="hidden" name="projectId" value={projectId} />
        <div className="sliders">
          <Field label="Metrik">
            <input name="metric" defaultValue={state.input.metric || "approval"} style={FIELD} />
          </Field>
          <Field label="Segmen terpapar" hint="Kelompok yang menerima komunikasi">
            <input
              name="treated_segment"
              list="segmen"
              defaultValue={state.input.treated_segment}
              style={FIELD}
            />
          </Field>
          <Field label="Segmen pembanding" hint="Kelompok yang TIDAK terpapar — wajib">
            <input
              name="control_segment"
              list="segmen"
              defaultValue={state.input.control_segment}
              style={FIELD}
            />
          </Field>
        </div>
        <datalist id="segmen">
          {segments.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>

        <div className="sliders" style={{ marginTop: 16 }}>
          <Field label="Periode sebelum" hint="Tanggal akhir pengukuran pra-perlakuan">
            <input
              type="date"
              name="pre_period_end"
              defaultValue={state.input.pre_period_end}
              style={FIELD}
            />
          </Field>
          <Field label="Periode sesudah" hint="Tanggal akhir pengukuran pasca-perlakuan">
            <input
              type="date"
              name="post_period_end"
              defaultValue={state.input.post_period_end}
              style={FIELD}
            />
          </Field>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button
              type="submit"
              disabled={isPending}
              style={{
                ...FIELD,
                width: "auto",
                padding: "8px 16px",
                cursor: isPending ? "wait" : "pointer",
              }}
            >
              {isPending ? "Menghitung…" : "Ukur dampak"}
            </button>
          </div>
        </div>
      </form>

      {state.error && (
        <div className="insufficient" style={{ marginTop: 18 }}>
          <div className="insufficient-t">Desain belum memadai</div>
          <div className="insufficient-d">{state.error}</div>
        </div>
      )}

      {r && r.insufficient_data && (
        <div className="insufficient" style={{ marginTop: 18 }}>
          <div className="insufficient-t">Data tidak cukup</div>
          <div className="insufficient-d">{r.note}</div>
        </div>
      )}

      {r && !r.insufficient_data && r.effect !== null && (
        <div style={{ marginTop: 20 }}>
          {/* Asumsi tren paralel yang gagal MEMBATALKAN pembacaan angka ini
              sebagai efek — bukan sekadar catatan kaki. Peringatannya
              didahulukan sebelum angkanya. */}
          {r.parallel_trends_ok === false && (
            <div className="insufficient" style={{ marginBottom: 16 }}>
              <div className="insufficient-t">Asumsi tren paralel gagal</div>
              <div className="insufficient-d">
                Kedua kelompok sudah bergerak berbeda sebelum perlakuan. Selisih di
                bawah tidak boleh dibaca sebagai efek komunikasi.
              </div>
            </div>
          )}

          <div className="fc-out">
            <div>
              <span className="kicker">Efek (DiD)</span>
              <b style={{ color: r.parallel_trends_ok === false ? "var(--txt3)" : "var(--survey)" }}>
                {r.effect > 0 ? "+" : ""}
                {r.effect.toFixed(2)}
              </b>
            </div>
            <div>
              <span className="kicker">Interval {Math.round(r.ci_level * 100)}%</span>
              <b>
                {r.ci_low?.toFixed(2)} … {r.ci_high?.toFixed(2)}
              </b>
            </div>
            <div>
              <span className="kicker">Perubahan terpapar</span>
              <b>
                {(r.treated_change ?? 0) > 0 ? "+" : ""}
                {r.treated_change?.toFixed(2)}
              </b>
            </div>
            <div>
              <span className="kicker">Perubahan pembanding</span>
              <b>
                {(r.control_change ?? 0) > 0 ? "+" : ""}
                {r.control_change?.toFixed(2)}
              </b>
            </div>
          </div>

          <div style={{ marginTop: 14, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span className={r.distinguishable_from_zero ? "pill pill-ok" : "pill pill-warn"}>
              {r.distinguishable_from_zero
                ? "dapat dibedakan dari nol"
                : "belum dapat dibedakan dari nol"}
            </span>
            <span
              className={
                !r.parallel_trends_checked
                  ? "pill pill-warn"
                  : r.parallel_trends_ok
                    ? "pill pill-ok"
                    : "pill pill-warn"
              }
            >
              {!r.parallel_trends_checked
                ? "tren paralel tidak diperiksa"
                : r.parallel_trends_ok
                  ? "tren paralel lolos"
                  : "tren paralel gagal"}
            </span>
          </div>

          {r.note && (
            <p className="proj-s" style={{ marginTop: 12, maxWidth: 640 }}>
              {r.note}
            </p>
          )}

          <Provenance
            method={r.method}
            ci={`${r.ci_low?.toFixed(2)} … ${r.ci_high?.toFixed(2)}`}
            confidence={r.distinguishable_from_zero ? "Sedang" : "Rendah"}
            limits={r.limitations.join(" ")}
          />
        </div>
      )}
    </>
  );
}
