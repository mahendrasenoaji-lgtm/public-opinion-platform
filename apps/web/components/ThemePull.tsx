"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { SOURCE } from "@/lib/tokens";
import {
  controlThemePull,
  createThemePull,
  listThemePlatforms,
  listThemePulls,
  refreshSignals,
  removeSource,
  type ThemePlatform,
  type ThemePlatformKey,
  type ThemePull as Job,
} from "@/app/(dashboard)/sinyal/actions";

const ACTIVE = new Set<Job["status"]>(["searching", "details", "collecting", "waiting_quota"]);
const POLL_MS = 5000;

const PLATFORM_LABEL: Record<ThemePlatformKey, string> = {
  youtube: "YouTube",
  tiktok: "TikTok",
  instagram: "Instagram",
};

/** Kata untuk satu unggahan per platform (Instagram: unggahan, bukan video). */
const ITEM_WORD: Record<ThemePlatformKey, string> = {
  youtube: "video",
  tiktok: "video",
  instagram: "unggahan",
};

function statusLabel(status: Job["status"], platform: ThemePlatformKey): string {
  const item = ITEM_WORD[platform];
  switch (status) {
    case "searching":
      return `Mencari ${item}`;
    case "details":
      return `Memeriksa ${item}`;
    case "collecting":
      return "Menarik komentar";
    case "waiting_quota":
      return `Menunggu kuota ${PLATFORM_LABEL[platform]}`;
    case "done":
      return "Selesai";
    case "failed":
      return "Gagal";
    case "stopped":
      return "Dihentikan";
  }
}

