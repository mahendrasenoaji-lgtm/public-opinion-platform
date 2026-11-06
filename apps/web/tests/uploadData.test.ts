import { describe, expect, it } from "vitest";
import { parseUpload } from "@/lib/uploadParse";

const item = { external_id: "a", text: "antre bbm", published_at: "2026-10-12T01:00:00Z" };

describe("parseUpload", () => {
  it("menerima larik polos dengan bawaan manual/SOCIAL", () => {
    const p = parseUpload(JSON.stringify([item]));
    expect(p).toEqual({ connector: "manual", source: "SOCIAL", items: [item] });
  });

  it("membaca connector dan source dari objek", () => {
    const p = parseUpload(JSON.stringify({ connector: "youtube_api", source: "SOCIAL", items: [item] }));
    expect(p.connector).toBe("youtube_api");
  });

  it("menolak items kosong, source asing, dan item tanpa field wajib", () => {
    expect(() => parseUpload("[]")).toThrow(/items/);
    expect(() => parseUpload(JSON.stringify({ source: "SURVEY", items: [item] }))).toThrow(/source/);
    expect(() => parseUpload(JSON.stringify([{ text: "x" }]))).toThrow(/ke-1/);
  });
});
