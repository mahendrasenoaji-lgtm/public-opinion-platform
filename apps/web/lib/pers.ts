/**
 * Pembaca API publik publikasi. Tanpa cookie, tanpa token: halaman /pers
 * hanya melihat artikel berstatus terbit, lewat fungsi baca-publik di backend.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/v1";

export interface PersRef {
  slug: string;
  title: string;
  summary: string;
  tags: string[];
  author_name: string;
  published_at: string;
  version: number;
}

export interface PersDay {
  day: string;
  volume: number;
  scored: number;
  /** null bila konten bernilai pada hari itu di bawah ambang. */
  mean: number | null;
  negative_share: number | null;
}

export interface PersItem {
  /** Kosong untuk konten warga: teks dan tautannya tidak pernah disimpan. */
  text?: string;
  source_url?: string | null;
  engagement: number | null;
  published_at: string;
}

export interface PersPeak {
  day: string;
  volume: number;
  ratio: number | null;
  is_spike: boolean;
  top_content: PersItem[];
  same_day_media: PersItem[];
}

export interface PersSource {
  source: string;
  n: number;
  scored: number;
  labels: Record<string, number>;
  days?: PersDay[];
  peaks?: PersPeak[];
  words?: [string, number][];
  hashtags?: [string, number][];
  emoji?: [string, number][];
}

export interface PersTopic {
  label: string;
  source: string;
  n: number;
  scored: number;
  sentiment: number | null;
}

export interface PersArticle extends PersRef {
  body: string;
  updated_at: string;
  snapshot: {
    frozen_at: string;
    period_start: string | null;
    period_end: string | null;
    timezone: string;
    note: string;
    report: {
      sources: PersSource[];
      outlets?: { domain: string; n: number }[];
      topics?: PersTopic[];
      methods?: Record<string, string>;
      limitations?: string[];
    };
  };
  corrections: { version: number; at: string; note: string }[];
}

export type PersResult<T> =
  | { state: "ok"; data: T }
  | { state: "missing" }
  | { state: "unavailable" };

async function read<T>(path: string): Promise<PersResult<T>> {
  try {
    const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
    if (res.status === 404) return { state: "missing" };
    if (!res.ok) return { state: "unavailable" };
    return { state: "ok", data: (await res.json()) as T };
  } catch {
    return { state: "unavailable" };
  }
}

export const PAGE_SIZE = 20;

export function listArticles(tag?: string, page = 1, limit = PAGE_SIZE) {
  const q = new URLSearchParams({ limit: String(limit), offset: String((page - 1) * limit) });
  if (tag) q.set("tag", tag);
  return read<{ total: number; items: PersRef[] }>(`/public/publications?${q}`);
}

export function getArticle(slug: string) {
  return read<PersArticle>(`/public/publications/${encodeURIComponent(slug)}`);
}

export function dateLabel(iso: string): string {
  return new Date(iso).toLocaleDateString("id-ID", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Asia/Jakarta",
  });
}

/** Bagian tiap label dari konten yang bernilai sentimen; null bila tidak ada. */
export function share(labels: Record<string, number>, key: string, scored: number): string | null {
  if (scored <= 0) return null;
  return `${(((labels[key] ?? 0) / scored) * 100).toFixed(1).replace(".", ",")}%`;
}

/** Saran sitasi gaya APA sederhana; versi disebut bila artikel pernah diralat. */
export function citation(a: PersRef, url: string): string {
  const year = new Date(a.published_at).getUTCFullYear();
  const version = a.version > 1 ? ` (versi ${a.version})` : "";
  return `${a.author_name}. (${year}). ${a.title}${version}. ${url}`;
}

/** Nomor halaman dari query; apa pun yang bukan bilangan bulat positif menjadi 1. */
export function pageNumber(raw: string | string[] | undefined): number {
  const text = (Array.isArray(raw) ? raw[0] : raw) ?? "";
  return /^[1-9]\d{0,5}$/.test(text) ? Number(text) : 1;
}

/** Tanggal pendek untuk sumbu dan tabel harian: "11 Okt". */
export function dayLabel(iso: string): string {
  return new Date(`${iso.slice(0, 10)}T00:00:00Z`).toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

/** Alamat dasar situs dari header permintaan (di belakang proxy Vercel). */
export function originOf(h: { get(name: string): string | null }): string {
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "";
  const local = host.startsWith("localhost") || host.startsWith("127.0.0.1");
  return `${h.get("x-forwarded-proto") ?? (local ? "http" : "https")}://${host}`;
}
