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

describe("parseMarkdown: tabel dan penanda", () => {
  it("tabel pipa dengan garis pemisah menjadi blok tabel; sel kurang diisi kosong", () => {
    const blocks = parseMarkdown("Pengantar.\n| A | B |\n|---|:--:|\n| 1 | **2** |\n| 3 |\nSesudah.");
    expect(blocks.map((b) => b.type)).toEqual(["p", "table", "p"]);
    const t = blocks[1];
    if (t?.type !== "table") throw new Error("bukan tabel");
    expect(t.head.map((c) => c[0]?.text)).toEqual(["A", "B"]);
    expect(t.rows[0]?.[1]).toEqual([{ text: "2", bold: true }]);
    expect(t.rows[1]?.[1]).toEqual([]);
  });

  it("baris berpipa tanpa garis pemisah dibaca sebagai paragraf", () => {
    expect(parseMarkdown("| bukan | tabel |").map((b) => b.type)).toEqual(["p"]);
  });

  it("penanda hanya dikenali sendirian di satu baris dan berhuruf kecil", () => {
    const blocks = parseMarkdown("[[grafik-harian]]\n\nlihat [[nada]] di sini\n\n[[Nada]]");
    expect(blocks[0]).toEqual({ type: "embed", name: "grafik-harian" });
    expect(blocks.slice(1).every((b) => b.type === "p")).toBe(true);
  });
});
