/**
 * Kaki wajib setiap kartu insight (CLAUDE.md R2).
 *
 * Kalau sebuah kartu tidak bisa mengisi komponen ini, kartu itu tidak boleh
 * dirender. Ini bukan dekorasi — ini yang membedakan platform ini dari
 * dashboard yang menampilkan angka tanpa asal-usul.
 */
export function Provenance({
  method,
  n,
  ci,
  confidence,
  limits,
}: {
  method: string;
  n?: string | number;
  ci?: string;
  confidence: string;
  limits: string;
}) {
  return (
    <div className="prov">
      <span><b>METODE</b> {method}</span>
      {n !== undefined && <span><b>n</b> {n}</span>}
      {ci && <span><b>CI 95%</b> {ci}</span>}
      <span><b>CONFIDENCE</b> {confidence}</span>
      <span className="prov-lim"><b>BATASAN</b> {limits}</span>
    </div>
  );
}

/** Tampilan untuk metrik yang tidak lolos ambang publikasi. */
export function InsufficientData({ reason }: { reason: string }) {
  return (
    <div className="insufficient">
      <div className="insufficient-t">Data tidak cukup</div>
      <div className="insufficient-d">{reason}</div>
    </div>
  );
}
