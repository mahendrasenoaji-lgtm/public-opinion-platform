/**
 * Bentuk data dan hitungan kecil halaman Laporan Percakapan.
 * Semua fungsi murni supaya bisa dites tanpa server.
 */

import type { SignalSource } from "@/lib/api";

export interface ReportItem {
  text: string;
  engagement: number;
  published_at: string;
  source_url: string | null;
}

export interface ReportPeak {
  day: string;
  volume: number;
  ratio: number | null;
  is_spike: boolean;
  top_content: ReportItem[];
  same_day_media: ReportItem[];
}

export interface ReportDay {
  day: string;
  volume: number;
  scored: number;
  mean: number | null;
  negative_share: number | null;
}

export interface ReportSource {
  source: SignalSource;
  n: number;
  scored: number;
  labels: Record<string, number>;
  days: ReportDay[];
  peaks: ReportPeak[];
  words: [string, number][];
  hashtags: [string, number][];
  emoji: [string, number][];
}

export interface ReportTopic {
  topic_id: string;
  label: string;
  source: SignalSource;
  n: number;
  engagement: number;
  scored: number;
  sentiment: number | null;
}

export interface ConversationReport {
  period_start: string;
  period_end: string;
  timezone: string;
  sources: ReportSource[];
  outlets: { domain: string; n: number }[];
  outlets_total: number;
  topics: ReportTopic[];
  methods: Record<string, string>;
  limitations: string[];
}

export const LABEL_ORDER = ["negatif", "netral", "positif"] as const;

/** Porsi tiap label di antara konten BERNILAI; null bila tidak ada yang bernilai. */
export function labelShares(
  labels: Record<string, number>,
): { label: string; n: number; share: number }[] | null {
  const scored = LABEL_ORDER.reduce((sum, key) => sum + (labels[key] ?? 0), 0);
  if (scored <= 0) return null;
  return LABEL_ORDER.map((label) => {
    const n = labels[label] ?? 0;
    return { label, n, share: n / scored };
  });
}

/** Hari dengan porsi negatif tertinggi di antara hari yang cukup datanya. */
export function mostNegativeDay(days: ReportDay[]): ReportDay | null {
  let best: ReportDay | null = null;
  for (const day of days) {
    if (day.negative_share === null) continue;
    if (best === null || day.negative_share > (best.negative_share ?? 0)) best = day;
  }
  return best;
}

/**
 * Tema satu sumber dalam dua urutan: paling banyak dibicarakan dan paling
 * banyak interaksi. `differs` benar bila tema teratasnya tidak sama.
 */
export function rankTopics(
  topics: ReportTopic[],
  source: SignalSource,
  limit = 5,
): { byVolume: ReportTopic[]; byEngagement: ReportTopic[]; differs: boolean } {
  const own = topics.filter((t) => t.source === source);
  const byVolume = [...own].sort((a, b) => b.n - a.n).slice(0, limit);
  const byEngagement = [...own]
    .filter((t) => t.engagement > 0)
    .sort((a, b) => b.engagement - a.engagement)
    .slice(0, limit);
  const differs =
    byVolume.length > 0 &&
    byEngagement.length > 0 &&
    byVolume[0]?.topic_id !== byEngagement[0]?.topic_id;
  return { byVolume, byEngagement, differs };
}

/** "15 Okt 2026" dari "2026-10-15"; teks asli bila tidak dikenali. */
export function dayLabel(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function pct(share: number, digits = 1): string {
  return `${(share * 100).toFixed(digits).replace(".", ",")}%`;
}

export function clip(text: string, max = 180): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > max ? `${flat.slice(0, max - 1).trimEnd()}…` : flat;
}
