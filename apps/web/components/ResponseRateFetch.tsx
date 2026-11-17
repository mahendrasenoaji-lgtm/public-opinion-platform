"use client";

import { useState } from "react";
import { fetchResponseRate } from "@/app/(dashboard)/kinerja/analisis/actions";
import type { ResponseRate } from "@/app/(dashboard)/kinerja/analisis/analisis";

/**
 * Hitung tingkat jawab (O8) kanal YouTube resmi. Komentar dibaca lewat API
 * resmi, dihitung, lalu dibuang; yang tampil hanya jumlah. Hasilnya saran:
 * skor O8 tetap diisi penilai di formulir indikator.
 */
export function ResponseRateFetch({ projectId, accounts }: { projectId: string; accounts: string[] }) {
  const [account, setAccount] = useState(accounts[0] ?? "");
  const [maxVideos, setMaxVideos] = useState(20);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<ResponseRate | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setDone(null);
    setPending(true);
    const res = await fetchResponseRate(projectId, account, maxVideos);
    setPending(false);
    if (res.ok) setDone(res.result);
    else setError(res.error);
  }

  if (accounts.length === 0) {
    return <p className="field-hint">Belum ada kanal YouTube resmi di proyek ini. Ambil dulu lewat halaman Kinerja.</p>;
  }

  return (
    <form onSubmit={onSubmit}>
      <div className="period-bar" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
        <label className="field" style={{ flex: "1 1 220px" }}>
          <span className="kicker">Kanal YouTube resmi</span>
          <select value={account} onChange={(e) => setAccount(e.target.value)} disabled={pending}>
            {accounts.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label className="field" style={{ width: 150 }}>
          <span className="kicker">Video terbaru</span>
          <input type="number" min={1} max={50} value={maxVideos} onChange={(e) => setMaxVideos(Number(e.target.value))} disabled={pending} />
        </label>
        <button className="btn btn-sm" type="submit" disabled={pending}>
          {pending ? "Menghitung…" : "Hitung tingkat jawab"}
        </button>
      </div>
      <p className="field-hint" style={{ marginTop: 8 }}>
        Memakai sekitar 1 unit kuota YouTube API per video. Teks komentar tidak disimpan.
      </p>
      {error && <div className="form-err" role="alert" style={{ marginTop: 10 }}>{error}</div>}
      {done && (
        <div className="read" style={{ marginTop: 14 }} role="status">
          <div className="read-t">
            {done.rate_pct === null
              ? `Data tidak cukup: ${done.n_questions} komentar berisi pertanyaan, butuh ${done.min_questions}.`
              : `${String(done.rate_pct).replace(".", ",")}% pertanyaan dibalas kanal (${done.n_answered} dari ${done.n_questions}). Saran skor O8: ${done.suggested_score}.`}
          </div>
          <div className="read-d">
            {done.n_comments.toLocaleString("id-ID")} komentar publik dari {done.n_videos} video
            {done.n_videos_skipped > 0 ? ` (${done.n_videos_skipped} video dilewati)` : ""}. Kuota terpakai: {done.quota_units} unit.
          </div>
          <ul className="read-d" style={{ marginTop: 6, paddingLeft: 18 }}>
            {done.limitations.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      )}
    </form>
  );
}
