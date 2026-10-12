import { afterEach, describe, expect, it, vi } from "vitest";
import { COOKIE_MAX_AGE, createToken, siteGateEnabled, verifyToken } from "@/lib/auth";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
});

describe("token gerbang situs", () => {
  it("token yang baru dibuat lolos dengan rahasia yang sama", async () => {
    expect(await verifyToken("rahasia", await createToken("rahasia"))).toBe(true);
  });

  it("ditolak dengan rahasia lain", async () => {
    expect(await verifyToken("lain", await createToken("rahasia"))).toBe(false);
  });

  it("ditolak bila waktunya diubah tanpa menandatangani ulang", async () => {
    const [, sig] = (await createToken("rahasia")).split(".");
    expect(await verifyToken("rahasia", `${Date.now() + 1000}.${sig}`)).toBe(false);
  });

  it("ditolak bila kosong atau cacat", async () => {
    expect(await verifyToken("rahasia", undefined)).toBe(false);
    expect(await verifyToken("rahasia", "")).toBe(false);
    expect(await verifyToken("rahasia", "tanpa-titik")).toBe(false);
  });

  it("kedaluwarsa setelah masa berlaku cookie", async () => {
    vi.useFakeTimers();
    const token = await createToken("rahasia");
    vi.advanceTimersByTime(COOKIE_MAX_AGE * 1000 - 1000);
    expect(await verifyToken("rahasia", token)).toBe(true);
    vi.advanceTimersByTime(2000);
    expect(await verifyToken("rahasia", token)).toBe(false);
  });
});

describe("siteGateEnabled", () => {
  it("mati secara bawaan", () => {
    vi.stubEnv("SITE_GATE", "");
    expect(siteGateEnabled()).toBe(false);
  });

  it("tidak hidup hanya karena SITE_PASSWORD masih terpasang", () => {
    vi.stubEnv("SITE_GATE", "");
    vi.stubEnv("SITE_PASSWORD", "apa-saja");
    vi.stubEnv("SESSION_SECRET", "apa-saja");
    expect(siteGateEnabled()).toBe(false);
  });

  it("hidup hanya dengan SITE_GATE=on", () => {
    vi.stubEnv("SITE_GATE", "on");
    expect(siteGateEnabled()).toBe(true);
    vi.stubEnv("SITE_GATE", "true");
    expect(siteGateEnabled()).toBe(false);
  });
});
