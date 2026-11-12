"use server";

import { revalidatePath } from "next/cache";
import { api, ApiError } from "@/lib/api";
import type { PubStatus, Publication } from "./publikasi";

type Result<T> = { ok: true; result: T } | { ok: false; error: string };

async function call<T>(path: string, init: RequestInit): Promise<Result<T>> {
  try {
    const result = await api<T>(path, init);
    revalidatePath("/publikasi");
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

/** Buat draf dengan snapshot beku bahan /laporan untuk periode tetap ini. */
export async function createDraft(
  projectId: string,
  input: { title: string; start: string; end: string; tz: string },
): Promise<Result<Publication>> {
  return call<Publication>(`/projects/${projectId}/publications`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function editPublication(
  projectId: string,
  id: string,
  input: { title: string; summary: string; body: string; tags: string[]; correction_note?: string },
): Promise<Result<Publication>> {
  return call<Publication>(`/projects/${projectId}/publications/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export async function setPublicationStatus(
  projectId: string,
  id: string,
  status: PubStatus,
): Promise<Result<Publication>> {
  return call<Publication>(`/projects/${projectId}/publications/${id}/status`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

export async function deleteDraft(projectId: string, id: string): Promise<Result<null>> {
  return call<null>(`/projects/${projectId}/publications/${id}`, { method: "DELETE" });
}
