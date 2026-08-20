import { Info } from "lucide-react";

export interface TimelineEvent {
  id: string;
  occurred_at: string;
  kind: string;
  label: string;
  value_note: string | null;
}

const TAG_CLASS: Record<string, string> = {
  event: "tl-event",
  media: "tl-media",
  alert: "tl-alert",
  signal: "",
};

/** Rangkaian peristiwa proyek. Urutan waktu ≠ sebab-akibat (CLAUDE.md §3). */
export function Timeline({ events }: { events: TimelineEvent[] }) {
  return (
    <>
      <ol className="tl">
        {events.map((e) => (
          <li key={e.id} className={TAG_CLASS[e.kind] ?? ""}>
            <span className="tl-d">
              {new Date(e.occurred_at).toLocaleDateString("id-ID", { day: "2-digit", month: "short" })}
            </span>
            <span className="tl-e">{e.label}</span>
            {e.value_note && <span className="tl-v">{e.value_note}</span>}
          </li>
        ))}
      </ol>
      <p className="note">
        <Info size={13} />
        Urutan waktu menunjukkan keterkaitan, bukan sebab-akibat. Klaim kausal memerlukan desain
        kuasi-eksperimen yang tersedia di modul Communication Impact.
      </p>
    </>
  );
}
