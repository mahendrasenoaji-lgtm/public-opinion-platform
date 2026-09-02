import { Info } from "lucide-react";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { SOURCE } from "@/lib/tokens";
import { apiOrNullLenient } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";

export const dynamic = "force-dynamic";

interface AccountPositionRow {
  author_hash: string;
  replies_received: number;
  quotes_received: number;
  in_degree: number;
  distinct_sources: number;
}

interface NetworkOut {
  top: AccountPositionRow[];
  total_accounts: number;
  total_edges: number;
  method: string;
  insufficient_data: boolean;
  note: string | null;
  limitations: string[];
}

export default async function JaringanPage() {
  const { id: projectId, name, is_demo: isDemo } = await getCurrentProject();
  // apiOrNullLenient: /network butuh kolom mentions.reply_to_hash/
  // quote_of_hash/conversation_id yang migrasinya ke Supabase bisa saja
  // belum diterapkan -- 500, bukan 404, dan tanpa ini menjatuhkan seluruh
  // halaman (lihat catatan yang sama di lib/api.ts).
  const data = await apiOrNullLenient<NetworkOut>(`/projects/${projectId}/network`);
  const social = SOURCE.SOCIAL.color;
  const peak = Math.max(1, ...(data?.top ?? []).map((r) => r.in_degree));

  return (
    <>
      <PageHeader kicker="Interaction Network" title={name} isDemo={isDemo} />
      <div className="body">
        {/* Judul kartu di sini sengaja "posisi struktural", bukan "pengaruh"
            atau "kendali" — CLAUDE.md §3. Yang terukur adalah seberapa sering
            sebuah akun dibalas/dikutip akun lain yang IKUT muncul di data
            yang sama, bukan apakah ia mengendalikan opini. */}
        <section className="stat-row">
          <div className="stat">
            <div className="kicker">Akun dalam graf</div>
            <div className="stat-v">{(data?.total_accounts ?? 0).toLocaleString("id-ID")}</div>
          </div>
          <div className="stat">
            <div className="kicker">Relasi balasan/kutipan</div>
            <div className="stat-v">{(data?.total_edges ?? 0).toLocaleString("id-ID")}</div>
          </div>
        </section>

        <Panel kicker="Posisi struktural" title="Akun paling sering dibalas/dikutip">
          {!data || data.insufficient_data || data.top.length === 0 ? (
            <InsufficientData
              reason={
                data?.note ??
                "Belum ada relasi balasan/kutipan yang tertangkap dari sumber yang menyediakannya (mis. konektor X)."
              }
            />
          ) : (
            <>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Akun (hash)</th>
                    <th>Dibalas</th>
                    <th>Dikutip</th>
                    <th>Akun sumber berbeda</th>
                    <th>In-degree</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top.map((r) => (
                    <tr key={r.author_hash}>
                      {/* Hash dipotong untuk keterbacaan, sama seperti
                          /pengaruh — bukan identitas, tidak bisa dibalik
                          tanpa salt deployment. */}
                      <td className="mono">{r.author_hash.slice(0, 12)}…</td>
                      <td className="mono">{r.replies_received}</td>
                      <td className="mono">{r.quotes_received}</td>
                      <td className="mono">{r.distinct_sources}</td>
                      <td>
                        <div className="bar100">
                          <div
                            style={{
                              width: `${(r.in_degree / peak) * 100}%`,
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
                n={data.total_edges}
                confidence="Rendah"
                limits={data.limitations[0] ?? ""}
              />
            </>
          )}

          <p className="note">
            <Info size={13} />
            &quot;Akun sumber berbeda&quot; membedakan satu akun yang membalas
            berkali-kali dari banyak akun yang masing-masing membalas sekali —
            in-degree yang sama bisa berasal dari salah satunya, dan itu
            perbedaan yang penting.
          </p>
        </Panel>

        <Panel kicker="Batasan" title="Apa yang graf ini tidak katakan">
          <ul className="nolist">
            {(data?.limitations ?? []).map((l) => (
              <li key={l}>{l}</li>
            ))}
            <li>
              Graf ini hanya memuat relasi antar akun yang KEDUANYA muncul sebagai
              penulis dalam data yang berhasil diambil. Kalau akun yang dibalas atau
              dikutip tidak ikut terambil konektor, relasinya tidak tercatat sama
              sekali — bukan tercatat sebagai nol.
            </li>
          </ul>
        </Panel>
      </div>
    </>
  );
}
