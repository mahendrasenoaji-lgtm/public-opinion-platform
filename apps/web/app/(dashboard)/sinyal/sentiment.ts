import type { Metric } from "@/lib/api";

/** Sumber yang punya penilai sentimen. SURVEY/DIGITAL tidak melewati jalur ini. */
export type SentimentSource = "SOCIAL" | "MEDIA";

export const SENTIMENT_LIMITS: Record<SentimentSource, string> = {
  SOCIAL:
    "Self-selected. Nada teks dari yang menulis, bukan sikap publik terhadap kebijakan.",
  MEDIA: "Nada judul dan ringkasan liputan — agenda redaksi, bukan opini pembaca.",
};

interface SummaryLike {
  volume: Metric;
  sentiment: Metric;
}

/**
 * Kartu sentimen yang layak ditampilkan: satu per sumber yang benar-benar
 * punya konten. Sumber tanpa konten tidak diberi kartu "data tidak cukup" —
 * proyek yang hanya memantau media tidak perlu kartu sosial kosong.
 */
export function sentimentCards(
  bySource: Record<SentimentSource, SummaryLike | null>,
): { source: SentimentSource; metric: Metric }[] {
  return (["SOCIAL", "MEDIA"] as const).flatMap((source) => {
    const summary = bySource[source];
    if (!summary || (summary.volume.value ?? 0) <= 0) return [];
    return [{ source, metric: summary.sentiment }];
  });
}

/** "+0.12", "-0.47", "0.00" — tanda plus eksplisit supaya arah terbaca sekilas. */
export function formatSentiment(value: number): string {
  const text = value.toFixed(2);
  if (text === "-0.00") return "0.00";
  return value > 0 && text !== "0.00" ? `+${text}` : text;
}
