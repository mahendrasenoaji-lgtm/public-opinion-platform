import type { ReactNode } from "react";
import Link from "next/link";
import type { Route } from "next";
import { PageHeader } from "@/components/PageHeader";
import { PrintButton } from "@/components/PrintButton";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { SOURCE } from "@/lib/tokens";
import { apiOrNullLenient, type Metric, type SignalSource } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";
import { SENTIMENT_LIMITS, formatSentiment } from "../sinyal/sentiment";
import { EMOTION_LABELS, ZONES, hourLabel, parseWindow, windowQuery } from "../sinyal/window";
import {
  type ConversationReport,
  type ReportItem,
  clip,
  dayLabel,
  labelShares,
  mostNegativeDay,
  pct,
  rankTopics,
} from "./report";

export const dynamic = "force-dynamic";

/**
 * Laporan Percakapan: satu halaman tanya-jawab yang merangkai angka dari
 * endpoint sinyal yang sudah ada, untuk dibaca berurutan atau dicetak.
 *
 * Tidak ada kalimat yang ditulis model di sini. Setiap jawaban adalah angka
 * dengan metode dan penyebutnya; yang belum bisa dijawab datanya dinyatakan
 * "data tidak cukup", bukan diisi. Sumber tidak pernah digabung (R1), akun
 * penulis tidak ditampilkan (CLAUDE.md bagian 3).
 */

interface Summary {
  volume: Metric;
  sentiment: Metric;
  distinct_authors: number;
  concentration_top10: number;
  period_start: string;
  period_end: string;
  limitations: string[];
}

interface Emotions {
  by_source: {
    source: SignalSource;
    method: string;
    n_total: number;
    n_with_emotion: number;
    coverage: number;
    share: Record<string, number> | null;
    insufficient_data: boolean;
    note: string | null;
    markers?: Record<string, [string, number][]>;
  }[];
  limitations: string[];
}

interface Actors {
  by_source: {
    source: SignalSource;
    method: string;
    n_total: number;
    n_with_actor: number;
    actors: { key: string; name: string; n: number; scored: number; sentiment: number | null }[];
  }[];
  limitations: string[];
}

interface Activity {
  timezone: string;
  weekdays: string[];
  by_source: {
    source: SignalSource;
    method: string;
    n: number;
    engagement_total: number;
    n_with_engagement: number;
    peak_weekday: number | null;
    peak_hour: number | null;
    peak_count: number | null;
    top: (ReportItem & { id: string })[];
  }[];
}

interface Network {
  total_accounts: number;
  total_edges: number;
  method: string;
  insufficient_data: boolean;
  note: string | null;
  limitations: string[];
}

const BELUM_ADA = "Backend belum memuat bagian ini. Coba muat ulang beberapa menit lagi.";

function Question({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <section className="panel qa">
      <header className="panel-head">
        <div>
          <div className="kicker">Pertanyaan {n}</div>
          <h2 className="panel-title">{title}</h2>
        </div>
      </header>
      {children}
    </section>
  );
}

function SourceTag({ source }: { source: SignalSource }) {
  return (
    <span className="pill" style={{ color: SOURCE[source].color }}>
      {SOURCE[source].label}
    </span>
  );
}

