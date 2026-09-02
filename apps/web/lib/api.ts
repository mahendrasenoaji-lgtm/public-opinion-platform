/**
 * Klien API. Semua metrik yang masuk sudah membawa sumber dan metodenya.
 *
 * Cuma dipakai dari konteks server (Server Component, Server Action, Route
 * Handler) — import next/headers di bawah membuat modul ini gagal dibundel
 * kalau ada client component yang mengimpornya langsung, dan itu memang
 * sengaja (lihat lib/session.ts).
 */
import type { Route } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE } from "@/lib/session";

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

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;

  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (res.status === 401) {
    // Sesi tidak ada/tidak valid/kadaluarsa — backend jadi otoritas
    // tunggal untuk itu (lihat lib/session.ts). Tidak ada auto-refresh di
    // sini, cuma lempar balik ke halaman login.
    // typedRoutes belum "melihat" /masuk sampai typegen jalan ulang; sama
    // seperti cast Route di (dashboard)/layout.tsx untuk rute yang belum
    // ada saat build pertama.
    redirect("/masuk" as Route);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, detailToMessage(body.detail));
  }
  return res.json() as Promise<T>;
}

/**
 * `detail` FastAPI bukan selalu string. `HTTPException(422, "pesan")` dari
 * kode aplikasi memang string, tapi 422 dari validasi Pydantic sendiri
 * (mis. daftar donor_segments kurang dari min_length) mengembalikan ARRAY
 * objek `{loc, msg, type, ...}`. Tanpa ini, ApiError.message jatuh ke
 * `Array.prototype.toString()` -> "[object Object]" yang tidak berarti
 * apa-apa bagi pengguna — ketahuan lewat verifikasi browser synthetic
 * control, bukan lewat tsc/build yang sama-sama hijau untuk keduanya.
 */
function detailToMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const pesan = detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : null))
      .filter((m): m is string => Boolean(m));
    if (pesan.length > 0) return pesan.join("; ");
  }
  return "Permintaan gagal.";
}

/**
 * Bungkus api() untuk endpoint yang sengaja 404 kalau proyek belum punya
 * data sama sekali (mis. GET .../opinion/index tanpa metric_snapshots
 * apapun, GET .../opinion/divergence dengan <2 sumber sinyal) -- beda dari
 * `insufficient_data:true` (Metric, di bawah ambang publikasi tapi
 * dimensinya ada). Dipakai halaman dashboard yang harus tetap merender
 * status "belum ada data" alih-alih menjatuhkan seluruh Server Component
 * dengan Application Error -- baru jadi kasus nyata sejak proyek bisa
 * dibuat lewat UI sendiri (app/proyek-baru) dan mulai kosong sama sekali.
 */
export async function apiOrNull<T>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    return await api<T>(path, init);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

/**
 * Seperti `apiOrNull`, tapi menganggap SEMUA `ApiError` dari backend (bukan
 * cuma 404) sebagai "belum bisa disajikan" -> null, bukan menjatuhkan
 * seluruh Server Component. Dipakai khusus untuk widget yang bergantung pada
 * kolom skema yang migrasinya belum tentu sudah diterapkan di setiap
 * environment (mis. `topics.review_status`, `mentions.reply_to_hash` --
 * lihat catatan migrasi Supabase di docs/deployment-status.md): kodenya
 * sudah di production, tapi kalau `ALTER TABLE` manual belum dijalankan di
 * sana, query backend gagal dengan 500 (kolom tidak ada), bukan 404 --
 * insiden nyata 2026-09-02 yang menjatuhkan /command, /tema, /jaringan
 * dengan "Application error" polos sebelum helper ini ada.
 *
 * JANGAN dipakai untuk endpoint yang errornya memang harus terlihat
 * pengguna (mis. hasil submit form) -- redirect 401 ke /masuk di `api()`
 * tetap jalan seperti biasa karena itu bukan `ApiError`.
 */
export async function apiOrNullLenient<T>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    return await api<T>(path, init);
  } catch (e) {
    if (e instanceof ApiError) return null;
    throw e;
  }
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
