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

export interface ReviewState {
  ok: boolean;
  message: string | null;
}

/**
 * Verifikasi manusia atas label kata-kunci sebuah tema.
 *
 * Label ASLI tidak pernah ditimpa (lihat app/routers/topics.py) -- yang
 * dikirim di sini disimpan terpisah sebagai reviewed_label, dan hanya dipakai
 * sebagai tampilan bila statusnya APPROVED.
 */
export async function reviewTopic(
  _prev: ReviewState,
  formData: FormData,
): Promise<ReviewState> {
  const projectId = String(formData.get("projectId") ?? "");
  const topicId = String(formData.get("topicId") ?? "");
  const status = String(formData.get("status") ?? "");
  const label = String(formData.get("label") ?? "").trim();

  if (!projectId || !topicId || !status) {
    return { ok: false, message: "Data tema tidak lengkap." };
  }

  try {
    await api(`/projects/${projectId}/topics/${topicId}/review`, {
      method: "PATCH",
      body: JSON.stringify({ status, label: label || null }),
    });
    revalidatePath("/tema");
    revalidatePath("/command");
    return { ok: true, message: null };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, message: e.message };
    throw e;
  }
}
