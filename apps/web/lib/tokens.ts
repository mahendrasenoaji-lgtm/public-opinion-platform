/**
 * Sumber tunggal token desain.
 *
 * Aturan R1 (CLAUDE.md): warna menandai sumber data, bukan estetika. Jangan
 * memakai warna sumber untuk hal lain, dan jangan menambah sumber baru di sini
 * tanpa menambah enum SignalSource di backend.
 *
 * `color` sengaja mengembalikan `var(--...)`, BUKAN hex. Alasannya bukan gaya:
 * komponen menyuntikkan nilai ini ke `style={{}}` dan ke atribut SVG Recharts,
 * jadi selama ia hex, warna itu membeku di satu tema. Hex-nya dipindah ke
 * `hex`, yang hanya dipakai kalau ada konteks yang benar-benar tidak bisa
 * membaca CSS custom property (kanvas, ekspor gambar, e-mail).
 *
 * Nilai hex di bawah adalah nilai TEMA GELAP. Nilai tema terang hidup di
 * app/globals.css. Itu memang tidak ideal — dua tempat — tapi CSS custom
 * property tidak bisa dibaca dari server component, dan meletakkannya di sini
 * berarti setiap perubahan tema harus melewati bundel JS. Selama `color`
 * dipakai (yang berlaku di semua pemanggil hari ini), yang mengikat tetap
 * globals.css.
 */

export const SOURCE = {
  SURVEY: {
    color: "var(--survey)",
    hex: "#4DA3FF",
    label: "SURVEI",
    meaning: "Dapat digeneralisasi ke populasi",
  },
  SOCIAL: {
    color: "var(--social)",
    hex: "#FF7A45",
    label: "SOSIAL",
    meaning: "Self-selected, tidak representatif",
  },
  MEDIA: {
    color: "var(--media)",
    hex: "#9B8AFB",
    label: "MEDIA",
    meaning: "Agenda redaksi, bukan opini pembaca",
  },
  DIGITAL: {
    color: "var(--digital)",
    hex: "#5FD4C4",
    label: "DIGITAL",
    meaning: "Perilaku terukur, bukan pernyataan",
  },
} as const;

export type SignalSource = keyof typeof SOURCE;

export const SURFACE = {
  ink: "var(--ink)",
  panel: "var(--panel)",
  panel2: "var(--panel2)",
  line: "var(--line)",
  text: "var(--txt)",
  text2: "var(--txt2)",
  text3: "var(--txt3)",
  /** Executive brief dibalik: halaman itu untuk dibaca dan dicetak. */
  paper: "var(--paper)",
  paperLine: "var(--paper-line)",
  paperText: "var(--paper-txt)",
} as const;

export const STATUS = {
  positive: "var(--pos)",
  warning: "var(--warn)",
  negative: "var(--neg)",
} as const;

/** Ramp risiko 0–100, sejalan dengan RISK_BANDS di services/risk.py */
export const RISK_RAMP = [
  "var(--risk-0)",
  "var(--risk-1)",
  "var(--risk-2)",
  "var(--risk-3)",
  "var(--risk-4)",
] as const;

export function riskColor(score: number): string {
  const band = Math.max(0, Math.min(4, Math.floor(score / 20)));
  return RISK_RAMP[band] ?? RISK_RAMP[0];
}

/**
 * Peringkat provinsi di GeoExplorer — ramp yang sama, arah terbalik (nilai
 * POI tinggi = baik). Ambangnya presentasi murni, bukan sumber R1.
 */
export function rankColor(value: number | null): string {
  if (value === null) return "var(--muted-fill)";
  if (value >= 75) return RISK_RAMP[0];
  if (value >= 70) return RISK_RAMP[1];
  if (value >= 66) return RISK_RAMP[2];
  if (value >= 63) return RISK_RAMP[3];
  return RISK_RAMP[4];
}

/** Ambang publikasi. Harus sama dengan MIN_EFFECTIVE_N di services/poi.py */
export const MIN_EFFECTIVE_N = 250;
