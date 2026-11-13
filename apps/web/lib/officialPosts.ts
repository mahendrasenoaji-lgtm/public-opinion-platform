/**
 * Pembaca berkas unggahan akun resmi (JSON atau CSV) untuk modul Kinerja
 * Komunikasi. Fungsi murni: tidak menyentuh jaringan maupun DOM.
 *
 * Angka yang kosong di berkas tetap kosong (`null`), tidak dijadikan nol:
 * "tidak tampil" dan "nol" adalah dua hal berbeda di platform ini.
 */

export const PLATFORMS = ["instagram", "tiktok", "x"] as const;
export type Platform = (typeof PLATFORMS)[number];

export const COUNT_FIELDS = [
  "likes",
  "comments",
  "shares",
  "views",
  "saves",
  "reach",
  "impressions",
  "followers",
] as const;
type CountField = (typeof COUNT_FIELDS)[number];

export type OfficialPostIn = {
  platform: Platform;
  account: string;
  external_id: string;
  posted_at: string;
  url?: string | null;
  kind?: string | null;
  caption?: string | null;
  captured_at?: string | null;
} & Partial<Record<CountField, number | null>>;

const TEXT_FIELDS = ["url", "kind", "caption", "captured_at"] as const;

/** Pemecah CSV kecil: koma atau titik koma, tanda kutip ganda, baris baru di dalam kutip. */
export function parseCsv(raw: string): string[][] {
  const text = raw.replace(/^﻿/, "");
  const firstLine = text.split(/\r?\n/, 1)[0] ?? "";
  const sep = firstLine.split(";").length > firstLine.split(",").length ? ";" : ",";
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === sep) {
      row.push(cell);
      cell = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell);
      cell = "";
      rows.push(row);
      row = [];
    } else cell += ch;
  }
  if (cell !== "" || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }
  return rows.filter((r) => r.some((c) => c.trim() !== ""));
}

function toCount(value: unknown, field: string, n: number): number | null {
  if (value === null || value === undefined) return null;
  const s = String(value).trim();
  if (s === "" || s === "-") return null;
  if (!/^\d+$/.test(s)) {
    throw new Error(`Baris ke-${n}: \`${field}\` harus bilangan bulat tidak negatif, bukan "${s}".`);
  }
  return Number(s);
}

function toPost(r: Record<string, unknown>, n: number, fallbackAccount?: string): OfficialPostIn {
  const platform = String(r.platform ?? "").trim().toLowerCase();
  if (!(PLATFORMS as readonly string[]).includes(platform)) {
    throw new Error(`Baris ke-${n}: \`platform\` harus instagram, tiktok, atau x.`);
  }
  const account = String(r.account ?? fallbackAccount ?? "").trim();
  const external_id = String(r.external_id ?? "").trim();
  const posted_at = String(r.posted_at ?? "").trim();
  if (!account || !external_id || !posted_at) {
    throw new Error(`Baris ke-${n} tidak punya account, external_id, atau posted_at.`);
  }
  if (Number.isNaN(Date.parse(posted_at))) {
    throw new Error(`Baris ke-${n}: \`posted_at\` bukan tanggal yang terbaca ("${posted_at}").`);
  }
  const post: OfficialPostIn = { platform: platform as Platform, account, external_id, posted_at };
  for (const f of TEXT_FIELDS) {
    const v = r[f];
    if (v !== null && v !== undefined && String(v).trim() !== "") post[f] = String(v).trim();
  }
  for (const f of COUNT_FIELDS) {
    const v = toCount(r[f], f, n);
    if (v !== null) post[f] = v;
  }
  return post;
}

/**
 * Terima JSON (larik, atau `{ account?, items: [...] }`) atau CSV berkepala.
 * Kolom wajib: platform, account, external_id, posted_at.
 */
export function parseOfficialPosts(raw: string): OfficialPostIn[] {
  const trimmed = raw.replace(/^﻿/, "").trim();
  if (trimmed === "") throw new Error("Berkas kosong.");

  if (trimmed.startsWith("[") || trimmed.startsWith("{")) {
    const data: unknown = JSON.parse(trimmed);
    const obj = (Array.isArray(data) ? { items: data } : data) as Record<string, unknown>;
    if (!Array.isArray(obj.items) || obj.items.length === 0) {
      throw new Error("Berkas harus berisi larik `items` yang tidak kosong.");
    }
    const account = typeof obj.account === "string" ? obj.account : undefined;
    return obj.items.map((it, i) => toPost(it as Record<string, unknown>, i + 1, account));
  }

  const [header = [], ...rows] = parseCsv(trimmed);
  const cols = header.map((h) => h.trim().toLowerCase());
  for (const required of ["platform", "account", "external_id", "posted_at"]) {
    if (!cols.includes(required)) throw new Error(`CSV tidak punya kolom \`${required}\`.`);
  }
  if (rows.length === 0) throw new Error("CSV tidak punya baris data.");
  return rows.map((cells, i) =>
    toPost(Object.fromEntries(cols.map((c, j) => [c, cells[j] ?? ""])), i + 2),
  );
}
