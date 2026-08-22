import { NextResponse } from "next/server";
import { createToken, COOKIE_NAME, COOKIE_MAX_AGE } from "@/lib/auth";

export async function POST(req: Request) {
  const { password } = await req.json().catch(() => ({ password: "" }));
  const expected = process.env.SITE_PASSWORD;
  const secret = process.env.SESSION_SECRET;

  if (!expected || !secret) {
    return NextResponse.json(
      { ok: false, error: "Server belum dikonfigurasi (SITE_PASSWORD / SESSION_SECRET)." },
      { status: 500 }
    );
  }
  if (password !== expected) {
    return NextResponse.json({ ok: false, error: "Password salah." }, { status: 401 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE_NAME, await createToken(secret), {
    httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: COOKIE_MAX_AGE,
  });
  return res;
}
