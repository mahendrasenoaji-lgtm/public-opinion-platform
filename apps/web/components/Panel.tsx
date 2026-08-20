import type { ReactNode } from "react";

/** Bungkus kartu standar — kicker + judul opsional, konten bebas. */
export function Panel({
  title,
  kicker,
  right,
  tone,
  children,
}: {
  title?: string;
  kicker?: string;
  right?: ReactNode;
  tone?: "light";
  children: ReactNode;
}) {
  return (
    <section className={"panel" + (tone === "light" ? " panel-light" : "")}>
      {(title || right) && (
        <header className="panel-head">
          <div>
            {kicker && <div className="kicker">{kicker}</div>}
            {title && <h2 className="panel-title">{title}</h2>}
          </div>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}
