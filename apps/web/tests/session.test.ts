import { describe, expect, it } from "vitest";
import { decodeJwtPayload, isExpired } from "@/lib/session";

function jwt(payload: object): string {
  const part = (v: object) => Buffer.from(JSON.stringify(v)).toString("base64url");
  return `${part({ alg: "HS256" })}.${part(payload)}.tanda-tangan`;
}

describe("decodeJwtPayload", () => {
  it("membaca klaim tanpa memverifikasi tanda tangan", () => {
    const payload = decodeJwtPayload(jwt({ sub: "u1", role: "RESEARCHER", exp: 2_000_000_000 }));
    expect(payload?.role).toBe("RESEARCHER");
    expect(payload?.exp).toBe(2_000_000_000);
  });

  it("menolak yang bukan tiga bagian", () => {
    expect(decodeJwtPayload("bukan-jwt")).toBeNull();
    expect(decodeJwtPayload("a.b")).toBeNull();
    expect(decodeJwtPayload("a.b.c.d")).toBeNull();
  });

  it("menolak payload yang bukan JSON", () => {
    expect(decodeJwtPayload("a.%%%.c")).toBeNull();
  });
});

describe("isExpired", () => {
  const now = Math.floor(Date.now() / 1000);

  it("sesi yang masih berlaku", () => {
    expect(isExpired(decodeJwtPayload(jwt({ exp: now + 60 })))).toBe(false);
  });

  it("sesi yang sudah lewat", () => {
    expect(isExpired(decodeJwtPayload(jwt({ exp: now - 1 })))).toBe(true);
  });

  it("tanpa exp atau tanpa payload dianggap kedaluwarsa", () => {
    expect(isExpired(decodeJwtPayload(jwt({ sub: "u1" })))).toBe(true);
    expect(isExpired(decodeJwtPayload(jwt({ exp: "besok" })))).toBe(true);
    expect(isExpired(null)).toBe(true);
  });
});
