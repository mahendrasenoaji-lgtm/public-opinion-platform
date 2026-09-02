"use client";

import { useActionState } from "react";
import { Provenance } from "@/components/Provenance";
import { analyzeSyntheticControl, type SyntheticControlState } from "./actions";

// Sama seperti ImpactForm.tsx — keadaan awal didefinisikan di sini, bukan di
// actions.ts, karena modul "use server" cuma boleh mengekspor fungsi async.
const AWAL: SyntheticControlState = {
  result: null,
  error: null,
  input: {
    metric: "approval",
    treated_segment: "",
    donor_segments: "",
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

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label style={{ display: "block" }}>
      <span className="kicker">{label}</span>
      <div style={{ marginTop: 5 }}>{children}</div>
      {hint && <div className="proj-s" style={{ marginTop: 4 }}>{hint}</div>}
    </label>
  );
}

export function SyntheticControlForm({
  projectId,
  segments,
}: {
  projectId: string;
  segments: string[];
}) {
  const [state, action, isPending] = useActionState(analyzeSyntheticControl, AWAL);
  const r = state.result;
  const bobot = r ? Object.entries(r.weights).sort((a, b) => b[1] - a[1]) : [];

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
              list="segmen-sc"
              defaultValue={state.input.treated_segment}
              style={FIELD}
            />
          </Field>
        </div>
        <datalist id="segmen-sc">
          {segments.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>

        <div style={{ marginTop: 16 }}>
          <Field
            label="Segmen donor"
            hint="Minimal 5 segmen yang TIDAK terpapar — satu per baris, atau dipisah koma"
          >
            <textarea
              name="donor_segments"
              defaultValue={state.input.donor_segments}
              rows={4}
              style={{ ...FIELD, resize: "vertical", fontFamily: "inherit" }}
              placeholder={segments.slice(0, 5).join("\n")}
            />
          </Field>
        </div>

        <div className="sliders" style={{ marginTop: 16 }}>
          <Field label="Akhir periode pra-perlakuan" hint="Snapshot &lt;= tanggal ini jadi deret pra">
            <input
              type="date"
              name="pre_period_end"
              defaultValue={state.input.pre_period_end}
              style={FIELD}
            />
          </Field>
          <Field label="Titik pasca-perlakuan" hint="Tanggal yang dibandingkan">
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
              {isPending ? "Menghitung…" : "Ukur dengan synthetic control"}
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
          {/* Kecocokan pra-perlakuan yang buruk MEMBATALKAN pembacaan angka
              ini sebagai efek yang bisa dipercaya — bukan sekadar catatan
              kaki, sama seperti tren paralel gagal di ImpactForm. */}
          {r.fit_quality_ok === false && (
            <div className="insufficient" style={{ marginBottom: 16 }}>
              <div className="insufficient-t">Kecocokan pra-perlakuan buruk</div>
              <div className="insufficient-d">
                Unit sintetis tidak meniru segmen terpapar dengan cukup baik sebelum
                perlakuan. Selisih di bawah tidak boleh dibaca sebagai efek komunikasi
                yang bisa dipercaya.
              </div>
            </div>
          )}

          <div className="fc-out">
            <div>
              <span className="kicker">Efek</span>
              <b style={{ color: r.fit_quality_ok === false ? "var(--txt3)" : "var(--survey)" }}>
                {r.effect > 0 ? "+" : ""}
                {r.effect.toFixed(2)}
              </b>
            </div>
            <div>
              <span className="kicker">Terpapar (pasca)</span>
              <b>{r.treated_post?.toFixed(2)}</b>
            </div>
            <div>
              <span className="kicker">Sintetis (pasca)</span>
              <b>{r.synthetic_post?.toFixed(2)}</b>
            </div>
            <div>
              <span className="kicker">RMSPE pra-perlakuan</span>
              <b>{r.pre_fit_rmspe?.toFixed(3)}</b>
            </div>
          </div>

          <div style={{ marginTop: 14, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span className={r.fit_quality_ok ? "pill pill-ok" : "pill pill-warn"}>
              {r.fit_quality_ok ? "kecocokan pra-perlakuan baik" : "kecocokan pra-perlakuan buruk"}
            </span>
            <span className="pill">{r.donors_used} donor · {r.n_pre_periods} periode pra</span>
            {r.rank_p_value !== null && (
              <span className="pill">
                rank p (placebo) = {r.rank_p_value.toFixed(3)}
              </span>
            )}
          </div>

          {bobot.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <span className="kicker">Bobot unit sintetis</span>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                {bobot.map(([nama, w]) => (
                  <span key={nama} className="pill mono">
                    {nama}: {w.toFixed(3)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {r.note && (
            <p className="proj-s" style={{ marginTop: 12, maxWidth: 640 }}>
              {r.note}
            </p>
          )}

          <Provenance
            method={r.method}
            confidence={r.fit_quality_ok ? "Sedang" : "Rendah"}
            limits={r.limitations.join(" ")}
          />
        </div>
      )}
    </>
  );
}
