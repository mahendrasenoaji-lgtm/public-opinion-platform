"use server";

import { api, ApiError } from "@/lib/api";

export interface ImpactOut {
  effect: number | null;
  ci_low: number | null;
  ci_high: number | null;
  ci_level: number;
  treated_change: number | null;
  control_change: number | null;
  distinguishable_from_zero: boolean;
  parallel_trends_checked: boolean;
  parallel_trends_ok: boolean | null;
  method: string;
  insufficient_data: boolean;
  note: string | null;
  limitations: string[];
}

export interface ImpactState {
  result: ImpactOut | null;
  error: string | null;
  input: {
    metric: string;
    treated_segment: string;
    control_segment: string;
    pre_period_end: string;
    post_period_end: string;
  };
}

// Keadaan awalnya TIDAK diekspor dari sini. Modul "use server" cuma boleh
// mengekspor fungsi async — sebuah objek biasa akan sampai ke client sebagai
// undefined, dan halaman ini jatuh dengan "Cannot read properties of
// undefined". Ketahuan lewat verifikasi browser, bukan lewat build: `next
// build` dan `tsc` sama-sama hijau. Konstanta awalnya ada di ImpactForm.tsx.

/**
 * Jalankan analisis difference-in-differences.
 *
 * Backend MENOLAK bekerja kalau salah satu dari empat sel tidak ada, dan
 * penolakan itu memang produknya — bukan kegagalan yang perlu disembunyikan.
 * Karena itu pesannya ditampilkan apa adanya ke pengguna.
 */
export async function analyzeImpact(
  _prev: ImpactState,
  formData: FormData,
): Promise<ImpactState> {
  const projectId = String(formData.get("projectId") ?? "");
  const input = {
    metric: String(formData.get("metric") ?? "approval"),
    treated_segment: String(formData.get("treated_segment") ?? "").trim(),
    control_segment: String(formData.get("control_segment") ?? "").trim(),
    pre_period_end: String(formData.get("pre_period_end") ?? ""),
    post_period_end: String(formData.get("post_period_end") ?? ""),
  };

  if (!input.treated_segment || !input.control_segment) {
    return {
      result: null,
      input,
      error:
        "Kelompok terpapar dan kelompok pembanding keduanya wajib diisi. Tanpa " +
        "pembanding, yang bisa dihitung hanyalah perubahan sebelum-sesudah — dan " +
        "itu tidak bisa dipisahkan dari tren yang memang sudah berjalan.",
    };
  }
  if (!input.pre_period_end || !input.post_period_end) {
    return { result: null, input, error: "Kedua periode pengukuran wajib diisi." };
  }

  try {
    const result = await api<ImpactOut>(`/projects/${projectId}/impact/analyze`, {
      method: "POST",
      body: JSON.stringify(input),
    });
    return { result, error: null, input };
  } catch (e) {
    if (e instanceof ApiError) return { result: null, error: e.message, input };
    throw e;
  }
}
