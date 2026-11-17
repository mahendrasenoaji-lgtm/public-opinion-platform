"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { saveCoding } from "@/app/(dashboard)/kinerja/analisis/actions";
import type { CodingRow, Variable } from "@/app/(dashboard)/kinerja/analisis/analisis";

/**
 * Lembar coding satu unggahan (Lampiran A kerangka). Semua kode diisi
 * manusia; variabel yang dibiarkan kosong tetap kosong. Nilai lembar pengode
 * lain tidak pernah dikirim ke sini, supaya dua pengode tidak saling melihat.
 */
export function CodingForm({
  projectId,
  coder,
  row,
  variables,
  canEdit,
}: {
  projectId: string;
  coder: 1 | 2;
  row: CodingRow;
  variables: Variable[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [codes, setCodes] = useState<Record<string, number | null>>(row.codes);
  const [note, setNote] = useState(row.note);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const filled = Object.values(codes).some((v) => v !== null && v !== undefined);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaved(false);
    setPending(true);
    const res = await saveCoding(projectId, row.post_id, { coder, coder_name: "", codes, note });
    setPending(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setSaved(true);
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} className="code-card">
      <div className="code-head">
        <div>
          <span className="strong">{row.account}</span>{" "}
          <span className="proj-s">
            · {row.platform} · {new Date(row.posted_at).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Jakarta" })}
            {row.kind ? ` · ${row.kind}` : ""}
          </span>
        </div>
        <div className="proj-s">
          {row.coded ? "Sudah dikode lembar ini" : "Belum dikode lembar ini"}
          {row.coded_by_other ? " · lembar lain sudah mengisi" : ""}
        </div>
      </div>
      <p className="code-caption">
        {row.caption || <span className="dim">Tanpa takarir.</span>}{" "}
        {row.url && /^https?:\/\//i.test(row.url) && (
          <a href={row.url} target="_blank" rel="noopener noreferrer">
            Buka unggahan
          </a>
        )}
      </p>
      <div className="code-grid">
        {variables.map((v) => (
          <label key={v.code} className="field">
            <span className="kicker">
              {v.code} · {v.name}
            </span>
            <select
              value={codes[v.code] ?? ""}
              disabled={!canEdit || pending}
              onChange={(e) =>
                setCodes({ ...codes, [v.code]: e.target.value === "" ? null : Number(e.target.value) })
              }
            >
              <option value="">(belum diisi)</option>
              {v.values.map(([value, label]) => (
                <option key={value} value={value}>
                  {value} · {label}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <label className="field" style={{ marginTop: 10 }}>
        <span className="kicker">A20 · Catatan pengode</span>
        <input value={note} maxLength={2000} disabled={!canEdit || pending} onChange={(e) => setNote(e.target.value)} />
      </label>
      {canEdit && (
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 10 }}>
          <button className="btn btn-sm" type="submit" disabled={pending || !filled}>
            {pending ? "Menyimpan…" : "Simpan kode"}
          </button>
          {saved && <span className="proj-s" role="status">Tersimpan.</span>}
          {error && <span className="form-err" role="alert">{error}</span>}
        </div>
      )}
    </form>
  );
}
