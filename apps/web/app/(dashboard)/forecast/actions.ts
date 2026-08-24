"use server";

import { api, ApiError } from "@/lib/api";

export interface ForecastPoint {
  horizon_days: number;
  expected: number;
  pi_low: number;
  pi_high: number;
}

export interface WhatIfResult {
  points: ForecastPoint[];
  pi_level: number;
  model: string;
  is_simulation: boolean;
  scenario: Record<string, number>;
  driver_contributions: Array<{
    driver: string;
    input: number;
    unit: string;
    effect_at_max_horizon: number;
  }>;
  limitations: string[];
}

/**
 * Membungkus POST /forecast/what-if. WeightEditor/opinion-index/actions.ts
 * punya alasan yang sama untuk pola ini: next/headers (baca cookie sesi)
 * cuma jalan di konteks server, ForecastSimulator.tsx client component
 * tidak bisa memanggil api() langsung.
 */
export async function runWhatIf(
  projectId: string,
  baseline: number,
  scenario: Record<string, number>,
): Promise<{ ok: true; result: WhatIfResult } | { ok: false; error: string }> {
  try {
    const result = await api<WhatIfResult>(`/projects/${projectId}/forecast/what-if`, {
      method: "POST",
      body: JSON.stringify({ baseline, scenario, pi_level: 0.8 }),
    });
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}
