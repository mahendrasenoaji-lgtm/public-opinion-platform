import type { ReactNode } from "react";
import {
  KinerjaAccounts, KinerjaCoding, KinerjaIndicators, KinerjaScorecards, KinerjaSites,
} from "@/components/PersKinerja";
import {
  ActorsTable, SourceDaily, SourcePeaks, SourceTone, SourcesTable, TopicsTable, WordsTable, sourceMeta,
} from "@/components/PersLaporan";
import { parseMarkdown, type Inline } from "@/lib/miniMarkdown";
import { EMBEDS, boardItems, type PersSnapshot } from "@/lib/pers";

/**
 * Isi artikel publikasi seperti yang dibaca publik: papan angka di kepala,
 * lalu teks dengan tabel dan penanda blok `[[nama]]` yang dirender dari
 * snapshot beku di tempatnya. Dipakai di /pers/[slug] dan sebagai pratinjau
 * di /publikasi, supaya penyunting melihat tampilan yang sama sebelum terbit.
 */

function Text({ inline }: { inline: Inline[] }) {
  return <>{inline.map((p, i) => (p.bold ? <b key={i}>{p.text}</b> : <span key={i}>{p.text}</span>))}</>;
}

export function PersBoard({ snap }: { snap: PersSnapshot }) {
  const items = boardItems(snap, (s) => sourceMeta(s).label);
  if (items.length === 0) return null;
  return (
    <div className="pers-board" aria-label="Ringkasan angka">
      {items.map((it) => (
        <div key={it.label}>
          <b>{it.value}</b>
          <span>{it.label}</span>
        </div>
      ))}
    </div>
  );
}

/** Satu penanda blok; null bila datanya tidak ada di snapshot ini. */
function embed(name: string, snap: PersSnapshot): ReactNode {
  const k = snap.kind === "kinerja" ? snap.kinerja : undefined;
  if (k) {
    switch (name) {
      case "kartu-skor":
        return <KinerjaScorecards k={k} />;
      case "indikator":
        return <KinerjaIndicators k={k} />;
      case "akun":
        return k.accounts.accounts.length > 0 ? <KinerjaAccounts k={k} /> : null;
      case "situs":
        return k.sites.sites.length > 0 ? <KinerjaSites k={k} /> : null;
      case "pengodean":
        return k.coding.n_coded > 0 ? <KinerjaCoding k={k} /> : null;
      default:
        return null;
    }
  }
  const sources = snap.report.sources;
  const many = sources.length > 1;
  switch (name) {
    case "grafik-harian": {
      const charts = sources.filter((s) => s.days && s.days.length > 1);
      return charts.length > 0 ? charts.map((s) => <SourceDaily key={s.source} s={s} withTable={false} />) : null;
    }
    case "nada": {
      const toned = sources.filter((s) => s.scored > 0);
      return toned.length > 0 ? toned.map((s) => <SourceTone key={s.source} s={s} titled={many} />) : null;
    }
    case "puncak": {
      const peaked = sources.filter((s) => (s.peaks ?? []).length > 0);
      return peaked.length > 0 ? peaked.map((s) => <SourcePeaks key={s.source} s={s} />) : null;
    }
    case "tema":
      return (snap.report.topics ?? []).length > 0 ? <TopicsTable snap={snap} /> : null;
    case "aktor":
      return (snap.actors ?? []).some((g) => g.actors.length > 0) ? <ActorsTable snap={snap} /> : null;
    case "kata":
      return sources.some((s) => (s.words ?? []).length > 0) ? <WordsTable sources={sources} /> : null;
    case "sumber":
      return <SourcesTable sources={sources} />;
    default:
      return null;
  }
}

export function PersArticleBody({
  body,
  snap,
  preview = false,
}: {
  body: string;
  snap: PersSnapshot;
  /** Pratinjau penyunting: penanda yang tidak dikenal/kosong diberi tahu, bukan disembunyikan. */
  preview?: boolean;
}) {
  const known: Record<string, string> = snap.kind === "kinerja" ? EMBEDS.kinerja : EMBEDS.laporan;
  return (
    <div className="pers-body">
      {parseMarkdown(body).map((b, i) => {
        switch (b.type) {
          case "ul":
            return (
              <ul key={i}>
                {b.items.map((item, j) => (
                  <li key={j}>
                    <Text inline={item} />
                  </li>
                ))}
              </ul>
            );
          case "h2":
            return (
              <h2 key={i}>
                <Text inline={b.inline} />
              </h2>
            );
          case "h3":
            return (
              <h3 key={i}>
                <Text inline={b.inline} />
              </h3>
            );
          case "p":
            return (
              <p key={i}>
                <Text inline={b.inline} />
              </p>
            );
          case "table":
            return (
              <div key={i} className="pers-tbl-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      {b.head.map((h, j) => (
                        <th key={j} scope="col">
                          <Text inline={h} />
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {b.rows.map((r, j) => (
                      <tr key={j}>
                        {r.map((c, n) => (
                          <td key={n}>
                            <Text inline={c} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          case "embed": {
            const node = known[b.name] ? embed(b.name, snap) : null;
            if (node) return <div key={i} className="pers-embed">{node}</div>;
            if (!preview) return null;
            return (
              <p key={i} className="pers-embed-missing">
                {known[b.name]
                  ? `[[${b.name}]] tidak tampil: datanya tidak ada di snapshot ini.`
                  : `[[${b.name}]] bukan penanda yang dikenal. Pilihan: ${Object.keys(known).map((n) => `[[${n}]]`).join(", ")}.`}
              </p>
            );
          }
        }
      })}
    </div>
  );
}

/** Daftar penanda untuk petunjuk di penyunting. */
export function EmbedHelp({ kind }: { kind: "laporan" | "kinerja" }) {
  return (
    <ul className="pers-embed-help">
      {Object.entries(EMBEDS[kind]).map(([name, label]) => (
        <li key={name}>
          <code>[[{name}]]</code> {label}
        </li>
      ))}
    </ul>
  );
}
