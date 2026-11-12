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

export interface PersSource {
  source: string;
  n: number;
  scored: number;
  labels: Record<string, number>;
  words?: [string, number][];
  hashtags?: [string, number][];
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

export function listArticles(tag?: string) {
  const q = new URLSearchParams({ limit: "50" });
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
