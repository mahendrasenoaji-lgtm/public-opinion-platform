import { DIMENSION_LABEL, dimensionCell, idNum, type PersKinerja as Kinerja } from "@/lib/pers";

const DIMENSIONS = ["INPUT", "PROCESS", "OUTPUT", "OUTCOME"] as const;

/**
 * Angka di balik artikel kinerja komunikasi: kartu skor per lembaga, indikator
 * yang berskor, angka akun resmi, keaktifan situs, dan uji pengodean isi.
 *
 * Server component, tanpa grafik: lembaga tidak diperingkat dan skor total
 * hanya tampil bila model menerbitkannya (keempat dimensi cakupannya cukup).
 */
export function PersKinerja({ k }: { k: Kinerja }) {
  const cards = k.scorecards;
  // Indikator yang berskor di minimal satu lembaga, urut seperti kerangka.
  const codes = cards[0]?.items.map((i) => i.indicator) ?? [];
  const scoredCodes = codes.filter((c) => cards.some((card) => card.items.find((i) => i.indicator === c)?.score != null));
  const nameOf = (c: string) => cards[0]?.items.find((i) => i.indicator === c)?.name ?? c;

  return (
    <>
      <p className="pers-meta">
        Model <span className="mono">{k.model_version}</span>. {k.disclaimer}
      </p>

      <h3>Kartu skor per lembaga</h3>
      {cards.length === 0 ? (
        <p className="pers-empty">Belum ada lembaga yang dinilai pada periode ini.</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th scope="col">Lembaga</th>
                {DIMENSIONS.map((d) => (
                  <th key={d} scope="col">
                    {DIMENSION_LABEL[d]}
                  </th>
                ))}
                <th scope="col">Skor total</th>
                <th scope="col">Indikator berskor / tidak tersedia</th>
              </tr>
            </thead>
            <tbody>
              {cards.map((c) => (
                <tr key={`${c.subject}|${c.period}`}>
                  <td>{c.subject}</td>
                  {DIMENSIONS.map((d) => {
                    const dim = c.dimensions.find((x) => x.dimension === d);
                    return (
                      <td key={d} className="mono">
                        {dim ? dimensionCell(dim) : "–"}
                      </td>
                    );
                  })}
                  <td className="mono">
                    {c.total === null ? "tidak terbit" : `${c.total.toFixed(2).replace(".", ",")} (${c.label})`}
                  </td>
                  <td className="mono">
                    {c.n_scored} / {c.n_unavailable}
                    {c.n_empty > 0 && ` (${c.n_empty} belum diisi)`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="pers-meta">
        Dimensi terbit bila minimal 60% indikatornya punya skor; skor total hanya dihitung bila keempat
        dimensi terbit. Lembaga tidak diperingkat.
      </p>

      {scoredCodes.length > 0 && (
        <>
          <h3>Indikator yang berskor</h3>
          <div style={{ overflowX: "auto" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th scope="col">Indikator</th>
                  {cards.map((c) => (
                    <th key={c.subject} scope="col">
                      {c.subject}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {scoredCodes.map((code) => (
                  <tr key={code}>
                    <td>
                      <span className="mono">{code}</span> {nameOf(code)}
                    </td>
                    {cards.map((c) => {
                      const item = c.items.find((i) => i.indicator === code);
                      return (
                        <td key={c.subject} className="mono" title={item?.evidence || item?.unavailable_reason || ""}>
                          {item?.score ?? (item?.unavailable_reason ? "tidak tersedia" : "–")}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <details className="pers-details">
            <summary>Lihat bukti dan alasan tiap indikator</summary>
            {cards.map((c) => (
              <div key={c.subject}>
                <h4>{c.subject}</h4>
                <ul>
                  {c.items
                    .filter((i) => i.score !== null || i.unavailable_reason)
                    .map((i) => (
                      <li key={i.indicator}>
                        <b>
                          {i.indicator} {i.name}:
                        </b>{" "}
                        {i.score !== null ? `skor ${i.score}. ${i.evidence}` : `tidak tersedia. ${i.unavailable_reason}`}
                      </li>
                    ))}
                </ul>
              </div>
            ))}
          </details>
        </>
      )}

      {k.accounts.accounts.length > 0 && (
        <>
          <h3>Akun resmi</h3>
          <div style={{ overflowX: "auto" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th scope="col">Akun</th>
                  <th scope="col">Platform</th>
                  <th scope="col">Unggahan</th>
                  <th scope="col">Median tayangan</th>
                  <th scope="col">Median suka</th>
                  <th scope="col">Median komentar</th>
                  <th scope="col">Engagement per pengikut</th>
                </tr>
              </thead>
              <tbody>
                {k.accounts.accounts.map((a) => (
                  <tr key={`${a.platform}|${a.account}`}>
                    <td className="mono">{a.account}</td>
                    <td>{a.platform}</td>
                    <td className="mono">{idNum(a.n_posts)}</td>
                    <td className="mono">{idNum(a.median_views, 1)}</td>
                    <td className="mono">{idNum(a.median_likes, 1)}</td>
                    <td className="mono">{idNum(a.median_comments, 1)}</td>
                    <td className="mono">
                      {a.median_engagement_rate === null ? "–" : `${idNum(a.median_engagement_rate, 3)}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="pers-meta">{k.accounts.method}</p>
        </>
      )}

      {k.sites.sites.length > 0 && (
        <>
          <h3>Situs web resmi</h3>
          <div style={{ overflowX: "auto" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th scope="col">Lembaga</th>
                  <th scope="col">Terbitan 30 hari</th>
                  <th scope="col">Terakhir terbit</th>
                  <th scope="col">Jeda terpanjang (hari)</th>
                  <th scope="col">Bacaan</th>
                </tr>
              </thead>
              <tbody>
                {k.sites.sites.map((s) => (
                  <tr key={s.base_url}>
                    <td>
                      {s.subject}
                      <div className="proj-s">{s.base_url.replace(/^https?:\/\//, "")}</div>
                    </td>
                    <td className="mono">{idNum(s.n_30)}</td>
                    <td className="mono">{s.last_published ?? "tidak tercatat"}</td>
                    <td className="mono">{idNum(s.longest_gap_days)}</td>
                    <td>{s.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="pers-meta">
            Dihitung per {k.sites.as_of}, dari butir yang tercatat. {k.sites.method}
          </p>
        </>
      )}

      {k.coding.n_coded > 0 && (
        <>
          <h3>Pengodean isi unggahan</h3>
          <p className="pers-meta">
            {idNum(k.coding.n_coded)} dari {idNum(k.coding.n_posts)} unggahan dikode;{" "}
            {idNum(k.coding.n_double_coded)} dikode dua pengode.
          </p>
          <div style={{ overflowX: "auto" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th scope="col">Variabel</th>
                  <th scope="col">Krippendorff alpha</th>
                  <th scope="col">Keterangan</th>
                </tr>
              </thead>
              <tbody>
                {k.coding.variables.map((v) => (
                  <tr key={v.code}>
                    <td>
                      <span className="mono">{v.code}</span> {v.name}
                    </td>
                    <td className="mono">{v.alpha === null ? "–" : idNum(v.alpha, 3)}</td>
                    <td>{v.label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {k.coding.distributions.map((d) => (
            <p key={d.code} className="pers-meta">
              <b>
                {d.code} {d.name}
              </b>{" "}
              (n {idNum(d.n)}): {d.counts.map(([, label, n]) => `${label} ${idNum(n)}`).join(" · ")}
            </p>
          ))}
          {k.coding.distributions.length === 0 && (
            <p className="pers-meta">
              Sebaran kode belum ditampilkan: belum ada variabel yang kesepakatan antar-pengodenya
              teruji dan lolos ambang 0,667.
            </p>
          )}
        </>
      )}

      <h3>Batas tiap bagian</h3>
      <ul>
        {[
          ...new Set([
            ...cards.flatMap((c) => c.limitations ?? []),
            ...k.accounts.limitations,
            ...k.sites.limitations,
            ...(k.coding.limitations ?? []),
          ]),
        ].map((l) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
    </>
  );
}
