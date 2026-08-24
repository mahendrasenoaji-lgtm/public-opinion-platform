import { NextResponse } from "next/server";
import { SESSION_COOKIE, REFRESH_COOKIE } from "@/lib/session";

// Route handler polos (bukan Server Action) supaya bisa dipicu langsung dari
// <form method="post"> tanpa JS tambahan, dan redirect di response.
export async function POST(req: Request) {
  const res = NextResponse.redirect(new URL("/masuk", req.url));
  res.cookies.set(SESSION_COOKIE, "", { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 0 });
  res.cookies.set(REFRESH_COOKIE, "", { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 0 });
  return res;
}
