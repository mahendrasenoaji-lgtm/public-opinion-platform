"use server";

import { revalidatePath } from "next/cache";
import { api, ApiError } from "@/lib/api";

interface DiscoveryResult {
  topics: unknown[];
  n_analysed: number;
  unclustered: number;
  unclustered_pct: number;
  method: string;
  insufficient_data: boolean;
  note: string | null;
  limitations: string[];
}

export interface DiscoverState {
  ok: boolean;
  message: string | null;
}

// Keadaan awal ada di DiscoverButton.tsx, bukan di sini: modul "use server"
// hanya boleh mengekspor fungsi async. Lihat catatan di dampak/actions.ts.

/**
 * Jalankan penemuan tema.
 *
 * POST, bukan GET, karena operasi ini MENULIS: ia mengganti isi tabel topics
 * proyek dan menetapkan topic_id pada mentions (lihat app/routers/topics.py).
 */
export async function discoverTopics(
  _prev: DiscoverState,
  formData: FormData,
): Promise<DiscoverState> {
  const projectId = String(formData.get("projectId") ?? "");
  if (!projectId) return { ok: false, message: "Proyek tidak dikenali." };

  try {
    const result = await api<DiscoveryResult>(`/projects/${projectId}/topics/discover`, {
      method: "POST",
    });

    if (result.insufficient_data) {
      return {
        ok: false,
        message: result.note ?? "Data belum cukup untuk menemukan tema.",
      };
    }

    revalidatePath("/tema");
    return {
      ok: true,
      message:
        `${result.topics.length} tema ditemukan dari ${result.n_analysed} percakapan. ` +
        `${result.unclustered_pct.toFixed(1)}% tidak masuk tema mana pun` +
        (result.unclustered_pct >= 30
          ? " — peta tema ini tidak menggambarkan sebagian besar percakapan."
          : "."),
    };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, message: e.message };
    throw e;
  }
}
