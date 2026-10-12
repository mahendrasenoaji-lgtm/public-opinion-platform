import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { COOKIE_NAME, createToken } from "@/lib/auth";
import { SESSION_COOKIE } from "@/lib/session";
import { middleware } from "@/middleware";

const ORIGIN = "https://contoh.test";

function sessionJwt(expiresInSeconds: number): string {
  const part = (v: object) => Buffer.from(JSON.stringify(v)).toString("base64url");
  const exp = Math.floor(Date.now() / 1000) + expiresInSeconds;
  return `${part({ alg: "HS256" })}.${part({ sub: "u1", role: "VIEWER", exp })}.sig`;
}

function request(path: string, cookies: Record<string, string> = {}): NextRequest {
  const cookie = Object.entries(cookies)
    .map(([k, v]) => `${k}=${v}`)
    .join("; ");
  return new NextRequest(`${ORIGIN}${path}`, { headers: cookie ? { cookie } : {} });
}

/** Tujuan redirect sebagai "path?query", atau null bila permintaan diteruskan. */
async function redirectOf(req: NextRequest): Promise<string | null> {
  const location = (await middleware(req)).headers.get("location");
  if (!location) return null;
  const url = new URL(location);
  return url.pathname + url.search;
}

afterEach(() => vi.unstubAllEnvs());

describe("gerbang situs dilepas (bawaan)", () => {
  beforeEach(() => {
    vi.stubEnv("SITE_GATE", "");
    // Sisa konfigurasi lama di Vercel tidak boleh menghidupkan gerbang lagi.
    vi.stubEnv("SITE_PASSWORD", "sisa-lama");
    vi.stubEnv("SESSION_SECRET", "sisa-lama");
  });

  it("pengunjung tanpa sesi langsung ke login pengguna, bukan ke gerbang", async () => {
    expect(await redirectOf(request("/"))).toBe("/masuk?next=%2F");
    expect(await redirectOf(request("/sinyal"))).toBe("/masuk?next=%2Fsinyal");
  });

  it("halaman masuk dan daftar terbuka tanpa cookie apa pun", async () => {
    expect(await redirectOf(request("/masuk"))).toBeNull();
    expect(await redirectOf(request("/daftar"))).toBeNull();
    expect(await redirectOf(request("/api/session/login"))).toBeNull();
  });

  it("sesi pengguna yang berlaku diteruskan", async () => {
    expect(await redirectOf(request("/sinyal", { [SESSION_COOKIE]: sessionJwt(600) }))).toBeNull();
  });

  it("sesi pengguna yang kedaluwarsa diminta masuk lagi", async () => {
    expect(await redirectOf(request("/sinyal", { [SESSION_COOKIE]: sessionJwt(-5) }))).toBe(
      "/masuk?next=%2Fsinyal",
    );
  });

  it("cookie sesi yang bukan JWT ditolak", async () => {
    expect(await redirectOf(request("/sinyal", { [SESSION_COOKIE]: "asal" }))).toBe(
      "/masuk?next=%2Fsinyal",
    );
  });
});

describe("gerbang situs dihidupkan lagi (SITE_GATE=on)", () => {
  beforeEach(() => {
    vi.stubEnv("SITE_GATE", "on");
    vi.stubEnv("SESSION_SECRET", "rahasia");
  });

  it("tanpa cookie gerbang diarahkan ke /login", async () => {
    expect(await redirectOf(request("/sinyal"))).toBe("/login?next=%2Fsinyal");
    expect(await redirectOf(request("/masuk"))).toBe("/login?next=%2Fmasuk");
  });

  it("cookie gerbang yang sah meneruskan ke lapis sesi pengguna", async () => {
    const gate = { [COOKIE_NAME]: await createToken("rahasia") };
    expect(await redirectOf(request("/masuk", gate))).toBeNull();
    expect(await redirectOf(request("/sinyal", gate))).toBe("/masuk?next=%2Fsinyal");
    expect(
      await redirectOf(request("/sinyal", { ...gate, [SESSION_COOKIE]: sessionJwt(600) })),
    ).toBeNull();
  });

  it("tertutup bila SESSION_SECRET tidak ada (fail-closed)", async () => {
    vi.stubEnv("SESSION_SECRET", "");
    const gate = { [COOKIE_NAME]: await createToken("rahasia") };
    expect(await redirectOf(request("/sinyal", gate))).toBe("/login?next=%2Fsinyal");
  });
});
