import { describe, expect, it } from "vitest";
import { alphaLabel, coderSlot, hoursLabel, stampToIso } from "@/app/(dashboard)/kinerja/analisis/analisis";

describe("stampToIso", () => {
  it("menambah zona pada nilai datetime-local", () => {
    expect(stampToIso("2026-10-01T08:30", "WIB")).toBe("2026-10-01T08:30:00+07:00");
    expect(stampToIso("2026-10-01T08:30:15", "WIT")).toBe("2026-10-01T08:30:00+09:00");
  });
  it("kosong atau bentuk lain tetap kosong", () => {
    expect(stampToIso("", "WIB")).toBeNull();
    expect(stampToIso("kemarin", "WIB")).toBeNull();
  });
});

describe("hoursLabel", () => {
  it("jam di bawah dua hari, hari di atasnya", () => {
    expect(hoursLabel(6)).toBe("6 jam");
    expect(hoursLabel(1.5)).toBe("1,5 jam");
    expect(hoursLabel(51)).toBe("2 hari 3 jam");
    expect(hoursLabel(72)).toBe("3 hari");
  });
  it("tidak mengarang angka untuk yang kosong", () => {
    expect(hoursLabel(null)).toBe("tidak tercatat");
    expect(hoursLabel(undefined)).toBe("tidak tercatat");
  });
});

describe("alphaLabel dan coderSlot", () => {
  it("alpha tiga desimal berkoma", () => {
    expect(alphaLabel(0.8)).toBe("0,800");
    expect(alphaLabel(null)).toBe("—");
  });
  it("lembar selain 2 jatuh ke 1", () => {
    expect(coderSlot("2")).toBe(2);
    expect(coderSlot("3")).toBe(1);
    expect(coderSlot("")).toBe(1);
  });
});

import { normalizeDate, siteItemsFromRows } from "@/app/(dashboard)/kinerja/analisis/analisis";

describe("butir situs dari CSV", () => {
  it("menerima tanggal ISO dan hari/bulan/tahun", () => {
    expect(normalizeDate("2026-11-10")).toBe("2026-11-10");
    expect(normalizeDate("5/11/2026")).toBe("2026-11-05");
    expect(normalizeDate("2026-11-10T08:00:00+07:00")).toBe("2026-11-10T08:00:00+07:00");
    expect(normalizeDate("10 November 2026")).toBeNull();
    expect(normalizeDate("32/13/2026")).toBeNull();
  });
  it("membaca kolom menurut kepala, bukan urutan", () => {
    const items = siteItemsFromRows([
      ["Published_At", "URL", "title"],
      ["10/11/2026", "https://x.go.id/berita/a", " Judul "],
      ["", "", ""],
    ]);
    expect(items).toEqual([
      { url: "https://x.go.id/berita/a", title: "Judul", published_at: "2026-11-10", category: null },
    ]);
  });
  it("menyebut baris yang salah", () => {
    expect(() => siteItemsFromRows([["url", "published_at"], ["x.go.id/a", "2026-11-10"]])).toThrow("Baris 2");
    expect(() => siteItemsFromRows([["url", "published_at"], ["https://x.go.id/a", "kemarin"]])).toThrow("tanggal");
    expect(() => siteItemsFromRows([["url"], ["https://x.go.id/a"]])).toThrow("published_at");
    expect(() => siteItemsFromRows([["url", "published_at"]])).toThrow("tidak memuat");
  });
});
