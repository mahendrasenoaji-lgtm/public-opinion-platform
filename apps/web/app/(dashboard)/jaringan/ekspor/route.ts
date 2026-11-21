import { cookies } from "next/headers";
import { SESSION_COOKIE } from "@/lib/session";
import { getCurrentProjectId } from "@/lib/currentProject";

export const dynamic = "force-dynamic";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/v1";
const FORMATS = new Set(["gexf", "nodes", "edges"]);
const DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Unduhan graf untuk Gephi. Peramban tidak memegang token API, jadi rute ini
 * meneruskan permintaan dengan sesi pengguna. Pembatasan peran (DATA_ANALYST
 * ke atas) dan audit log ditegakkan backend, bukan di sini.
 */
export async function GET(req: Request) {
  const u = new URL(req.url);
  const format = u.searchParams.get("format") ?? "gexf";
  if (!FORMATS.has(format)) return new Response("Format tidak dikenal.", { status: 400 });
  const q = new URLSearchParams({ format });
  const dari = u.searchParams.get("dari");
  const sampai = u.searchParams.get("sampai");
  if (dari && sampai && DATE.test(dari) && DATE.test(sampai)) {
    q.set("start", dari);
    q.set("end", sampai);
  }
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sesi berakhir; masuk lagi.", { status: 401 });
  const projectId = await getCurrentProjectId();
  const res = await fetch(`${BASE}/projects/${projectId}/network/export?${q}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.json().then((b: { detail?: unknown }) => b.detail).catch(() => null);
    return new Response(typeof detail === "string" ? detail : "Ekspor gagal.", { status: res.status });
  }
  return new Response(res.body, {
    headers: {
      "content-type": res.headers.get("content-type") ?? "application/octet-stream",
      "content-disposition": res.headers.get("content-disposition") ?? "attachment",
    },
  });
}
