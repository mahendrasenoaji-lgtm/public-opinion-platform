/** Bar atas tiap halaman dashboard — nama view + status data. */
export function PageHeader({ kicker, title }: { kicker: string; title: string }) {
  return (
    <header className="top">
      <div>
        <div className="kicker">{kicker}</div>
        <div className="top-t">{title}</div>
      </div>
      <div className="top-r">
        <span className="dot" /> Data demo sintetis
      </div>
    </header>
  );
}
