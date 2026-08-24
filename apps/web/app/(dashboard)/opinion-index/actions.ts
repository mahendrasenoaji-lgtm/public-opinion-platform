"use server";

import { api, ApiError } from "@/lib/api";

/**
 * Membungkus PUT bobot dimensi POI. `api()` butuh konteks server (baca
 * cookie sesi lewat next/headers) — WeightEditor.tsx client component tidak
 * bisa memanggilnya langsung, jadi lewat Server Action ini.
 *
 * Mengembalikan hasil terstruktur, bukan melempar error: Next.js meredaksi
 * pesan error yang di-throw dari Server Action di build produksi (demi
 * keamanan), jadi pesan asli dari backend (mis. alasan validasi) tidak akan
 * sampai ke pengguna kalau di-throw begitu saja.
 */
export async function saveOpinionWeights(
  projectId: string,
  weights: Record<string, number>,
): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    await api(`/projects/${projectId}/opinion/weights`, {
      method: "PUT",
      body: JSON.stringify({ weights }),
    });
    return { ok: true };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}
