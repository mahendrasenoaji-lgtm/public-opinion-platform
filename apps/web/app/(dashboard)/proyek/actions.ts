"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { CURRENT_PROJECT_COOKIE } from "@/lib/currentProject";

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
