/** Bar atas tiap halaman dashboard — nama view + status data. */
export function PageHeader({
  kicker,
  title,
  isDemo = true,
}: {
  kicker: string;
  title: string;
  //: Default true supaya pemanggil lama (belum diperbarui) tetap tampil
  //: persis seperti sebelumnya -- lihat CLAUDE.md §7, penanda ini wajib
  //: selama datanya memang demo, dan SEMUA pemanggil di repo ini per
  //: 2026-08-27 sudah eksplisit mengisinya dari project.is_demo asli.
  isDemo?: boolean;
}) {
  return (
    <header className="top">
      <div>
        <div className="kicker">{kicker}</div>
        <div className="top-t">{title}</div>
      </div>
      <div className="top-r">
        <span className="dot" /> {isDemo ? "Data demo sintetis" : "Data proyek Anda sendiri"}
      </div>
    </header>
  );
}
