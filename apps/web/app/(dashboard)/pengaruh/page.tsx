import { Info } from "lucide-react";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { SOURCE } from "@/lib/tokens";
import { apiOrNull } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";

export const dynamic = "force-dynamic";

interface InfluenceRow {
  author_hash: string;
  posts: number;
  engagement: number;
  post_share_pct: number;
  engagement_share_pct: number;
  amplification: number;
  influence_estimate: number;
}

interface InfluenceOut {
  top: InfluenceRow[];
  total_authors: number;
  ranked_authors: number;
  total_posts: number;
  total_engagement: number;
  concentration_top10_pct: number;
  method: string;
  insufficient_data: boolean;
  note: string | null;
  limitations: string[];
}

export default async function PengaruhPage() {
  const { id: projectId, name, is_demo: isDemo } = await getCurrentProject();
  const data = await apiOrNull<InfluenceOut>(`/projects/${projectId}/influence`);
  const social = SOURCE.SOCIAL.color;
  const peak = Math.max(1, ...(data?.top ?? []).map((r) => r.influence_estimate));

  return (
    <>
      <PageHeader kicker="Influence Estimate" title={name} isDemo={isDemo} />
      <div className="body">
        {/* Judul halaman ini sengaja "estimasi", bukan "pengaruh". Yang diukur
            adalah keterpaparan; apakah ada yang berubah pikiran tidak terukur
            di data ini sama sekali (CLAUDE.md §3). */}
        <section className="stat-row">
          <div className="stat">
            <div className="kicker">Akun berbeda</div>
            <div className="stat-v">{(data?.total_authors ?? 0).toLocaleString("id-ID")}</div>
          </div>
          <div className="stat">
            <div className="kicker">Akun yang diperingkat</div>
            <div className="stat-v">{data?.ranked_authors ?? 0}</div>
            <div className="proj-s" style={{ marginTop: 6 }}>
              Minimal 3 unggahan — sekali viral bukan keterpaparan
            </div>
          </div>
          <div className="stat">
            <div className="kicker">Porsi 10 akun teratas</div>
            <div className="stat-v" style={{ color: social }}>
              {(data?.concentration_top10_pct ?? 0).toFixed(1)}
              <span className="stat-u">%</span>
            </div>
          </div>
          <div className="stat">
            <div className="kicker">Total keterlibatan</div>
            <div className="stat-v">{(data?.total_engagement ?? 0).toLocaleString("id-ID")}</div>
          </div>
        </section>

        <Panel kicker="Keterpaparan" title="Akun dengan porsi percakapan terbesar">
          {!data || data.insufficient_data || data.top.length === 0 ? (
            <InsufficientData
              reason={data?.note ?? "Belum ada percakapan yang membawa identitas akun."}
            />
          ) : (
            <>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Akun (hash)</th>
                    <th>Unggahan</th>
                    <th>Porsi unggahan</th>
                    <th>Porsi keterlibatan</th>
                    <th>Amplifikasi</th>
                    <th>Estimasi</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top.map((r) => (
                    <tr key={r.author_hash}>
                      {/* Hash dipotong untuk keterbacaan. Nilai penuhnya pun
                          bukan identitas — ia tidak bisa dikembalikan jadi
                          nama akun tanpa salt deployment. */}
                      <td className="mono">{r.author_hash.slice(0, 12)}…</td>
                      <td className="mono">{r.posts}</td>
                      <td className="mono">{r.post_share_pct.toFixed(2)}%</td>
                      <td className="mono">{r.engagement_share_pct.toFixed(2)}%</td>
                      <td className="mono">{r.amplification.toFixed(2)}×</td>
                      <td>
                        <div className="bar100">
                          <div
                            style={{
                              width: `${(r.influence_estimate / peak) * 100}%`,
                              background: social,
                            }}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <Provenance
                method={data.method}
                n={data.total_posts}
                confidence="Rendah"
                limits={data.limitations[0] ?? ""}
              />
            </>
          )}

          <p className="note">
            <Info size={13} />
            Amplifikasi adalah keterlibatan per unggahan dibanding median akun lain.
            1,00× berarti biasa saja. Sebagian perbedaan antar-akun berasal dari
            distribusi algoritma platform, bukan dari isi pesannya.
          </p>
        </Panel>

        <Panel kicker="Batasan" title="Apa yang angka ini tidak katakan">
          <ul className="nolist">
            {(data?.limitations ?? []).map((l) => (
              <li key={l}>{l}</li>
            ))}
            <li>
              Modul ini tidak menyimpulkan koordinasi antar-akun. Beberapa akun yang
              memposting hal serupa pada waktu berdekatan adalah pola yang sama persis
              untuk kampanye terkoordinasi dan untuk orang-orang yang membaca berita
              yang sama pagi itu — data ini tidak bisa memisahkan keduanya.
            </li>
          </ul>
        </Panel>
      </div>
    </>
  );
}
