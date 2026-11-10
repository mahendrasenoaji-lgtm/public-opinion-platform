import { cookies } from "next/headers";
import { Info } from "lucide-react";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { RescoreButton } from "@/components/RescoreButton";
import { SentimentCorrector } from "@/components/SentimentCorrector";
import { SourceManager } from "@/components/SourceManager";
import { UploadData } from "@/components/UploadData";
import { SOURCE } from "@/lib/tokens";
import { apiOrNullLenient, type Metric, type SignalSource } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";
import { SESSION_COOKIE, decodeJwtPayload } from "@/lib/session";
import type { CollectorTokenStatus } from "./actions";
import { SENTIMENT_LIMITS, formatSentiment, sentimentCards } from "./sentiment";
import {
  EMOTION_LABELS,
  ZONES,
  heatOpacity,
  hourLabel,
  parseWindow,
  windowQuery,
} from "./window";

//: Cermin RANK[RESEARCHER]/RANK[RESEARCH_DIRECTOR] di app/deps.py + tiap
//: dependencies=[Depends(require_role(...))] di app/routers/signals.py.
//: Sama pola dengan CAN_APPROVE_ROLES di app/(dashboard)/brief/page.tsx --
//: ini cuma UX (sembunyikan kontrol yang toh akan ditolak server), batas
//: keamanan sungguhan tetap di backend.
const CAN_MANAGE_ROLES = new Set(["SUPER_ADMIN", "RESEARCH_DIRECTOR", "RESEARCHER"]);
const CAN_MANAGE_TOKENS_ROLES = new Set(["SUPER_ADMIN", "RESEARCH_DIRECTOR"]);

export const dynamic = "force-dynamic";

interface SignalSummary {
  volume: Metric;
  sentiment: Metric;
  /** Tidak ada kalau backend belum memuat ragam berita (deploy tertinggal). */
  sentiment_revised?: Metric | null;
  distinct_authors: number;
  concentration_top10: number;
  source_mix: Record<string, number>;
  period_start: string;
  period_end: string;
  limitations: string[];
}

interface TrendPoint {
  day: string;
  volume: number;
  sentiment: number | null;
  scored: number;
}

/** Sebaran penanda emosi satu sumber; lihat GET .../signals/emotions. */
interface EmotionBySource {
  source: SignalSource;
  method: string;
  n_total: number;
  n_with_emotion: number;
  coverage: number;
  share: Record<string, number> | null;
  dominant: Record<string, number> | null;
  insufficient_data: boolean;
  note: string | null;
}

interface EmotionSummary {
  by_source: EmotionBySource[];
  limitations: string[];
}

interface ActivityBySource {
  source: SignalSource;
  method: string;
  n: number;
  engagement_total: number;
  n_with_engagement: number;
  by_day: { day: string; volume: number; engagement: number }[];
  /** heatmap[hari][jam]; hari 0 = Senin. */
  heatmap: number[][];
  by_hour: number[];
  peak_weekday: number | null;
  peak_hour: number | null;
  peak_count: number | null;
  top: {
    id: string;
    text: string;
    published_at: string;
    engagement: number;
    sentiment: number | null;
    source_url: string | null;
  }[];
}

interface Activity {
  timezone: string;
  weekdays: string[];
  by_source: ActivityBySource[];
  limitations: string[];
}

interface ActorTally {
  key: string;
  name: string;
  role: string | null;
  level: string;
  n: number;
  scored: number;
  sentiment: number | null;
}

/** Peta aktor + kutipan liputan; lihat GET .../signals/actors. */
interface ActorsBySource {
  source: SignalSource;
  method: string;
  n_total: number;
  n_with_actor: number;
  actors: ActorTally[];
  levels: ActorTally[];
  quotes: {
    text: string;
    speaker: string | null;
    published_at: string;
    source_url: string | null;
  }[];
  quotes_total: number;
}

interface Actors {
  by_source: ActorsBySource[];
  limitations: string[];
}

interface ClassMetrics {
  precision: number;
  recall: number;
  f1: number;
  support: number;
}

interface FieldScores {
  accuracy: number;
  accuracy_scored_only: number;
  macro_f1: number;
  abstain_rate: number;
  abstain_by_class: Record<string, number>;
  per_class: Record<string, ClassMetrics>;
}

/** Mutu pada komentar YouTube nyata; lihat services/sentiment_eval_field.py di API. */
interface FieldQuality {
  model_version: string;
  n: number;
  n_dev: number;
  informal: FieldScores;
  baseline: FieldScores;
  predicted_positive: number;
  predicted_positive_supporting_critic: number;
  predicted_positive_actually_negative: number;
  sarcasm_n: number;
  sarcasm_correct: number;
  caveat: string;
  /** Kesepakatan dua penilai; tidak ada kalau backend tertinggal. */
  agreement?: {
    n: number;
    observed_agreement: number;
    kappa: number;
    informal_macro_f1_vs_rater2: number;
    informal_macro_f1_on_agreed: number;
    agreed_test_n: number;
    caveat: string;
  };
}

