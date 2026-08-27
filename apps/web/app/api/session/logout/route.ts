import { NextResponse } from "next/server";
import { SESSION_COOKIE, REFRESH_COOKIE } from "@/lib/session";
import { CURRENT_PROJECT_COOKIE } from "@/lib/currentProject";

// Route handler polos (bukan Server Action) supaya bisa dipicu langsung dari
// <form method="post"> tanpa JS tambahan, dan redirect di response.
export async function POST(req: Request) {
  const res = NextResponse.redirect(new URL("/masuk", req.url));
  res.cookies.set(SESSION_COOKIE, "", { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 0 });
  res.cookies.set(REFRESH_COOKIE, "", { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 0 });
  // pop_project_id TIDAK terikat sesi (lib/currentProject.ts) -- kalau tidak
  // ikut dihapus di sini, browser yang sama dipakai login akun lain akan
  // membawa cookie proyek akun SEBELUMNYA. RLS mencegah kebocoran data (akun
  // baru cuma dapat 404 -> "belum ada proyek" dari apiOrNull), tapi akibatnya
  // akun yang sebenarnya PUNYA proyek sendiri jadi terlihat kosong keliru,
  // bukan menampilkan proyeknya sendiri.
  res.cookies.set(CURRENT_PROJECT_COOKIE, "", {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return res;
}
