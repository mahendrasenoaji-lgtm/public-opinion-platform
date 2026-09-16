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
