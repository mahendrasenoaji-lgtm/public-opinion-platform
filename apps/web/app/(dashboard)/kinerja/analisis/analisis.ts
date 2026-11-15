/**
 * Tipe dan pembantu murni halaman Analisis isi & arus informasi.
 * Kontrak API: apps/api/app/routers/comm_coding.py.
 */

export interface Variable {
  code: string;
  name: string;
  level: "nominal" | "ordinal";
  values: [number, string][];
}

export interface CodingRow {
  post_id: string;
  platform: string;
  account: string;
  posted_at: string;
  url: string | null;
  kind: string | null;
  caption: string | null;
  codes: Record<string, number>;
  note: string;
  coded: boolean;
  coded_by_other: boolean;
}

export interface CodingList {
  coder: number;
  total: number;
  n_coded: number;
  variables: Variable[];
  accounts: string[];
  items: CodingRow[];
}

export interface Reliability {
  method: string;
  n_posts: number;
  n_coded: number;
  n_double_coded: number;
  n_coders: number;
  double_share: number;
  target_double_share: number;
  meets_target: boolean;
  variables: {
    code: string;
    name: string;
    level: string;
    n_double_coded: number;
    alpha: number | null;
    label: string;
    percent_agreement: number | null;
  }[];
  distributions: {
    code: string;
    name: string;
    n: number;
    published: boolean;
    tested: boolean;
    counts: [number, string, number][];
  }[];
  limitations: string[];
}

export const FLOW_STAMPS = [
  ["requested_at", "Bahan diminta"],
  ["received_at", "Bahan diterima"],
  ["verified_at", "Terverifikasi"],
  ["drafted_at", "Draf selesai"],
  ["approved_at", "Disetujui"],
  ["published_at", "Terbit"],
] as const;

export type FlowStamp = (typeof FLOW_STAMPS)[number][0];

export interface FlowRow extends Record<FlowStamp, string | null> {
  id: string;
  subject: string;
  label: string;
  kind: "rutin" | "klarifikasi";
  bottleneck_stage: number | null;
  note: string;
  hours: Record<string, number | null>;
}

export interface Flow {
  method: string;
  subjects: string[];
  n_records: number;
  min_records: number;
  intervals: {
    code: string;
    meaning: string;
    stages: number[];
    n: number;
    median_hours: number | null;
    max_hours: number | null;
  }[];
  slowest: string | null;
  stages: { stage: number; name: string; n_bottleneck: number }[];
  records: FlowRow[];
  limitations: string[];
}

export const ALIGNMENT_LABEL: Record<string, string> = {
  selaras: "Selaras",
  beda_penekanan: "Berbeda penekanan",
  bertentangan: "Bertentangan",
};

export interface AlignmentRow {
  id: string;
  issue: string;
  subject_a: string;
  url_a: string | null;
  subject_b: string;
  url_b: string | null;
  coder: number;
  code: keyof typeof ALIGNMENT_LABEL;
  corrected: boolean;
  note: string;
}

export interface Alignment {
  method: string;
  n_pairs: number;
  counts: Record<string, number>;
  n_contradiction_open: number;
  suggested_score: number | null;
  min_pairs: number;
  n_double_coded: number;
  alpha: number | null;
  alpha_label: string;
  items: AlignmentRow[];
  limitations: string[];
}

export interface ResponseTime {
  method: string;
  account: string;
  period_start: string;
  period_end: string;
  timezone: string;
  n_days: number;
  n_official_posts: number;
  median_daily_volume: number;
  spikes: {
    day: string;
    volume: number;
    ratio: number;
    hours: number | null;
    first_post_at: string | null;
  }[];
  median_hours: number | null;
  n_unanswered: number;
  suggested_score: number | null;
  limitations: string[];
}

export interface ResponseRate {
  method: string;
  account: string;
  n_videos: number;
  n_videos_skipped: number;
  n_comments: number;
  n_questions: number;
  n_answered: number;
  n_uncertain: number;
  rate_pct: number | null;
  suggested_score: number | null;
  min_questions: number;
  quota_units: number;
  limitations: string[];
}

const ZONE_OFFSET = { WIB: "+07:00", WITA: "+08:00", WIT: "+09:00" } as const;
export type Zone = keyof typeof ZONE_OFFSET;

/**
 * Nilai `<input type="datetime-local">` menjadi cap waktu berzona. Kosong
 * atau bentuk lain menjadi null: cap waktu yang tidak diisi tetap kosong.
 */
export function stampToIso(local: string, zone: Zone): string | null {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})(?::\d{2})?$/.exec(local.trim());
  return m ? `${m[1]}T${m[2]}:00${ZONE_OFFSET[zone]}` : null;
}

/** "6 jam", "1,5 jam", "2 hari 3 jam"; null menjadi "tidak tercatat". */
export function hoursLabel(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return "tidak tercatat";
  if (hours < 48) return `${String(Math.round(hours * 10) / 10).replace(".", ",")} jam`;
  const days = Math.floor(hours / 24);
  const rest = Math.round(hours - days * 24);
  return rest > 0 ? `${days} hari ${rest} jam` : `${days} hari`;
}

/** Alpha tiga desimal dengan koma; null menjadi tanda pisah. */
export function alphaLabel(alpha: number | null): string {
  return alpha === null ? "—" : alpha.toFixed(3).replace(".", ",");
}

/** Lembar pengode dari query: hanya 1 atau 2. */
export function coderSlot(raw: string): 1 | 2 {
  return raw === "2" ? 2 : 1;
}
