/** Tipe respons dan pembantu tampilan modul Kinerja Komunikasi. Fungsi murni. */

export interface Indicator {
  code: string;
  dimension: string;
  name: string;
  availability: "PUBLIC" | "ACCOUNT" | "INTERNAL" | "SURVEY";
  definition: string;
  rubric: string;
}

export interface Framework {
  model_version: string;
  disclaimer: string;
  dimensions: string[];
  weights: Record<string, number>;
  min_coverage: number;
  min_posts_for_median: number;
  indicators: Indicator[];
  document: string;
}

export interface AccountSummary {
  account: string;
  platform: string;
  n_posts: number;
  first_post: string;
  last_post: string;
  by_kind: Record<string, number>;
  posts_by_month: Record<string, number>;
  median_likes: number | null;
  median_comments: number | null;
  median_shares: number | null;
  median_views: number | null;
  median_engagement_rate: number | null;
  n_engagement_rate: number;
  insufficient_data: boolean;
}

export interface PostsSummary {
  source: string;
  method: string;
  n_posts: number;
  accounts: AccountSummary[];
  limitations: string[];
}

export interface ScoreItem {
  indicator: string;
  score: number | null;
  unavailable_reason: string | null;
  evidence: string;
  assessed_at: string | null;
}

export interface DimensionScore {
  dimension: string;
  score: number | null;
  coverage: number;
  n_available: number;
  n_total: number;
  published: boolean;
  weight: number;
}

export interface Scorecard {
  subject: string;
  period: string;
  method: string;
  model_version: string;
  disclaimer: string;
  dimensions: DimensionScore[];
  total: number | null;
  total_equal_weights: number | null;
  label: string | null;
  n_scored: number;
  n_unavailable: number;
  n_empty: number;
  items: ScoreItem[];
  limitations: string[];
}

export interface AssessmentRef {
  subject: string;
  period: string;
  n_scored: number;
  n_unavailable: number;
}

export const PLATFORM_LABEL: Record<string, string> = {
  instagram: "Instagram",
  tiktok: "TikTok",
  x: "X",
};

export const AVAILABILITY_LABEL: Record<Indicator["availability"], string> = {
  PUBLIC: "data publik",
  ACCOUNT: "insight pemilik akun",
  INTERNAL: "dokumen atau wawancara",
  SURVEY: "kuesioner",
};

const DIMENSION_LABEL: Record<string, string> = {
  INPUT: "Input",
  PROCESS: "Process",
  OUTPUT: "Output",
  OUTCOME: "Outcome",
};

export function dimensionLabel(d: string): string {
  return DIMENSION_LABEL[d] ?? d;
}

const NUM = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 });

/** Median yang ditahan atau tidak ada ditulis "tidak tersedia", tidak pernah 0. */
export function formatMedian(v: number | null): string {
  return v === null ? "tidak tersedia" : NUM.format(v);
}

export function formatScore(v: number): string {
  return v.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function coverageText(d: Pick<DimensionScore, "n_available" | "n_total" | "coverage">): string {
  return `${d.n_available} dari ${d.n_total} indikator (${Math.round(d.coverage * 100)}%)`;
}

/** Bulan berjalan sebagai YYYY-MM (zona peramban/server; hanya nilai awal formulir). */
export function currentPeriod(now: Date = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export const PERIOD_RE = /^[0-9]{4}-(0[1-9]|1[0-2])$/;
