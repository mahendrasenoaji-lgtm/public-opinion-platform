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

export interface SyntheticControlOut {
  effect: number | null;
  treated_post: number | null;
  synthetic_post: number | null;
  weights: Record<string, number>;
  donors_used: number;
  n_pre_periods: number;
  pre_fit_rmspe: number | null;
  fit_quality_ok: boolean | null;
  placebo_effects: Record<string, number>;
  rank_p_value: number | null;
  method: string;
  insufficient_data: boolean;
  note: string | null;
  limitations: string[];
}

export interface SyntheticControlState {
  result: SyntheticControlOut | null;
  error: string | null;
  input: {
    metric: string;
    treated_segment: string;
    donor_segments: string;
    pre_period_end: string;
    post_period_end: string;
  };
}

// Sama seperti ImpactState di atas — keadaan awal TIDAK diekspor dari sini,
// ada di SyntheticControlForm.tsx.

/**
 * Jalankan analisis synthetic control (Abadie et al.) — alternatif dari DiD
 * ketika tidak ada satu kelompok pembanding tunggal yang meyakinkan, tapi ada
 * beberapa kandidat donor. Backend yang memutuskan penolakannya (donor
 * kurang, periode pra-perlakuan tidak cukup); di sini hanya meneruskan.
 */
export async function analyzeSyntheticControl(
  _prev: SyntheticControlState,
  formData: FormData,
): Promise<SyntheticControlState> {
  const projectId = String(formData.get("projectId") ?? "");
  const donorRaw = String(formData.get("donor_segments") ?? "");
  const input = {
    metric: String(formData.get("metric") ?? "approval"),
    treated_segment: String(formData.get("treated_segment") ?? "").trim(),
    donor_segments: donorRaw,
    pre_period_end: String(formData.get("pre_period_end") ?? ""),
    post_period_end: String(formData.get("post_period_end") ?? ""),
  };

  const donors = donorRaw
    .split(/[\n,]/)
    .map((s) => s.trim())
    .filter(Boolean);

  if (!input.treated_segment) {
    return { result: null, input, error: "Segmen terpapar wajib diisi." };
  }
  if (donors.length === 0) {
    return {
      result: null,
      input,
      error: "Daftar segmen donor wajib diisi — satu segmen per baris atau dipisah koma.",
    };
  }
  if (!input.pre_period_end || !input.post_period_end) {
    return { result: null, input, error: "Kedua periode pengukuran wajib diisi." };
  }

  try {
    const result = await api<SyntheticControlOut>(
      `/projects/${projectId}/impact/synthetic-control`,
      {
        method: "POST",
        body: JSON.stringify({
          metric: input.metric,
          treated_segment: input.treated_segment,
          donor_segments: donors,
          pre_period_end: input.pre_period_end,
          post_period_end: input.post_period_end,
        }),
      },
    );
    return { result, error: null, input };
  } catch (e) {
    if (e instanceof ApiError) return { result: null, error: e.message, input };
    throw e;
  }
}
