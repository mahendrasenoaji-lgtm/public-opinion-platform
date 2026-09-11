import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Public Opinion Intelligence Platform",
  description:
    "Menggabungkan survei, percakapan sosial, dan liputan media menjadi intelligence opini publik.",
};

/**
 * Pasang tema sebelum cat pertama.
 *
 * Harus skrip inline yang berjalan sinkron di <head>: kalau preferensi tema
 * dibaca dari dalam React (useEffect), halaman sempat tercat dengan tema
 * default dulu lalu berkedip ke tema yang benar. Pembacaan dibungkus try/catch
 * karena localStorage bisa melempar di mode privat — halaman harus tetap
 * tampil (tema terang) kalau itu terjadi.
 */
const THEME_BOOT = `
try {
  if (localStorage.getItem("pop-theme") === "dark") {
    document.documentElement.dataset.theme = "dark";
  }
} catch (e) {}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
