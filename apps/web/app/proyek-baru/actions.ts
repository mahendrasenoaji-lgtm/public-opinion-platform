"use server";

import { cookies } from "next/headers";
import { api, ApiError } from "@/lib/api";
import { CURRENT_PROJECT_COOKIE } from "@/lib/currentProject";

/**
 * Buat proyek baru (pertama ATAU tambahan, lihat catatan di page.tsx), lalu
 * jadikan proyek aktif lewat cookie -- lihat lib/currentProject.ts. Server
 * Action, bukan Route Handler: sama alasannya dengan
 * app/(dashboard)/opinion-index/actions.ts:saveOpinionWeights -- `api()`
 * butuh next/headers, dan mengembalikan hasil terstruktur (bukan throw)
 * supaya pesan error asli dari backend tidak diredaksi Next.js di produksi.
 */
export async function createFirstProject(
  name: string,
): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    const project = await api<{ id: string }>("/projects", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    (await cookies()).set(CURRENT_PROJECT_COOKIE, project.id, {
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      path: "/",
      // Umur panjang dengan sengaja -- cuma berubah lagi kalau user
      // eksplisit membuat/mengaktifkan proyek lain (di sini atau lewat
      // app/(dashboard)/proyek). Bukan token sesi, jadi tidak perlu ikut
      // umur JWT.
      maxAge: 60 * 60 * 24 * 365,
    });
    return { ok: true };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}
