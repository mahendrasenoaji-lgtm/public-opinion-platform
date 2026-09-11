"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

/**
 * Pemindah tema terang/gelap.
 *
 * Tema terang adalah default yang dipilih; gelap adalah pilihan pengguna yang
 * bertahan di localStorage. SENGAJA tidak mengikuti `prefers-color-scheme` —
 * kalau ia mengikuti, pengguna bersistem gelap tidak akan pernah melihat
 * desain terang yang dipilih untuk produk ini tanpa mengubah setelan OS-nya.
 *
 * Pembacaan awal terjadi di skrip inline di app/layout.tsx, bukan di sini.
 * Komponen ini hanya perlu menyamakan state React-nya setelah hidrasi, supaya
 * ikon yang tampil cocok dengan tema yang sudah terpasang di <html>.
 */
export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.dataset.theme === "dark");
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    const root = document.documentElement;
    if (next) root.dataset.theme = "dark";
    else delete root.dataset.theme;
    try {
      localStorage.setItem("pop-theme", next ? "dark" : "light");
    } catch {
      // Mode privat / penyimpanan diblokir: temanya tetap berganti untuk
      // sesi ini, cuma tidak diingat. Bukan alasan untuk gagal.
    }
  }

  return (
    <button
      className="theme-btn"
      onClick={toggle}
      type="button"
      aria-pressed={dark}
      title={dark ? "Beralih ke tema terang" : "Beralih ke tema gelap"}
    >
      {dark ? <Sun size={12} strokeWidth={2.5} /> : <Moon size={12} strokeWidth={2.5} />}
      {dark ? "Terang" : "Gelap"}
    </button>
  );
}
