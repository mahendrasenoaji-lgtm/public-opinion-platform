import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { InsufficientData } from "@/components/Provenance";
import { apiOrNullLenient } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";
import { SOURCE, type SignalSource } from "@/lib/tokens";
import { CollectForm, type MetricConnector } from "./CollectForm";

export const dynamic = "force-dynamic";

interface SeriesSummary {
  metric: string;
  source: SignalSource;
  method: string;
  n_observations: number;
  period_start: string;
  period_end: string;
  latest_value: number | null;
  is_national: boolean;
  provinces: string[];
}

/** Minimal pengamatan sebelum model state-space punya sesuatu untuk di-fit. */
const MIN_FOR_FIT = 8;

export default async function DeretPage() {
  const { id: projectId, name: projectName, is_demo: isDemo } = await getCurrentProject();

  // apiOrNullLenient di kedua panggilan -- bukan api polos. Error backend APA
  // PUN (bukan cuma 404) tidak boleh menjatuhkan halaman; lihat catatan yang
  // sama di command/page.tsx dan audit crash 2026-09-02.
  const [connectors, series] = await Promise.all([
    apiOrNullLenient<MetricConnector[]>("/metrics/connectors"),
    apiOrNullLenient<SeriesSummary[]>(`/projects/${projectId}/metrics`),
  ]);

  const rows = series ?? [];
  const fittable = rows.filter((s) => s.is_national && s.n_observations >= MIN_FOR_FIT);

  return (
    <>
      <PageHeader kicker="Deret Data Publik" title={projectName} isDemo={isDemo} />
      <div className="body">
        <section className="stat-row">
          <div className="stat">
            <div className="kicker">Deret tersimpan</div>
            <div className="stat-v">{rows.length}</div>
            <div className="dim" style={{ fontSize: 11.5, marginTop: 6 }}>
              Termasuk deret survei bawaan proyek ini
            </div>
          </div>
          <div className="stat">
            <div className="kicker">Siap di-fit forecast</div>
            <div className="stat-v">{fittable.length}</div>
            <div className="dim" style={{ fontSize: 11.5, marginTop: 6 }}>
              Deret nasional dengan ≥ {MIN_FOR_FIT} pengamatan
            </div>
          </div>
          <div className="stat">
            <div className="kicker">Konektor tersedia</div>
            <div className="stat-v">{connectors?.length ?? 0}</div>
            <div className="dim" style={{ fontSize: 11.5, marginTop: 6 }}>
              Semuanya tanpa kunci API
            </div>
          </div>
        </section>

        <Panel
          kicker="Perhatian dan konteks, bukan opini"
          title="Tarik deret dari sumber publik"
        >
          <p className="dim" style={{ fontSize: 12.5, margin: "0 0 16px", maxWidth: "72ch" }}>
            Deret di sini mengukur hal-hal di sekitar opini — berapa banyak
            orang mencari tahu sebuah topik, seburuk apa udaranya — bukan apa
            yang orang percayai. Ia berguna justru karena berbeda: ia memberi
            pembanding yang bergerak harian, ketika survei hanya bergerak per
            gelombang.
          </p>
          {connectors === null || connectors.length === 0 ? (
            <InsufficientData reason="Deployment ini belum punya konektor deret waktu yang terdaftar." />
          ) : (
            <CollectForm projectId={projectId} connectors={connectors} />
          )}
        </Panel>

        <Panel kicker="Riwayat yang bisa dijadikan baseline" title="Deret di proyek ini">
          {rows.length === 0 ? (
            <InsufficientData reason="Proyek ini belum punya satu pun deret metrik. Tarik satu di panel di atas, atau jalankan survei gelombang pertama." />
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Deret</th>
                    <th>Sumber</th>
                    <th>Pengamatan</th>
                    <th>Rentang</th>
                    <th>Terakhir</th>
                    <th>Forecast</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((s) => {
                    const ready = s.is_national && s.n_observations >= MIN_FOR_FIT;
                    return (
                      <tr key={s.metric}>
                        <td className="strong mono">{s.metric}</td>
                        <td style={{ color: SOURCE[s.source]?.color }}>
                          {SOURCE[s.source]?.label ?? s.source}
                        </td>
                        <td className="mono">{s.n_observations}</td>
                        <td className="mono dim">
                          {s.period_start} → {s.period_end}
                        </td>
                        <td className="mono">
                          {s.latest_value === null ? (
                            <span className="dim" title="Deret per provinsi tidak punya satu nilai terakhir">
                              —
                            </span>
                          ) : (
                            s.latest_value.toLocaleString("id-ID")
                          )}
                        </td>
                        <td>
                          {ready ? (
                            <span className="pill pill-ok">Siap</span>
                          ) : !s.is_national ? (
                            <span className="pill pill-warn">
                              Per provinsi ({s.provinces.length})
                            </span>
                          ) : (
                            <span className="pill pill-warn">
                              Butuh {MIN_FOR_FIT - s.n_observations} lagi
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <div className="note">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 16v-4M12 8h.01" />
            </svg>
            <span>
              Deret per provinsi sengaja tidak dipakai sebagai baseline forecast.
              Menggabungkan potongan populasi yang berbeda menjadi satu riwayat
              akan menghasilkan &quot;pengamatan&quot; yang sebenarnya bukan
              deret yang sama.
            </span>
          </div>
        </Panel>
      </div>
    </>
  );
}
