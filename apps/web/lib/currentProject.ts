/**
 * Proyek aktif per-sesi browser.
 *
 * Belum ada project switcher/multi-proyek sungguhan -- ini cuma jalur
 * minimal supaya org yang baru daftar (app/daftar, app/proyek-baru) tidak
 * terjebak melihat DEMO_PROJECT_ID (proyek org lain, RLS akan mengosongkan
 * semuanya). User demo lama (login lewat /masuk tanpa pernah membuat
 * proyek sendiri) tidak terpengaruh sama sekali -- cookie ini belum pernah
 * diset untuk mereka, jadi selalu jatuh ke DEMO_PROJECT_ID persis seperti
 * sebelumnya.
 *
 * Cuma dipakai dari konteks server, sama seperti lib/api.ts.
 */
import { cookies } from "next/headers";
import { api, ApiError } from "@/lib/api";

export const CURRENT_PROJECT_COOKIE = "pop_project_id";

export async function getCurrentProjectId(): Promise<string> {
  const fromCookie = (await cookies()).get(CURRENT_PROJECT_COOKIE)?.value;
  return fromCookie ?? process.env.DEMO_PROJECT_ID!;
}

export interface CurrentProject {
  id: string;
  name: string;
  is_demo: boolean;
}

/**
 * Nama + status demo proyek aktif, dipakai PageHeader di semua halaman
 * dashboard supaya tidak lagi menampilkan "Persepsi Kebijakan Nasional
 * 2026" / "Data demo sintetis" hardcoded untuk proyek siapa pun (termasuk
 * proyek asli, non-demo, yang dibuat lewat app/proyek-baru). Fallback ke
 * ApiError generik saja -- bukan ApiError 401, itu tetap harus lempar ke
 * redirect() di api() seperti biasa (lihat catatan serupa di
 * (dashboard)/layout.tsx sebelum helper ini ada).
 */
export async function getCurrentProject(): Promise<CurrentProject> {
  const id = await getCurrentProjectId();
  try {
    const project = await api<{ name: string; is_demo: boolean }>(`/projects/${id}`);
    return { id, name: project.name, is_demo: project.is_demo };
  } catch (e) {
    if (e instanceof ApiError) return { id, name: "Proyek", is_demo: false };
    throw e;
  }
}
