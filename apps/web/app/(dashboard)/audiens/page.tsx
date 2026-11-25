import { Info } from "lucide-react";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { PeriodBar } from "@/components/PeriodBar";
import { SOURCE } from "@/lib/tokens";
import { apiOrNullLenient } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";
import { parseWindow, windowQuery } from "../sinyal/window";

export const dynamic = "force-dynamic";

/*
 * Profil Audiens (P11): estimasi gender, kelompok umur, dan minat akun dari
 * komentarnya sendiri. Hanya agregat; tidak ada hash akun di halaman ini.
 * Estimasi tidak pernah dicampur dengan variabel survei (CLAUDE.md §3), jadi
 * halaman ini terpisah dari "Segmen Publik".
 */

interface ValueCount {
  value: string;
  accounts: number;
  share: number | null;
}

interface Attribute {
  known: number;
  unknown: number;
  values: ValueCount[];
  insufficient_data: boolean;
  note: string | null;
}

interface Interest {
  value: string;
  accounts: number;
  share_of_accounts: number | null;
}

interface AudienceOut {
  period_start: string;
  period_end: string;
  method: string;
  model_version: string;
  min_confidence: number;
  evaluated: boolean;
  n_accounts: number;
  n_comments: number;
  gender: Attribute;
  age: Attribute;
  pyramid: { age: string; gender: string; accounts: number | null }[];
  interests: Interest[];
  interests_by_gender: Record<string, Interest[]>;
  evidence: Record<string, { marker: string; accounts: number }[]>;
  sentiment: { segment: string; accounts: number; scored: number; mean: number | null }[];
  computed_at: string;
  insufficient_data: boolean;
  note: string | null;
  excluded: string[];
  limitations: string[];
}

const GENDER_LABEL: Record<string, string> = { L: "Laki-laki", P: "Perempuan" };
const AGE_LABEL: Record<string, string> = {
  "<=17": "≤ 17",
  "18-24": "18–24",
  "25-34": "25–34",
  "35-44": "35–44",
  "45+": "45+",
};

function segmentLabel(key: string): string {
  const [kind = "", value = ""] = key.split(":");
  if (kind === "gender") return GENDER_LABEL[value] ?? value;
  if (kind === "age") return `Umur ${AGE_LABEL[value] ?? value}`;
  if (kind === "minat") return `Minat ${value}`;
  return key;
}

function pct(known: number, total: number): string {
  if (!total || !known) return "0";
  const v = (100 * known) / total;
  return v < 0.01 ? "< 0,01" : v.toLocaleString("id-ID", { maximumFractionDigits: 2 });
}

function first(v: string | string[] | undefined): string {
  return (Array.isArray(v) ? v[0] : v)?.trim() ?? "";
}

function Evidence({ items }: { items?: { marker: string; accounts: number }[] }) {
  if (!items?.length) return null;
  return (
    <span className="proj-s">
      Penanda: {items.map((e) => `${e.marker} (${e.accounts})`).join(", ")}
    </span>
  );
}

