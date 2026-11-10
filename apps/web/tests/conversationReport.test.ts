import { describe, expect, it } from "vitest";
import {
  clip,
  dayLabel,
  labelShares,
  mostNegativeDay,
  pct,
  rankTopics,
  type ReportDay,
  type ReportTopic,
} from "../app/(dashboard)/laporan/report";

const day = (d: string, negative_share: number | null): ReportDay => ({
  day: d,
  volume: 50,
  scored: 40,
  mean: negative_share === null ? null : -0.1,
  negative_share,
});

const topic = (id: string, n: number, engagement: number, source = "SOCIAL"): ReportTopic => ({
  topic_id: id,
  label: id,
  source: source as ReportTopic["source"],
  n,
  engagement,
  scored: 0,
  sentiment: null,
});

describe("labelShares", () => {
  it("membagi dengan konten bernilai, bukan seluruh konten", () => {
    const shares = labelShares({ negatif: 6, netral: 3, positif: 1, "tidak dinilai": 90 });
    expect(shares?.map((s) => [s.label, s.share])).toEqual([
      ["negatif", 0.6],
      ["netral", 0.3],
      ["positif", 0.1],
    ]);
  });
  it("null bila tidak ada yang bernilai", () => {
    expect(labelShares({ "tidak dinilai": 5 })).toBeNull();
    expect(labelShares({})).toBeNull();
  });
});

describe("mostNegativeDay", () => {
  it("melewati hari yang datanya ditahan", () => {
    const days = [day("2026-10-11", null), day("2026-10-12", 0.4), day("2026-10-13", 0.7)];
    expect(mostNegativeDay(days)?.day).toBe("2026-10-13");
    expect(mostNegativeDay([day("2026-10-11", null)])).toBeNull();
  });
});

describe("rankTopics", () => {
  it("memisahkan urutan volume dan urutan interaksi per sumber", () => {
    const topics = [topic("a", 100, 10), topic("b", 20, 900), topic("m", 500, 0, "MEDIA")];
    const r = rankTopics(topics, "SOCIAL");
    expect(r.byVolume.map((t) => t.topic_id)).toEqual(["a", "b"]);
    expect(r.byEngagement.map((t) => t.topic_id)).toEqual(["b", "a"]);
    expect(r.differs).toBe(true);
    const media = rankTopics(topics, "MEDIA");
    expect(media.byEngagement).toEqual([]);
    expect(media.differs).toBe(false);
  });
});

describe("format", () => {
  it("tanggal, persen, potongan teks", () => {
    expect(dayLabel("2026-10-15")).toBe("15 Okt 2026");
    expect(dayLabel("bukan tanggal")).toBe("bukan tanggal");
    expect(pct(0.4567)).toBe("45,7%");
    expect(clip("a  b\n c", 10)).toBe("a b c");
    expect(clip("x".repeat(20), 10)).toHaveLength(10);
  });
});
