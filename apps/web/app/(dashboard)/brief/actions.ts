"use server";

import { api, ApiError } from "@/lib/api";

export interface BriefPayload {
  apa_yang_terjadi: string;
  mengapa: string;
  siapa: string;
  di_mana: string;
  apa_berikutnya: string;
  yang_perlu_diawasi: string;
}

export interface EvidenceRef {
  kind: string;
  label: string;
  source: "SURVEY" | "SOCIAL" | "MEDIA" | "DIGITAL";
  n: number | null;
}

export interface BriefOut {
  id: string;
  payload: BriefPayload;
  method: string;
  model_version: string;
  confidence: "LOW" | "MEDIUM" | "HIGH";
  evidence: EvidenceRef[];
  limitations: string;
  human_review: "PENDING" | "APPROVED" | "REJECTED" | "NEEDS_REVIEW";
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
}

type ActionResult = { ok: true; brief: BriefOut } | { ok: false; error: string };

/** Membungkus POST .../brief/generate — pola sama actions.ts lain di proyek
 * ini (Server Action karena next/headers cuma jalan di konteks server). */
export async function generateBrief(projectId: string): Promise<ActionResult> {
  try {
    const brief = await api<BriefOut>(`/projects/${projectId}/brief/generate`, {
      method: "POST",
    });
    return { ok: true, brief };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

export async function approveBrief(projectId: string, briefId: string): Promise<ActionResult> {
  try {
    const brief = await api<BriefOut>(`/projects/${projectId}/brief/${briefId}/approve`, {
      method: "POST",
    });
    return { ok: true, brief };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}
