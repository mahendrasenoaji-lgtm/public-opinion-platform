import Link from "next/link";
import type { Route } from "next";
import { cookies } from "next/headers";
import { IndicatorForm } from "@/components/IndicatorForm";
import { OfficialPostsUpload } from "@/components/OfficialPostsUpload";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { api, ApiError } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";
import { SESSION_COOKIE, decodeJwtPayload } from "@/lib/session";
import {
  PERIOD_RE,
  PLATFORM_LABEL,
  coverageText,
  currentPeriod,
  dimensionLabel,
  formatMedian,
  formatScore,
  type AssessmentRef,
  type Framework,
  type PostsSummary,
  type Scorecard,
} from "./kinerja";

export const dynamic = "force-dynamic";

const CAN_EDIT_ROLES = new Set(["SUPER_ADMIN", "RESEARCH_DIRECTOR", "RESEARCHER"]);

/**
 * Kinerja Komunikasi Pemerintah (rancangan model, belum divalidasi).
 *
 * Halaman ini tidak menghitung apa pun dari percakapan warga dan tidak memuat
 * kalimat buatan model. Isinya: (1) kartu skor dari isian penilai, yang hanya
 * terbit bila cakupan datanya cukup; (2) ringkasan unggahan akun resmi per
 * akun per platform, tidak dijumlah lintas platform; (3) formulir isian.
 * Kerangka: docs/kerangka-kinerja-komunikasi-pemerintah.md.
 */

interface Loaded<T> {
  data: T | null;
  missing: boolean;
  message?: string;
}

/** 409 = tabel modul belum dimigrasikan; galat backend lain = belum bisa disajikan. */
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

