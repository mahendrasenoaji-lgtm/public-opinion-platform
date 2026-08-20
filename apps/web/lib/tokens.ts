/**
 * Sumber tunggal token desain.
 *
 * Aturan R1 (CLAUDE.md): warna menandai sumber data, bukan estetika. Jangan
 * memakai warna sumber untuk hal lain, dan jangan menambah sumber baru di sini
 * tanpa menambah enum SignalSource di backend.
 */

export const SOURCE = {
  SURVEY: { color: "#4DA3FF", label: "SURVEI", meaning: "Dapat digeneralisasi ke populasi" },
  SOCIAL: { color: "#FF7A45", label: "SOSIAL", meaning: "Self-selected, tidak representatif" },
  MEDIA:  { color: "#9B8AFB", label: "MEDIA",  meaning: "Agenda redaksi, bukan opini pembaca" },
  DIGITAL:{ color: "#5FD4C4", label: "DIGITAL", meaning: "Perilaku terukur, bukan pernyataan" },
} as const;

export type SignalSource = keyof typeof SOURCE;

export const SURFACE = {
  ink: "#0A1017",
  panel: "#0F1720",
  panel2: "#131D28",
  line: "#1F2B3C",
  text: "#E6EDF6",
  text2: "#8FA0B5",
  text3: "#5C6E85",
  /** Executive brief dibalik: halaman itu untuk dibaca dan dicetak. */
  paper: "#F2EFE9",
  paperLine: "#DDD7CC",
  paperText: "#1A1D21",
} as const;

export const STATUS = {
  positive: "#2FBF71",
  warning: "#F5B301",
  negative: "#EF4B4B",
} as const;

/** Ramp risiko 0–100, sejalan dengan RISK_BANDS di services/risk.py */
export const RISK_RAMP = ["#2FBF71", "#7FB45C", "#F5B301", "#EF8A3C", "#EF4B4B"] as const;

export function riskColor(score: number): string {
  return RISK_RAMP[Math.min(4, Math.floor(score / 20))];
}

export const TYPE = {
  display: "'Archivo', system-ui, sans-serif",
  body: "'IBM Plex Sans', system-ui, sans-serif",
  utility: "'IBM Plex Mono', monospace",
} as const;

/** Ambang publikasi. Harus sama dengan MIN_EFFECTIVE_N di services/poi.py */
export const MIN_EFFECTIVE_N = 250;
