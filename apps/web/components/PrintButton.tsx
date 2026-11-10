"use client";

/** Tombol cetak: laporan disimpan sebagai PDF lewat dialog cetak peramban. */
export function PrintButton() {
  return (
    <button type="button" className="btn btn-ghost btn-sm no-print" onClick={() => window.print()}>
      Cetak / simpan PDF
    </button>
  );
}
