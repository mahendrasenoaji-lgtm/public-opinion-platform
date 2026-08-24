import Link from "next/link";
import type { Route } from "next";
import { cookies } from "next/headers";
import { Activity } from "lucide-react";
import { SESSION_COOKIE, decodeJwtPayload } from "@/lib/session";

const NAV = [
  ["/command", "Command Center"],
  ["/opinion-index", "Opinion Index"],
  ["/consistency", "Signal Consistency"],
  ["/narrative", "Narrative Map"],
  ["/segments", "Public Segments"],
  ["/geo", "Geographic Map"],
  ["/forecast", "Forecast & Simulator"],
  ["/brief", "Executive Brief"],
  ["/governance", "AI Governance"],
] as const;

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const sessionToken = (await cookies()).get(SESSION_COOKIE)?.value;
  const email = sessionToken ? decodeJwtPayload(sessionToken)?.email : undefined;

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
          <div className="proj">Persepsi Kebijakan Nasional 2026</div>
          {/* Penanda wajib selama berjalan di atas seed (CLAUDE.md §7) */}
          <div className="proj-s">Gelombang 12 · Demo data sintetis</div>
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
