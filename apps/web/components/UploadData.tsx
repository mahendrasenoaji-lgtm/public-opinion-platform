"use client";

import { useState } from "react";
import { ingestBatch } from "@/app/(dashboard)/sinyal/actions";
import { parseUpload, type Parsed } from "@/lib/uploadParse";

/** Item per panggilan. Backend menerima 1.000, tapi server action Next dibatasi 1 MB. */
const CHUNK = 300;

const ZERO = { received: 0, stored: 0, already_present: 0, duplicates_dropped: 0, language_rejected: 0, sentiment_abstained: 0, empty_dropped: 0 };

/**
 * Unggah data yang sudah dimiliki peneliti ke proyek aktif, lewat
 * `POST /signals/ingest`. Dipotong per CHUNK supaya satu permintaan tidak
 * melewati batas ukuran maupun waktu. Mengunggah ulang berkas yang sama aman:
 * item yang sudah ada tidak digandakan (`already_present`).
 */
export function UploadData({ projectId }: { projectId: string }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState("");
  const [sum, setSum] = useState<typeof ZERO | null>(null);
  const [caveats, setCaveats] = useState<string[]>([]);

  async function onFile(file: File) {
    setError("");
    setSum(null);
    setCaveats([]);
    let parsed: Parsed;
    try {
      parsed = parseUpload(await file.text());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Berkas tidak bisa dibaca.");
      return;
    }
    setPending(true);
    const total = { ...ZERO };
    const notes = new Set<string>();
    for (let start = 0; start < parsed.items.length; start += CHUNK) {
      setProgress(`Mengunggah ${Math.min(start + CHUNK, parsed.items.length)} / ${parsed.items.length}…`);
      const res = await ingestBatch(
        projectId,
        parsed.connector,
        parsed.source,
        parsed.items.slice(start, start + CHUNK),
      );
      if (!res.ok) {
        setError(`Berhenti di item ${start + 1}: ${res.error}`);
        break;
      }
      for (const k of Object.keys(total) as (keyof typeof ZERO)[]) total[k] += res.result[k];
      res.result.caveats.forEach((c) => notes.add(c));
      setSum({ ...total });
    }
    setCaveats([...notes]);
    setProgress("");
    setPending(false);
  }

  return (
    <div style={{ marginTop: 22 }}>
      <h3 className="kicker">Unggah data (JSON)</h3>
      <p className="field-hint" style={{ marginBottom: 10 }}>
        Untuk data yang sudah Anda miliki atau rentang waktu lampau yang tidak terjangkau
        &quot;Tarik semua&quot;. Format: <span className="mono">{"{ connector, source, items: [...] }"}</span>,
        tiap item berisi <span className="mono">external_id</span>, <span className="mono">text</span>,{" "}
        <span className="mono">published_at</span>, dan sebaiknya <span className="mono">url</span>. Data
        melewati dedup, deteksi bahasa, dan sentimen yang sama. Pastikan Anda berhak memakai datanya.
      </p>
      <input
        type="file"
        accept="application/json,.json"
        disabled={pending}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void onFile(f);
          e.target.value = "";
        }}
      />
      {progress && <div className="field-hint" style={{ marginTop: 8 }}>{progress}</div>}
      {error && (
        <div className="form-err" role="alert" style={{ marginTop: 10 }}>
          {error}
        </div>
      )}
      {sum && (
        <div className="read" style={{ marginTop: 14 }}>
          <div className="read-t">
            {sum.received} item diterima: {sum.stored} tersimpan baru, {sum.already_present} sudah ada,{" "}
            {sum.duplicates_dropped} duplikat dibuang, {sum.empty_dropped} kosong,{" "}
            {sum.language_rejected} ditolak bahasa, {sum.sentiment_abstained} sentimen abstain.
          </div>
          {caveats.map((c) => (
            <div key={c} className="read-d">{c}</div>
          ))}
        </div>
      )}
    </div>
  );
}
