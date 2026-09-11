"use server";

import { revalidatePath } from "next/cache";
import { api, ApiError } from "@/lib/api";

export interface CollectResult {
  metric: string;
  fetched: number;
  stored: number;
  replaced: number;
  period_start: string | null;
  period_end: string | null;
  source: string;
  method: string;
  provinces: string[];
  limitations: string[];
}

/**
 * Tarik satu deret publik ke dalam proyek.
 *
 * Mengembalikan `{ ok, ... }` alih-alih melempar karena dipanggil dari client
 * component — pola yang sama dengan renameProject di /proyek/actions.ts.
 *
 * Pesan error backend diteruskan APA ADANYA. Konektor di sini sengaja menulis
 * pesan yang bisa ditindaklanjuti ("periksa ejaan judul artikelnya", "kode
 * provinsi belum punya koordinat"), dan menggantinya dengan "Gagal menarik
 * data" akan membuang justru bagian yang berguna.
 */
export async function collectSeries(
  projectId: string,
  connector: string,
  config: Record<string, string>,
  days: number,
): Promise<{ ok: true; result: CollectResult } | { ok: false; error: string }> {
  try {
    const result = await api<CollectResult>(`/projects/${projectId}/metrics/collect`, {
      method: "POST",
      body: JSON.stringify({ connector, config, days }),
    });
    revalidatePath("/deret");
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}
