import Link from "next/link";
import type { Route } from "next";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { InsufficientData } from "@/components/Provenance";
import { api } from "@/lib/api";
import { getCurrentProjectId } from "@/lib/currentProject";
import { activateProject } from "./actions";

export const dynamic = "force-dynamic";

interface ProjectOut {
  id: string;
  name: string;
  objective: string | null;
  is_demo: boolean;
  created_at: string;
}

export default async function ProyekPage() {
  const [projects, currentId] = await Promise.all([
    api<ProjectOut[]>("/projects"),
    getCurrentProjectId(),
  ]);

  return (
    <>
      <PageHeader kicker="Ganti Proyek" title="Semua Proyek" isDemo={false} />
      <div className="body">
        <Panel
          kicker={`${projects.length} proyek di organisasi Anda`}
          title="Pilih proyek aktif"
          right={
            <Link href={"/proyek-baru" as Route} className="nav-i">
              + Buat proyek baru
            </Link>
          }
        >
          {projects.length === 0 ? (
            <InsufficientData reason="Organisasi Anda belum punya proyek. Klik &ldquo;+ Buat proyek baru&rdquo; di atas." />
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>Nama</th>
                  <th>Jenis</th>
                  <th>Dibuat</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {projects.map((p) => {
                  const isActive = p.id === currentId;
                  const activate = activateProject.bind(null, p.id);
                  return (
                    <tr key={p.id}>
                      <td className="strong">{p.name}</td>
                      <td className="dim">{p.is_demo ? "Demo" : "Asli"}</td>
                      <td className="dim">
                        {new Date(p.created_at).toLocaleDateString("id-ID", {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                        })}
                      </td>
                      <td>
                        {isActive ? (
                          <span className="pill pill-ok">Aktif</span>
                        ) : (
                          <form action={activate}>
                            <button type="submit" className="pill pill-warn" style={{ border: "none", cursor: "pointer" }}>
                              Aktifkan
                            </button>
                          </form>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </>
  );
}
