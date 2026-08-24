import { NextResponse, type NextRequest } from "next/server";
import { verifyToken, COOKIE_NAME } from "@/lib/auth";
import { SESSION_COOKIE, decodeJwtPayload, isExpired } from "@/lib/session";

// Dua lapis, dua concern berbeda — jangan digabung:
// 1) Gerbang password situs (pre-launch, satu password bersama semua orang).
// 2) Sesi user asli (JWT per-user dari backend, RBAC).
const SITE_GATE_PUBLIC = ["/login", "/api/auth"];
const APP_SESSION_PUBLIC = ["/login", "/api/auth", "/masuk", "/api/session"];

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Lapis 1 — gerbang password situs (tidak diubah dari sebelumnya).
  if (!SITE_GATE_PUBLIC.some((p) => pathname.startsWith(p))) {
    const secret = process.env.SESSION_SECRET;
    // Fail-closed by design: kalau SESSION_SECRET belum diset, situs TETAP
    // terkunci (redirect ke /login) alih-alih otomatis terbuka ke publik.
    const gateToken = req.cookies.get(COOKIE_NAME)?.value;
    const gateOk = secret ? await verifyToken(secret, gateToken) : false;
    if (!gateOk) {
      const url = req.nextUrl.clone();
      url.pathname = "/login";
      url.searchParams.set("next", pathname);
      return NextResponse.redirect(url);
    }
  }

  // Lapis 2 — sesi user asli. Cuma cek cookie ada & belum expired (tanpa
  // verifikasi tanda tangan) — ini convenience, bukan batas keamanan.
  // Lihat lib/session.ts untuk alasannya; batas sungguhan ada di backend.
  if (!APP_SESSION_PUBLIC.some((p) => pathname.startsWith(p))) {
    const sessionToken = req.cookies.get(SESSION_COOKIE)?.value;
    const payload = sessionToken ? decodeJwtPayload(sessionToken) : null;
    if (!sessionToken || isExpired(payload)) {
      const url = req.nextUrl.clone();
      url.pathname = "/masuk";
      url.searchParams.set("next", pathname);
      return NextResponse.redirect(url);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|css|js)$).*)"],
};
