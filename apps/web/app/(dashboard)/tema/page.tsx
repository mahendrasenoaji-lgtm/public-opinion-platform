import { Info } from "lucide-react";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { SOURCE } from "@/lib/tokens";
import { apiOrNull } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";
import { DiscoverButton } from "./DiscoverButton";
import { ReviewTopic } from "./ReviewTopic";

export const dynamic = "force-dynamic";

interface TopicRow {
  id: string;
  label: string;
  keywords: string[];
  volume: number;
  share_pct: number | null;
  coherence: number | null;
  sentiment: number | null;
  scored: number;
  momentum_pct: number | null;
  effective_label: string;
  review_status: string;
  reviewed_label: string | null;
}

export default async function TemaPage() {
  const { id: projectId, name, is_demo: isDemo } = await getCurrentProject();
  const topics = (await apiOrNull<TopicRow[]>(`/projects/${projectId}/topics`)) ?? [];
  const peak = Math.max(1, ...topics.map((t) => t.volume));
  const social = SOURCE.SOCIAL.color;

  return (
    <>
      <PageHeader kicker="Topic Discovery" title={name} isDemo={isDemo} />
      <div className="body">
        <Panel
          kicker="Tema percakapan"
          title="Klaster yang ditemukan"
          right={<DiscoverButton projectId={projectId} />}
        >
          {topics.length === 0 ? (
            <InsufficientData
              reason={
                "Belum ada tema. Masukkan percakapan lewat Signal Monitor, lalu " +
                "jalankan penemuan tema. Dibutuhkan minimal 20 percakapan — di " +
                "bawah itu yang ditemukan lebih mungkin derau daripada tema."
              }
            />
          ) : (
            <div className="narrs">
              {topics.map((t) => (
                <div key={t.id} className="narr">
                  <div className="narr-head">
                    <span className="narr-t">{t.effective_label}</span>
                    <span className="narr-v mono">
                      {t.volume} konten
                      {t.share_pct !== null && ` · ${t.share_pct.toFixed(1)}%`}
                    </span>
                  </div>
                  <div className="bar100" style={{ margin: "8px 0" }}>
                    <div style={{ width: `${(t.volume / peak) * 100}%`, background: social }} />
                  </div>
                  <div className="narr-meta">
                    <span className="mono">{t.keywords.slice(0, 6).join(" · ")}</span>
                  </div>

                  <ReviewTopic
                    projectId={projectId}
                    topicId={t.id}
                    reviewStatus={t.review_status}
                    reviewedLabel={t.reviewed_label}
                    rawLabel={t.label}
                  />
                  <div className="narr-meta" style={{ marginTop: 4 }}>
                    {/* Momentum null berarti tema ini tidak ada di periode
                        pembanding. Pertumbuhan dari nol tidak punya persentase
                        yang bermakna — services/topics.py:momentum(). */}
                    <span className="mono">
                      Momentum 7 hari:{" "}
                      {t.momentum_pct === null ? (
                        <span style={{ color: "var(--txt3)" }}>tema baru (tidak ada pembanding)</span>
                      ) : (
                        <span
                          style={{
                            color: t.momentum_pct > 0 ? "var(--warn)" : "var(--pos)",
                          }}
                        >
                          {t.momentum_pct > 0 ? "+" : ""}
                          {t.momentum_pct.toFixed(1)}%
                        </span>
                      )}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          <Provenance
            method="TF-IDF + LSA(SVD) + HDBSCAN, label dari kata kunci teratas"
            n={topics.reduce((a, t) => a + t.volume, 0)}
            confidence="Rendah"
            limits={
              "Klasterisasi memakai kemiripan kata, bukan makna: dua keluhan yang " +
              "sama dengan pilihan kata berbeda bisa jatuh ke tema berbeda. Label " +
              "adalah gabungan kata kunci, bukan interpretasi yang sudah " +
              "diverifikasi manusia."
            }
          />

          <p className="note">
            <Info size={13} />
            Porsi tiap tema dihitung dari percakapan yang MASUK tema, bukan dari
            seluruh percakapan. Jalankan penemuan tema untuk melihat berapa banyak
            yang tidak terpetakan.
          </p>
        </Panel>
      </div>
    </>
  );
}
