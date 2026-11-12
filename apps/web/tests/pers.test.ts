import { describe, expect, it } from "vitest";
import { parseInline, parseMarkdown } from "@/lib/miniMarkdown";
import { citation, share } from "@/lib/pers";

describe("parseMarkdown", () => {
  it("mengenali subjudul, paragraf, dan daftar", () => {
    const blocks = parseMarkdown("## Temuan\n\nBaris satu\nbaris dua.\n\n- a\n- **b** c\n\n### Catatan");
    expect(blocks.map((b) => b.type)).toEqual(["h2", "p", "ul", "h3"]);
    expect(blocks[1]).toEqual({ type: "p", inline: [{ text: "Baris satu baris dua.", bold: false }] });
    const list = blocks[2];
    expect(list?.type === "ul" && list.items.length).toBe(2);
  });

  it("markup HTML tetap teks biasa, tidak pernah menjadi elemen", () => {
    const blocks = parseMarkdown("<script>alert(1)</script>");
    expect(blocks).toEqual([{ type: "p", inline: [{ text: "<script>alert(1)</script>", bold: false }] }]);
  });

  it("isi kosong menghasilkan nol blok", () => {
    expect(parseMarkdown("  \n\n")).toEqual([]);
  });
});

describe("parseInline", () => {
  it("memisah teks tebal", () => {
    expect(parseInline("a **b** c")).toEqual([
      { text: "a ", bold: false },
      { text: "b", bold: true },
      { text: " c", bold: false },
    ]);
  });
});

describe("share", () => {
  it("persen dari konten bernilai, koma desimal", () => {
    expect(share({ negatif: 1 }, "negatif", 8)).toBe("12,5%");
    expect(share({}, "positif", 8)).toBe("0,0%");
  });
  it("tanpa konten bernilai: null, bukan 0%", () => {
    expect(share({}, "negatif", 0)).toBeNull();
  });
});

describe("citation", () => {
  const ref = { slug: "s", title: "Judul", summary: "", tags: [], author_name: "Tim", published_at: "2026-11-13T00:00:00Z", version: 1 };
  it("menyebut versi hanya bila pernah diralat", () => {
    expect(citation(ref, "https://x/pers/s")).toBe("Tim. (2026). Judul. https://x/pers/s");
    expect(citation({ ...ref, version: 2 }, "u")).toContain("Judul (versi 2).");
  });
});
