"use client";

import { useState } from "react";
import { runRescore, type RescoreOut } from "@/app/(dashboard)/sinyal/actions";

/** Batas putaran per klik: 20 x 500 baris. Proyek yang lebih besar tinggal diklik lagi. */
const MAX_ROUNDS = 20;

/**
 * Pemicu penilaian ulang sentimen konten lama.
 *
 * Backend mengerjakannya bertahap (500 baris per panggilan) dan melaporkan
 * sisanya; tombol ini mengulang sampai sisanya nol. Skor lama tidak hilang:
 * skor percakapan yang diganti diarsipkan, dan skor utama liputan tidak
 * disentuh sama sekali — lihat POST /projects/{id}/signals/rescore.
 */
export function RescoreButton({ projectId }: { projectId: string }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [total, setTotal] = useState<Omit<RescoreOut, "models"> | null>(null);

  async function submit() {
    setPending(true);
    setError("");
    const sum = { examined: 0, primary_changed: 0, alt_written: 0, remaining: 0 };
    for (let round = 0; round < MAX_ROUNDS; round++) {
      const res = await runRescore(projectId);
      if (!res.ok) {
        setError(res.error);
        break;
      }
      sum.examined += res.result.examined;
      sum.primary_changed += res.result.primary_changed;
      sum.alt_written += res.result.alt_written;
      sum.remaining = res.result.remaining;
      setTotal({ ...sum });
      if (res.result.remaining === 0 || res.result.examined === 0) break;
    }
    setPending(false);
  }

  return (
    <div style={{ marginTop: 22 }}>
      <h3 className="kicker">Penilaian ulang sentimen</h3>
      <p className="field-hint" style={{ marginBottom: 10 }}>
        Menilai konten lama dengan penilai terkini. Komentar yang dulu dinilai leksikon baku dinilai
        ulang dengan ragam informal dan skor lamanya diarsipkan. Liputan tidak diubah skor
        utamanya; ia hanya mendapat skor ragam berita sebagai angka pendamping. Aman dijalankan
        berulang.
      </p>
      <button type="button" className="btn btn-ghost" onClick={submit} disabled={pending}>
        {pending ? "Menilai ulang…" : "Nilai ulang konten lama"}
      </button>

      {error && (
        <div className="form-err" role="alert" style={{ marginTop: 10 }}>
          {error}
        </div>
      )}

      {total && (
        <div className="read" style={{ marginTop: 14 }}>
          <div className="read-t">
            {total.examined === 0
              ? "Tidak ada yang perlu dinilai ulang."
              : `${total.examined} konten diperiksa: ${total.primary_changed} komentar berubah skornya, ${total.alt_written} liputan mendapat skor ragam berita.`}
            {total.remaining > 0 && ` Masih ${total.remaining} menunggu — klik lagi.`}
          </div>
        </div>
      )}
    </div>
  );
}
