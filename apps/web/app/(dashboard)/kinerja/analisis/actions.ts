"use server";

import { revalidatePath } from "next/cache";
import { api, ApiError } from "@/lib/api";
import type {
  AlignmentRow,
  CodingRow,
  FlowRow,
  ResponseRate,
  SiteItemIn,
  SiteReadResult,
} from "./analisis";

type Result<T> = { ok: true; result: T } | { ok: false; error: string };

const PATH = "/kinerja/analisis";

async function call<T>(path: string, init: RequestInit): Promise<Result<T>> {
  try {
    const result = await api<T>(path, init);
    revalidatePath(PATH);
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

const base = (projectId: string) => `/projects/${projectId}/comm-performance`;

/** Simpan kode satu unggahan untuk satu lembar pengode. */
export async function saveCoding(
  projectId: string,
  postId: string,
  body: { coder: 1 | 2; coder_name: string; codes: Record<string, number | null>; note: string },
): Promise<Result<CodingRow>> {
  return call(`${base(projectId)}/coding/${postId}`, { method: "PUT", body: JSON.stringify(body) });
}

export type FlowInput = Omit<FlowRow, "id" | "hours">;

export async function addFlow(projectId: string, body: FlowInput): Promise<Result<FlowRow>> {
  return call(`${base(projectId)}/flow`, { method: "POST", body: JSON.stringify(body) });
}

export async function deleteFlow(projectId: string, id: string): Promise<Result<null>> {
  return call(`${base(projectId)}/flow/${id}`, { method: "DELETE" });
}

export async function saveAlignment(
  projectId: string,
  body: Omit<AlignmentRow, "id">,
): Promise<Result<AlignmentRow>> {
  return call(`${base(projectId)}/alignment`, { method: "PUT", body: JSON.stringify(body) });
}

export async function deleteAlignment(projectId: string, id: string): Promise<Result<null>> {
  return call(`${base(projectId)}/alignment/${id}`, { method: "DELETE" });
}

/** Hitung O8 dari komentar publik kanal YouTube resmi (memakai kuota API). */
export async function fetchResponseRate(
  projectId: string,
  account: string,
  maxVideos: number,
): Promise<Result<ResponseRate>> {
  return call(`${base(projectId)}/youtube-response-rate`, {
    method: "POST",
    body: JSON.stringify({ account, max_videos: maxVideos }),
  });
}

/** Daftarkan situs resmi lembaga dan langsung coba baca feed/sitemap-nya. */
export async function addSite(
  projectId: string,
  subject: string,
  url: string,
): Promise<Result<SiteReadResult>> {
  return call(`${base(projectId)}/sites`, { method: "POST", body: JSON.stringify({ subject, url }) });
}

export async function refreshSite(projectId: string, id: string): Promise<Result<SiteReadResult>> {
  return call(`${base(projectId)}/sites/${id}/refresh`, { method: "POST" });
}

export async function uploadSiteItems(
  projectId: string,
  id: string,
  items: SiteItemIn[],
): Promise<Result<{ received: number; stored: number; updated: number }>> {
  return call(`${base(projectId)}/sites/${id}/items`, {
    method: "POST",
    body: JSON.stringify({ items }),
  });
}

export async function deleteSite(projectId: string, id: string): Promise<Result<null>> {
  return call(`${base(projectId)}/sites/${id}`, { method: "DELETE" });
}
