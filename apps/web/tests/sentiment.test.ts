import { describe, expect, it } from "vitest";
import { formatSentiment, sentimentCards } from "@/app/(dashboard)/sinyal/sentiment";
import type { Metric } from "@/lib/api";

function metric(value: number | null, source: Metric["source"]): Metric {
  return {
    key: "k",
    label: "l",
    value,
    unit: "u",
    source,
    method: "m",
    ci_low: null,
    ci_high: null,
    effective_n: 0,
    insufficient_data: value === null,
    note: null,
  };
}

const summary = (volume: number, sentiment: number | null, source: Metric["source"]) => ({
  volume: metric(volume, source),
  sentiment: metric(sentiment, source),
});

describe("sentimentCards", () => {
  it("satu kartu per sumber yang punya konten, sosial dulu", () => {
    const cards = sentimentCards({
      SOCIAL: summary(1599, -0.31, "SOCIAL"),
      MEDIA: summary(203, -0.47, "MEDIA"),
    });
    expect(cards.map((c) => [c.source, c.metric.value])).toEqual([
      ["SOCIAL", -0.31],
      ["MEDIA", -0.47],
    ]);
  });

  it("sumber tanpa konten tidak diberi kartu", () => {
    const cards = sentimentCards({
      SOCIAL: summary(0, null, "SOCIAL"),
      MEDIA: summary(64, -0.47, "MEDIA"),
    });
    expect(cards.map((c) => c.source)).toEqual(["MEDIA"]);
  });

  it("sumber yang ada kontennya tapi belum cukup tetap tampil sebagai data tidak cukup", () => {
    const cards = sentimentCards({ SOCIAL: summary(5, null, "SOCIAL"), MEDIA: null });
    expect(cards).toHaveLength(1);
    expect(cards[0]?.metric.value).toBeNull();
  });

  it("angka ragam berita ikut di kartu liputan, tidak pernah menggantikan angka utama", () => {
    const media = { ...summary(203, -0.2, "MEDIA"), sentiment_revised: metric(-0.35, "MEDIA") };
    const cards = sentimentCards({ SOCIAL: summary(10, null, "SOCIAL"), MEDIA: media });
    expect(cards.map((c) => [c.source, c.metric.value, c.revised?.value ?? null])).toEqual([
      ["SOCIAL", null, null],
      ["MEDIA", -0.2, -0.35],
    ]);
  });

  it("backend tidak menjawab: tidak ada kartu, bukan error", () => {
    expect(sentimentCards({ SOCIAL: null, MEDIA: null })).toEqual([]);
  });
});

describe("formatSentiment", () => {
  it("tanda plus eksplisit untuk positif", () => {
    expect(formatSentiment(0.123)).toBe("+0.12");
  });

  it("negatif apa adanya", () => {
    expect(formatSentiment(-0.468)).toBe("-0.47");
  });

  it("nol tidak diberi tanda, termasuk yang membulat ke nol", () => {
    expect(formatSentiment(0)).toBe("0.00");
    expect(formatSentiment(0.004)).toBe("0.00");
    expect(formatSentiment(-0.004)).toBe("0.00");
  });
});