interface SentimentQuality {
  model_version: string;
  n: number;
  accuracy: number;
  accuracy_scored_only: number;
  macro_f1: number;
  abstain_rate: number;
  abstain_by_class: Record<string, number>;
  per_class: Record<string, ClassMetrics>;
  caveat: string;
  /** Tidak ada kalau backend belum memuat ragam informal (deploy tertinggal). */
  field?: FieldQuality;
}

interface SourceRow {
  id: string;
  connector: string;
  source: SignalSource;
  config: Record<string, string>;
  is_active: boolean;
  last_sync_at: string | null;
}

interface MentionRow {
  id: string;
  external_id: string;
  url: string | null;
  /** URL terbaik yang tersedia; lihat `_recover_source_url` di API. */
  source_url: string | null;
  /** "kolom_url" = tersimpan sebagai URL. "guid_feed" = dipulihkan dari
   *  identitas feed pada item lama. Dibedakan di UI, bukan disamarkan. */
  source_url_origin: "kolom_url" | "guid_feed" | null;
  text: string;
  published_at: string;
  source: SignalSource;
  connector: string;
  engagement: number;
  sentiment: number | null;
  /** Tidak ada kalau backend tertinggal. */
  sentiment_manual?: boolean;
}

/** Penilai otomatis vs label manusia; lihat GET .../signals/correction-quality. */
interface CorrectionQuality {
  source: SignalSource;
  n: number;
  machine_abstained: number;
  agreed: number;
  agreement: number | null;
  insufficient_data: boolean;
  caveat: string;
}

const MENTION_LABELS = ["negatif", "netral", "positif", "abstain"] as const;
const MENTIONS_PER_PAGE = 20;

interface ConnectorRow {
  key: string;
  label: string;
  source: SignalSource;
  requires_credential: string | null;
  credential_configured: boolean;
  config_fields: string[];
  optional_fields: string[];
  notes: string;
}

const pct = (v: number) => `${Math.round(v * 100)}%`;

//: Ditampilkan saat endpoint Phase 2 membalas 404 — biasanya karena backend
//: belum selesai dideploy padahal frontend sudah. Pesannya menyebut penyebab
//: yang sebenarnya, bukan "data tidak cukup" yang akan menyesatkan.
const BACKEND_TERTINGGAL =
  "Endpoint ini belum tersedia di backend yang sedang aktif. Biasanya berarti " +
  "backend belum selesai dideploy setelah rilis frontend — coba lagi beberapa " +
  "menit lagi.";

