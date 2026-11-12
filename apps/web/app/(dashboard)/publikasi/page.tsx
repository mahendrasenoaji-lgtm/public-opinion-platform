import Link from "next/link";
import type { Route } from "next";
import { cookies } from "next/headers";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { PublicationEditor } from "@/components/PublicationEditor";
import { api, ApiError } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";
import { SESSION_COOKIE, decodeJwtPayload } from "@/lib/session";
import { SOURCE } from "@/lib/tokens";
import {
  EDITOR_ROLES,
  PUBLISHER_ROLES,
  STATUS_LABEL,
  formatDateTime,
  type Publication,
  type PublicationRef,
} from "./publikasi";

export const dynamic = "force-dynamic";

/**
 * Publikasi hasil riset: daftar draf dan artikel proyek ini, dan penyunting
 * satu artikel (`?id=`). Draf dibuat dari Laporan Percakapan; angkanya
 * dibekukan saat itu. Rencana: docs/rencana-situs-publikasi.md.
 */

interface Loaded<T> {
  data: T | null;
  message?: string;
}

async function load<T>(path: string): Promise<Loaded<T>> {
  try {
    return { data: await api<T>(path) };
  } catch (e) {
    if (e instanceof ApiError) return { data: null, message: e.message };
    throw e;
  }
}

const PILL: Record<string, string> = { draft: "pill", review: "pill pill-warn", published: "pill pill-ok" };

export default async function PublikasiPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const id = (Array.isArray(sp.id) ? sp.id[0] : sp.id) ?? "";
  const project = await getCurrentProject();
  const base = `/projects/${project.id}/publications`;

  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  const role = token ? decodeJwtPayload(token)?.role : undefined;
  const canEdit = typeof role === "string" && EDITOR_ROLES.has(role);
  const canPublish = typeof role === "string" && PUBLISHER_ROLES.has(role);

  const list = await load<PublicationRef[]>(base);
  const current = /^[0-9a-f-]{36}$/.test(id) ? await load<Publication>(`${base}/${id}`) : null;
  const pub = current?.data ?? null;
  const publicSite = process.env.NEXT_PUBLIC_PERS_URL;

  return (
    <>
      <PageHeader kicker="Publikasi hasil riset" title={project.name} isDemo={project.is_demo} />

      {!list.data ? (
        <Panel title="Publikasi belum aktif">
          <InsufficientData reason={list.message ?? "Backend belum memuat bagian ini."} />
        </Panel>
      ) : (
        <Panel
          kicker={`${list.data.length} artikel di proyek ini`}
          title="Draf dan artikel"
          right={
            <Link href={"/laporan" as Route} className="btn btn-ghost btn-sm">
              Buat draf dari Laporan Percakapan
            </Link>
          }
        >
          {list.data.length === 0 ? (
            <InsufficientData reason="Belum ada draf. Buka Laporan Percakapan, pilih periode tetap, lalu tekan Buat draf publikasi." />
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th scope="col">Judul</th>
                    <th scope="col">Status</th>
                    <th scope="col">Versi</th>
                    <th scope="col">Penulis</th>
                    <th scope="col">Diubah</th>
                  </tr>
                </thead>
                <tbody>
                  {list.data.map((p) => (
                    <tr key={p.id}>
                      <td className="strong">
                        <Link href={`/publikasi?id=${p.id}` as Route} aria-current={p.id === id ? "true" : undefined}>
                          {p.title}
                        </Link>
                      </td>
                      <td>
                        <span className={PILL[p.status] ?? "pill"}>{STATUS_LABEL[p.status]}</span>
                      </td>
                      <td className="mono">{p.version}</td>
                      <td>{p.author_name}</td>
                      <td className="mono">{formatDateTime(p.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="field-hint" style={{ marginTop: 10 }}>
            Alur: draf → tinjauan → terbit. Menerbitkan dan meralat hanya oleh Research Director.
            Artikel terbit tidak bisa dihapus atau ditarik; perubahan tercatat sebagai ralat.
          </p>
        </Panel>
      )}

      {id && !pub && list.data && (
        <Panel title="Artikel tidak ditemukan">
          <InsufficientData reason={current?.message ?? "Artikel ini tidak ada di proyek aktif."} />
        </Panel>
      )}

      {pub && (
        <>
          <Panel
            kicker={`${STATUS_LABEL[pub.status]} · versi ${pub.version}`}
            title="Sunting artikel"
            right={
              pub.status === "published" ? (
                <a className="btn btn-ghost btn-sm" href={`${publicSite ?? ""}/pers/${pub.slug}`} target="_blank" rel="noreferrer">
                  Buka halaman publik
                </a>
              ) : undefined
            }
          >
            <PublicationEditor key={pub.id} projectId={project.id} publication={pub} canEdit={canEdit} canPublish={canPublish} />
          </Panel>

          <Panel kicker="Snapshot beku" title="Angka yang menyertai artikel ini">
            <table className="tbl">
              <thead>
                <tr>
                  <th scope="col">Sumber</th>
                  <th scope="col">Konten</th>
                  <th scope="col">Bernilai sentimen</th>
                  <th scope="col">Negatif / netral / positif</th>
                </tr>
              </thead>
              <tbody>
                {pub.snapshot.report.sources.map((s) => (
                  <tr key={s.source}>
                    <td>
                      <span style={{ color: SOURCE[s.source as keyof typeof SOURCE]?.color }}>●</span>{" "}
                      {SOURCE[s.source as keyof typeof SOURCE]?.label ?? s.source}
                    </td>
                    <td className="mono">{s.n.toLocaleString("id-ID")}</td>
                    <td className="mono">{s.scored.toLocaleString("id-ID")}</td>
                    <td className="mono">
                      {s.labels.negatif ?? 0} / {s.labels.netral ?? 0} / {s.labels.positif ?? 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Provenance
              method={`Bahan Laporan Percakapan, dibekukan ${formatDateTime(pub.snapshot.frozen_at)} WIB`}
              n={`periode ${pub.snapshot.period_start} s.d. ${pub.snapshot.period_end} (${pub.snapshot.timezone})`}
              confidence="mengikuti metode tiap sumber"
              limits={pub.snapshot.note}
            />
            {pub.corrections.length > 0 && (
              <div className="read" style={{ marginTop: 14 }}>
                <div className="read-t">Riwayat ralat</div>
                {pub.corrections.map((c) => (
                  <div key={c.version} className="read-d">
                    Versi {c.version} diganti {formatDateTime(c.at)}: {c.note}
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </>
      )}
    </>
  );
}
