import { NextResponse, type NextRequest } from "next/server";
import { verifyToken, COOKIE_NAME } from "@/lib/auth";

// Password gate — pre-launch: seluruh situs terkunci di belakang satu
// password sampai siap dipublikasikan.
const PUBLIC = ["/login", "/api/auth"];

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (PUBLIC.some((p) => pathname.startsWith(p))) return NextResponse.next();

  const secret = process.env.SESSION_SECRET;
  // Fail-closed by design: kalau SESSION_SECRET belum diset, situs TETAP
  // terkunci (redirect ke /login) alih-alih otomatis terbuka ke publik.
  const token = req.cookies.get(COOKIE_NAME)?.value;
  const ok = secret ? await verifyToken(secret, token) : false;
  if (ok) return NextResponse.next();

  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.searchParams.set("next", pathname);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|css|js)$).*)"],
};