function AttributeTable({
  attr,
  labels,
  evidence,
  prefix,
  color,
}: {
  attr: Attribute;
  labels: Record<string, string>;
  evidence: AudienceOut["evidence"];
  prefix: string;
  color: string;
}) {
  const peak = Math.max(1, ...attr.values.map((v) => v.accounts));
  return (
    <table className="tbl">
      <thead>
        <tr>
          <th>Nilai</th>
          <th>Akun</th>
          <th>Porsi dari yang diketahui</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {attr.values.map((v) => (
          <tr key={v.value}>
            <td>
              {labels[v.value] ?? v.value}
              <br />
              <Evidence items={evidence[`${prefix}:${v.value}`]} />
            </td>
            <td className="mono">{v.accounts.toLocaleString("id-ID")}</td>
            <td className="mono">{v.share === null ? "—" : `${v.share.toLocaleString("id-ID")}%`}</td>
            <td style={{ width: "30%" }}>
              <div className="bar100">
                <div style={{ width: `${(v.accounts / peak) * 100}%`, background: color }} />
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default async function AudiensPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const win = parseWindow(params);
  const kecuali = first(params.kecuali);
  const { id: projectId, name, is_demo: isDemo } = await getCurrentProject();
  const data = await apiOrNullLenient<AudienceOut>(
    `/projects/${projectId}/audience${windowQuery(win, kecuali ? { exclude: kecuali } : {})}`,
  );
  const social = SOURCE.SOCIAL.color;
  const n = data?.n_accounts ?? 0;

  return (
    <>
      <PageHeader kicker="Profil Audiens (estimasi)" title={name} isDemo={isDemo} />
      <div className="body">
        <PeriodBar win={win} note="Hanya percakapan SOSIAL" />

        <section className="stat-row">
          <div className="stat">
            <div className="kicker">Akun berbeda</div>
            <div className="stat-v">{n.toLocaleString("id-ID")}</div>
            <div className="proj-s" style={{ marginTop: 6 }}>
              dari {(data?.n_comments ?? 0).toLocaleString("id-ID")} komentar
            </div>
          </div>
          <div className="stat">
            <div className="kicker">Gender diketahui</div>
            <div className="stat-v" style={{ color: social }}>
              {(data?.gender.known ?? 0).toLocaleString("id-ID")}
            </div>
            <div className="proj-s" style={{ marginTop: 6 }}>
              {pct(data?.gender.known ?? 0, n)}% akun
            </div>
          </div>
          <div className="stat">
            <div className="kicker">Umur diketahui</div>
            <div className="stat-v" style={{ color: social }}>
              {(data?.age.known ?? 0).toLocaleString("id-ID")}
            </div>
            <div className="proj-s" style={{ marginTop: 6 }}>
              {pct(data?.age.known ?? 0, n)}% akun
            </div>
          </div>
          <div className="stat">
            <div className="kicker">Akun dengan minat</div>
            <div className="stat-v" style={{ color: social }}>
              {(data?.interests ?? []).reduce((a, i) => Math.max(a, i.accounts), 0).toLocaleString("id-ID")}
            </div>
            <div className="proj-s" style={{ marginTop: 6 }}>
              kategori terbesar; satu akun bisa punya beberapa minat
            </div>
          </div>
        </section>

        <p className="note">
          <Info size={13} />
          Semua angka di halaman ini ESTIMASI dari teks komentar, bukan data demografi, dan belum
          dievaluasi terhadap label manusia. Akun yang tidak menyatakan dirinya tercatat
          &ldquo;tidak diketahui&rdquo;. Persen hanya terbit bila minimal 30 akun diketahui.
        </p>

        {!data ? (
          <Panel title="Profil audiens">
            <InsufficientData reason="Profil audiens belum bisa dimuat. Coba muat ulang halaman." />
          </Panel>
        ) : (
          <>
            <div className="grid-2">
              <Panel kicker="Estimasi" title="Gender">
                <AttributeTable
                  attr={data.gender}
                  labels={GENDER_LABEL}
                  evidence={data.evidence}
                  prefix="gender"
                  color={social}
                />
                {data.gender.note && <p className="note">{data.gender.note}</p>}
                <p className="proj-s">
                  Tidak diketahui: {data.gender.unknown.toLocaleString("id-ID")} akun
                </p>
              </Panel>
              <Panel kicker="Estimasi" title="Kelompok umur">
                <AttributeTable
                  attr={data.age}
                  labels={AGE_LABEL}
                  evidence={data.evidence}
                  prefix="age"
                  color={social}
                />
                {data.age.note && <p className="note">{data.age.note}</p>}
                <p className="proj-s">
                  Tidak diketahui: {data.age.unknown.toLocaleString("id-ID")} akun
                </p>
              </Panel>
            </div>

            <Panel kicker="Estimasi" title="Piramida umur × gender">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Umur</th>
                    <th>Laki-laki</th>
                    <th>Perempuan</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(AGE_LABEL)
                    .reverse()
                    .map((age) => (
                      <tr key={age}>
                        <td>{AGE_LABEL[age]}</td>
                        {["L", "P"].map((g) => {
                          const cell = data.pyramid.find((c) => c.age === age && c.gender === g);
                          return (
                            <td key={g} className="mono">
                              {cell?.accounts === null ? "< 5" : (cell?.accounts ?? 0)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                </tbody>
              </table>
              <p className="proj-s">
                Hanya akun yang gender DAN umurnya diketahui. Sel di bawah 5 akun disembunyikan.
              </p>
            </Panel>

            <Panel kicker="Estimasi" title="Minat teratas">
              {data.interests.length === 0 ? (
                <InsufficientData reason="Belum ada akun dengan penanda minat di minimal dua komentar." />
              ) : (
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Minat</th>
                      <th>Akun</th>
                      <th>% dari semua akun</th>
                      <th>Laki-laki</th>
                      <th>Perempuan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.interests.map((i) => (
                      <tr key={i.value}>
                        <td>
                          {i.value}
                          <br />
                          <Evidence items={data.evidence[`minat:${i.value}`]} />
                        </td>
                        <td className="mono">{i.accounts.toLocaleString("id-ID")}</td>
                        <td className="mono">
                          {i.share_of_accounts === null
                            ? "—"
                            : `${pct(i.accounts, n)}%`}
                        </td>
                        {["L", "P"].map((g) => (
                          <td key={g} className="mono">
                            {data.interests_by_gender[g]?.find((x) => x.value === i.value)?.accounts ?? 0}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <form method="get" className="period-bar" style={{ marginTop: 14 }}>
                {win.start && <input type="hidden" name="dari" value={win.start} />}
                {win.end && <input type="hidden" name="sampai" value={win.end} />}
                <label className="field" style={{ flex: 1 }}>
                  <span className="kicker">Kecualikan kata topik (pisahkan dengan koma)</span>
                  <input
                    type="text"
                    name="kecuali"
                    defaultValue={kecuali}
                    placeholder="mis. martabak, kuliah"
                    maxLength={500}
                  />
                </label>
                <button type="submit" className="btn btn-sm">
                  Hitung ulang
                </button>
              </form>
              <p className="note">
                <Info size={13} />
                Periksa kata penanda di tiap baris. Kata yang sebenarnya topik proyek (mis.
                &ldquo;martabak&rdquo; pada percakapan tentang Gibran) membuat minat terlihat besar
                padahal bukan minat penulisnya; kecualikan kata itu lalu hitung ulang.
                {data.excluded.length > 0 && ` Sedang dikecualikan: ${data.excluded.join(", ")}.`}
              </p>
            </Panel>

            <Panel kicker="Estimasi" title="Sentimen per segmen">
              {data.sentiment.length === 0 ? (
                <InsufficientData reason="Belum ada segmen yang terisi." />
              ) : (
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Segmen</th>
                      <th>Akun</th>
                      <th>Konten bernilai</th>
                      <th>Rata-rata sentimen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.sentiment.map((s) => (
                      <tr key={s.segment}>
                        <td>{segmentLabel(s.segment)}</td>
                        <td className="mono">{s.accounts.toLocaleString("id-ID")}</td>
                        <td className="mono">{s.scored.toLocaleString("id-ID")}</td>
                        <td className="mono">
                          {s.mean === null ? "data tidak cukup" : s.mean.toLocaleString("id-ID")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <Provenance
                method={data.method}
                n={`${n.toLocaleString("id-ID")} akun`}
                confidence="Rendah — belum dievaluasi"
                limits={data.limitations[0] ?? ""}
              />
            </Panel>

            <Panel kicker="Batasan" title="Apa yang angka ini tidak katakan">
              <ul className="nolist">
                {data.limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
              <p className="proj-s">
                Dihitung {new Date(data.computed_at).toLocaleString("id-ID", { timeZone: "Asia/Jakarta", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} WIB; hasil disimpan
                10 menit. Ambang keyakinan {data.min_confidence.toLocaleString("id-ID")}.
              </p>
            </Panel>
          </>
        )}
      </div>
    </>
  );
}
