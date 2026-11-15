import { ImageResponse } from "next/og";

export const OG_SIZE = { width: 1200, height: 630 };

/**
 * Gambar pratinjau tautan. Hex dipakai langsung karena gambar dirender di
 * luar halaman dan tidak bisa membaca token CSS; nilainya sama dengan
 * `--txt`, `--txt2`, `--panel`, `--ink` tema terang di globals.css.
 */
export function persOgImage(title: string, meta: string): ImageResponse {
  const size = title.length > 90 ? 46 : title.length > 50 ? 56 : 68;
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%", height: "100%", display: "flex", flexDirection: "column",
          justifyContent: "space-between", padding: 72, background: "#FFFFFF",
          borderLeft: "20px solid #27233A", color: "#27233A", fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", fontSize: 26, letterSpacing: 4, color: "#575268" }}>
          RISET OPINI PUBLIK
        </div>
        <div style={{ display: "flex", fontSize: size, fontWeight: 700, lineHeight: 1.15 }}>
          {title.length > 140 ? `${title.slice(0, 137)}…` : title}
        </div>
        <div style={{ display: "flex", fontSize: 26, color: "#575268" }}>{meta}</div>
      </div>
    ),
    OG_SIZE,
  );
}
