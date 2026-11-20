"use server";

import { revalidatePath } from "next/cache";
import { api, ApiError } from "@/lib/api";

type Result<T> = { ok: true; result: T } | { ok: false; error: string };

export interface SourceOut {
  id: string;
  connector: string;
  source: string;
  config: Record<string, string>;
  is_active: boolean;
  last_sync_at: string | null;
}

/**
 * Daftarkan satu sumber data untuk proyek ini (K6, 2026-09-16).
 *
 * Sebelum ini, mendaftarkan sumber / mengelola token pengumpul hanya bisa
 * lewat curl langsung ke API -- peneliti non-teknis tidak bisa mengelolanya.
 * Backend-nya sudah ada sejak PR #15; ini murni menambah UI untuknya.
 *
 * Pola sama dengan collectSeries di app/(dashboard)/deret/actions.ts:
 * mengembalikan `{ ok, ... }`, bukan melempar, karena dipanggil langsung dari
 * client component (bukan lewat <form action=...>) — fieldnya dinamis per
 * konektor (lihat SourceManager.tsx), jadi FormData tidak cocok di sini.
 */
export async function addSource(
  projectId: string,
  connector: string,
  config: Record<string, string>,
): Promise<Result<SourceOut>> {
  try {
    const result = await api<SourceOut>(`/projects/${projectId}/signals/sources`, {
      method: "POST",
      body: JSON.stringify({ connector, config }),
    });
    revalidatePath("/sinyal");
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

export async function removeSource(
  projectId: string,
  sourceId: string,
): Promise<Result<null>> {
  try {
    await api(`/projects/${projectId}/signals/sources/${sourceId}`, { method: "DELETE" });
    revalidatePath("/sinyal");
    return { ok: true, result: null };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

interface IngestResult {
  received: number;
  stored: number;
  already_present: number;
  duplicates_dropped: number;
}

interface SourceCollectOut {
  source_id: string;
  connector: string;
  label: string | null;
  ok: boolean;
  error: string | null;
  offered: number | null;
  matched: number | null;
  coverage_gap: boolean;
  result: IngestResult | null;
  /** Keterangan sumber penemuan video; tidak ada di backend lama. */
  note?: string | null;
}

export interface CollectAllOut {
  sources_total: number;
  sources_ok: number;
  sources_failed: number;
  sources_inactive: number;
  coverage_gaps: number;
  stored_total: number;
  results: SourceCollectOut[];
}

/**
 * Tarik semua sumber aktif sekarang -- jalur manual yang sama persis dengan
 * yang dipicu terjadwal lewat GitHub Actions tiap 30 menit (lihat
 * docs/deployment-status.md, "Pengumpulan sinyal terjadwal"). Status 200
 * berarti permintaan diproses, BUKAN berarti semua sumber berhasil --
 * `sources_failed` dan `coverage_gap` per sumber tetap harus dibaca dari
 * `result`, sama seperti job summary GitHub Actions membacanya.
 */
export async function runCollectAll(projectId: string): Promise<Result<CollectAllOut>> {
  try {
    const result = await api<CollectAllOut>(`/projects/${projectId}/signals/collect-all`, {
      method: "POST",
    });
    revalidatePath("/sinyal");
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

export interface RescoreOut {
  examined: number;
  primary_changed: number;
  alt_written: number;
  remaining: number;
  models: Record<string, string>;
}

/**
 * Satu putaran penilaian ulang (backend membatasi 500 baris per panggilan dan
 * melaporkan `remaining`). Pengulangannya di RescoreButton, bukan di sini,
 * supaya kemajuan terlihat dan satu server action tidak berjalan bermenit-menit.
 */
export async function runRescore(projectId: string): Promise<Result<RescoreOut>> {
  try {
    const result = await api<RescoreOut>(`/projects/${projectId}/signals/rescore`, {
      method: "POST",
    });
    revalidatePath("/sinyal");
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

export interface CollectorTokenStatus {
  active: boolean;
  token_id: string | null;
  issued_at: string | null;
  expires_at: string | null;
  issued_by: string | null;
}

export interface CollectorTokenOut {
  token: string;
  token_id: string;
  expires_at: string;
  scope: string;
}

/**
 * Terbitkan token pengumpul baru. Backend menampilkan nilainya TEPAT SEKALI
 * di respons ini -- tidak bisa dibaca ulang sesudahnya (lihat docstring
 * issue_collector_token di app/routers/signals.py). Menerbitkan token baru
 * otomatis mematikan yang lama, jadi UI ini WAJIB memperingatkan itu sebelum
 * memanggil, bukan sesudahnya.
 */
export async function issueToken(
  projectId: string,
  days: number,
): Promise<Result<CollectorTokenOut>> {
  try {
    const result = await api<CollectorTokenOut>(
      `/projects/${projectId}/signals/collector-token`,
      { method: "POST", body: JSON.stringify({ days }) },
    );
    revalidatePath("/sinyal");
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

export async function revokeToken(projectId: string): Promise<Result<null>> {
  try {
    await api(`/projects/${projectId}/signals/collector-token`, { method: "DELETE" });
    revalidatePath("/sinyal");
    return { ok: true, result: null };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

export interface IngestItemIn {
  external_id: string;
  text: string;
  published_at: string;
  url?: string | null;
  author_handle?: string | null;
  engagement?: number;
  conversation_id?: string | null;
}

export interface FullIngestResult {
  received: number;
  stored: number;
  already_present: number;
  duplicates_dropped: number;
  duplicate_rate: number;
  language_rejected: number;
  language_unknown: number;
  sentiment_abstained: number;
  sentiment_abstain_rate: number;
  empty_dropped: number;
  caveats: string[];
}

/**
 * Satu potong unggahan data yang sudah dimiliki peneliti (2026-11-05).
 *
 * Endpoint `POST /signals/ingest` sudah ada sejak Phase 2 tetapi hanya bisa
 * dipanggil dengan curl. Kebutuhan pertamanya: komentar YouTube untuk jendela
 * waktu yang sudah lewat (krisis BBM Bali 11–20 Okt 2026) — `collect-all` selalu
 * menarik yang terbaru, jadi rentang lampau tidak bisa diambil lewat tombol
 * "Tarik semua". Data tetap melewati pipeline yang sama (dedup, bahasa,
 * sentimen). Pemotongan per batch ada di UploadData.tsx, bukan di sini.
 *
 * Tidak memanggil revalidatePath: pemanggil memanggil `finishIngest` SEKALI
 * sesudah potongan terakhir. Dulu revalidasi per potongan 300 item membuat
 * Next menghitung ulang seluruh /sinyal puluhan kali per berkas; pada proyek
 * besar (Gibran, 17 Nov 2026) itu menjatuhkan server API ("Bad Gateway").
 */
export async function ingestBatch(
  projectId: string,
  connector: string,
  source: SignalSourceKey,
  items: IngestItemIn[],
): Promise<Result<FullIngestResult>> {
  try {
    const result = await api<FullIngestResult>(`/projects/${projectId}/signals/ingest`, {
      method: "POST",
      body: JSON.stringify({ connector, source, items }),
    });
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

/** Segarkan /sinyal sekali, sesudah seluruh potongan sebuah unggahan selesai atau berhenti. */
export async function finishIngest(): Promise<void> {
  revalidatePath("/sinyal");
}

export type SignalSourceKey = "SOCIAL" | "MEDIA";

export interface SentimentCorrectionOut {
  id: string;
  sentiment: number | null;
  sentiment_manual: boolean;
  changed: boolean;
}

export type SentimentLabel = "negatif" | "netral" | "positif";

/**
 * Tetapkan label sentimen satu konten secara manual, atau batalkan
 * (`label === null`) supaya kembali ke skor penilai otomatis. Label manusia
 * menang atas penilaian ulang dan tercatat di audit log (backend).
 */
export async function correctSentiment(
  projectId: string,
  mentionId: string,
  label: SentimentLabel | null,
): Promise<Result<SentimentCorrectionOut>> {
  try {
    const result = await api<SentimentCorrectionOut>(
      `/projects/${projectId}/mentions/${mentionId}/sentiment`,
      label === null
        ? { method: "DELETE" }
        : { method: "PUT", body: JSON.stringify({ label }) },
    );
    revalidatePath("/sinyal");
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

// ------------------------------------------------------- tarik tema ----

export interface ThemeVideo {
  id: string;
  title: string;
  channel: string;
  comment_count: number;
  got: number;
  state: "pending" | "done" | "skipped";
  note: string | null;
}

export interface ThemePull {
  id: string;
  label: string;
  queries: string[];
  start: string;
  end: string;
  max_videos: number;
  include_replies: boolean;
  comments_until_now: boolean;
  keyword_filter: boolean;
  status: "searching" | "details" | "collecting" | "waiting_quota" | "done" | "failed" | "stopped";
  running: boolean;
  videos_total: number;
  videos_done: number;
  videos_skipped: number;
  comments_expected: number;
  received: number;
  stored: number;
  outside_window: number;
  dropped_by_filter: number;
  units: number;
  units_remaining_est: number;
  current_video: string | null;
  error: string | null;
  notes: string[];
  created_at: string | null;
  updated_at: string | null;
  finished_at: string | null;
  resume_at: string | null;
  videos: ThemeVideo[];
  method: string;
  limitations: string[];
}

export interface ThemeCreate {
  queries: string;
  start: string;
  end: string;
  max_videos: number;
  include_replies: boolean;
  comments_until_now: boolean;
  keyword_filter: boolean;
  label?: string;
}

/**
 * Tarik tema YouTube: server mencari video di periode itu lalu menarik
 * komentarnya sendiri di latar belakang (backend routers/theme_pulls.py).
 * Membuka daftar ini juga melanjutkan pekerjaan yang terhenti karena server
 * restart -- karena itu panel memanggilnya berkala selama ada yang berjalan.
 */
export async function listThemePulls(projectId: string): Promise<Result<ThemePull[]>> {
  try {
    const result = await api<ThemePull[]>(`/projects/${projectId}/signals/theme-pulls`);
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

export async function createThemePull(
  projectId: string,
  body: ThemeCreate,
): Promise<Result<ThemePull>> {
  try {
    const result = await api<ThemePull>(`/projects/${projectId}/signals/theme-pulls`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

export async function controlThemePull(
  projectId: string,
  jobId: string,
  action: "stop" | "resume",
): Promise<Result<ThemePull>> {
  try {
    const result = await api<ThemePull>(
      `/projects/${projectId}/signals/theme-pulls/${jobId}/${action}`,
      { method: "POST" },
    );
    revalidatePath("/sinyal");
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

/** Dipanggil sekali sesudah penarikan selesai supaya angka halaman ikut baru. */
export async function refreshSignals(): Promise<void> {
  revalidatePath("/sinyal");
}
