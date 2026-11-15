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
