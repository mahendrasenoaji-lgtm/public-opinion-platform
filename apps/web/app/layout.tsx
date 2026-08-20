import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Public Opinion Intelligence Platform",
  description:
    "Menggabungkan survei, percakapan sosial, dan liputan media menjadi intelligence opini publik.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}
