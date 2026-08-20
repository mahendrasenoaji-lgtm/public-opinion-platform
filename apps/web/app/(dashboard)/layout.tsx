import Link from "next/link";
import { Activity } from "lucide-react";

const NAV = [
  ["/command", "Command Center"],
  ["/index", "Opinion Index"],
  ["/consistency", "Signal Consistency"],
  ["/narrative", "Narrative Map"],
  ["/segments", "Public Segments"],
  ["/geo", "Geographic Map"],
  ["/forecast", "Forecast & Simulator"],
  ["/brief", "Executive Brief"],
  ["/governance", "AI Governance"],
] as const;

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
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
            <Link key={href} href={href} className="nav-i">{label}</Link>
          ))}
        </nav>
        <div className="nav-foot">
          <div className="kicker">Proyek aktif</div>
          <div className="proj">Persepsi Kebijakan Nasional 2026</div>
          {/* Penanda wajib selama berjalan di atas seed (CLAUDE.md §7) */}
          <div className="proj-s">Gelombang 12 · Demo data sintetis</div>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
