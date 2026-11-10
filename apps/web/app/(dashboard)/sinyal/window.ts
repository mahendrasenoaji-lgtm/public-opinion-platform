/**
 * Periode dan zona waktu halaman Sinyal, dibaca dari query URL
 * (`?dari=2026-10-11&sampai=2026-10-20&zona=WITA`).
 *
 * Tanpa `dari`/`sampai`, backend memakai jendela relatif 30 hari. Jendela
 * mutlak dibutuhkan untuk data historis (mis. proyek BBM Bali, 11-20 Okt):
 * tanpa itu datanya hilang dari tampilan begitu lewat 30 hari.
 */

export const ZONES = ["WIB", "WITA", "WIT"] as const;
export type Zone = (typeof ZONES)[number];

export interface SignalWindow {
  /** Keduanya terisi atau keduanya null. */
  start: string | null;
  end: string | null;
  zone: Zone;
  /** Alasan periode yang diminta diabaikan; null bila tidak ada masalah. */
  error: string | null;
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const MAX_DAYS = 366;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

function isRealDate(text: string): boolean {
  if (!ISO_DATE.test(text)) return false;
  const d = new Date(`${text}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === text;
}

export function parseWindow(
  params: Record<string, string | string[] | undefined>,
): SignalWindow {
  const zoneRaw = first(params.zona).toUpperCase();
  const zone: Zone = (ZONES as readonly string[]).includes(zoneRaw) ? (zoneRaw as Zone) : "WIB";
  const start = first(params.dari);
  const end = first(params.sampai);
  const none = { start: null, end: null, zone };

  if (!start && !end) return { ...none, error: null };
  if (!start || !end) {
    return { ...none, error: "Isi kedua tanggal (dari dan sampai) untuk memakai periode tetap." };
  }
  if (!isRealDate(start) || !isRealDate(end)) {
    return { ...none, error: "Tanggal tidak dikenali. Format: TTTT-BB-HH." };
  }
  if (end < start) {
    return { ...none, error: "Tanggal akhir lebih awal daripada tanggal mulai." };
  }
  const days = (Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86_400_000 + 1;
  if (days > MAX_DAYS) {
    return { ...none, error: `Periode paling panjang ${MAX_DAYS} hari.` };
  }
  return { start, end, zone, error: null };
}

/** Query untuk endpoint agregat; `extra` ditambahkan apa adanya. */
export function windowQuery(win: SignalWindow, extra: Record<string, string> = {}): string {
  const q = new URLSearchParams(extra);
  if (win.start && win.end) {
    q.set("start", win.start);
    q.set("end", win.end);
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

/** Urutan tampil dan label Indonesia untuk kunci emosi dari API. */
export const EMOTION_LABELS: [key: string, label: string][] = [
  ["anger", "Marah"],
  ["fear", "Takut"],
  ["sadness", "Sedih"],
  ["disgust", "Jijik"],
  ["joy", "Senang"],
  ["trust", "Percaya"],
];

/** "09.00", jam lokal dua digit. */
export function hourLabel(hour: number): string {
  return `${String(hour).padStart(2, "0")}.00`;
}

/** Opasitas sel peta jam: 0 untuk kosong, minimal terlihat untuk yang berisi. */
export function heatOpacity(count: number, max: number): number {
  if (count <= 0 || max <= 0) return 0;
  return Math.round((0.12 + 0.88 * (count / max)) * 100) / 100;
}
