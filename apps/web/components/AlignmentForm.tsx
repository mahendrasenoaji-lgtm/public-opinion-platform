"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { saveAlignment } from "@/app/(dashboard)/kinerja/analisis/actions";
import { ALIGNMENT_LABEL } from "@/app/(dashboard)/kinerja/analisis/analisis";

/**
 * Kode keselarasan satu pasangan pernyataan dua lembaga tentang satu isu
 * (indikator C3). Menyimpan pasangan yang sama untuk lembar yang sama menimpa
 * kode lama.
 */
export function AlignmentForm({ projectId, coder }: { projectId: string; coder: 1 | 2 }) {
  const router = useRouter();
  const [f, setF] = useState({ issue: "", subject_a: "", url_a: "", subject_b: "", url_b: "", note: "" });
  const [code, setCode] = useState("selaras");
  const [corrected, setCorrected] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setPending(true);
    const res = await saveAlignment(projectId, {
      issue: f.issue.trim(),
      subject_a: f.subject_a.trim(),
      url_a: f.url_a.trim() || null,
      subject_b: f.subject_b.trim(),
      url_b: f.url_b.trim() || null,
      coder,
      code,
      corrected: code === "bertentangan" && corrected,
      note: f.note.trim(),
    });
    setPending(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setF({ ...f, issue: "", url_a: "", url_b: "", note: "" });
    setCorrected(false);
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} className="kin-form">
      <div className="code-grid">
        <label className="field">
          <span className="kicker">Isu</span>
          <input value={f.issue} onChange={set("issue")} required maxLength={200} disabled={pending} />
        </label>
        <label className="field">
          <span className="kicker">Lembaga A</span>
          <input value={f.subject_a} onChange={set("subject_a")} required maxLength={120} disabled={pending} />
        </label>
        <label className="field">
          <span className="kicker">Tautan pernyataan A</span>
          <input type="url" value={f.url_a} onChange={set("url_a")} placeholder="https://" maxLength={2000} disabled={pending} />
        </label>
        <label className="field">
          <span className="kicker">Lembaga B</span>
          <input value={f.subject_b} onChange={set("subject_b")} required maxLength={120} disabled={pending} />
        </label>
        <label className="field">
          <span className="kicker">Tautan pernyataan B</span>
          <input type="url" value={f.url_b} onChange={set("url_b")} placeholder="https://" maxLength={2000} disabled={pending} />
        </label>
        <label className="field">
          <span className="kicker">Kode (lembar pengode {coder})</span>
          <select value={code} onChange={(e) => setCode(e.target.value)} disabled={pending}>
            {Object.entries(ALIGNMENT_LABEL).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="kicker">Catatan pengode</span>
          <input value={f.note} onChange={set("note")} maxLength={2000} disabled={pending} />
        </label>
      </div>
      {code === "bertentangan" && (
        <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 10, fontSize: 13 }}>
          <input type="checkbox" checked={corrected} onChange={(e) => setCorrected(e.target.checked)} disabled={pending} />
          Pernyataan yang bertentangan sudah diralat
        </label>
      )}
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 12 }}>
        <button className="btn btn-sm" type="submit" disabled={pending}>
          {pending ? "Menyimpan…" : "Simpan pasangan"}
        </button>
        {error && <span className="form-err" role="alert">{error}</span>}
      </div>
    </form>
  );
}
