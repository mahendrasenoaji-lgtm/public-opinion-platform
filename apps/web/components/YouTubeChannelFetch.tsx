"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { fetchYouTubeChannel, type YouTubeFetchResult } from "@/app/(dashboard)/kinerja/actions";

/**
 * Ambil video kanal YouTube RESMI lembaga lewat YouTube Data API. Hanya
 * handle, ID kanal, atau URL kanal yang diterima: nama bebas tidak dicari,
 * supaya yang terambil pasti akun resmi yang dimaksud.
 */
export function YouTubeChannelFetch({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [channel, setChannel] = useState("");
  const [sinceDays, setSinceDays] = useState(90);
  const [maxVideos, setMaxVideos] = useState(50);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<YouTubeFetchResult | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setDone(null);
    setPending(true);
    const res = await fetchYouTubeChannel(projectId, channel.trim(), sinceDays, maxVideos);
    setPending(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setDone(res.result);
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit}>
      <p className="field-hint" style={{ marginBottom: 10 }}>
        Tulis handle (<span className="mono">@namakanal</span>), ID kanal (
        <span className="mono">UC…</span>), atau URL kanal resmi lembaga. Yang diambil: judul,
        tanggal, tayangan, suka, dan jumlah komentar tiap video, plus jumlah pelanggan saat ini.
        Mengambil ulang memperbarui angkanya. Pastikan kanal itu memang akun resmi lembaga.
      </p>
      <div className="period-bar" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
        <div className="field" style={{ flex: "1 1 220px" }}>
          <label htmlFor="yt-channel">Kanal YouTube</label>
          <input
            id="yt-channel"
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
            placeholder="@namakanal"
            required
            minLength={2}
            maxLength={200}
            disabled={pending}
          />
        </div>
        <div className="field" style={{ width: 130 }}>
          <label htmlFor="yt-days">Rentang (hari)</label>
          <input
            id="yt-days"
            type="number"
            min={1}
            max={365}
            value={sinceDays}
            onChange={(e) => setSinceDays(Number(e.target.value))}
            disabled={pending}
          />
        </div>
        <div className="field" style={{ width: 130 }}>
          <label htmlFor="yt-max">Maks. video</label>
          <input
            id="yt-max"
            type="number"
            min={1}
            max={200}
            value={maxVideos}
            onChange={(e) => setMaxVideos(Number(e.target.value))}
            disabled={pending}
          />
        </div>
        <button className="btn" type="submit" disabled={pending || channel.trim() === ""}>
          {pending ? "Mengambil…" : "Ambil dari YouTube"}
        </button>
      </div>
      {error && (
        <div className="form-err" role="alert" style={{ marginTop: 10 }}>
          {error}
        </div>
      )}
      {done && (
        <div className="read" style={{ marginTop: 14 }} role="status">
          <div className="read-t">
            {done.channel_title} ({done.account}): {done.n_videos} video dalam {done.since_days} hari
            terakhir — {done.result.stored} baru, {done.result.updated} diperbarui.
          </div>
          <div className="read-d">
            Pelanggan saat ini:{" "}
            {done.subscribers === null ? "disembunyikan kanal" : done.subscribers.toLocaleString("id-ID")}.
            Kuota API terpakai: {done.quota_units} unit.
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
