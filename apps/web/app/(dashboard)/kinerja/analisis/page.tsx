import Link from "next/link";
import type { Route } from "next";
import { cookies } from "next/headers";
import { AlignmentForm } from "@/components/AlignmentForm";
import { CodingForm } from "@/components/CodingForm";
import { DeleteRowButton, FlowForm } from "@/components/FlowForm";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { ResponseRateFetch } from "@/components/ResponseRateFetch";
import { SiteActions, SiteAddForm } from "@/components/SiteControls";
import { api, ApiError } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";
import { SESSION_COOKIE, decodeJwtPayload } from "@/lib/session";
import type { PostsSummary } from "../kinerja";
import {
  ALIGNMENT_LABEL,
  FEED_KIND_LABEL,
  ORIGIN_LABEL,
  alphaLabel,
  coderSlot,
  hoursLabel,
  type Alignment,
  type CodingList,
  type Flow,
  type Reliability,
  type ResponseTime,
  type Sites,
} from "./analisis";

export const dynamic = "force-dynamic";

const CAN_EDIT_ROLES = new Set(["SUPER_ADMIN", "RESEARCH_DIRECTOR", "RESEARCHER"]);
const PAGE = 10;

const TABS = [
  ["kode", "Pengodean isi"],
  ["arus", "Arus informasi"],
  ["selaras", "Keselarasan (C3)"],
  ["tanggap", "Waktu tanggap & tingkat jawab (C4, O8)"],
  ["situs", "Situs resmi"],
] as const;
type Tab = (typeof TABS)[number][0];

/**
 * Analisis isi dan arus informasi (lanjutan modul Kinerja Komunikasi).
 *
 * Semua kode dan cap waktu di halaman ini diisi manusia. Angka yang dihitung
 * sistem (alpha, median selang, C4, O8) keluar sebagai saran dengan batasnya,
 * dan ditahan bila datanya kurang. Tidak ada kalimat buatan model.
 */

interface Loaded<T> {
  data: T | null;
  missing: boolean;
  message?: string;
}

async function load<T>(path: string): Promise<Loaded<T>> {
  try {
    return { data: await api<T>(path), missing: false };
  } catch (e) {
    if (e instanceof ApiError) return { data: null, missing: e.status === 409, message: e.message };
    throw e;
  }
}

function one(v: string | string[] | undefined): string {
  return (Array.isArray(v) ? v[0] : v)?.trim() ?? "";
}

function href(params: Record<string, string | number | undefined>): Route {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") q.set(k, String(v));
  return `/kinerja/analisis?${q.toString()}` as Route;
}

function Missing({ message }: { message?: string }) {
  return (
    <Panel title="Bagian ini belum aktif di basis data">
      <InsufficientData
        reason={
          message ??
          "Tabel pengodean dan arus informasi belum ada. Jalankan db/migrations/2026-11-15-kinerja-pengodean-arus.sql."
        }
      />
    </Panel>
  );
}

