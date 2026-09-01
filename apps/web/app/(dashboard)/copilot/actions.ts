"use server";

import { api, ApiError } from "@/lib/api";

export interface CopilotAnswer {
  jawaban: string;
  bukti_dipakai: string[];
  data_tidak_tersedia: boolean;
}

export interface AskResponse {
  id: string;
  payload: CopilotAnswer;
  method: string;
  model_version: string;
  confidence: "LOW" | "MEDIUM" | "HIGH";
  evidence: Array<{ kind: string; label: string; source: string; n: number | null }>;
  limitations: string;
  human_review: string;
  matched_terms: Record<string, string[]>;
  cards_considered: number;
  cards_used: number;
}

export interface AskState {
  answer: AskResponse | null;
  error: string | null;
  question: string;
}

// Keadaan awal ada di AskForm.tsx, bukan di sini: modul "use server" hanya
// boleh mengekspor fungsi async. Lihat catatan lengkap di dampak/actions.ts.

/**
 * Ajukan pertanyaan ke Copilot.
 *
 * Kegagalan dikembalikan sebagai pesan, bukan dilempar: 409 ("proyek belum
 * punya data agregat") dan 502 ("provider belum siap") adalah keadaan yang
 * harus dibaca pengguna, bukan Application Error.
 */
export async function askCopilot(_prev: AskState, formData: FormData): Promise<AskState> {
  const projectId = String(formData.get("projectId") ?? "");
  const question = String(formData.get("question") ?? "").trim();

  if (question.length < 3) {
    return { answer: null, error: "Pertanyaan terlalu pendek.", question };
  }

  try {
    const answer = await api<AskResponse>(`/projects/${projectId}/copilot/ask`, {
      method: "POST",
      body: JSON.stringify({ question }),
    });
    return { answer, error: null, question };
  } catch (e) {
    if (e instanceof ApiError) return { answer: null, error: e.message, question };
    throw e;
  }
}
