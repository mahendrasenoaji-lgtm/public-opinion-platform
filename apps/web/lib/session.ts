// Sesi user asli (JWT dari backend) — beda dari gerbang SITE_PASSWORD di
// lib/auth.ts (satu password bersama, bukan identitas per-user).
//
// Middleware di sini SENGAJA tidak verifikasi tanda tangan JWT: cuma cek
// cookie ada + `exp` belum lewat, supaya tidak perlu sinkronkan JWT_SECRET
// ke Vercel. Batas keamanan sungguhan tetap di FastAPI (app/deps.py
// decode_token, verifikasi HS256 penuh) + RLS Postgres — lihat R3 CLAUDE.md.
// Cookie palsu dengan exp masa depan bisa lolos gerbang ini, tapi setiap
// panggilan API sungguhan akan ditolak backend begitu tanda tangannya salah.

export const SESSION_COOKIE = "pop_session";
export const REFRESH_COOKIE = "pop_refresh";

export interface JwtPayload {
  sub: string;
  org: string;
  role: string;
  email: string;
  exp: number;
  [key: string]: unknown;
}

/** Decode payload JWT tanpa verifikasi tanda tangan — lihat catatan di atas. */
export function decodeJwtPayload(token: string): JwtPayload | null {
  const parts = token.split(".");
  const [, payload] = parts;
  if (parts.length !== 3 || !payload) return null;
  try {
    const json = Buffer.from(payload, "base64url").toString("utf-8");
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}

export function isExpired(payload: JwtPayload | null): boolean {
  if (!payload || typeof payload.exp !== "number") return true;
  return Date.now() >= payload.exp * 1000;
}
