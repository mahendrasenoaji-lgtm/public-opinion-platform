"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { SOURCE } from "@/lib/tokens";
import {
  controlThemePull,
  createThemePull,
  listThemePulls,
  refreshSignals,
  removeSource,
  type ThemePull as Job,
} from "@/app/(dashboard)/sinyal/actions";

const ACTIVE = new Set<Job["status"]>(["searching", "details", "collecting", "waiting_quota"]);
const POLL_MS = 5000;

const STATUS_LABEL: Record<Job["status"], string> = {
  searching: "Mencari video",
  details: "Memeriksa video",
  collecting: "Menarik komentar",
  waiting_quota: "Menunggu kuota YouTube",
  done: "Selesai",
  failed: "Gagal",
  stopped: "Dihentikan",
};

const nf = new Intl.NumberFormat("id-ID");

/** Tanggal hari ini di WIB, format yyyy-mm-dd, tanpa bergantung zona peramban. */
function wibDate(offsetDays = 0): string {
  const d = new Date(Date.now() + 7 * 3600_000 + offsetDays * 86400_000);
  return d.toISOString().slice(0, 10);
}

function wibTime(iso: string | null): string {
  if (!iso) return "–";
  return new Date(iso).toLocaleString("id-ID", {
    timeZone: "Asia/Jakarta",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }) + " WIB";
}

export function ThemePull({
  projectId,
  initial,
  canManage,
}: {
  projectId: string;
  initial: Job[] | null;
  canManage: boolean;
}) {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>(initial ?? []);
  const [loadError, setLoadError] = useState(initial === null ? "Daftar penarikan belum bisa dimuat." : "");
  const wasActive = useRef<Set<string>>(new Set((initial ?? []).filter((j) => ACTIVE.has(j.status)).map((j) => j.id)));

  const reload = useCallback(async () => {
    const res = await listThemePulls(projectId);
    if (!res.ok) {
      setLoadError(res.error);
      return;
    }
    setLoadError("");
    setJobs(res.result);
    const nowActive = new Set(res.result.filter((j) => ACTIVE.has(j.status)).map((j) => j.id));
    const finished = [...wasActive.current].some((id) => !nowActive.has(id));
    wasActive.current = nowActive;
    if (finished) {
      await refreshSignals();
      router.refresh();
    }
  }, [projectId, router]);

  const anyActive = jobs.some((j) => ACTIVE.has(j.status));
  useEffect(() => {
    // Sekali saat dibuka: memicu backend melanjutkan pekerjaan yang terhenti.
    void reload();
  }, [reload]);
  useEffect(() => {
    if (!anyActive) return;
    const t = setInterval(() => void reload(), POLL_MS);
    return () => clearInterval(t);
  }, [anyActive, reload]);

  return (
    <div>
      <p className="field-hint" style={{ marginBottom: 12 }}>
        Isi kata kunci dan periode, tekan <b>Tarik</b>. Server mencari video YouTube yang{" "}
        <b>terbit</b> dalam periode itu, membuang yang judul/deskripsinya tidak memuat kata kunci,
        lalu menarik komentar (dan balasan) dari video paling ramai lebih dulu. Halaman ini boleh
        ditutup; kemajuan tersimpan di server. Kalau kuota harian YouTube habis, penarikan menunggu
        dan lanjut sendiri sesudah kuota pulih (sekitar 15.05 WIB).
      </p>

      {canManage && <ThemeForm projectId={projectId} onCreated={reload} />}

      {loadError && <div className="form-err" role="alert" style={{ marginTop: 10 }}>{loadError}</div>}

      {jobs.length > 0 && (
        <div style={{ display: "grid", gap: 12, marginTop: 18 }}>
          {jobs.map((j) => (
            <JobCard key={j.id} projectId={projectId} job={j} canManage={canManage} onChange={reload} />
          ))}
        </div>
      )}
    </div>
  );
}