export default async function KinerjaPage({
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

  const [framework, posts, refs] = await Promise.all([
    load<Framework>(`${base}/framework`),
    load<PostsSummary>(`${base}/posts/summary`),
    load<AssessmentRef[]>(`${base}/assessments`),
  ]);

  const assessments = refs.data ?? [];
  const subject = one(sp.lembaga) || assessments[0]?.subject || "";
  const periodParam = one(sp.periode);
  const period = PERIOD_RE.test(periodParam) ? periodParam : assessments[0]?.period || currentPeriod();
  const card = subject
    ? await load<Scorecard>(
        `${base}/scores?${new URLSearchParams({ subject, period }).toString()}`,
      )
    : null;

  const tablesMissing = posts.missing || refs.missing;
  const fw = framework.data;

  return (
    <>
      <PageHeader kicker="Kinerja Komunikasi Pemerintah" title={project.name} isDemo={project.is_demo} />

      <div className="kin-flag" role="note">
        <b>Rancangan model, belum divalidasi.</b>{" "}
        Bobot, ambang, dan sebutan skor adalah usulan penyusun, bukan standar resmi pemerintah. Skor diisi penilai dengan bukti; data yang tidak ada dicatat &quot;tidak tersedia&quot; dan tidak
        ditebak. Popularitas di media sosial bukan ukuran efektivitas komunikasi.
        {fw && <> Versi model: <span className="mono">{fw.model_version}</span>.</>}
      </div>

      {tablesMissing && (
        <Panel title="Modul belum aktif di basis data">
          <InsufficientData
            reason={
              posts.message ??
              refs.message ??
              "Tabel modul Kinerja Komunikasi belum ada. Jalankan migrasi 2026-11-12 di basis data."
            }
          />
        </Panel>
      )}

      {!fw && !tablesMissing && (
        <Panel title="Kerangka belum bisa dimuat">
          <InsufficientData reason="Backend belum memuat modul ini. Coba muat ulang beberapa menit lagi." />
        </Panel>
      )}

      {fw && !tablesMissing && (
        <>
          <div id="kartu" />
          <Panel
            kicker="Kartu skor"
            title={subject ? `${subject} · ${period}` : "Belum ada lembaga yang dinilai"}
          >
            {assessments.length > 0 && (
              <div className="chips" style={{ marginBottom: 14 }}>
                {assessments.map((a) => {
                  const q = new URLSearchParams({ lembaga: a.subject, periode: a.period });
                  const on = a.subject === subject && a.period === period;
                  return (
                    <Link
                      key={`${a.subject}|${a.period}`}
                      href={`/kinerja?${q.toString()}#kartu` as Route}
                      className="chip"
                      aria-current={on ? "true" : undefined}
                      style={on ? { borderColor: "var(--txt2)", color: "var(--txt)" } : undefined}
                    >
                      {a.subject} · {a.period} ({a.n_scored} skor)
                    </Link>
                  );
                })}
              </div>
            )}

            {!card?.data ? (
              <InsufficientData
                reason={
                  subject
                    ? "Isian untuk lembaga dan periode ini belum bisa dimuat."
                    : "Belum ada isian. Isi indikator di bagian bawah untuk membuat kartu skor pertama."
                }
              />
            ) : (
              <>
                <div className="kin-dims">
                  {card.data.dimensions.map((d) => (
                    <div key={d.dimension} className="kin-dim">
                      <div className="kicker">
                        {dimensionLabel(d.dimension)} · bobot {d.weight}%
                      </div>
                      {d.score !== null ? (
                        <div className="kin-dim-v">
                          {formatScore(d.score)} <span className="stat-u">dari 5</span>
                        </div>
                      ) : (
                        <div className="kin-dim-off">Tidak terbit</div>
                      )}
                      <div className="field-hint">Cakupan: {coverageText(d)}</div>
                      <div
                        className="kin-bar"
                        role="img"
                        aria-label={`Cakupan ${dimensionLabel(d.dimension)} ${Math.round(d.coverage * 100)} persen`}
                      >
                        <span style={{ width: `${Math.round(d.coverage * 100)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>

                <div className="read" style={{ marginTop: 14 }}>
                  {card.data.total !== null ? (
                    <>
                      <div className="read-t">
                        Skor total {formatScore(card.data.total)} dari 5 · sebutan usulan:{" "}
                        {card.data.label}
                      </div>
                      <div className="read-d">
                        Uji kepekaan dengan bobot rata (25% per dimensi):{" "}
                        {card.data.total_equal_weights !== null
                          ? formatScore(card.data.total_equal_weights)
                          : "tidak terbit"}
                        . Bila kedua angka jatuh pada sebutan berbeda, jangan memakai sebutannya.
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="read-t">Skor total tidak terbit</div>
                      <div className="read-d">
                        Skor total hanya dihitung bila keempat dimensi terbit, dan satu dimensi terbit
                        bila minimal {Math.round(fw.min_coverage * 100)}% indikatornya punya skor.
                      </div>
                    </>
                  )}
                  <div className="read-d">
                    {card.data.n_scored} indikator berskor, {card.data.n_unavailable} dicatat tidak
                    tersedia, {card.data.n_empty} belum diisi.
                  </div>
                </div>

                <Provenance
                  method={card.data.method}
                  n={`${card.data.n_scored} dari ${fw.indicators.length} indikator`}
                  confidence="rendah (model belum divalidasi)"
                  limits={card.data.limitations.join(" ")}
                />
              </>
            )}
          </Panel>

          <Panel kicker="Output · data unggahan" title="Akun resmi per platform">
            {!posts.data || posts.data.n_posts === 0 ? (
              <InsufficientData reason="Belum ada data unggahan akun resmi. Unggah berkas di bagian bawah." />
            ) : (
              <>
                <div style={{ overflowX: "auto" }}>
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th scope="col">Akun</th>
                        <th scope="col">Platform</th>
                        <th scope="col">Unggahan</th>
                        <th scope="col">Median like</th>
                        <th scope="col">Median komentar</th>
                        <th scope="col">Median share</th>
                        <th scope="col">Median views</th>
                        <th scope="col">Engagement rate (per pengikut)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {posts.data.accounts.map((a) => (
                        <tr key={`${a.account}|${a.platform}`}>
                          <td className="strong">{a.account}</td>
                          <td>{PLATFORM_LABEL[a.platform] ?? a.platform}</td>
                          <td className="mono">
                            {a.n_posts}
                            {a.insufficient_data && (
                              <span className="pill pill-warn" style={{ marginLeft: 6 }}>
                                data tidak cukup
                              </span>
                            )}
                          </td>
                          <td className="mono">{formatMedian(a.median_likes)}</td>
                          <td className="mono">{formatMedian(a.median_comments)}</td>
                          <td className="mono">{formatMedian(a.median_shares)}</td>
                          <td className="mono">{formatMedian(a.median_views)}</td>
                          <td className="mono">
                            {a.median_engagement_rate === null
                              ? "tidak tersedia"
                              : `${formatMedian(a.median_engagement_rate)}% (n ${a.n_engagement_rate})`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="field-hint" style={{ marginTop: 10 }}>
                  Baris tidak dijumlah dan tidak diperingkat lintas platform. &quot;Tidak tersedia&quot;
                  berarti angkanya tidak ada di berkas atau kurang dari {fw.min_posts_for_median}{" "}
                  unggahan memuatnya.
                </p>
                <Provenance
                  method={posts.data.method}
                  n={`${posts.data.n_posts} unggahan akun resmi`}
                  confidence="bergantung pada berkas yang diunggah"
                  limits={posts.data.limitations.join(" ")}
                />
              </>
            )}
            {canEdit && (
              <div className="act-block" style={{ marginTop: 22 }}>
                <h3 className="kicker" style={{ marginBottom: 8 }}>Unggah data akun resmi</h3>
                <OfficialPostsUpload projectId={project.id} />
              </div>
            )}
          </Panel>

          <Panel kicker="Isian penilai" title="Indikator Input, Process, Output, Outcome">
            <IndicatorForm
              key={`${subject}|${period}`}
              projectId={project.id}
              indicators={fw.indicators}
              dimensions={fw.dimensions}
              initialSubject={subject}
              initialPeriod={period}
              initialItems={card?.data?.items ?? []}
              canEdit={canEdit}
            />
          </Panel>
        </>
      )}
    </>
  );
}
