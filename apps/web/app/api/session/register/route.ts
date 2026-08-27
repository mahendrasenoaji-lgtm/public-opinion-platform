import { NextResponse } from "next/server";
import { SESSION_COOKIE, REFRESH_COOKIE, decodeJwtPayload } from "@/lib/session";

// Sama persis dengan api/session/login/route.ts (termasuk perhitungan
// maxAge dari klaim exp token) -- lihat komentar di sana untuk alasannya.
// Dipisah jadi route sendiri, bukan cabang di dalam login/route.ts, supaya
// method POST-nya tidak ambigu (satu route = satu bentuk body request).
const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/v1").replace(/\/$/, "");

function maxAgeFromToken(token: string): number {
  const payload = decodeJwtPayload(token);
  if (!payload) return 0;
  return Math.max(0, payload.exp - Math.floor(Date.now() / 1000));
}

export async function POST(req: Request) {
  const { orgName, orgSlug, fullName, email, password } = await req
    .json()
    .catch(() => ({ orgName: "", orgSlug: "", fullName: "", email: "", password: "" }));

  if (!orgName || !orgSlug || !fullName || !email || !password) {
    return NextResponse.json({ ok: false, error: "Semua field wajib diisi." }, { status: 400 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        org_name: orgName,
        org_slug: orgSlug,
        full_name: fullName,
        email,
        password,
      }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ ok: false, error: "Tidak bisa menghubungi server." }, { status: 502 });
  }

  const body = await upstream.json().catch(() => ({}));
  if (!upstream.ok) {
    // Backend balas 409 "slug sudah dipakai" atau 422 pelanggaran validasi
    // Pydantic (mis. slug tidak lolos pattern) -- keduanya sudah pesan yang
    // layak ditampilkan apa adanya, bukan cuma "Permintaan gagal.".
    const detail = typeof body.detail === "string" ? body.detail : undefined;
    return NextResponse.json(
      { ok: false, error: detail ?? "Pendaftaran gagal." },
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