function ThemeForm({ projectId, onCreated }: { projectId: string; onCreated: () => Promise<void> }) {
  const [queries, setQueries] = useState("");
  const [start, setStart] = useState(wibDate(-7));
  const [end, setEnd] = useState(wibDate(0));
  const [maxVideos, setMaxVideos] = useState(50);
  const [replies, setReplies] = useState(true);
  const [untilNow, setUntilNow] = useState(false);
  const [filter, setFilter] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setPending(true);
    setError("");
    const res = await createThemePull(projectId, {
      queries,
      start,
      end,
      max_videos: maxVideos,
      include_replies: replies,
      comments_until_now: untilNow,
      keyword_filter: filter,
    });
    setPending(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setQueries("");
    await onCreated();
  }

  const check = { display: "flex", gap: 8, alignItems: "center", fontSize: 13, marginBottom: 6 } as const;

  return (
    <div>
      <div className="field">
        <label htmlFor="tema-kunci">Kata kunci (pisahkan dengan koma, maks. 5)</label>
        <textarea
          id="tema-kunci"
          rows={2}
          value={queries}
          onChange={(e) => setQueries(e.target.value)}
          placeholder="gibran mundur, pengunduran diri gibran"
          disabled={pending}
        />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
        <div className="field">
          <label htmlFor="tema-dari">Dari (WIB)</label>
          <input id="tema-dari" type="date" value={start} max={wibDate(0)} onChange={(e) => setStart(e.target.value)} disabled={pending} />
        </div>
        <div className="field">
          <label htmlFor="tema-sampai">Sampai (WIB)</label>
          <input id="tema-sampai" type="date" value={end} max={wibDate(0)} onChange={(e) => setEnd(e.target.value)} disabled={pending} />
        </div>
        <div className="field">
          <label htmlFor="tema-video">Video paling banyak</label>
          <input
            id="tema-video"
            type="number"
            min={1}
            max={300}
            value={maxVideos}
            onChange={(e) => setMaxVideos(Number(e.target.value) || 1)}
            disabled={pending}
          />
        </div>
      </div>
      <label style={check}>
        <input type="checkbox" checked={replies} onChange={(e) => setReplies(e.target.checked)} disabled={pending} />
        Ikutkan balasan komentar
      </label>
      <label style={check}>
        <input type="checkbox" checked={filter} onChange={(e) => setFilter(e.target.checked)} disabled={pending} />
        Hanya video yang judul/deskripsinya memuat kata kunci
      </label>
      <label style={check}>
        <input type="checkbox" checked={untilNow} onChange={(e) => setUntilNow(e.target.checked)} disabled={pending} />
        Simpan juga komentar yang ditulis sesudah periode (sampai hari ini)
      </label>

      {error && <div className="form-err" role="alert" style={{ marginTop: 8 }}>{error}</div>}

      <button
        type="button"
        className="btn"
        style={{ marginTop: 10 }}
        onClick={submit}
        disabled={pending || !queries.trim() || !start || !end}
      >
        {pending ? "Memulai…" : "Tarik"}
      </button>
      <p className="field-hint" style={{ marginTop: 8 }}>
        Kuota YouTube 10.000 unit/hari: tiap kata kunci memakai 100–400 unit untuk pencarian, lalu
        ±1 unit per 100 komentar. Tema sedang selesai dalam satu hari; tema besar bisa beberapa hari.
      </p>
    </div>
  );
}

