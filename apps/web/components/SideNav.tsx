"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";

/** Kelompok navigasi: judul + rutenya, berurutan. */
interface NavGroup {
  title: string;
  items: readonly (readonly [string, string])[];
}

/**
 * Dikelompokkan menurut APA YANG DIUKUR, bukan menurut fase pembangunan.
 *
 * Urutan lama mengikuti Phase 1/2/3 di roadmap — berguna bagi yang
 * membangunnya, tidak berguna bagi yang memakainya. Seorang peneliti yang
 * mencari "dari mana angka ini" tidak tahu fitur mana lahir di fase berapa;
 * yang ia tahu adalah ia sedang mencari pengukuran, sinyal mentah, atau
 * proyeksi. Itu yang dipakai di sini.
 *
 * Catatan satu penempatan yang mungkin mengejutkan: Jaringan Interaksi ada di
 * "Sinyal", bukan "Prediksi", walau dibangun di Phase 3. Ia mendeskripsikan
 * siapa membalas siapa pada data yang sudah ada — tidak memproyeksikan apa
 * pun. Menaruhnya di Prediksi akan menyiratkan klaim yang tidak dibuatnya.
 */
const NAV_GROUPS: readonly NavGroup[] = [
  {
    title: "Pengukuran",
    items: [
      ["/command", "Command Center"],
      ["/opinion-index", "Opinion Index"],
      ["/consistency", "Konsistensi Sinyal"],
      ["/segments", "Segmen Publik"],
      ["/geo", "Peta Geografis"],
    ],
  },
  {
    title: "Sinyal",
    items: [
      ["/sinyal", "Sinyal & Sentimen"],
      ["/deret", "Deret Data Publik"],
      ["/tema", "Tema"],
      ["/narrative", "Peta Narasi"],
      ["/jaringan", "Jaringan Interaksi"],
    ],
  },
  {
    title: "Prediksi",
    items: [
      ["/forecast", "Forecast & Simulator"],
      ["/risiko", "Skor Risiko"],
      ["/pengaruh", "Estimasi Pengaruh"],
      ["/dampak", "Dampak Komunikasi"],
    ],
  },
  {
    title: "AI & Tata Kelola",
    items: [
      ["/brief", "Executive Brief"],
      ["/copilot", "AI Copilot"],
      ["/governance", "AI Governance"],
    ],
  },
] as const;

export function SideNav() {
  const pathname = usePathname();

  return (
    <nav>
      {NAV_GROUPS.map((group) => (
        <div key={group.title} className="nav-grp">
          <div className="nav-grp-t">{group.title}</div>
          {group.items.map(([href, label]) => {
            // Cocokkan segmen, bukan awalan string: startsWith akan membuat
            // "/tema" ikut menyala saat berada di rute lain yang kebetulan
            // berawalan sama.
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href as Route}
                className={active ? "nav-i nav-on" : "nav-i"}
                aria-current={active ? "page" : undefined}
              >
                {label}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
