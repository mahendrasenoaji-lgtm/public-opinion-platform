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

/* ------------------------------------------------------ situs web resmi */

export interface SiteItemIn {
  url: string;
  title: string | null;
  published_at: string;
  category: string | null;
}

export interface Site {
  id: string;
  subject: string;
  base_url: string;
  feed_kind: "rss" | "sitemap" | "halaman" | "none";
  source_url: string | null;
  list_urls: string[];
  check_notes: string[];
  checked_at: string | null;
  last_captured_at: string | null;
  n_total: number;
  n_window: number;
  n_30: number;
  last_published: string | null;
  days_since_last: number | null;
  longest_gap_days: number | null;
  median_gap_days: number | null;
  active_days: number;
  weeks_without: number;
  quiet: boolean;
  status: string;
  weeks: { start: string; n: number }[];
  categories: [string, string, number][];
  origins: Record<string, number>;
  latest: { url: string; title: string | null; published_at: string; category: string; origin: string }[];
}

export interface Sites {
  method: string;
  window_days: number;
  quiet_days: number;
  today: string;
  sites: Site[];
  limitations: string[];
}

export interface SiteReadResult {
  site_id: string;
  feed_kind: string;
  source_url: string | null;
  notes: string[];
  n_requests: number;
  result: { received: number; stored: number; updated: number };
}

export const FEED_KIND_LABEL: Record<string, string> = {
  rss: "Feed RSS/Atom",
  sitemap: "Sitemap bertanggal",
  halaman: "Halaman daftar berita",
  none: "Belum terbaca",
};

export const SITE_CSV_TEMPLATE =
  "url,title,published_at,category\n" +
  "https://lembaga.go.id/siaran-pers/contoh,Judul siaran pers,2026-11-10,siaran_pers\n";

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;
const DMY = /^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/;

/** `2026-11-10`, `10/11/2026`, atau cap waktu ISO menjadi nilai untuk API. */
export function normalizeDate(raw: string): string | null {
  const v = raw.trim();
  if (DATE_ONLY.test(v)) return v;
  const m = DMY.exec(v);
  if (m) {
    const [d, mo, y] = [m[1] ?? "", m[2] ?? "", m[3] ?? ""];
    if (Number(mo) < 1 || Number(mo) > 12 || Number(d) < 1 || Number(d) > 31) return null;
    return `${y}-${mo.padStart(2, "0")}-${d.padStart(2, "0")}`;
  }
  return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v) && !Number.isNaN(Date.parse(v)) ? v : null;
}

/**
 * Baris CSV (sudah dipecah) menjadi butir situs. Kolom wajib: `url`,
 * `published_at`. Melempar Error berbahasa Indonesia yang menyebut barisnya.
 */
export function siteItemsFromRows(rows: string[][]): SiteItemIn[] {
  const [header = [], ...body] = rows;
  const cols = header.map((h) => h.trim().toLowerCase());
  const at = (name: string) => cols.indexOf(name);
  const [iUrl, iDate, iTitle, iCat] = [at("url"), at("published_at"), at("title"), at("category")];
  if (iUrl < 0 || iDate < 0) throw new Error("Kepala kolom harus memuat url dan published_at.");
  const items: SiteItemIn[] = [];
  body.forEach((row, i) => {
    if (row.every((c) => c.trim() === "")) return;
    const url = (row[iUrl] ?? "").trim();
    const date = normalizeDate(row[iDate] ?? "");
    if (!/^https?:\/\//i.test(url)) throw new Error(`Baris ${i + 2}: url harus diawali http:// atau https://.`);
    if (!date) throw new Error(`Baris ${i + 2}: tanggal tidak terbaca (pakai 2026-11-10 atau 10/11/2026).`);
    items.push({
      url,
      title: iTitle >= 0 ? (row[iTitle] ?? "").trim() || null : null,
      published_at: date,
      category: iCat >= 0 ? (row[iCat] ?? "").trim() || null : null,
    });
  });
  if (items.length === 0) throw new Error("Berkas tidak memuat baris data.");
  return items;
}

/** Isi kotak teks (satu alamat per baris) menjadi daftar alamat. */
export function linesToUrls(raw: string): string[] {
  return raw
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l !== "");
}

export const ORIGIN_LABEL: Record<string, string> = {
  rss: "feed RSS",
  sitemap: "sitemap",
  halaman: "halaman daftar",
  manual: "unggahan manual",
};