export default async function AnalisisPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const project = await getCurrentProject();
  const base = `/projects/${project.id}/comm-performance`;
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  const role = token ? decodeJwtPayload(token)?.role : undefined;
  const canEdit = typeof role === "string" && CAN_EDIT_ROLES.has(role);

  const rawTab = one(sp.bagian);
  const tab: Tab = TABS.some(([k]) => k === rawTab) ? (rawTab as Tab) : "kode";
  const coder = coderSlot(one(sp.pengode));
  const account = one(sp.akun);

  return (
    <>
      <PageHeader kicker="Kinerja Komunikasi · analisis" title={project.name} isDemo={project.is_demo} />

      <div className="kin-flag" role="note">
        <b>Rancangan model, belum divalidasi.</b> Kode dan cap waktu diisi manusia; sistem hanya
        menghitung dan menahan angka yang datanya kurang. Saran skor bukan skor resmi: penilai
        tetap mengisinya di{" "}
        <Link href={"/kinerja" as Route}>halaman Kinerja</Link>.
      </div>

      <nav className="chips" aria-label="Bagian analisis" style={{ margin: "14px 0 18px" }}>
        {TABS.map(([k, label]) => (
          <Link key={k} href={href({ bagian: k })} className={"chip" + (k === tab ? " chip-on" : "")} aria-current={k === tab ? "page" : undefined}>
            {label}
          </Link>
        ))}
      </nav>

      {tab === "kode" && <Kode base={base} projectId={project.id} coder={coder} account={account} canEdit={canEdit} page={Math.max(1, Number(one(sp.halaman)) || 1)} onlyUncoded={one(sp.belum) === "1"} />}
      {tab === "arus" && <Arus base={base} projectId={project.id} subject={one(sp.lembaga)} canEdit={canEdit} />}
      {tab === "selaras" && <Selaras base={base} projectId={project.id} coder={coder} canEdit={canEdit} />}
      {tab === "situs" && <Situs base={base} projectId={project.id} canEdit={canEdit} />}
      {tab === "tanggap" && <Tanggap base={base} projectId={project.id} account={account} keyword={one(sp.kata)} canEdit={canEdit} />}
    </>
  );
}

/* ------------------------------------------------------------ pengodean */

