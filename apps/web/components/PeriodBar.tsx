import type { SignalWindow } from "@/app/(dashboard)/sinyal/window";

/**
 * Pemilih periode tetap untuk halaman tanpa zona waktu (Tema, Jaringan,
 * Pengaruh). Form GET polos: periode hidup di URL (`?dari=&sampai=`), jadi
 * bisa dibagikan dan tidak butuh komponen klien. Kedua tanggal kosong berarti
 * 30 hari terakhir.
 */
export function PeriodBar({ win, note }: { win: SignalWindow; note?: string }) {
  return (
    <form method="get" className="period-bar">
      <label className="field">
        <span className="kicker">Dari</span>
        <input type="date" name="dari" defaultValue={win.start ?? ""} />
      </label>
      <label className="field">
        <span className="kicker">Sampai</span>
        <input type="date" name="sampai" defaultValue={win.end ?? ""} />
      </label>
      <button type="submit" className="btn btn-sm">
        Terapkan
      </button>
      {(win.start || win.error) && (
        <a className="btn btn-ghost btn-sm" href="?">
          30 hari terakhir
        </a>
      )}
      <span className="proj-s period-now">
        {win.error
          ? `${win.error} Menampilkan 30 hari terakhir.`
          : win.start && win.end
            ? `Periode tampil: ${win.start} s.d. ${win.end} (UTC)${note ? `. ${note}` : ""}`
            : `Periode tampil: 30 hari terakhir${note ? `. ${note}` : ""}`}
      </span>
    </form>
  );
}
