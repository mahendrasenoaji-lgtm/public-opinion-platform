"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { uploadOfficialPosts } from "@/app/(dashboard)/kinerja/actions";
import { parseOfficialPosts, type OfficialPostIn } from "@/lib/officialPosts";

/** Baris per panggilan. Backend menerima 1.000; server action Next dibatasi 1 MB. */
const CHUNK = 300;

/**
 * Unggah data unggahan akun resmi lembaga (JSON atau CSV). Platform ini tidak
 * mengambil data Instagram, TikTok, atau X sendiri; berkasnya disiapkan
 * peneliti dari tampilan publik atau dari ekspor pemilik akun.
 */
export function OfficialPostsUpload({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState("");
  const [sum, setSum] = useState<{ received: number; stored: number; updated: number; duplicates_dropped: number } | null>(null);

  async function onFile(file: File) {
    setError("");
    setSum(null);
    let items: OfficialPostIn[];
    try {
      items = parseOfficialPosts(await file.text());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Berkas tidak bisa dibaca.");
      return;
    }
    setPending(true);
    const total = { received: 0, stored: 0, updated: 0, duplicates_dropped: 0 };
    for (let start = 0; start < items.length; start += CHUNK) {
      setProgress(`Mengunggah ${Math.min(start + CHUNK, items.length)} / ${items.length}…`);
      const res = await uploadOfficialPosts(projectId, items.slice(start, start + CHUNK));
      if (!res.ok) {
        setError(`Berhenti di baris ${start + 1}: ${res.error}`);
        break;
      }
      total.received += res.result.received;
      total.stored += res.result.stored;
      total.updated += res.result.updated;
      total.duplicates_dropped += res.result.duplicates_dropped;
      setSum({ ...total });
    }
    setProgress("");
    setPending(false);
    router.refresh();
  }

  return (
    <div>
      <p className="field-hint" style={{ marginBottom: 10 }}>
        Berkas JSON (larik baris) atau CSV berkepala. Kolom wajib:{" "}
        <span className="mono">platform</span> (instagram, tiktok, x),{" "}
        <span className="mono">account</span>, <span className="mono">external_id</span>,{" "}
        <span className="mono">posted_at</span>. Kolom pilihan: <span className="mono">kind</span>,{" "}
        <span className="mono">url</span>, <span className="mono">caption</span>,{" "}
        <span className="mono">likes</span>, <span className="mono">comments</span>,{" "}
        <span className="mono">shares</span>, <span className="mono">views</span>,{" "}
        <span className="mono">followers</span>, <span className="mono">captured_at</span>, dan dari
        insight pemilik akun: <span className="mono">saves</span>, <span className="mono">reach</span>,{" "}
        <span className="mono">impressions</span>. Biarkan kosong bila angkanya tidak tampil; jangan
        diisi nol. Pastikan Anda berhak memakai datanya.
      </p>
      <input
        type="file"
        aria-label="Berkas unggahan akun resmi"
        accept="application/json,.json,text/csv,.csv"
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
        <div className="read" style={{ marginTop: 14 }} role="status">
          <div className="read-t">
            {sum.received} baris diterima: {sum.stored} tersimpan baru, {sum.updated} diperbarui,{" "}
            {sum.duplicates_dropped} duplikat dalam berkas dibuang.
          </div>
        </div>
      )}
    </div>
  );
}