async function Kode({
  base, projectId, coder, account, canEdit, page, onlyUncoded,
}: {
  base: string; projectId: string; coder: 1 | 2; account: string; canEdit: boolean; page: number; onlyUncoded: boolean;
}) {
  const q = new URLSearchParams({ coder: String(coder), limit: String(PAGE), offset: String((page - 1) * PAGE) });
  if (account) q.set("account", account);
  if (onlyUncoded) q.set("only_uncoded", "true");
  const relQ = account ? `?${new URLSearchParams({ account }).toString()}` : "";
  const [list, rel] = await Promise.all([
    load<CodingList>(`${base}/coding?${q.toString()}`),
    load<Reliability>(`${base}/coding/reliability${relQ}`),
  ]);
  if (list.missing || rel.missing) return <Missing message={list.message ?? rel.message} />;
  const l = list.data;
  const r = rel.data;
  const common = { bagian: "kode", akun: account, belum: onlyUncoded ? "1" : undefined };

  return (
    <>
      <Panel kicker="Uji kesepakatan antar-pengode" title="Krippendorff alpha per variabel">
        {!r || r.n_coded === 0 ? (
          <InsufficientData reason="Belum ada unggahan yang dikode." />
        ) : (
          <>
            <section className="stat-row" style={{ marginBottom: 14 }}>
              <div className="stat"><div className="kicker">Unggahan dikode</div><div className="stat-v">{r.n_coded}<span className="stat-u">dari {r.n_posts}</span></div></div>
              <div className="stat"><div className="kicker">Dikode ganda</div><div className="stat-v">{r.n_double_coded}</div>
                <div className="proj-s" style={{ marginTop: 6 }}>
                  {String(Math.round(r.double_share * 1000) / 10).replace(".", ",")}% dari seluruh unggahan · target {Math.round(r.target_double_share * 100)}% {r.meets_target ? "tercapai" : "belum tercapai"}
                </div>
              </div>
            </section>
            <div style={{ overflowX: "auto" }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th scope="col">Variabel</th><th scope="col">Skala</th><th scope="col">n ganda</th>
                    <th scope="col">Alpha</th><th scope="col">Persen sepakat</th><th scope="col">Bacaan</th>
                  </tr>
                </thead>
                <tbody>
                  {r.variables.map((v) => (
                    <tr key={v.code}>
                      <td><span className="strong">{v.code}</span> {v.name}</td>
                      <td>{v.level}</td>
                      <td className="mono">{v.n_double_coded}</td>
                      <td className="mono">{alphaLabel(v.alpha)}</td>
                      <td className="mono">{v.percent_agreement === null ? "—" : `${String(Math.round(v.percent_agreement * 1000) / 10).replace(".", ",")}%`}</td>
                      <td>{v.label}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h3 className="kicker" style={{ margin: "18px 0 8px" }}>Sebaran kode (satu kode per unggahan)</h3>
            <div className="code-grid">
              {r.distributions.filter((d) => d.n > 0).map((d) => (
                <div key={d.code} className="read">
                  <div className="read-t">{d.code} · {d.name} <span className="proj-s">n {d.n}{d.tested ? "" : " · belum diuji kesepakatannya"}</span></div>
                  {d.published ? (
                    <ul className="bar-list">
                      {d.counts.map(([value, label, n]) => (
                        <li key={value}>
                          <span className="bar-list-l">{label}</span>
                          <span className="bar-list-track"><span className="bar-list-fill" style={{ width: `${(n / d.n) * 100}%` }} /></span>
                          <span className="mono bar-list-v">{n}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="read-d">Ditahan: alpha di bawah ambang. Perbaiki definisi kategori lalu kode ulang.</div>
                  )}
                </div>
              ))}
            </div>
            <Provenance
              method={r.method}
              n={`${r.n_double_coded} unggahan dikode ganda, ${r.n_coded} dikode`}
              confidence="alpha ≥ 0,80 dapat diandalkan; 0,667–0,80 sementara; di bawahnya ditahan"
              limits={r.limitations.join(" ")}
            />
          </>
        )}
      </Panel>

      <Panel kicker={`Lembar pengode ${coder}`} title="Kode isi per unggahan">
        <div className="chips" style={{ marginBottom: 12 }}>
          {[1, 2].map((c) => (
            <Link key={c} href={href({ ...common, pengode: c })} className={"chip" + (c === coder ? " chip-on" : "")}>Lembar pengode {c}</Link>
          ))}
          <Link href={href({ bagian: "kode", akun: account, pengode: coder, belum: onlyUncoded ? undefined : "1" })} className={"chip" + (onlyUncoded ? " chip-on" : "")}>
            Hanya yang belum dikode
          </Link>
        </div>
        {l && l.accounts.length > 1 && (
          <div className="chips" style={{ marginBottom: 12 }}>
            <Link href={href({ bagian: "kode", pengode: coder })} className={"chip" + (account === "" ? " chip-on" : "")}>Semua akun</Link>
            {l.accounts.map((a) => (
              <Link key={a} href={href({ bagian: "kode", pengode: coder, akun: a })} className={"chip" + (a === account ? " chip-on" : "")}>{a}</Link>
            ))}
          </div>
        )}
        <p className="field-hint" style={{ marginBottom: 12 }}>
          Dua lembar dipakai untuk uji kesepakatan: pengode kedua mengisi lembar 2 tanpa melihat lembar 1.
          Sistem tidak bisa memastikan keduanya bekerja terpisah. Buku kode: Lampiran A kerangka.
        </p>
        {!l || l.total === 0 ? (
          <InsufficientData reason="Belum ada unggahan akun resmi di proyek ini. Ambil atau unggah dulu di halaman Kinerja." />
        ) : (
          <>
            <div className="proj-s" style={{ marginBottom: 10 }}>
              {l.n_coded} dari {l.total} unggahan sudah dikode di lembar ini
            </div>
            {l.items.length === 0 && <p className="field-hint">Tidak ada unggahan pada halaman ini.</p>}
            {l.items.map((row) => (
              <CodingForm key={`${row.post_id}-${coder}`} projectId={projectId} coder={coder} row={row} variables={l.variables} canEdit={canEdit} />
            ))}
            <div className="chips" style={{ marginTop: 12 }}>
              {page > 1 && <Link className="chip" href={href({ ...common, pengode: coder, halaman: page - 1 })}>← Sebelumnya</Link>}
              {l.items.length === PAGE && <Link className="chip" href={href({ ...common, pengode: coder, halaman: page + 1 })}>Berikutnya →</Link>}
            </div>
          </>
        )}
      </Panel>
    </>
  );
}

/* ------------------------------------------------------- arus informasi */

async function Arus({ base, projectId, subject, canEdit }: { base: string; projectId: string; subject: string; canEdit: boolean }) {
  const q = subject ? `?${new URLSearchParams({ subject }).toString()}` : "";
  const flow = await load<Flow>(`${base}/flow${q}`);
  if (flow.missing) return <Missing message={flow.message} />;
  const f = flow.data;
  if (!f) return <Panel title="Arus informasi"><InsufficientData reason={flow.message ?? "Belum bisa dimuat."} /></Panel>;
  const maxB = Math.max(1, ...f.stages.map((s) => s.n_bottleneck));
  const stageInterval = (stage: number) => f.intervals.find((i) => i.stages.includes(stage))?.code;

  return (
    <>
      <Panel kicker="Information Flow" title={subject ? `Selang T1–T4 · ${subject}` : "Selang T1–T4 pada 11 tahap model acuan"}>
        {f.subjects.length > 1 && (
          <div className="chips" style={{ marginBottom: 12 }}>
            <Link href={href({ bagian: "arus" })} className={"chip" + (subject === "" ? " chip-on" : "")}>Semua lembaga</Link>
            {f.subjects.map((s) => (
              <Link key={s} href={href({ bagian: "arus", lembaga: s })} className={"chip" + (s === subject ? " chip-on" : "")}>{s}</Link>
            ))}
          </div>
        )}
        {f.n_records === 0 ? (
          <InsufficientData reason="Belum ada konten yang ditelusuri. Catat 10–20 konten dari log atau wawancara di formulir bawah." />
        ) : (
          <>
            <div className="kin-dims">
              {f.intervals.map((i) => (
                <div key={i.code} className="kin-dim">
                  <div className="kicker">{i.code}{f.slowest === i.code ? " · paling lambat" : ""}</div>
                  {i.median_hours === null ? (
                    <div className="kin-dim-off">Data tidak cukup</div>
                  ) : (
                    <div className="kin-dim-v">{hoursLabel(i.median_hours)}</div>
                  )}
                  <div className="read-d">{i.meaning}</div>
                  <div className="proj-s" style={{ marginTop: 6 }}>
                    n {i.n} dari minimal {f.min_records}{i.max_hours !== null ? ` · terlama ${hoursLabel(i.max_hours)}` : ""}
                  </div>
                </div>
              ))}
            </div>
            <h3 className="kicker" style={{ margin: "18px 0 8px" }}>Tahap yang ditandai auditor sebagai hambatan</h3>
            <ol className="bar-list bar-list-wide">
              {f.stages.map((s) => (
                <li key={s.stage}>
                  <span className="bar-list-l">{s.stage}. {s.name}{stageInterval(s.stage) ? <span className="proj-s"> {stageInterval(s.stage)}</span> : null}</span>
                  <span className="bar-list-track"><span className="bar-list-fill" style={{ width: `${(s.n_bottleneck / maxB) * 100}%` }} /></span>
                  <span className="mono bar-list-v">{s.n_bottleneck}</span>
                </li>
              ))}
            </ol>
            <Provenance method={f.method} n={`${f.n_records} konten ditelusuri`} confidence="bergantung pada kelengkapan log auditor" limits={f.limitations.join(" ")} />
          </>
        )}
      </Panel>

      <Panel kicker="Catatan auditor" title="Konten yang ditelusuri">
        {f.records.length > 0 && (
          <div style={{ overflowX: "auto", marginBottom: 18 }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th scope="col">Konten</th><th scope="col">Lembaga</th><th scope="col">Jenis</th>
                  <th scope="col">T1</th><th scope="col">T2</th><th scope="col">T3</th><th scope="col">T4</th>
                  <th scope="col">Hambatan</th>{canEdit && <th scope="col"><span className="sr-only">Tindakan</span></th>}
                </tr>
              </thead>
              <tbody>
                {f.records.map((r) => (
                  <tr key={r.id}>
                    <td className="strong">{r.label}{r.note && <div className="proj-s">{r.note}</div>}</td>
                    <td>{r.subject}</td>
                    <td>{r.kind}</td>
                    {["T1", "T2", "T3", "T4"].map((t) => <td key={t} className="mono">{hoursLabel(r.hours[t])}</td>)}
                    <td>{r.bottleneck_stage ? `tahap ${r.bottleneck_stage}` : "—"}</td>
                    {canEdit && <td><DeleteRowButton projectId={projectId} id={r.id} kind="flow" /></td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {canEdit ? (
          <FlowForm projectId={projectId} stages={f.stages} defaultSubject={subject || f.subjects[0] || ""} />
        ) : (
          <p className="field-hint">Peran Anda hanya bisa melihat.</p>
        )}
      </Panel>
    </>
  );
}

/* ---------------------------------------------------------- keselarasan */

async function Selaras({ base, projectId, coder, canEdit }: { base: string; projectId: string; coder: 1 | 2; canEdit: boolean }) {
  const res = await load<Alignment>(`${base}/alignment`);
  if (res.missing) return <Missing message={res.message} />;
  const a = res.data;
  if (!a) return <Panel title="Keselarasan"><InsufficientData reason={res.message ?? "Belum bisa dimuat."} /></Panel>;

  return (
    <>
      <Panel kicker="Indikator C3" title="Keselarasan pesan antarlembaga">
        {a.n_pairs === 0 ? (
          <InsufficientData reason="Belum ada pasangan pernyataan yang dikode." />
        ) : (
          <>
            <section className="stat-row" style={{ marginBottom: 14 }}>
              <div className="stat stat-big">
                <div className="kicker">Saran skor C3</div>
                {a.suggested_score === null ? (
                  <div className="kin-dim-off">Data tidak cukup ({a.n_pairs} dari minimal {a.min_pairs} pasangan)</div>
                ) : (
                  <div className="stat-v">{a.suggested_score}<span className="stat-u">dari 5</span></div>
                )}
              </div>
              {Object.entries(ALIGNMENT_LABEL).map(([k, label]) => (
                <div key={k} className="stat"><div className="kicker">{label}</div><div className="stat-v">{a.counts[k] ?? 0}</div></div>
              ))}
              <div className="stat"><div className="kicker">Bertentangan, belum diralat</div><div className="stat-v">{a.n_contradiction_open}</div></div>
            </section>
            <p className="field-hint">
              Kesepakatan dua lembar pengode: alpha {alphaLabel(a.alpha)} · {a.alpha_label} · {a.n_double_coded} pasangan dikode ganda.
            </p>
            <div style={{ overflowX: "auto", marginTop: 12 }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th scope="col">Isu</th><th scope="col">Lembaga A</th><th scope="col">Lembaga B</th>
                    <th scope="col">Lembar</th><th scope="col">Kode</th><th scope="col">Catatan</th>
                    {canEdit && <th scope="col"><span className="sr-only">Tindakan</span></th>}
                  </tr>
                </thead>
                <tbody>
                  {a.items.map((p) => (
                    <tr key={p.id}>
                      <td className="strong">{p.issue}</td>
                      <td>{p.url_a ? <a href={p.url_a} target="_blank" rel="noopener noreferrer">{p.subject_a}</a> : p.subject_a}</td>
                      <td>{p.url_b ? <a href={p.url_b} target="_blank" rel="noopener noreferrer">{p.subject_b}</a> : p.subject_b}</td>
                      <td className="mono">{p.coder}</td>
                      <td>{ALIGNMENT_LABEL[p.code]}{p.code === "bertentangan" ? (p.corrected ? " (sudah diralat)" : " (belum diralat)") : ""}</td>
                      <td>{p.note || "—"}</td>
                      {canEdit && <td><DeleteRowButton projectId={projectId} id={p.id} kind="alignment" /></td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Provenance method={a.method} n={`${a.n_pairs} pasangan pernyataan`} confidence="saran dari kode manusia; bukan skor resmi" limits={a.limitations.join(" ")} />
          </>
        )}
      </Panel>
      {canEdit && (
        <Panel kicker={`Lembar pengode ${coder}`} title="Kode pasangan pernyataan">
          <div className="chips" style={{ marginBottom: 12 }}>
            {[1, 2].map((c) => (
              <Link key={c} href={href({ bagian: "selaras", pengode: c })} className={"chip" + (c === coder ? " chip-on" : "")}>Lembar pengode {c}</Link>
            ))}
          </div>
          <AlignmentForm projectId={projectId} coder={coder} />
        </Panel>
      )}
    </>
  );
}

/* ------------------------------------------- waktu tanggap & tingkat jawab */

async function Tanggap({ base, projectId, account, keyword, canEdit }: { base: string; projectId: string; account: string; keyword: string; canEdit: boolean }) {
  const posts = await load<PostsSummary>(`${base}/posts/summary`);
  if (posts.missing) return <Missing message={posts.message} />;
  const accounts = Array.from(new Set((posts.data?.accounts ?? []).map((x) => x.account)));
  const youtube = Array.from(new Set((posts.data?.accounts ?? []).filter((x) => x.platform === "youtube").map((x) => x.account)));
  const chosen = account || accounts[0] || "";
  const q = new URLSearchParams({ account: chosen });
  if (keyword) q.set("keyword", keyword);
  const rt = chosen ? await load<ResponseTime>(`${base}/response-time?${q.toString()}`) : null;
  const t = rt?.data ?? null;

  return (
    <>
      <Panel kicker="Indikator C4 · saran" title="Waktu tanggap terhadap lonjakan percakapan">
        {accounts.length === 0 ? (
          <InsufficientData reason="Belum ada unggahan akun resmi di proyek ini." />
        ) : (
          <>
            <form method="get" className="period-bar">
              <input type="hidden" name="bagian" value="tanggap" />
              <label className="field">
                <span className="kicker">Akun resmi</span>
                <select name="akun" defaultValue={chosen}>
                  {accounts.map((x) => <option key={x} value={x}>{x}</option>)}
                </select>
              </label>
              <label className="field">
                <span className="kicker">Kata di takarir (opsional)</span>
                <input name="kata" defaultValue={keyword} maxLength={80} />
              </label>
              <button type="submit" className="btn btn-sm">Terapkan</button>
            </form>
            {!t ? (
              <InsufficientData reason={rt?.message ?? "Belum bisa dimuat."} />
            ) : (
              <>
                <section className="stat-row" style={{ marginBottom: 14 }}>
                  <div className="stat stat-big">
                    <div className="kicker">Saran skor C4</div>
                    {t.suggested_score === null ? <div className="kin-dim-off">Data tidak cukup</div> : <div className="stat-v">{t.suggested_score}<span className="stat-u">dari 5</span></div>}
                  </div>
                  <div className="stat"><div className="kicker">Median selang</div><div className="stat-v" style={{ fontSize: 20 }}>{t.median_hours === null ? "belum ada" : hoursLabel(t.median_hours)}</div></div>
                  <div className="stat"><div className="kicker">Hari lonjakan</div><div className="stat-v">{t.spikes.length}</div><div className="proj-s" style={{ marginTop: 6 }}>{t.n_unanswered} tanpa unggahan dalam batas waktu</div></div>
                  <div className="stat"><div className="kicker">Unggahan resmi dihitung</div><div className="stat-v">{t.n_official_posts}</div></div>
                </section>
                {t.spikes.length > 0 && (
                  <div style={{ overflowX: "auto" }}>
                    <table className="tbl">
                      <thead><tr><th scope="col">Hari lonjakan ({t.timezone})</th><th scope="col">Percakapan sosial</th><th scope="col">Kali median</th><th scope="col">Selang ke unggahan resmi pertama</th></tr></thead>
                      <tbody>
                        {t.spikes.map((s) => (
                          <tr key={s.day}>
                            <td className="strong">{s.day}</td>
                            <td className="mono">{s.volume.toLocaleString("id-ID")}</td>
                            <td className="mono">{String(s.ratio).replace(".", ",")}×</td>
                            <td className="mono">{s.hours === null ? "tidak ada unggahan" : hoursLabel(s.hours)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <Provenance
                  method={t.method}
                  n={`${t.n_days} hari berdata, ${t.period_start} s.d. ${t.period_end}; median ${String(t.median_daily_volume).replace(".", ",")} percakapan per hari`}
                  confidence="saran; selang waktu, bukan bukti tanggapan"
                  limits={t.limitations.join(" ")}
                />
              </>
            )}
          </>
        )}
      </Panel>
      <Panel kicker="Indikator O8 · saran" title="Tingkat jawab di kanal YouTube resmi">
        {canEdit ? <ResponseRateFetch projectId={projectId} accounts={youtube} /> : <p className="field-hint">Peran Anda hanya bisa melihat.</p>}
      </Panel>
    </>
  );
}

/* ------------------------------------------------------- situs web resmi */

function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Jakarta" });
}

async function Situs({ base, projectId, canEdit }: { base: string; projectId: string; canEdit: boolean }) {
  const res = await load<Sites>(`${base}/sites`);
  if (res.missing) {
    return <Missing message={res.message ?? "Tabel situs resmi belum ada. Jalankan db/migrations/2026-11-15b-kinerja-situs-resmi.sql."} />;
  }
  const d = res.data;
  if (!d) return <Panel title="Situs resmi"><InsufficientData reason={res.message ?? "Belum bisa dimuat."} /></Panel>;
  const quiet = d.sites.filter((s) => s.n_total > 0 && s.quiet).length;
  const unread = d.sites.filter((s) => s.feed_kind === "none").length;

  return (
    <>
      <Panel kicker="Situs web resmi" title="Apa yang terbit untuk publik, dan seberapa sering">
        {d.sites.length === 0 ? (
          <InsufficientData reason="Belum ada situs resmi yang didaftarkan di proyek ini." />
        ) : (
          <>
            <section className="stat-row" style={{ marginBottom: 14 }}>
              <div className="stat"><div className="kicker">Situs terdaftar</div><div className="stat-v">{d.sites.length}</div></div>
              <div className="stat"><div className="kicker">Belum terbaca</div><div className="stat-v">{unread}</div><div className="proj-s" style={{ marginTop: 6 }}>tanpa feed, sitemap bertanggal, atau halaman daftar</div></div>
              <div className="stat"><div className="kicker">Sepi ≥ {d.quiet_days} hari</div><div className="stat-v">{quiet}</div><div className="proj-s" style={{ marginTop: 6 }}>dari situs yang punya butir tercatat</div></div>
            </section>
            <div style={{ overflowX: "auto" }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th scope="col">Lembaga</th><th scope="col">Dibaca dari</th>
                    <th scope="col">Terbitan 30 hari</th><th scope="col">Terbitan {d.window_days} hari</th>
                    <th scope="col">Terakhir terbit</th><th scope="col">Jeda terpanjang</th>
                    <th scope="col">Median jeda</th><th scope="col">Bacaan</th>
                  </tr>
                </thead>
                <tbody>
                  {d.sites.map((s) => (
                    <tr key={s.id}>
                      <td><span className="strong">{s.subject}</span><div className="proj-s">{s.base_url.replace("https://", "")}</div></td>
                      <td>{FEED_KIND_LABEL[s.feed_kind]}</td>
                      <td className="mono">{s.n_total === 0 ? "—" : s.n_30}</td>
                      <td className="mono">{s.n_total === 0 ? "—" : s.n_window}</td>
                      <td className="mono">{s.last_published ? `${s.last_published} (${s.days_since_last} hari lalu)` : "tidak tercatat"}</td>
                      <td className="mono">{s.longest_gap_days === null ? "—" : `${s.longest_gap_days} hari`}</td>
                      <td className="mono">{s.median_gap_days === null ? "data tidak cukup" : `${String(s.median_gap_days).replace(".", ",")} hari`}</td>
                      <td>{s.quiet && s.n_total > 0 ? <span className="pill pill-warn">{s.status}</span> : s.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="field-hint" style={{ marginTop: 10 }}>
              Baris tidak diperingkat. Angka hanya menghitung butir yang tercatat di proyek ini per {d.today}.
            </p>
            <Provenance
              method={d.method}
              n={`${d.sites.reduce((a, s) => a + s.n_total, 0)} butir dari ${d.sites.length} situs`}
              confidence="bergantung pada kelengkapan butir yang tercatat per situs"
              limits={d.limitations.join(" ")}
            />
          </>
        )}
      </Panel>

      {d.sites.map((s) => {
        const max = Math.max(1, ...s.weeks.map((w) => w.n));
        return (
          <Panel key={s.id} kicker={`${FEED_KIND_LABEL[s.feed_kind]} · ${s.base_url.replace("https://", "")}`} title={s.subject}>
            {s.n_total === 0 ? (
              <InsufficientData reason="Belum ada butir tercatat untuk situs ini. Daftarkan halaman daftar beritanya, atau unggah butirnya lewat CSV." />
            ) : (
              <>
                <h3 className="kicker" style={{ marginBottom: 8 }}>Terbitan per minggu ({d.window_days} hari terakhir)</h3>
                <div className="week-bars" role="img" aria-label={`Terbitan per minggu ${s.subject}: ${s.weeks.map((w) => `${w.start} ${w.n}`).join(", ")}`}>
                  {s.weeks.map((w) => (
                    <div key={w.start} className="week-bar" title={`Minggu ${w.start}: ${w.n} terbitan`}>
                      <span className="week-bar-n">{w.n}</span>
                      <span className={"week-bar-fill" + (w.n === 0 ? " is-empty" : "")} style={{ height: `${w.n === 0 ? 2 : Math.max(6, (w.n / max) * 64)}px` }} />
                      <span className="week-bar-l">{w.start.slice(8)}/{w.start.slice(5, 7)}</span>
                    </div>
                  ))}
                </div>
                <p className="field-hint">
                  {s.weeks_without} dari {s.weeks.length} minggu tanpa terbitan tercatat · {s.active_days} hari berbeda punya terbitan · butir berasal dari{" "}
                  {Object.entries(s.origins).map(([k, n]) => `${ORIGIN_LABEL[k] ?? k} (${n})`).join(", ")}
                  {s.last_captured_at ? ` · data terakhir masuk ${shortDate(s.last_captured_at)}` : ""}
                </p>
                {s.categories.length > 0 && (
                  <div className="chips" style={{ margin: "10px 0" }}>
                    {s.categories.map(([k, label, n]) => <span key={k} className="chip">{label}<b>{n}</b></span>)}
                  </div>
                )}
                <h3 className="kicker" style={{ margin: "14px 0 6px" }}>Butir terbaru</h3>
                <ul className="site-latest">
                  {s.latest.map((i) => (
                    <li key={i.url}>
                      <span className="mono">{shortDate(i.published_at)}</span>{" "}
                      <a href={i.url} target="_blank" rel="noopener noreferrer">{i.title || decodeURIComponent(new URL(i.url).pathname.split("/").filter(Boolean).pop() ?? i.url)}</a>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {s.check_notes.length > 0 && (
              <details style={{ marginTop: 12 }}>
                <summary className="field-hint">Catatan pembacaan{s.checked_at ? ` (${shortDate(s.checked_at)})` : ""}</summary>
                <ul className="read-d" style={{ paddingLeft: 18, marginTop: 6 }}>
                  {s.check_notes.map((n) => <li key={n}>{n}</li>)}
                </ul>
              </details>
            )}
            {canEdit && <SiteActions projectId={projectId} siteId={s.id} baseUrl={s.base_url} listUrls={s.list_urls} />}
          </Panel>
        );
      })}

      {canEdit && (
        <Panel kicker="Tambah situs" title="Daftarkan situs web resmi lembaga">
          <SiteAddForm projectId={projectId} />
        </Panel>
      )}
    </>
  );
}
