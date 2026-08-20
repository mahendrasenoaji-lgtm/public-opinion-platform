/** Klien API. Semua metrik yang masuk sudah membawa sumber dan metodenya. */

export type SignalSource = "SURVEY" | "SOCIAL" | "MEDIA" | "DIGITAL";

export interface Metric {
  key: string;
  label: string;
  /** null berarti sampel di bawah ambang publikasi — tampilkan "data tidak cukup" */
  value: number | null;
  unit: string;
  source: SignalSource;
  method: string;
  ci_low: number | null;
  ci_high: number | null;
  effective_n: number | null;
  insufficient_data: boolean;
  note: string | null;
}

export interface AIEnvelope<T> {
  payload: T;
  method: string;
  model_version: string;
  confidence: "LOW" | "MEDIUM" | "HIGH";
  evidence: Array<{ kind: string; label: string; source: SignalSource; n: number | null }>;
  limitations: string;
  human_review: "PENDING" | "APPROVED" | "REJECTED" | "NEEDS_REVIEW";
  is_simulation: boolean;
}

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/v1";

// TODO(frontend-auth): belum ada halaman login/session di Next.js — di luar
// cakupan Phase 1 (roadmap.md hanya mewajibkan Command Center + Opinion
// Index). DEMO_ACCESS_TOKEN/NEXT_PUBLIC_DEMO_ACCESS_TOKEN adalah jalan
// pintas SEMENTARA supaya server component ATAU komponen client (mis. slider
// bobot yang menyimpan lewat PUT) bisa memanggil API bertenant selama
// dev/demo lokal. NEXT_PUBLIC_* memang dibundel ke JS client — jangan pernah
// isi ini dengan token produksi sungguhan. Ganti seluruhnya dengan sesi asli
// (cookie httpOnly dari /auth/login) sebelum ada halaman publik.
const DEMO_TOKEN = process.env.DEMO_ACCESS_TOKEN ?? process.env.NEXT_PUBLIC_DEMO_ACCESS_TOKEN;

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(DEMO_TOKEN ? { Authorization: `Bearer ${DEMO_TOKEN}` } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? "Permintaan gagal.");
  }
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** Bangun query string dengan param berulang, mis. ?metrics=a&metrics=b. */
export function repeatedQuery(params: Record<string, string | string[] | number | undefined>): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) continue;
    for (const v of Array.isArray(value) ? value : [value]) q.append(key, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}
