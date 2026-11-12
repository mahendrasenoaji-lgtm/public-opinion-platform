import { describe, expect, it } from "vitest";
import { nextSteps, parseTags } from "@/app/(dashboard)/publikasi/publikasi";

describe("parseTags", () => {
  it("memisah dengan koma dan membuang yang kosong", () => {
    expect(parseTags(" kebijakan, Energi BBM ,, ")).toEqual(["kebijakan", "Energi BBM"]);
    expect(parseTags("")).toEqual([]);
  });
});

describe("nextSteps", () => {
  it("draf hanya bisa diajukan untuk ditinjau", () => {
    expect(nextSteps("draft", true)).toEqual(["review"]);
  });
  it("hanya penerbit yang ditawari tombol terbit", () => {
    expect(nextSteps("review", true)).toEqual(["published", "draft"]);
    expect(nextSteps("review", false)).toEqual(["draft"]);
  });
  it("artikel terbit tidak punya langkah berikutnya", () => {
    expect(nextSteps("published", true)).toEqual([]);
  });
});