export default async function SinyalPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id: projectId, name, is_demo: isDemo } = await getCurrentProject();
  const params = await searchParams;
  const win = parseWindow(params);
  const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v)?.trim() ?? "";
  const search = one(params.cari).slice(0, 80);
  const tone_ = one(params.nada);
  const labelFilter = (MENTION_LABELS as readonly string[]).includes(tone_) ? tone_ : "";
  const page = Math.max(1, Math.min(500, Number.parseInt(one(params.hal), 10) || 1));
  const mentionQuery: Record<string, string> = {
    limit: String(MENTIONS_PER_PAGE),
    offset: String((page - 1) * MENTIONS_PER_PAGE),
  };
  if (search.length >= 2) mentionQuery.q = search;
  if (labelFilter) mentionQuery.label = labelFilter;
  const q = (extra: Record<string, string> = {}) => windowQuery(win, extra);

  // SEMUA panggilan pakai apiOrNullLenient, termasuk dua yang secara logika "selalu
  // ada" (sentiment-quality dan daftar konektor tidak bergantung pada data
  // proyek sama sekali). Alasannya bukan data kosong, melainkan urutan deploy:
  // frontend di Vercel dan backend di Render naik terpisah, dan Vercel jauh
  // lebih cepat. Ada jendela waktu tiap rilis ketika halaman ini sudah baru
  // tapi backend-nya masih lama dan membalas 404 untuk endpoint Phase 2 —
  // dengan api() polos, satu panel yang hilang menjatuhkan SELURUH halaman
  // jadi "Application error". Kelas bug yang sama pernah kena tiga halaman
  // lain di repo ini (lihat docs/deployment-status.md, bagian registrasi
  // self-service).
  const [
    summary,
    summarySocial,
    summaryMedia,
    trend,
    quality,
    sources,
    connectors,
    mentions,
    tokenStatus,
    emotions,
    activity,
    corrections,
    actors,
  ] = await Promise.all([
    apiOrNullLenient<SignalSummary>(`/projects/${projectId}/signals/summary${q()}`),
    // Sentimen diminta PER SUMBER (R1). Ringkasan tanpa `source` di atas
    // hanya dipakai untuk volume, komposisi, dan sebaran akun.
    apiOrNullLenient<SignalSummary>(`/projects/${projectId}/signals/summary${q({ source: "SOCIAL" })}`,
    ),
    apiOrNullLenient<SignalSummary>(
      `/projects/${projectId}/signals/summary${q({ source: "MEDIA" })}`,
    ),
    apiOrNullLenient<TrendPoint[]>(`/projects/${projectId}/signals/trend${q()}`),
    apiOrNullLenient<SentimentQuality>(`/projects/${projectId}/signals/sentiment-quality`),
    apiOrNullLenient<SourceRow[]>(`/projects/${projectId}/signals/sources`),
    apiOrNullLenient<ConnectorRow[]>(`/signals/connectors`),
    apiOrNullLenient<MentionRow[]>(`/projects/${projectId}/mentions${q(mentionQuery)}`),
    apiOrNullLenient<CollectorTokenStatus>(`/projects/${projectId}/signals/collector-token`),
    apiOrNullLenient<EmotionSummary>(`/projects/${projectId}/signals/emotions${q()}`),
    apiOrNullLenient<Activity>(`/projects/${projectId}/signals/activity${q({ tz: win.zone })}`),
    apiOrNullLenient<CorrectionQuality[]>(`/projects/${projectId}/signals/correction-quality`),
    apiOrNullLenient<Actors>(`/projects/${projectId}/signals/actors${q()}`),
  ]);

  /** Tautan halaman daftar konten yang mempertahankan periode dan filter. */
  const mentionsHref = (target: number) => {
    const u = new URLSearchParams();
    if (win.start && win.end) {
      u.set("dari", win.start);
      u.set("sampai", win.end);
    }
    u.set("zona", win.zone);
    if (search) u.set("cari", search);
    if (labelFilter) u.set("nada", labelFilter);
    if (target > 1) u.set("hal", String(target));
    return `?${u.toString()}#konten`;
  };

  const sessionToken = (await cookies()).get(SESSION_COOKIE)?.value;
  const role = sessionToken ? decodeJwtPayload(sessionToken)?.role : undefined;
  const canManage = typeof role === "string" && CAN_MANAGE_ROLES.has(role);
  const canManageTokens = typeof role === "string" && CAN_MANAGE_TOKENS_ROLES.has(role);

  const volume = summary?.volume.value ?? 0;
  // Warna mengikuti sumber yang dominan, bukan estetika (R1).
  const tone = SOURCE[summary?.volume.source ?? "SOCIAL"].color;
  const sentimentBySource = sentimentCards({ SOCIAL: summarySocial, MEDIA: summaryMedia });
  const withVolume = (trend ?? []).filter((p) => p.volume > 0);
  const peak = Math.max(1, ...withVolume.map((p) => p.volume));

  return (
    <>
      <PageHeader kicker="Sinyal & Sentimen" title={name} isDemo={isDemo} />
      <div className="body">
        {/* Form GET polos: periode hidup di URL, jadi bisa dibagikan dan
            tidak butuh komponen klien. Kosongkan kedua tanggal = 30 hari
            terakhir (perilaku bawaan backend). */}
        <form method="get" className="period-bar">
          <label className="field">
            <span className="kicker">Dari</span>
            <input type="date" name="dari" defaultValue={win.start ?? ""} />
          </label>
          <label className="field">
            <span className="kicker">Sampai</span>
            <input type="date" name="sampai" defaultValue={win.end ?? ""} />
          </label>
          <label className="field">
            <span className="kicker">Zona jam ramai</span>
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
          {(win.start || win.error) && (
            <a className="btn btn-ghost btn-sm" href={`?zona=${win.zone}`}>
              30 hari terakhir
            </a>
          )}
          <span className="proj-s period-now">
            {win.error
              ? `${win.error} Menampilkan 30 hari terakhir.`
              : summary
                ? `Periode tampil: ${summary.period_start} s.d. ${summary.period_end} (UTC)`
                : ""}
          </span>
        </form>

        <section className="stat-row">
          <div className="stat stat-big">
            <div className="kicker">Volume percakapan</div>
            <div className="stat-v" style={{ color: tone }}>
              {volume.toLocaleString("id-ID")}
              <span className="stat-u">konten</span>
            </div>
            {summary && (
              <Provenance
                method={summary.volume.method}
                n={summary.volume.effective_n ?? 0}
                confidence="Tinggi"
                limits="Hitungan konten unik setelah deduplikasi, bukan jumlah orang."
              />
            )}
          </div>

          {/* Satu kartu per sumber, tidak pernah satu angka gabungan: nada
              liputan dan nada komentar diukur penilai berbeda atas populasi
              berbeda, dan rata-ratanya hanya mengikuti sumber yang lebih
              banyak (proyek MBG: -0,47 jadi -0,28 begitu komentar masuk). */}
          {sentimentBySource.length === 0 ? (
            <div className="stat">
              <div className="kicker">Sentimen rata-rata</div>
              <InsufficientData reason="Belum ada percakapan yang masuk untuk proyek ini." />
            </div>
          ) : (
            sentimentBySource.map(({ source, metric, revised }) => (
              <div className="stat" key={source}>
                <div className="kicker">Sentimen rata-rata · {SOURCE[source].label}</div>
                {metric.value === null ? (
                  <InsufficientData
                    reason={metric.note ?? "Belum cukup konten bernilai sentimen."}
                  />
                ) : (
                  <>
                    <div className="stat-v" style={{ color: SOURCE[source].color }}>
                      {formatSentiment(metric.value)}
                      <span className="stat-u">/ 1.00</span>
                    </div>
                    <Provenance
                      method={metric.method}
                      n={metric.effective_n ?? 0}
                      confidence="Rendah"
                      limits={SENTIMENT_LIMITS[source]}
                    />
                  </>
                )}
                {/* Angka KEDUA, bukan pengganti: skor utama liputan tetap
                    leksikon baku supaya deret yang sedang berjalan tidak
                    patah. Ragam berita membuang kata yang di judul berita
                    bermakna korporat ("dukung", "apresiasi"). */}
                {revised && (
                  <div className="proj-s" style={{ marginTop: 8 }}>
                    Ragam berita:{" "}
                    <b style={{ color: SOURCE[source].color }}>
                      {revised.value === null ? "belum cukup" : formatSentiment(revised.value)}
                    </b>{" "}
                    · n {revised.effective_n ?? 0}
                    {revised.note ? ` · ${revised.note}` : ""}
                  </div>
                )}
              </div>
            ))
          )}

          <div className="stat">
            <div className="kicker">Akun berbeda</div>
            <div className="stat-v">{(summary?.distinct_authors ?? 0).toLocaleString("id-ID")}</div>
            <div className="proj-s" style={{ marginTop: 6 }}>
              Identitas di-hash, tidak pernah disimpan apa adanya
            </div>
          </div>

          <div className="stat">
            <div className="kicker">Porsi 10 akun teratas</div>
            <div className="stat-v">{pct(summary?.concentration_top10 ?? 0)}</div>
            <div className="proj-s" style={{ marginTop: 6 }}>
              Deskripsi sebaran, bukan indikasi koordinasi
            </div>
          </div>
        </section>

        <div className="grid-2">
          <Panel kicker="Volume harian" title="Tren percakapan">
            {withVolume.length === 0 ? (
              <InsufficientData reason="Belum ada percakapan pada periode ini." />
            ) : (
              <div className="dq">
                {withVolume.slice(-14).map((p) => (
                  <div key={p.day} className="dq-row">
                    <span className="mono">{p.day}</span>
                    <div className="bar100">
                      <div style={{ width: `${(p.volume / peak) * 100}%`, background: tone }} />
                    </div>
                    <b>{p.volume}</b>
                  </div>
                ))}
              </div>
            )}
            <p className="note">
              <Info size={13} />
              Hari tanpa konten bernilai sentimen tidak ditampilkan sebagai netral —
              ia memang tidak terukur, dan nol akan terbaca sebagai pengukuran.
            </p>
          </Panel>

          <Panel kicker="Komposisi" title="Sumber sinyal">
            {!summary || Object.keys(summary.source_mix).length === 0 ? (
              <InsufficientData reason="Belum ada sinyal yang masuk." />
            ) : (
              <div className="dq">
                {Object.entries(summary.source_mix).map(([src, count]) => {
                  const meta = SOURCE[src as SignalSource];
                  const share = (count / Math.max(1, volume)) * 100;
                  return (
                    <div key={src} className="dq-row">
                      <span>
                        <span className="pill" style={{ color: meta.color }}>{meta.label}</span>
                      </span>
                      <div className="bar100">
                        <div style={{ width: `${share}%`, background: meta.color }} />
                      </div>
                      <b>{count}</b>
                    </div>
                  );
                })}
              </div>
            )}
            {summary && (
              <ul className="nolist" style={{ marginTop: 14 }}>
                {summary.limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <Panel kicker="Emosi" title="Penanda emosi per sumber">
          {!emotions ? (
            <InsufficientData reason={BACKEND_TERTINGGAL} />
          ) : emotions.by_source.length === 0 ? (
            <InsufficientData reason="Belum ada konten pada periode ini." />
          ) : (
            <>
              <div className="grid-2">
                {emotions.by_source.map((e) => {
                  const color = SOURCE[e.source].color;
                  return (
                    <div key={e.source}>
                      <div className="kicker" style={{ marginBottom: 10 }}>
                        <span className="pill" style={{ color }}>{SOURCE[e.source].label}</span>{" "}
                        {e.n_with_emotion.toLocaleString("id-ID")} dari{" "}
                        {e.n_total.toLocaleString("id-ID")} konten memuat penanda (
                        {(e.coverage * 100).toFixed(1)}%)
                      </div>
                      {e.share === null ? (
                        <InsufficientData reason={e.note ?? "Belum cukup konten berpenanda emosi."} />
                      ) : (
                        <div className="dq">
                          {EMOTION_LABELS.map(([key, label]) => {
                            const share = e.share?.[key] ?? 0;
                            return (
                              <div key={key} className="dq-row dq-row-wide">
                                <span>{label}</span>
                                <div className="bar100">
                                  <div style={{ width: `${share * 100}%`, background: color }} />
                                </div>
                                <b>{(share * 100).toFixed(1)}%</b>
                              </div>
                            );
                          })}
                        </div>
                      )}
                      <Provenance
                        method={e.method}
                        n={e.n_with_emotion}
                        confidence="Rendah"
                        limits="Porsi di antara konten berpenanda saja, bukan seluruh konten."
                      />
                    </div>
                  );
                })}
              </div>
              <ul className="nolist" style={{ marginTop: 14 }}>
                {emotions.limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </>
          )}
        </Panel>

        <Panel
          kicker="Engagement & jam ramai"
          title="Kapan percakapan terjadi"
          right={activity && <span className="pill pill-warn">{activity.timezone}</span>}
        >
          {!activity ? (
            <InsufficientData reason={BACKEND_TERTINGGAL} />
          ) : activity.by_source.length === 0 ? (
            <InsufficientData reason="Belum ada konten pada periode ini." />
          ) : (
            <>
              {activity.by_source.map((a) => {
                const color = SOURCE[a.source].color;
                const max = Math.max(1, ...a.heatmap.flat());
                const peakDay = Math.max(1, ...a.by_day.map((d) => d.engagement));
                return (
                  <div key={a.source} className="act-block">
                    <div className="fc-out" style={{ marginTop: 0, borderTop: 0, paddingTop: 0 }}>
                      <div>
                        <span className="kicker">
                          <span className="pill" style={{ color }}>{SOURCE[a.source].label}</span>{" "}
                          Konten
                        </span>
                        <b>{a.n.toLocaleString("id-ID")}</b>
                      </div>
                      <div>
                        <span className="kicker">Total engagement</span>
                        <b>
                          {a.n_with_engagement === 0
                            ? "tidak dilaporkan"
                            : a.engagement_total.toLocaleString("id-ID")}
                        </b>
                      </div>
                      <div>
                        <span className="kicker">Konten dengan engagement</span>
                        <b>{a.n_with_engagement.toLocaleString("id-ID")}</b>
                      </div>
                      <div>
                        <span className="kicker">Jam paling ramai</span>
                        <b>
                          {a.peak_hour === null || a.peak_weekday === null
                            ? "-"
                            : `${activity.weekdays[a.peak_weekday]} ${hourLabel(a.peak_hour)}`}
                        </b>
                      </div>
                    </div>

                    <div className="heat" role="img" aria-label={`Peta jam terbit konten ${SOURCE[a.source].label}, ${activity.timezone}`}>
                      <div className="heat-row heat-head">
                        <span />
                        {a.by_hour.map((_, h) => (
                          <span key={h}>{h % 3 === 0 ? String(h).padStart(2, "0") : ""}</span>
                        ))}
                      </div>
                      {a.heatmap.map((hours, d) => (
                        <div className="heat-row" key={d}>
                          <span className="heat-day">{activity.weekdays[d]}</span>
                          {hours.map((count, h) => (
                            <span
                              key={h}
                              className="heat-cell"
                              title={`${activity.weekdays[d]} ${hourLabel(h)} ${activity.timezone}: ${count} konten`}
                            >
                              <i style={{ background: color, opacity: heatOpacity(count, max) }} />
                            </span>
                          ))}
                        </div>
                      ))}
                    </div>

                    {a.n_with_engagement > 0 && (
                      <div className="grid-2" style={{ marginTop: 16 }}>
                        <div>
                          <div className="kicker" style={{ marginBottom: 8 }}>
                            Engagement per hari ({activity.timezone})
                          </div>
                          <div className="dq">
                            {a.by_day.slice(-14).map((d) => (
                              <div key={d.day} className="dq-row dq-row-wide">
                                <span className="mono">{d.day}</span>
                                <div className="bar100">
                                  <div
                                    style={{
                                      width: `${(d.engagement / peakDay) * 100}%`,
                                      background: color,
                                    }}
                                  />
                                </div>
                                <b>{d.engagement.toLocaleString("id-ID")}</b>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div>
                          <div className="kicker" style={{ marginBottom: 8 }}>
                            Konten paling ramai
                          </div>
                          <table className="tbl">
                            <tbody>
                              {a.top.map((t) => (
                                <tr key={t.id}>
                                  <td>
                                    {t.text.length > 120 ? `${t.text.slice(0, 120)}…` : t.text}
                                    {t.source_url && (
                                      <>
                                        {" "}
                                        <a
                                          href={t.source_url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          style={{ color }}
                                        >
                                          sumber ↗
                                        </a>
                                      </>
                                    )}
                                  </td>
                                  <td className="mono" style={{ textAlign: "right" }}>
                                    {t.engagement.toLocaleString("id-ID")}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                    <Provenance
                      method={a.method}
                      n={a.n}
                      confidence="Tinggi"
                      limits="Hitungan jam terbit, bukan jam dibaca. Engagement dicatat saat konten diambil."
                    />
                  </div>
                );
              })}
              <ul className="nolist" style={{ marginTop: 14 }}>
                {activity.limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </>
          )}
        </Panel>

        <Panel kicker="Aktor & kutipan" title="Siapa yang disebut">
          {!actors ? (
            <InsufficientData reason={BACKEND_TERTINGGAL} />
          ) : actors.by_source.length === 0 ? (
            <InsufficientData reason="Belum ada konten pada periode ini." />
          ) : (
            <>
              {actors.by_source.map((a) => {
                const color = SOURCE[a.source].color;
                const top = Math.max(1, ...a.actors.map((t) => t.n));
                return (
                  <div key={a.source} className="act-block">
                    <div className="kicker" style={{ marginBottom: 10 }}>
                      <span className="pill" style={{ color }}>{SOURCE[a.source].label}</span>{" "}
                      {a.n_with_actor.toLocaleString("id-ID")} dari{" "}
                      {a.n_total.toLocaleString("id-ID")} konten menyebut aktor bernama
                    </div>
                    {a.actors.length === 0 ? (
                      <InsufficientData reason="Tidak ada aktor dari daftar yang disebut pada periode ini." />
                    ) : (
                      <div className="grid-2" style={{ alignItems: "start" }}>
                        <table className="tbl">
                          <thead>
                            <tr>
                              <th>Aktor</th>
                              <th>Disebut</th>
                              <th>Nada konten</th>
                            </tr>
                          </thead>
                          <tbody>
                            {a.actors.slice(0, 10).map((t) => (
                              <tr key={t.key}>
                                <td>
                                  {t.name}
                                  <div className="proj-s">{t.role}</div>
                                  <div className="bar100" style={{ marginTop: 5 }}>
                                    <div style={{ width: `${(t.n / top) * 100}%`, background: color }} />
                                  </div>
                                </td>
                                <td className="mono">{t.n.toLocaleString("id-ID")}</td>
                                <td className="mono">
                                  {t.sentiment === null
                                    ? `belum cukup (n ${t.scored})`
                                    : `${formatSentiment(t.sentiment)} (n ${t.scored})`}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <table className="tbl">
                          <thead>
                            <tr>
                              <th>Tingkat kekuasaan</th>
                              <th>Disebut</th>
                              <th>Nada konten</th>
                            </tr>
                          </thead>
                          <tbody>
                            {a.levels.map((t) => (
                              <tr key={t.key}>
                                <td>{t.name}</td>
                                <td className="mono">{t.n.toLocaleString("id-ID")}</td>
                                <td className="mono">
                                  {t.sentiment === null
                                    ? `belum cukup (n ${t.scored})`
                                    : `${formatSentiment(t.sentiment)} (n ${t.scored})`}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                    {a.source === "MEDIA" && (
                      <div style={{ marginTop: 16 }}>
                        <div className="kicker" style={{ marginBottom: 8 }}>
                          Kutipan langsung di liputan ({a.quotes_total})
                        </div>
                        {a.quotes.length === 0 ? (
                          <div className="proj-s">
                            Tidak ada kutipan bertanda petik di judul atau ringkasan pada periode ini.
                          </div>
                        ) : (
                          <ul className="quotes">
                            {a.quotes.map((qt, i) => (
                              <li key={i}>
                                “{qt.text}”
                                <div className="proj-s">
                                  {qt.speaker ?? "penutur tidak disebut di ringkasan"} ·{" "}
                                  {qt.published_at.slice(0, 10)}
                                  {qt.source_url && (
                                    <>
                                      {" · "}
                                      <a
                                        href={qt.source_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{ color }}
                                      >
                                        sumber ↗
                                      </a>
                                    </>
                                  )}
                                </div>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                    <Provenance
                      method={a.method}
                      n={a.n_total}
                      confidence="Rendah"
                      limits="Nada konten yang menyebut aktor, bukan nada terhadap aktornya."
                    />
                  </div>
                );
              })}
              <ul className="nolist" style={{ marginTop: 14 }}>
                {actors.limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </>
          )}
        </Panel>

        <div id="konten" />
        <Panel kicker="Akuntabilitas riset" title="Konten (validasi dan koreksi manual)">
          <form method="get" action="#konten" className="period-bar">
            {win.start && win.end && (
              <>
                <input type="hidden" name="dari" value={win.start} />
                <input type="hidden" name="sampai" value={win.end} />
              </>
            )}
            <input type="hidden" name="zona" value={win.zone} />
            <label className="field" style={{ flex: "1 1 220px" }}>
              <span className="kicker">Cari teks</span>
              <input type="search" name="cari" defaultValue={search} placeholder="mis. antre" />
            </label>
            <label className="field">
              <span className="kicker">Nada</span>
              <select name="nada" defaultValue={labelFilter}>
                <option value="">semua</option>
                <option value="negatif">negatif</option>
                <option value="netral">netral</option>
                <option value="positif">positif</option>
                <option value="abstain">tidak dinilai</option>
              </select>
            </label>
            <button type="submit" className="btn btn-sm">
              Saring
            </button>
          </form>
          {!mentions || mentions.length === 0 ? (
            <InsufficientData
              reason={
                search || labelFilter || page > 1
                  ? "Tidak ada konten yang cocok dengan saringan ini pada periode tampil."
                  : "Belum ada konten yang bisa ditelusuri untuk proyek ini."
              }
            />
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>Konten</th>
                  <th>Sumber</th>
                  <th>Tanggal</th>
                  <th>Sentimen</th>
                  <th>Sumber asli</th>
                </tr>
              </thead>
              <tbody>
                {mentions.map((m) => (
                  <tr key={m.id}>
                    <td style={{ maxWidth: 420 }}>
                      {m.text.length > 140 ? `${m.text.slice(0, 140)}…` : m.text}
                    </td>
                    <td>
                      <span className="pill" style={{ color: SOURCE[m.source].color }}>
                        {SOURCE[m.source].label}
                      </span>
                    </td>
                    <td className="mono">{m.published_at.slice(0, 16).replace("T", " ")}</td>
                    <td>
                      <SentimentCorrector
                        key={`${m.id}:${m.sentiment}:${m.sentiment_manual ? 1 : 0}`}
                        projectId={projectId}
                        mentionId={m.id}
                        sentiment={m.sentiment}
                        manual={m.sentiment_manual ?? false}
                        canEdit={canManage}
                      />
                    </td>
                    <td>
                      {m.source_url ? (
                        <>
                          <a
                            href={m.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ color: SOURCE[m.source].color }}
                          >
                            Buka sumber ↗
                          </a>
                          {/* Tautan hasil pemulihan ditandai, bukan disamakan
                              diam-diam dengan yang tersimpan sebagai URL.
                              Bedanya kecil tapi nyata: yang ini berasal dari
                              guid feed, dan pembaca yang memverifikasi berhak
                              tahu itu sebelum mengutipnya. */}
                          {m.source_url_origin === "guid_feed" && (
                            <span
                              className="mono"
                              title="URL dipulihkan dari guid feed RSS, yang untuk keempat outlet ini sama dengan permalink artikelnya. Kolom url sendiri kosong karena item ini diingest sebelum kolom itu ada (2026-09-11)."
                              style={{ color: "var(--txt3)", marginLeft: 7, fontSize: 10 }}
                            >
                              dari guid feed
                            </span>
                          )}
                        </>
                      ) : (
                        <span style={{ color: "var(--txt3)" }}>tidak ada URL sumber</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {(page > 1 || (mentions?.length ?? 0) === MENTIONS_PER_PAGE) && (
            <div className="pager">
              {page > 1 ? (
                <a className="btn btn-ghost btn-sm" href={mentionsHref(page - 1)}>
                  ← Lebih baru
                </a>
              ) : (
                <span />
              )}
              <span className="proj-s">Halaman {page}</span>
              {(mentions?.length ?? 0) === MENTIONS_PER_PAGE ? (
                <a className="btn btn-ghost btn-sm" href={mentionsHref(page + 1)}>
                  Lebih lama →
                </a>
              ) : (
                <span />
              )}
            </div>
          )}
          {corrections && corrections.length > 0 && (
            <p className="note">
              <Info size={13} />
              <span>
                <b>Koreksi manual sebagai alat ukur.</b>{" "}
                {corrections
                  .map((c) =>
                    c.agreement === null
                      ? `${SOURCE[c.source].label}: ${c.n} konten berlabel manusia, belum cukup untuk angka kesepakatan (perlu 30 yang dinilai mesin).`
                      : `${SOURCE[c.source].label}: dari ${c.n} konten berlabel manusia, penilai otomatis menilai ${c.n - c.machine_abstained} dan sepakat pada ${pct(c.agreement)}.`,
                  )
                  .join(" ")}{" "}
                {corrections[0]?.caveat}
              </span>
            </p>
          )}
          {/* Isi catatan dibungkus SATU span: `.note` itu display:flex, jadi
              elemen apa pun yang disisipkan di tengah teks akan jadi flex
              item tersendiri dan terperas jadi kolom sempit. */}
          <p className="note">
            <Info size={13} />
            <span>
              {MENTIONS_PER_PAGE} konten per halaman, terbaru dulu, pada periode tampil. Label
              yang ditetapkan manusia (bertanda{" "}
              <span className="mono" style={{ fontSize: 10 }}>
                manual
              </span>
              ) menang atas penilai otomatis dan tercatat di audit log. Tautan bertanda{" "}
              <span className="mono" style={{ fontSize: 10 }}>
                dari guid feed
              </span>{" "}
              dipulihkan dari identitas feed RSS — untuk Antara, CNBC Indonesia, Republika, dan
              Sindonews, guid itu memang permalink artikelnya. &quot;Tidak ada URL sumber&quot;
              berarti guid-nya bukan URL, atau sumbernya memang tidak punya halaman publik —
              bukan tanda datanya tidak asli.
            </span>
          </p>
        </Panel>

        <Panel
          kicker="Mutu pengukuran"
          title="Akurasi leksikon pada set internal"
          right={
            quality && <span className="pill pill-warn">{quality.model_version}</span>
          }
        >
          {!quality ? (
            <InsufficientData reason={BACKEND_TERTINGGAL} />
          ) : (
            <>
          {/* docs/roadmap.md mensyaratkan akurasi sentimen dilaporkan di UI
              sebelum fitur ini dipakai di proyek nyata. Ini pemenuhannya. */}
          <div className="fc-out">
            <div>
              <span className="kicker">Macro F1</span>
              <b>{quality.macro_f1.toFixed(3)}</b>
            </div>
            <div>
              <span className="kicker">Akurasi (yang dinilai)</span>
              <b>{quality.accuracy_scored_only.toFixed(3)}</b>
            </div>
            <div>
              <span className="kicker">Akurasi (ketat)</span>
              <b>{quality.accuracy.toFixed(3)}</b>
            </div>
            <div>
              <span className="kicker">Tidak dinilai</span>
              <b>{pct(quality.abstain_rate)}</b>
            </div>
          </div>

          <table className="tbl" style={{ marginTop: 18 }}>
            <thead>
              <tr>
                <th>Kelas</th>
                <th>Presisi</th>
                <th>Recall</th>
                <th>F1</th>
                <th>Tidak dinilai</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(quality.per_class).map(([kelas, m]) => (
                <tr key={kelas}>
                  <td style={{ textTransform: "capitalize" }}>{kelas}</td>
                  <td className="mono">{m.precision.toFixed(3)}</td>
                  <td className="mono">{m.recall.toFixed(3)}</td>
                  <td className="mono">{m.f1.toFixed(3)}</td>
                  <td className="mono">{quality.abstain_by_class[kelas] ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <p className="note">
            <Info size={13} />
            {quality.caveat}
          </p>
            </>
          )}
        </Panel>

        <Panel
          kicker="Mutu pengukuran"
          title="Akurasi pada komentar nyata"
          right={
            quality?.field && (
              <span className="pill pill-warn">{quality.field.model_version}</span>
            )
          }
        >
          {!quality?.field ? (
            <InsufficientData reason={BACKEND_TERTINGGAL} />
          ) : (
            <>
              {/* Angka panel di atas diukur pada kalimat buatan (batas atas).
                  Panel ini ukuran lapangannya: komentar YouTube sungguhan,
                  belahan uji, dengan leksikon baku sebagai pembanding pada
                  komentar yang SAMA. */}
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Penilai ({quality.field.n} komentar uji)</th>
                    <th>Macro F1</th>
                    <th>Akurasi (yang dinilai)</th>
                    <th>Akurasi (ketat)</th>
                    <th>Tidak dinilai</th>
                  </tr>
                </thead>
                <tbody>
                  {(
                    [
                      ["Ragam informal — dipakai untuk sumber sosial", quality.field.informal],
                      ["Leksikon baku — pembanding", quality.field.baseline],
                    ] as const
                  ).map(([nama, m]) => (
                    <tr key={nama}>
                      <td>{nama}</td>
                      <td className="mono">{m.macro_f1.toFixed(3)}</td>
                      <td className="mono">{m.accuracy_scored_only.toFixed(3)}</td>
                      <td className="mono">{m.accuracy.toFixed(3)}</td>
                      <td className="mono">{pct(m.abstain_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <p className="note">
                <Info size={13} />
                <span>
                  <b>Positif bukan berarti mendukung.</b> Dari {quality.field.predicted_positive}{" "}
                  komentar uji yang terbaca positif,{" "}
                  {quality.field.predicted_positive_supporting_critic} adalah pujian kepada orang
                  yang sedang mengkritik program dan{" "}
                  {quality.field.predicted_positive_actually_negative} sebenarnya bernada negatif.
                  Sarkasme tidak dikenali: hanya {quality.field.sarcasm_correct} dari{" "}
                  {quality.field.sarcasm_n} komentar sarkastis yang nadanya terbaca benar, dan itu
                  karena kata lain di kalimatnya.
                </span>
              </p>
              <p className="note">
                <Info size={13} />
                <span>
                  {quality.field.caveat} Kamusnya disusun dari {quality.field.n_dev} komentar
                  lain yang tidak ikut dihitung di sini.
                </span>
              </p>
              {quality.field.agreement && (
                <p className="note">
                  <Info size={13} />
                  <span>
                    <b>Kesepakatan dua penilai.</b> Dari {quality.field.agreement.n} komentar,
                    kedua penilai memberi label sama pada{" "}
                    {pct(quality.field.agreement.observed_agreement)} (kappa Cohen{" "}
                    {quality.field.agreement.kappa.toFixed(3)}). Terhadap label penilai kedua,
                    Macro F1 ragam informal{" "}
                    {quality.field.agreement.informal_macro_f1_vs_rater2.toFixed(3)}; pada{" "}
                    {quality.field.agreement.agreed_test_n} komentar uji yang disepakati,{" "}
                    {quality.field.agreement.informal_macro_f1_on_agreed.toFixed(3)}.{" "}
                    {quality.field.agreement.caveat}
                  </span>
                </p>
              )}
            </>
          )}
        </Panel>

        <Panel kicker="Pengaturan" title="Sumber data terdaftar">
          {!sources ? (
            <InsufficientData reason={BACKEND_TERTINGGAL} />
          ) : (
            <SourceManager
              projectId={projectId}
              sources={sources}
              connectors={connectors ?? []}
              canManage={canManage}
              canManageTokens={canManageTokens}
              tokenStatus={tokenStatus}
            />
          )}
          {canManage && <UploadData projectId={projectId} />}
          {canManageTokens && <RescoreButton projectId={projectId} />}

          <h3 className="kicker" style={{ marginTop: 22 }}>Konektor yang tersedia</h3>
          {!connectors ? (
            <InsufficientData reason={BACKEND_TERTINGGAL} />
          ) : (
          <table className="tbl" style={{ marginTop: 8 }}>
            <thead>
              <tr>
                <th>Konektor</th>
                <th>Sumber</th>
                <th>Kredensial</th>
                <th>Batasan sumber</th>
              </tr>
            </thead>
            <tbody>
              {connectors.map((c) => (
                <tr key={c.key}>
                  <td>{c.label}</td>
                  <td>
                    <span className="pill" style={{ color: SOURCE[c.source].color }}>
                      {SOURCE[c.source].label}
                    </span>
                  </td>
                  <td>
                    {c.requires_credential === null ? (
                      <span className="pill pill-ok">tidak perlu</span>
                    ) : c.credential_configured ? (
                      <span className="pill pill-ok">{c.requires_credential} aktif</span>
                    ) : (
                      <span className="pill pill-warn">{c.requires_credential} belum diset</span>
                    )}
                  </td>
                  <td style={{ color: "var(--txt2)" }}>{c.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
          )}
        </Panel>
      </div>
    </>
  );
}
