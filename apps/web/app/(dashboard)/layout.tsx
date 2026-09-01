import Link from "next/link";
import type { Route } from "next";
import { cookies } from "next/headers";
import { Activity } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { getCurrentProjectId } from "@/lib/currentProject";
import { SESSION_COOKIE, decodeJwtPayload } from "@/lib/session";

interface ActiveProject {
  name: string;
  is_demo: boolean;
}

const NAV = [
  ["/command", "Command Center"],
  ["/opinion-index", "Opinion Index"],
  ["/consistency", "Signal Consistency"],
  ["/narrative", "Narrative Map"],
  ["/segments", "Public Segments"],
  ["/geo", "Geographic Map"],
  ["/forecast", "Forecast & Simulator"],
  // Phase 2 — sinyal
  ["/sinyal", "Signal Monitor"],
  ["/tema", "Topic Discovery"],
  ["/copilot", "AI Copilot"],
  // Phase 3 — prediksi
  ["/risiko", "Opinion Risk Score"],
  ["/pengaruh", "Influence Estimate"],
  ["/dampak", "Communication Impact"],
  ["/brief", "Executive Brief"],
  ["/governance", "AI Governance"],
] as const;

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const sessionToken = (await cookies()).get(SESSION_COOKIE)?.value;
  const email = sessionToken ? decodeJwtPayload(sessionToken)?.email : undefined;

  // Gagal-aman ke null kalau proyeknya sendiri bermasalah (mis. cookie
  // pop_project_id basi menunjuk proyek yang sudah dihapus) -- layout ini
  // membungkus SEMUA halaman dashboard, satu label proyek yang hilang tidak
  // boleh menjatuhkan seluruh shell, halaman anak yang menampilkan alasan
  // sebenarnya (mis. InsufficientData). TAPI cuma tangkap ApiError -- 401
  // dari api() jalan lewat redirect() (next/navigation), yang melempar
  // sinyal internal Next.js, BUKAN ApiError; catch generik di sini akan
  // diam-diam meredam redirect itu dan membuat pop_session yang
  // kadaluarsa gagal senyap alih-alih lempar ke /masuk.
  const projectId = await getCurrentProjectId();
  let project: ActiveProject | null = null;
  try {
    project = await api<ActiveProject>(`/projects/${projectId}`);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
  }

  return (
    <div className="app">
      <aside className="nav">
        <div className="brand">
          <Activity size={18} />
          <div>
            <div className="brand-n">PUBLIC OPINION</div>
            <div className="brand-s">Intelligence Platform</div>
          </div>
        </div>
        <nav>
          {NAV.map(([href, label]) => (
            // Sebagian besar rute di sini belum punya halaman — Phase 1 hanya
            // mewajibkan Command Center + Opinion Index (roadmap.md). Cast ke
            // Route supaya typedRoutes tidak menolak build sebelum semua
            // halaman di-port; link yang belum ada akan 404 sampai dibangun.
            <Link key={href} href={href as Route} className="nav-i">{label}</Link>
          ))}
        </nav>
        <div className="nav-foot">
          <div className="kicker">Proyek aktif</div>
          <div className="proj">{project?.name ?? "Proyek"}</div>
          {/* "Gelombang 12" cuma benar untuk proyek demo asli -- itu fakta
              spesifik seed (db/seed.py), bukan sesuatu yang bisa
              digeneralisasi ke proyek baru siapa pun. Penanda "Demo data
              sintetis" wajib selama proyeknya memang demo (CLAUDE.md §7). */}
          <div className="proj-s">
            {project === null
              ? "—"
              : project.is_demo
                ? "Gelombang 12 · Demo data sintetis"
                : "Proyek Anda sendiri"}
          </div>
          <Link href={"/proyek" as Route} className="nav-i" style={{ marginTop: 6, display: "inline-block" }}>
            Ganti proyek
          </Link>
          {email && (
            <form action="/api/session/logout" method="post" style={{ marginTop: 12 }}>
              <div className="proj-s" style={{ marginBottom: 6 }}>{email}</div>
              <button type="submit" className="nav-i" style={{ background: "none", border: "none", padding: 0, cursor: "pointer", textAlign: "left" }}>
                Keluar
              </button>
            </form>
          )}
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
