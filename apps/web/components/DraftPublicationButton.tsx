"use client";

import { useState, useTransition } from "react";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { createDraft } from "@/app/(dashboard)/publikasi/actions";

/**
 * Tombol "Buat draf publikasi" di Laporan Percakapan. Draf menyimpan snapshot
 * beku angka periode ini; karena itu butuh periode tetap, bukan jendela
 * relatif 30 hari yang bergeser tiap hari.
 */
export function DraftPublicationButton({
  projectId,
  start,
  end,
  zone,
}: {
  projectId: string;
  start: string | null;
  end: string | null;
  zone: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  if (!start || !end) {
    return (
      <span className="field-hint no-print">
        Pilih periode tetap (dari dan sampai) untuk membuat draf publikasi.
      </span>
    );
  }

  function submit() {
    setError("");
    if (title.trim().length < 3) return setError("Judul minimal 3 huruf.");
    startTransition(async () => {
      const res = await createDraft(projectId, { title: title.trim(), start: start!, end: end!, tz: zone });
      if (!res.ok) {
        setError(res.error);
        return;
      }
      router.push(`/publikasi?id=${res.result.id}` as Route);
    });
  }

  if (!open) {
    return (
      <button type="button" className="btn btn-ghost btn-sm no-print" onClick={() => setOpen(true)}>
        Buat draf publikasi
      </button>
    );
  }

  return (
    <div className="no-print" style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "flex-end" }}>
      <div className="field" style={{ margin: 0, minWidth: 280 }}>
        <label htmlFor="draf-judul">Judul artikel</label>
        <input
          id="draf-judul"
          value={title}
          maxLength={200}
          disabled={pending}
          autoFocus
          onChange={(e) => setTitle(e.target.value)}
          // Tombol ini hidup di dalam form periode; Enter tidak boleh mengirim form itu.
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="mis. Sentimen publik terhadap …"
        />
      </div>
      <button type="button" className="btn btn-sm" disabled={pending} onClick={submit}>
        {pending ? "Membekukan angka…" : "Buat draf"}
      </button>
      <button type="button" className="btn btn-ghost btn-sm" disabled={pending} onClick={() => setOpen(false)}>
        Batal
      </button>
      {error && (
        <span className="form-err" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
