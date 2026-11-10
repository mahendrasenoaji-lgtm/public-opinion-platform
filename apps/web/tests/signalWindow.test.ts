import { describe, expect, it } from "vitest";
import {
  heatOpacity,
  hourLabel,
  parseWindow,
  windowQuery,
} from "@/app/(dashboard)/sinyal/window";

describe("parseWindow", () => {
  it("tanpa parameter memakai jendela bawaan dan WIB", () => {
    expect(parseWindow({})).toEqual({ start: null, end: null, zone: "WIB", error: null });
  });

  it("menerima periode tetap dan zona", () => {
    const win = parseWindow({ dari: "2026-10-11", sampai: "2026-10-20", zona: "wita" });
    expect(win).toEqual({ start: "2026-10-11", end: "2026-10-20", zone: "WITA", error: null });
  });

  it("satu tanggal saja ditolak dengan alasan, zona tetap dipakai", () => {
    const win = parseWindow({ dari: "2026-10-11", zona: "WIT" });
    expect(win.start).toBeNull();
    expect(win.zone).toBe("WIT");
    expect(win.error).toMatch(/kedua tanggal/);
  });

  it("tanggal terbalik, tidak nyata, atau terlalu panjang ditolak", () => {
    expect(parseWindow({ dari: "2026-10-20", sampai: "2026-10-11" }).error).toMatch(/lebih awal/);
    expect(parseWindow({ dari: "2026-02-30", sampai: "2026-03-01" }).error).toMatch(/tidak dikenali/);
    expect(parseWindow({ dari: "2025-01-01", sampai: "2026-10-11" }).error).toMatch(/366/);
  });

  it("zona asing jatuh ke WIB, parameter berulang ambil yang pertama", () => {
    const win = parseWindow({ zona: "GMT", dari: ["2026-10-11", "x"], sampai: "2026-10-11" });
    expect(win.zone).toBe("WIB");
    expect(win.start).toBe("2026-10-11");
  });
});

describe("windowQuery", () => {
  it("kosong bila jendela bawaan", () => {
    expect(windowQuery(parseWindow({}))).toBe("");
  });

  it("menyertakan start/end dan parameter tambahan", () => {
    const win = parseWindow({ dari: "2026-10-11", sampai: "2026-10-20" });
    expect(windowQuery(win, { source: "SOCIAL" })).toBe(
      "?source=SOCIAL&start=2026-10-11&end=2026-10-20",
    );
  });
});

describe("tampilan jam", () => {
  it("label jam dua digit", () => {
    expect(hourLabel(9)).toBe("09.00");
    expect(hourLabel(23)).toBe("23.00");
  });

  it("sel kosong transparan, sel terisi selalu terlihat", () => {
    expect(heatOpacity(0, 10)).toBe(0);
    expect(heatOpacity(1, 1000)).toBeGreaterThanOrEqual(0.12);
    expect(heatOpacity(10, 10)).toBe(1);
  });
});