function Items({ items, empty }: { items: ReportItem[]; empty: string }) {
  if (items.length === 0) return <p className="proj-s">{empty}</p>;
  return (
    <ul className="quotes">
      {items.map((item, i) => (
        <li key={`${item.published_at}-${i}`}>
          {clip(item.text)}
          <div className="proj-s">
            {item.engagement > 0 && `${item.engagement.toLocaleString("id-ID")} interaksi · `}
            {item.source_url ? (
              <a href={item.source_url} target="_blank" rel="noreferrer">
                buka sumber
              </a>
            ) : (
              "tanpa tautan sumber"
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

function Counts({ rows, unit }: { rows: [string, number][]; unit: string }) {
  if (rows.length === 0) return <p className="proj-s">Tidak ditemukan pada periode ini.</p>;
  return (
    <div className="chips">
      {rows.map(([text, n]) => (
        <span key={text} className="chip" title={`${n.toLocaleString("id-ID")} ${unit}`}>
          {text} <b>{n.toLocaleString("id-ID")}</b>
        </span>
      ))}
    </div>
  );
}

export default async function LaporanPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id: projectId, name, is_demo: isDemo } = await getCurrentProject();
  const win = parseWindow(await searchParams);
  const q = (extra: Record<string, string> = {}) => windowQuery(win, extra);
  const base = `/projects/${projectId}`;

  const [report, summary, summarySocial, summaryMedia, emotions, actors, activity, network] =
    await Promise.all([
      apiOrNullLenient<ConversationReport>(`${base}/signals/report${q({ tz: win.zone })}`),
      apiOrNullLenient<Summary>(`${base}/signals/summary${q()}`),
      apiOrNullLenient<Summary>(`${base}/signals/summary${q({ source: "SOCIAL" })}`),
      apiOrNullLenient<Summary>(`${base}/signals/summary${q({ source: "MEDIA" })}`),
      apiOrNullLenient<Emotions>(`${base}/signals/emotions${q()}`),
      apiOrNullLenient<Actors>(`${base}/signals/actors${q()}`),
      apiOrNullLenient<Activity>(`${base}/signals/activity${q({ tz: win.zone })}`),
      apiOrNullLenient<Network>(`${base}/network`),
    ]);

  const sources = report?.sources ?? [];
  const summaries: Partial<Record<SignalSource, Summary | null>> = {
    SOCIAL: summarySocial,
    MEDIA: summaryMedia,
  };
  const sinyalHref = (
    win.start && win.end
      ? `/sinyal?dari=${win.start}&sampai=${win.end}&zona=${win.zone}`
      : `/sinyal?zona=${win.zone}`
  ) as Route;
  const hasTopics = (report?.topics.length ?? 0) > 0;

  return (
    <>
      <PageHeader kicker="Laporan Percakapan" title={name} isDemo={isDemo} />
      <div className="body report">
        <form method="get" className="period-bar no-print">
          <label className="field">
            <span className="kicker">Dari</span>
            <input type="date" name="dari" defaultValue={win.start ?? ""} />
          </label>
          <label className="field">
            <span className="kicker">Sampai</span>
            <input type="date" name="sampai" defaultValue={win.end ?? ""} />
          </label>
          <label className="field">
            <span className="kicker">Zona waktu</span>
            <select name="zona" defaultValue={win.zone}>
              {ZONES.map((z) => (
                <option key={z} value={z}>
                  {z}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" className="btn btn-sm">
            Terapkan
          </button>
          <PrintButton />
          {win.error && <span className="proj-s period-now">{win.error} Menampilkan 30 hari terakhir.</span>}
        </form>

        {!report ? (
          <section className="panel">
            <InsufficientData reason={BELUM_ADA} />
          </section>
        ) : sources.length === 0 ? (
          <section className="panel">
            <InsufficientData reason="Belum ada percakapan atau liputan pada periode ini. Pilih periode lain, atau masukkan data lewat halaman Sinyal & Sentimen." />
          </section>
        ) : (
          <>
            <Question n={1} title="Bagaimana analisis ini dilakukan?">
              <p className="qa-lead">
                Laporan ini membaca konten proyek <b>{name}</b> yang terbit{" "}
                <b>
                  {dayLabel(report.period_start)} sampai {dayLabel(report.period_end)}
                </b>{" "}
                (hari dihitung menurut {report.timezone}). Percakapan dan liputan dihitung
                terpisah dan tidak pernah dijadikan satu angka.
              </p>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Sumber</th>
                    <th>Konten</th>
                    <th>Bernilai sentimen</th>
                    <th>Akun berbeda</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((s) => (
                    <tr key={s.source}>
                      <td>
                        <SourceTag source={s.source} />
                      </td>
                      <td>{s.n.toLocaleString("id-ID")}</td>
                      <td>
                        {s.scored.toLocaleString("id-ID")} ({pct(s.n ? s.scored / s.n : 0)})
                      </td>
                      <td>
                        {s.source === "SOCIAL" && summaries.SOCIAL
                          ? summaries.SOCIAL.distinct_authors.toLocaleString("id-ID")
                          : "tidak berlaku"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <ul className="nolist" style={{ marginTop: 14 }}>
                {Object.entries(report.methods).map(([key, text]) => (
                  <li key={key}>
                    <b>{key.replace("_", " ")}:</b> {text}
                  </li>
                ))}
              </ul>
            </Question>

            <Question n={2} title="Kapan volume melonjak, dan apa yang terbit hari itu?">
              <div className="grid-2">
                {sources.map((s) => (
                  <div key={s.source}>
                    <div className="kicker" style={{ marginBottom: 10 }}>
                      <SourceTag source={s.source} /> {s.days.length} hari berisi konten
                    </div>
                    {s.peaks.map((p) => (
                      <div key={p.day} className="peak">
                        <div className="peak-h">
                          <b>{dayLabel(p.day)}</b> · {p.volume.toLocaleString("id-ID")} konten
                          {p.ratio !== null && ` · ${String(p.ratio).replace(".", ",")} kali median harian`}{" "}
                          {p.is_spike ? (
                            <span className="pill pill-warn">lonjakan</span>
                          ) : (
                            <span className="pill">hari teramai, bukan lonjakan</span>
                          )}
                        </div>
                        {s.source === "SOCIAL" && (
                          <>
                            <div className="kicker peak-k">Konten paling banyak interaksi hari itu</div>
                            <Items items={p.top_content} empty="Tidak ada konten berinteraksi." />
                            <div className="kicker peak-k">Liputan yang terbit pada hari yang sama</div>
                            <Items
                              items={p.same_day_media}
                              empty="Tidak ada liputan tercatat pada hari itu."
                            />
                          </>
                        )}
                      </div>
                    ))}
                    <Provenance
                      method={report.methods.lonjakan ?? ""}
                      n={s.n}
                      confidence="Sedang"
                      limits="Kebersamaan waktu, bukan sebab. Liputan hari yang sama belum tentu pemicunya."
                    />
                  </div>
                ))}
              </div>
            </Question>

            <Question n={3} title="Bagaimana sentimennya, dan kapan paling negatif?">
              <div className="grid-2">
                {sources.map((s) => {
                  const shares = labelShares(s.labels);
                  const worst = mostNegativeDay(s.days);
                  const metric = summaries[s.source]?.sentiment;
                  const color = SOURCE[s.source].color;
                  return (
                    <div key={s.source}>
                      <div className="kicker" style={{ marginBottom: 10 }}>
                        <SourceTag source={s.source} />{" "}
                        {metric && metric.value !== null
                          ? `rata-rata ${formatSentiment(metric.value)} (skala -1 sampai +1)`
                          : "rata-rata ditahan"}
                      </div>
                      {shares === null ? (
                        <InsufficientData reason="Belum ada konten bernilai sentimen." />
                      ) : (
                        <div className="dq">
                          {shares.map((row) => (
                            <div key={row.label} className="dq-row dq-row-wide">
                              <span>{row.label}</span>
                              <div className="bar100">
                                <div style={{ width: `${row.share * 100}%`, background: color }} />
                              </div>
                              <b>{pct(row.share)}</b>
                            </div>
                          ))}
                        </div>
                      )}
                      <p className="qa-note">
                        {worst
                          ? `Hari paling negatif: ${dayLabel(worst.day)}, ${pct(worst.negative_share ?? 0)} dari ${worst.scored.toLocaleString("id-ID")} konten bernilai hari itu.`
                          : "Tidak ada hari dengan cukup konten bernilai untuk dibandingkan."}
                      </p>
                      <Provenance
                        method={metric?.method ?? report.methods.sentimen_harian ?? ""}
                        n={s.scored}
                        confidence="Rendah"
                        limits={
                          s.source === "SOCIAL" || s.source === "MEDIA"
                            ? SENTIMENT_LIMITS[s.source]
                            : ""
                        }
                      />
                    </div>
                  );
                })}
              </div>
            </Question>

            <Question n={4} title="Emosi apa yang paling menonjol, dan dari kata apa terbaca?">
              {!emotions ? (
                <InsufficientData reason={BELUM_ADA} />
              ) : (
                <>
                  <div className="grid-2">
                    {emotions.by_source.map((e) => (
                      <div key={e.source}>
                        <div className="kicker" style={{ marginBottom: 10 }}>
                          <SourceTag source={e.source} /> {e.n_with_emotion.toLocaleString("id-ID")}{" "}
                          dari {e.n_total.toLocaleString("id-ID")} konten memuat penanda (
                          {pct(e.coverage)})
                        </div>
                        {e.share === null ? (
                          <InsufficientData reason={e.note ?? "Belum cukup konten berpenanda emosi."} />
                        ) : (
                          <table className="tbl">
                            <thead>
                              <tr>
                                <th>Emosi</th>
                                <th>Porsi</th>
                                <th>Penanda tersering</th>
                              </tr>
                            </thead>
                            <tbody>
                              {EMOTION_LABELS.filter(([key]) => (e.share?.[key] ?? 0) > 0)
                                .sort((a, b) => (e.share?.[b[0]] ?? 0) - (e.share?.[a[0]] ?? 0))
                                .map(([key, label]) => (
                                  <tr key={key}>
                                    <td>{label}</td>
                                    <td>{pct(e.share?.[key] ?? 0)}</td>
                                    <td>
                                      {(e.markers?.[key] ?? [])
                                        .map(([m, n]) => `${m} (${n.toLocaleString("id-ID")})`)
                                        .join(", ") || "tidak tersedia"}
                                    </td>
                                  </tr>
                                ))}
                            </tbody>
                          </table>
                        )}
                        <Provenance
                          method={e.method}
                          n={e.n_with_emotion}
                          confidence="Rendah"
                          limits="Porsi di antara konten berpenanda saja, bukan seluruh konten."
                        />
                      </div>
                    ))}
                  </div>
                  <ul className="nolist" style={{ marginTop: 14 }}>
                    {emotions.limitations.map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ul>
                </>
              )}
            </Question>

            <Question n={5} title="Siapa yang paling sering disebut, dan dengan nada apa?">
              {!actors ? (
                <InsufficientData reason={BELUM_ADA} />
              ) : (
                <div className="grid-2">
                  {actors.by_source.map((a) => (
                    <div key={a.source}>
                      <div className="kicker" style={{ marginBottom: 10 }}>
                        <SourceTag source={a.source} /> {a.n_with_actor.toLocaleString("id-ID")} dari{" "}
                        {a.n_total.toLocaleString("id-ID")} konten menyebut aktor
                      </div>
                      {a.actors.length === 0 ? (
                        <p className="proj-s">Tidak ada aktor dari daftar yang disebut.</p>
                      ) : (
                        <table className="tbl">
                          <thead>
                            <tr>
                              <th>Aktor</th>
                              <th>Konten</th>
                              <th>Nada rata-rata</th>
                            </tr>
                          </thead>
                          <tbody>
                            {a.actors.slice(0, 8).map((row) => (
                              <tr key={row.key}>
                                <td>{row.name}</td>
                                <td>{row.n.toLocaleString("id-ID")}</td>
                                <td>
                                  {row.sentiment === null
                                    ? "data tidak cukup"
                                    : formatSentiment(row.sentiment)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                      <Provenance
                        method={a.method}
                        n={a.n_with_actor}
                        confidence="Rendah"
                        limits="Nada konten yang menyebut aktor, bukan nada terhadap aktor itu. Hanya pejabat publik, lembaga, dan partai dari daftar tetap."
                      />
                    </div>
                  ))}
                </div>
              )}
            </Question>

            <Question n={6} title="Isu apa yang paling banyak dibicarakan, dan mana yang paling memancing interaksi?">
              {!hasTopics ? (
                <InsufficientData reason="Tema belum ditemukan untuk konten periode ini. Jalankan penemuan tema di halaman Tema, lalu muat ulang laporan." />
              ) : (
                <div className="grid-2">
                  {sources.map((s) => {
                    const ranked = rankTopics(report.topics, s.source);
                    if (ranked.byVolume.length === 0) return null;
                    return (
                      <div key={s.source}>
                        <div className="kicker" style={{ marginBottom: 10 }}>
                          <SourceTag source={s.source} /> paling banyak dibicarakan
                        </div>
                        <table className="tbl">
                          <tbody>
                            {ranked.byVolume.map((t) => (
                              <tr key={t.topic_id}>
                                <td>{t.label}</td>
                                <td>{t.n.toLocaleString("id-ID")} konten</td>
                                <td>{t.sentiment === null ? "" : formatSentiment(t.sentiment)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {ranked.byEngagement.length > 0 && (
                          <>
                            <div className="kicker peak-k">Paling banyak interaksi</div>
                            <table className="tbl">
                              <tbody>
                                {ranked.byEngagement.map((t) => (
                                  <tr key={t.topic_id}>
                                    <td>{t.label}</td>
                                    <td>{t.engagement.toLocaleString("id-ID")} interaksi</td>
                                    <td>{t.n.toLocaleString("id-ID")} konten</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                            <p className="qa-note">
                              {ranked.differs
                                ? "Tema yang paling banyak dibicarakan bukan tema yang paling banyak memancing interaksi."
                                : "Tema yang paling banyak dibicarakan juga yang paling banyak memancing interaksi."}
                            </p>
                          </>
                        )}
                        <Provenance
                          method={report.methods.tema ?? ""}
                          n={ranked.byVolume.reduce((sum, t) => sum + t.n, 0)}
                          confidence="Rendah"
                          limits="Tema adalah kelompok kata otomatis. Konten di luar kelompok mana pun tidak ikut dihitung."
                        />
                      </div>
                    );
                  })}
                </div>
              )}
            </Question>

            <Question n={7} title="Media mana yang paling aktif memberitakan?">
              {report.outlets.length === 0 ? (
                <InsufficientData reason="Tidak ada liputan bertautan pada periode ini." />
              ) : (
                <>
                  <p className="qa-lead">
                    Liputan pada periode ini berasal dari{" "}
                    <b>{report.outlets_total.toLocaleString("id-ID")} situs</b>.
                  </p>
                  <Counts rows={report.outlets.map((o) => [o.domain, o.n])} unit="liputan" />
                  <Provenance
                    method={report.methods.media ?? ""}
                    n={report.outlets.reduce((sum, o) => sum + o.n, 0)}
                    confidence="Sedang"
                    limits="Hanya media yang feed-nya terdaftar di proyek ini. Media di luar daftar tidak terhitung."
                  />
                </>
              )}
            </Question>

            <Question n={8} title="Konten apa yang paling banyak memancing interaksi, dan pada jam berapa ramai?">
              {!activity ? (
                <InsufficientData reason={BELUM_ADA} />
              ) : (
                <div className="grid-2">
                  {activity.by_source.map((a) => (
                    <div key={a.source}>
                      <div className="kicker" style={{ marginBottom: 10 }}>
                        <SourceTag source={a.source} />{" "}
                        {a.peak_hour !== null && a.peak_weekday !== null
                          ? `paling ramai ${activity.weekdays[a.peak_weekday] ?? ""} ${hourLabel(a.peak_hour)} ${activity.timezone}`
                          : "belum ada jam ramai"}
                      </div>
                      {a.n_with_engagement === 0 ? (
                        <p className="proj-s">
                          Sumber ini tidak melaporkan interaksi (umum pada feed berita).
                        </p>
                      ) : (
                        <Items items={a.top} empty="Tidak ada konten berinteraksi." />
                      )}
                      <Provenance
                        method={a.method}
                        n={a.n}
                        confidence="Sedang"
                        limits="Interaksi adalah angka yang dilaporkan platform saat konten diambil, bukan jangkauan."
                      />
                    </div>
                  ))}
                </div>
              )}
            </Question>

            <Question n={9} title="Kata, tagar, dan emoji apa yang paling sering muncul?">
              {sources.map((s) => (
                <div key={s.source} className="qa-block">
                  <div className="kicker" style={{ marginBottom: 8 }}>
                    <SourceTag source={s.source} /> kata
                  </div>
                  <Counts rows={s.words} unit="konten" />
                  <div className="kicker peak-k">Tagar</div>
                  <Counts rows={s.hashtags} unit="konten" />
                  <div className="kicker peak-k">Emoji</div>
                  <Counts rows={s.emoji} unit="konten" />
                  <Provenance
                    method={report.methods.kata ?? ""}
                    n={s.n}
                    confidence="Tinggi"
                    limits="Hitungan kemunculan. Kata yang sama bisa dipakai untuk mendukung maupun menolak."
                  />
                </div>
              ))}
            </Question>

            <Question n={10} title="Seberapa terpusat percakapannya?">
              <p className="qa-lead">
                {summaries.SOCIAL ? (
                  <>
                    <b>{summaries.SOCIAL.distinct_authors.toLocaleString("id-ID")} akun berbeda</b>{" "}
                    menulis percakapan pada periode ini. Sepuluh akun paling aktif menulis{" "}
                    <b>{pct(summaries.SOCIAL.concentration_top10)}</b> dari seluruh konten.
                  </>
                ) : (
                  "Tidak ada percakapan pada periode ini."
                )}
              </p>
              {network && !network.insufficient_data ? (
                <p className="qa-note">
                  Jaringan balasan dan kutipan seluruh proyek: {network.total_accounts.toLocaleString("id-ID")}{" "}
                  akun, {network.total_edges.toLocaleString("id-ID")} relasi. Rinciannya ada di{" "}
                  <Link href={"/jaringan" as Route}>Jaringan Interaksi</Link>.
                </p>
              ) : (
                <p className="qa-note">
                  {network?.note ??
                    "Relasi balasan atau kutipan antar-akun belum cukup untuk memetakan kelompok percakapan."}
                </p>
              )}
              <p className="qa-note">
                Platform ini tidak menyebut nama akun dan tidak menyimpulkan akun mana yang
                "menggerakkan" percakapan. Yang dilaporkan hanya sebaran dan posisi dalam jaringan.
              </p>
            </Question>

            <Question n={11} title="Apa batas laporan ini?">
              <ul className="nolist">
                {[...report.limitations, ...(summary?.limitations ?? [])].map((l) => (
                  <li key={l}>{l}</li>
                ))}
                <li>
                  Laporan ini tidak memuat kesimpulan tertulis. Kesimpulan adalah tugas analis yang
                  membaca angka di atas bersama konteksnya.
                </li>
              </ul>
              <p className="qa-note no-print">
                Rincian tiap bagian, koreksi sentimen, dan daftar konten ada di{" "}
                <Link href={sinyalHref}>Sinyal &amp; Sentimen</Link>.
              </p>
            </Question>
          </>
        )}
      </div>
    </>
  );
}