function itemUrl(platform: ThemePlatformKey, v: Job["videos"][number]): string {
  if (v.url) return v.url;
  if (platform === "tiktok") return `https://www.tiktok.com/video/${v.id}`;
  return `https://www.youtube.com/watch?v=${v.id}`;
}

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
  const [platforms, setPlatforms] = useState<ThemePlatform[] | null>(null);
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
    void listThemePlatforms().then((res) => {
      // Backend lama (sebelum 21 Nov 2026) belum punya endpoint ini: anggap YouTube saja.
      setPlatforms(res.ok ? res.result : null);
    });
  }, []);
  useEffect(() => {
    if (!anyActive) return;
    const t = setInterval(() => void reload(), POLL_MS);
    return () => clearInterval(t);
  }, [anyActive, reload]);

  return (
    <div>
      <p className="field-hint" style={{ marginBottom: 12 }}>
        Pilih platform, isi kata kunci dan periode, tekan <b>Tarik</b>. Server mencari unggahan yang{" "}
        <b>terbit</b> dalam periode itu, membuang yang judul/deskripsinya tidak memuat kata kunci,
        lalu menarik komentar (dan balasan) dari unggahan paling ramai lebih dulu. Halaman ini boleh
        ditutup; kemajuan tersimpan di server. Kalau kuota harian platform habis, penarikan menunggu
        dan lanjut sendiri sesudah kuota pulih.
      </p>

      {canManage && <ThemeForm projectId={projectId} platforms={platforms} onCreated={reload} />}

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

const YOUTUBE_ONLY: ThemePlatform[] = [
  {
    key: "youtube",
    label: "YouTube",
    configured: true,
    env_vars: ["YOUTUBE_API_KEY"],
    collects_comments: true,
    max_days_back: null,
    access_note: "",
    method: "",
    limitations: [],
  },
];

function PlatformPicker({
  platforms,
  value,
  onChange,
  disabled,
}: {
  platforms: ThemePlatform[];
  value: ThemePlatformKey;
  onChange: (k: ThemePlatformKey) => void;
  disabled: boolean;
}) {
  return (
    <div className="field" role="radiogroup" aria-label="Platform">
      <label>Platform</label>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {platforms.map((p) => (
          <button
            key={p.key}
            type="button"
            role="radio"
            aria-checked={value === p.key}
            className={value === p.key ? "btn btn-sm" : "btn btn-ghost btn-sm"}
            onClick={() => onChange(p.key)}
            disabled={disabled}
          >
            {p.label}
            {!p.configured && " · belum aktif"}
          </button>
        ))}
      </div>
    </div>
  );
}

function ThemeForm({
  projectId,
  platforms,
  onCreated,
}: {
  projectId: string;
  platforms: ThemePlatform[] | null;
  onCreated: () => Promise<void>;
}) {
  const list = platforms ?? YOUTUBE_ONLY;
  const [platform, setPlatform] = useState<ThemePlatformKey>("youtube");
  const plat = list.find((p) => p.key === platform) ?? list[0] ?? YOUTUBE_ONLY[0]!;
  const isIg = platform === "instagram";
  const item = ITEM_WORD[platform];
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
      platform,
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

  function pick(k: ThemePlatformKey) {
    setPlatform(k);
    setError("");
    // Instagram hanya memberi unggahan ±24 jam terakhir: periode disetel ke kemarin–hari ini.
    if (k === "instagram") {
      setStart(wibDate(-1));
      setEnd(wibDate(0));
    }
  }

  const check = { display: "flex", gap: 8, alignItems: "center", fontSize: 13, marginBottom: 6 } as const;
  const minStart = plat.max_days_back != null ? wibDate(-plat.max_days_back) : undefined;

  return (
    <div>
      {list.length > 1 && (
        <PlatformPicker platforms={list} value={platform} onChange={pick} disabled={pending} />
      )}
      {!plat.configured && (
        <div className="read" style={{ marginBottom: 12 }}>
          <div className="read-t">{plat.label} belum aktif</div>
          <div className="read-d">
            Mesinnya sudah siap; tinggal mengisi {plat.env_vars.join(" dan ")} di environment backend
            (Render). {plat.access_note}
          </div>
          {plat.limitations.length > 0 && (
            <div className="field-hint" style={{ marginTop: 6 }}>
              Batasan bila aktif: {plat.limitations.join(" ")}
            </div>
          )}
        </div>
      )}
      <div className="field">
        <label htmlFor="tema-kunci">
          {isIg ? "Tagar (pisahkan dengan koma, maks. 5; tanpa spasi)" : "Kata kunci (pisahkan dengan koma, maks. 5)"}
        </label>
        <textarea
          id="tema-kunci"
          rows={2}
          value={queries}
          onChange={(e) => setQueries(e.target.value)}
          placeholder={isIg ? "#bbmbali, #antrebbm" : "gibran mundur, pengunduran diri gibran"}
          disabled={pending}
        />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
        <div className="field">
          <label htmlFor="tema-dari">Dari (WIB)</label>
          <input id="tema-dari" type="date" value={start} min={minStart} max={wibDate(0)} onChange={(e) => setStart(e.target.value)} disabled={pending} />
        </div>
        <div className="field">
          <label htmlFor="tema-sampai">Sampai (WIB)</label>
          <input id="tema-sampai" type="date" value={end} max={wibDate(0)} onChange={(e) => setEnd(e.target.value)} disabled={pending} />
        </div>
        <div className="field">
          <label htmlFor="tema-video">{isIg ? "Unggahan paling banyak" : "Video paling banyak"}</label>
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
      {isIg ? (
        <p className="field-hint" style={{ marginBottom: 6 }}>
          Instagram tidak mengizinkan pengambilan komentar unggahan akun lain. Yang disimpan adalah
          keterangan (caption) unggahan bertagar itu, dari ±24 jam terakhir.
        </p>
      ) : (
        <>
          <label style={check}>
            <input type="checkbox" checked={replies} onChange={(e) => setReplies(e.target.checked)} disabled={pending} />
            Ikutkan balasan komentar
          </label>
          <label style={check}>
            <input type="checkbox" checked={filter} onChange={(e) => setFilter(e.target.checked)} disabled={pending} />
            Hanya {item} yang judul/deskripsinya memuat kata kunci
          </label>
          <label style={check}>
            <input type="checkbox" checked={untilNow} onChange={(e) => setUntilNow(e.target.checked)} disabled={pending} />
            Simpan juga komentar yang ditulis sesudah periode (sampai hari ini)
          </label>
        </>
      )}

      {error && <div className="form-err" role="alert" style={{ marginTop: 8 }}>{error}</div>}

      <button
        type="button"
        className="btn"
        style={{ marginTop: 10 }}
        onClick={submit}
        disabled={pending || !plat.configured || !queries.trim() || !start || !end}
      >
        {pending ? "Memulai…" : `Tarik dari ${plat.label}`}
      </button>
      <p className="field-hint" style={{ marginTop: 8 }}>
        {platform === "youtube" &&
          "Kuota YouTube 10.000 unit/hari: tiap kata kunci memakai 100–400 unit untuk pencarian, lalu ±1 unit per 100 komentar. Tema sedang selesai dalam satu hari; tema besar bisa beberapa hari."}
        {platform === "tiktok" &&
          "TikTok Research API dihitung per permintaan (batas harian dari TikTok, pulih 07.05 WIB): 1 permintaan per 100 video saat mencari, 1 per 100 komentar. Nama akun komentator tidak diberikan API ini."}
        {platform === "instagram" &&
          "Instagram membatasi 30 tagar unik per 7 hari per akun; tiap tagar baru memakai satu jatah."}
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
  const platform: ThemePlatformKey = job.platform ?? "youtube";
  const item = ITEM_WORD[platform];
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
          <span className="pill">{PLATFORM_LABEL[platform]}</span>{" "}
          <span className="pill" style={{ color: SOURCE.SOCIAL.color }}>
            {SOURCE.SOCIAL.label}
          </span>
        </div>
        <span className={pillClass}>{statusLabel(job.status, platform)}</span>
      </div>
      <div className="read-d">
        Periode {job.start} s.d. {job.end} WIB · maks. {job.max_videos} {item}
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
        {platform === "instagram"
          ? `${nf.format(job.stored)} keterangan unggahan baru tersimpan`
          : job.status === "searching" || job.status === "details"
            ? `Menyusun daftar ${item}…`
            : `${processed}/${job.videos_total} ${item} · ${nf.format(job.stored)} komentar baru tersimpan`}
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
          {job.dropped_by_filter > 0 && `${job.dropped_by_filter} ${item} dibuang penyaring kata kunci. `}
          {job.outside_window > 0 && `${nf.format(job.outside_window)} komentar di luar periode tidak disimpan.`}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
        {job.videos_total > 0 && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOpen(!open)}>
            {open ? `Tutup daftar ${item}` : `Lihat daftar ${item}`}
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
              <th>{item === "video" ? "Video" : "Unggahan"}</th>
              <th>Akun</th>
              <th>Komentar ({PLATFORM_LABEL[platform]})</th>
              <th>Terambil</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {job.videos.map((v) => (
              <tr key={v.id}>
                <td>
                  <a href={itemUrl(platform, v)} target="_blank" rel="noreferrer">
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
