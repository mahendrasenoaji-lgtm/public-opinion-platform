"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { addFlow, deleteFlow } from "@/app/(dashboard)/kinerja/analisis/actions";
import { FLOW_STAMPS, stampToIso, type FlowStamp } from "@/app/(dashboard)/kinerja/analisis/analisis";

const EMPTY: Record<FlowStamp, string> = {
  requested_at: "", received_at: "", verified_at: "", drafted_at: "", approved_at: "", published_at: "",
};

/**
 * Catat penelusuran arus informasi satu konten. Cap waktu yang tidak ada di
 * log auditor dibiarkan kosong; selangnya lalu tidak dihitung.
 */
export function FlowForm({
  projectId,
  stages,
  defaultSubject,
}: {
  projectId: string;
  stages: { stage: number; name: string }[];
  defaultSubject: string;
}) {
  const router = useRouter();
  const [subject, setSubject] = useState(defaultSubject);
  const [label, setLabel] = useState("");
  const [kind, setKind] = useState<"rutin" | "klarifikasi">("rutin");
  const [stamps, setStamps] = useState(EMPTY);
  const [bottleneck, setBottleneck] = useState("");
  const [note, setNote] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const anyStamp = Object.values(stamps).some((v) => v !== "");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setPending(true);
    const res = await addFlow(projectId, {
      subject: subject.trim(),
      label: label.trim(),
      kind,
      requested_at: stampToIso(stamps.requested_at, "WIB"),
      received_at: stampToIso(stamps.received_at, "WIB"),
      verified_at: stampToIso(stamps.verified_at, "WIB"),
      drafted_at: stampToIso(stamps.drafted_at, "WIB"),
      approved_at: stampToIso(stamps.approved_at, "WIB"),
      published_at: stampToIso(stamps.published_at, "WIB"),
      bottleneck_stage: bottleneck === "" ? null : Number(bottleneck),
      note: note.trim(),
    });
    setPending(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setLabel("");
    setStamps(EMPTY);
    setBottleneck("");
    setNote("");
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} className="kin-form">
      <div className="code-grid">
        <label className="field">
          <span className="kicker">Lembaga</span>
          <input value={subject} onChange={(e) => setSubject(e.target.value)} required maxLength={120} disabled={pending} />
        </label>
        <label className="field">
          <span className="kicker">Konten yang ditelusuri</span>
          <input value={label} onChange={(e) => setLabel(e.target.value)} required maxLength={300} disabled={pending} />
        </label>
        <label className="field">
          <span className="kicker">Jenis</span>
          <select value={kind} onChange={(e) => setKind(e.target.value as "rutin" | "klarifikasi")} disabled={pending}>
            <option value="rutin">Rutin</option>
            <option value="klarifikasi">Klarifikasi</option>
          </select>
        </label>
        {FLOW_STAMPS.map(([key, name]) => (
          <label key={key} className="field">
            <span className="kicker">{name} (WIB)</span>
            <input
              type="datetime-local"
              value={stamps[key]}
              onChange={(e) => setStamps({ ...stamps, [key]: e.target.value })}
              disabled={pending}
            />
          </label>
        ))}
        <label className="field">
          <span className="kicker">Tahap hambatan (bila ada)</span>
          <select value={bottleneck} onChange={(e) => setBottleneck(e.target.value)} disabled={pending}>
            <option value="">(tidak ditandai)</option>
            {stages.map((s) => (
              <option key={s.stage} value={s.stage}>
                {s.stage} · {s.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="kicker">Catatan dan sumber bukti</span>
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} disabled={pending} />
        </label>
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 12 }}>
        <button className="btn btn-sm" type="submit" disabled={pending || !anyStamp || !subject.trim() || !label.trim()}>
          {pending ? "Menyimpan…" : "Catat penelusuran"}
        </button>
        {error && <span className="form-err" role="alert">{error}</span>}
      </div>
    </form>
  );
}

/** Tombol hapus satu baris (arus atau pasangan), dengan konfirmasi dua langkah. */
export function DeleteRowButton({
  projectId,
  id,
  kind,
}: {
  projectId: string;
  id: string;
  kind: "flow" | "alignment";
}) {
  const router = useRouter();
  const [armed, setArmed] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function remove() {
    setPending(true);
    const { deleteAlignment } = await import("@/app/(dashboard)/kinerja/analisis/actions");
    const res = kind === "flow" ? await deleteFlow(projectId, id) : await deleteAlignment(projectId, id);
    setPending(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    router.refresh();
  }

  if (error) return <span className="form-err" role="alert">{error}</span>;
  return armed ? (
    <span style={{ whiteSpace: "nowrap" }}>
      <button type="button" className="btn btn-ghost btn-sm" onClick={remove} disabled={pending}>
        {pending ? "Menghapus…" : "Ya, hapus"}
      </button>{" "}
      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setArmed(false)} disabled={pending}>
        Batal
      </button>
    </span>
  ) : (
    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setArmed(true)}>
      Hapus
    </button>
  );
}