function JobCard({
  projectId,
  job,
  canManage,
  onChange,
}: {
  projectId: string;
  job: Job;
  canManage: boolean;
  onChange: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const active = ACTIVE.has(job.status);
  const processed = job.videos_done + job.videos_skipped;
  const pct = job.videos_total > 0 ? Math.round((processed / job.videos_total) * 100) : 0;

  async function act(kind: "stop" | "resume" | "delete") {
    setBusy(true);
    setError("");
    const res =
      kind === "delete" ? await removeSource(projectId, job.id) : await controlThemePull(projectId, job.id, kind);
    setBusy(false);
    if (!res.ok) setError(res.error);
    await onChange();
  }

  const pillClass =
    job.status === "done" ? "pill pill-ok" : job.status === "failed" || job.status === "waiting_quota" ? "pill pill-warn" : "pill";

  return (
    <div className="read">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div className="read-t" style={{ marginBottom: 2 }}>
          {job.label}{" "}
          <span className="pill" style={{ color: SOURCE.SOCIAL.color }}>
            {SOURCE.SOCIAL.label}
          </span>
        </div>
        <span className={pillClass}>{STATUS_LABEL[job.status]}</span>
      </div>
      <div className="read-d">
        Periode {job.start} s.d. {job.end} WIB · maks. {job.max_videos} video
        {job.include_replies ? " · dengan balasan" : ""}
        {job.comments_until_now ? " · komentar sampai hari ini" : ""}
      </div>

      {job.videos_total > 0 && (
        <div style={{ marginTop: 10 }}>
          <div
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            style={{ height: 6, background: "var(--line)", borderRadius: 999, overflow: "hidden" }}
          >
            <div style={{ width: `${pct}%`, height: "100%", background: "var(--txt2)" }} />
          </div>
        </div>
      )}

      <div className="read-d" style={{ marginTop: 8 }}>
        {job.status === "searching" || job.status === "details"
          ? "Menyusun daftar video…"
          : `${processed}/${job.videos_total} video · ${nf.format(job.stored)} komentar baru tersimpan`}
        {job.received > job.stored && ` (${nf.format(job.received - job.stored)} sudah ada sebelumnya)`}
        {` · ${nf.format(job.units)} unit kuota`}
        {active && job.units_remaining_est > 0 && `, sisa ±${nf.format(job.units_remaining_est)}`}
      </div>
      {job.current_video && job.status === "collecting" && (
        <div className="read-d" style={{ marginTop: 4 }}>Sedang: {job.current_video}</div>
      )}
      {job.status === "waiting_quota" && (
        <div className="read-d" style={{ marginTop: 4 }}>
          Lanjut otomatis sekitar {wibTime(job.resume_at)}. Bila server sempat tidur, penarikan
          dilanjutkan saat halaman ini dibuka.
        </div>
      )}
      {job.error && <div className="form-err" style={{ marginTop: 6 }}>{job.error}</div>}
      {job.notes.length > 0 && (
        <div className="read-d" style={{ marginTop: 4 }}>{job.notes[job.notes.length - 1]}</div>
      )}
      {(job.dropped_by_filter > 0 || job.outside_window > 0) && (
        <div className="field-hint" style={{ marginTop: 4 }}>
          {job.dropped_by_filter > 0 && `${job.dropped_by_filter} video dibuang penyaring kata kunci. `}
          {job.outside_window > 0 && `${nf.format(job.outside_window)} komentar di luar periode tidak disimpan.`}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
        {job.videos_total > 0 && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOpen(!open)}>
            {open ? "Tutup daftar video" : "Lihat daftar video"}
          </button>
        )}
        {canManage && active && (
          <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => act("stop")}>
            Hentikan
          </button>
        )}
        {canManage && (job.status === "stopped" || job.status === "failed") && (
          <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => act("resume")}>
            Lanjutkan
          </button>
        )}
        {canManage && !active && (
          <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => act("delete")}>
            Hapus dari daftar
          </button>
        )}
      </div>
      {!active && canManage && (
        <div className="field-hint" style={{ marginTop: 4 }}>
          Menghapus dari daftar tidak menghapus komentar yang sudah tersimpan.
        </div>
      )}
      {error && <div className="form-err" role="alert" style={{ marginTop: 6 }}>{error}</div>}

      {open && (
        <table className="tbl" style={{ marginTop: 10 }}>
          <thead>
            <tr>
              <th>Video</th>
              <th>Kanal</th>
              <th>Komentar (YouTube)</th>
              <th>Terambil</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {job.videos.map((v) => (
              <tr key={v.id}>
                <td>
                  <a href={`https://www.youtube.com/watch?v=${v.id}`} target="_blank" rel="noreferrer">
                    {v.title}
                  </a>
                </td>
                <td>{v.channel}</td>
                <td className="mono">{nf.format(v.comment_count)}</td>
                <td className="mono">{nf.format(v.got)}</td>
                <td>{v.state === "done" ? "selesai" : v.state === "skipped" ? v.note ?? "dilewati" : "antre"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="field-hint" style={{ marginTop: 10 }}>
        Metode: {job.method}. Batasan: {job.limitations.join(" ")}
      </p>
    </div>
  );
}
