import Link from "next/link";
import type { Route } from "next";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { InsufficientData } from "@/components/Provenance";
import { apiOrNullLenient } from "@/lib/api";
import { getCurrentProjectId } from "@/lib/currentProject";
import { ProjectRow } from "./ProjectRow";

export const dynamic = "force-dynamic";

interface ProjectOut {
  id: string;
  name: string;
  objective: string | null;
  is_demo: boolean;
  created_at: string;
}

export default async function ProyekPage() {
  // apiOrNullLenient, bukan api polos -- lihat catatan yang sama di geo/page.tsx.
  const [projectsRaw, currentId] = await Promise.all([
    apiOrNullLenient<ProjectOut[]>("/projects"),
    getCurrentProjectId(),
  ]);
  const projects = projectsRaw ?? [];

  return (
    <>
      <PageHeader kicker="Current Trending Categories" title="Semua Proyek" isDemo={false} />
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
                  <th>Aksi</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((p) => (
                  <ProjectRow
                    key={p.id}
                    id={p.id}
                    name={p.name}
                    isDemo={p.is_demo}
                    createdAt={p.created_at}
                    isActive={p.id === currentId}
                  />
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </>
  );
}
