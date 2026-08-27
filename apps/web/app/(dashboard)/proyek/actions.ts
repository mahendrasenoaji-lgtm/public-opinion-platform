"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { api, ApiError } from "@/lib/api";
import { CURRENT_PROJECT_COOKIE, getCurrentProjectId } from "@/lib/currentProject";

/**
 * Jadikan satu proyek sebagai proyek aktif (cookie pop_project_id) lalu
 * kembali ke Command Center. Dipanggil sebagai bound action per baris di
 * page.tsx (`activateProject.bind(null, p.id)`) -- pola form action Next.js
 * untuk daftar dengan satu tombol per item, tanpa perlu client component.
 *
 * Validasi ulang lewat GET /projects/{id} sebelum menyimpan cookie -- baris
 * tombolnya memang cuma pernah dirender dari GET /projects milik org sendiri
 * (page.tsx), tapi form HTML tetap bisa dimanipulasi lewat devtools. Bukan
 * lubang keamanan kalaupun dilewati (RLS tetap yang menegakkan batas
 * tenant, lihat lib/currentProject.ts:getCurrentProject), ini cuma supaya
 * gagalnya jelas ("Proyek tidak ditemukan") alih-alih diam-diam menyimpan
 * id yang keliru.
 */
export async function activateProject(projectId: string): Promise<void> {
  try {
    await api(`/projects/${projectId}`);
  } catch (e) {
    if (e instanceof ApiError) return;
    throw e;
  }

  (await cookies()).set(CURRENT_PROJECT_COOKIE, projectId, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
  });
  redirect("/command");
}

/**
 * Ganti nama proyek via PATCH /projects/{id}.
 *
 * Mengembalikan `{ ok: true }` atau `{ ok: false, error: string }` --
 * dipanggil dari client component (ProjectRow) jadi tidak bisa
 * menggunakan redirect() atau throw (yang hanya bekerja di form action
 * sinkron / Server Component).
 */
export async function renameProject(
  projectId: string,
  newName: string,
): Promise<{ ok: boolean; error?: string }> {
  const trimmed = newName.trim();
  if (!trimmed) return { ok: false, error: "Nama tidak boleh kosong." };
  if (trimmed.length > 300) return { ok: false, error: "Nama maksimal 300 karakter." };

  try {
    await api(`/projects/${projectId}`, {
      method: "PATCH",
      body: JSON.stringify({ name: trimmed }),
    });
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }

  revalidatePath("/proyek");
  return { ok: true };
}

/**
 * Hapus proyek via DELETE /projects/{id}.
 *
 * Kalau proyek yang dihapus adalah proyek yang sedang aktif (cookie
 * pop_project_id), cookie di-clear supaya fallback ke DEMO_PROJECT_ID --
 * lebih baik kembali ke demo daripada terus menunjuk proyek yang sudah
 * tidak ada.
 *
 * Mengembalikan `{ ok, error?, cleared? }` -- `cleared` berarti proyek
 * aktif baru saja dicabut.
 */
export async function deleteProject(
  projectId: string,
): Promise<{ ok: boolean; error?: string; cleared?: boolean }> {
  try {
    await api(`/projects/${projectId}`, { method: "DELETE" });
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }

  const currentId = await getCurrentProjectId();
  let cleared = false;
  if (currentId === projectId) {
    (await cookies()).delete(CURRENT_PROJECT_COOKIE);
    cleared = true;
  }

  revalidatePath("/proyek");
  return { ok: true, cleared };
}
