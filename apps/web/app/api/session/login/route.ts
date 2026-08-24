import { NextResponse } from "next/server";
import { SESSION_COOKIE, REFRESH_COOKIE, decodeJwtPayload } from "@/lib/session";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/v1").replace(/\/$/, "");

/** maxAge cookie mengikuti klaim `exp` token sendiri — bukan diduplikasi manual. */
function maxAgeFromToken(token: string): number {
  const payload = decodeJwtPayload(token);
  if (!payload) return 0;
  return Math.max(0, payload.exp - Math.floor(Date.now() / 1000));
}

export async function POST(req: Request) {
  const { email, password } = await req.json().catch(() => ({ email: "", password: "" }));
  if (!email || !password) {
    return NextResponse.json({ ok: false, error: "Email dan password wajib diisi." }, { status: 400 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ ok: false, error: "Tidak bisa menghubungi server." }, { status: 502 });
  }

  const body = await upstream.json().catch(() => ({}));
  if (!upstream.ok) {
    return NextResponse.json(
      { ok: false, error: body.detail ?? "Email atau password salah." },
      { status: upstream.status },
    );
  }

  const { access_token, refresh_token } = body as { access_token: string; refresh_token: string };
  const res = NextResponse.json({ ok: true });
  const cookieOpts = { httpOnly: true, secure: true, sameSite: "lax" as const, path: "/" };
  res.cookies.set(SESSION_COOKIE, access_token, { ...cookieOpts, maxAge: maxAgeFromToken(access_token) });
  res.cookies.set(REFRESH_COOKIE, refresh_token, { ...cookieOpts, maxAge: maxAgeFromToken(refresh_token) });
  return res;
}
