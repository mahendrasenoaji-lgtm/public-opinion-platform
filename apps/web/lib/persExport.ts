/**
 * Ekspor artikel publikasi: CSV agregat dan feed RSS. Fungsi murni.
 *
 * Yang keluar dari sini hanya isi snapshot beku: hitungan per sumber, per
 * hari, kata, tagar, media. Tidak ada teks konten warga (snapshot memang
 * tidak menyimpannya), dan tidak ada angka lintas sumber yang dijumlah (R1):
 * setiap baris CSV membawa kolom `sumber`.
 */

import type { PersArticle, PersRef } from "@/lib/pers";

/**
 * Satu sel CSV. Sel yang diawali = + - @ diberi tanda petik tunggal di depan
 * supaya tidak dijalankan sebagai rumus saat dibuka di Excel (kata dan tagar
 * berasal dari teks publik, jadi isinya tidak bisa dipercaya).
 */
export function csvCell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "";
  const safe = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return /[",\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

const HEADER = ["bagian", "sumber", "butir", "ukuran", "nilai"] as const;

type Row = [string, string, string, string, string | number | null];

/** Data agregat artikel dalam bentuk panjang: satu angka per baris. */
export function aggregateCsv(a: PersArticle, url: string): string {
  const snap = a.snapshot;
  const rows: Row[] = [
    ["meta", "", "judul", "", a.title],
    ["meta", "", "alamat", "", url],
    ["meta", "", "versi", "", a.version],
    ["meta", "", "periode_mulai", "", snap.period_start],
    ["meta", "", "periode_akhir", "", snap.period_end],
    ["meta", "", "zona_waktu", "", snap.timezone],
    ["meta", "", "dibekukan", "", snap.frozen_at],
    ["meta", "", "catatan", "", snap.note],
  ];
  for (const s of snap.report.sources) {
    rows.push(["ringkasan", s.source, "semua", "konten", s.n]);
    rows.push(["ringkasan", s.source, "semua", "bernilai_sentimen", s.scored]);
    for (const [label, n] of Object.entries(s.labels).sort(([x], [y]) => x.localeCompare(y))) {
      rows.push(["sentimen", s.source, label, "konten", n]);
    }
    for (const d of s.days ?? []) {
      rows.push(["harian", s.source, d.day, "konten", d.volume]);
      rows.push(["harian", s.source, d.day, "bernilai_sentimen", d.scored]);
      // Kosong = ditahan karena konten bernilai di bawah ambang, bukan nol.
      rows.push(["harian", s.source, d.day, "rata_rata_skor", d.mean]);
      rows.push(["harian", s.source, d.day, "porsi_negatif", d.negative_share]);
    }
    for (const [w, n] of s.words ?? []) rows.push(["kata", s.source, w, "konten", n]);
    for (const [w, n] of s.hashtags ?? []) rows.push(["tagar", s.source, w, "konten", n]);
    for (const [w, n] of s.emoji ?? []) rows.push(["emoji", s.source, w, "konten", n]);
  }
  for (const t of snap.report.topics ?? []) {
    rows.push(["tema", t.source, t.label, "konten", t.n]);
    rows.push(["tema", t.source, t.label, "rata_rata_skor", t.sentiment]);
  }
  for (const o of snap.report.outlets ?? []) rows.push(["media", "MEDIA", o.domain, "liputan", o.n]);
  for (const [k, v] of Object.entries(snap.report.methods ?? {})) rows.push(["metode", "", k, "", v]);
  for (const [i, l] of (snap.report.limitations ?? []).entries()) {
    rows.push(["batas", "", String(i + 1), "", l]);
  }
  // BOM supaya Excel membaca UTF-8; CRLF sesuai RFC 4180.
  return "﻿" + [HEADER, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n") + "\r\n";
}

export function xmlEscape(text: string): string {
  return text
    // Karakter kendali yang tidak sah di XML 1.0 dibuang.
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/** Feed RSS 2.0 daftar artikel terbit. `origin` tanpa garis miring di akhir. */
export function rssXml(items: PersRef[], origin: string): string {
  const entries = items
    .map((a) => {
      const link = `${origin}/pers/${a.slug}`;
      return [
        "<item>",
        `<title>${xmlEscape(a.title)}</title>`,
        `<link>${xmlEscape(link)}</link>`,
        `<guid isPermaLink="true">${xmlEscape(link)}</guid>`,
        `<pubDate>${new Date(a.published_at).toUTCString()}</pubDate>`,
        `<description>${xmlEscape(a.summary)}</description>`,
        ...a.tags.map((t) => `<category>${xmlEscape(t)}</category>`),
        "</item>",
      ].join("");
    })
    .join("");
  const newest = items[0] ? `<lastBuildDate>${new Date(items[0].published_at).toUTCString()}</lastBuildDate>` : "";
  return (
    `<?xml version="1.0" encoding="UTF-8"?>` +
    `<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>` +
    `<title>Riset opini publik</title>` +
    `<link>${xmlEscape(origin)}/pers</link>` +
    `<atom:link href="${xmlEscape(origin)}/pers/rss.xml" rel="self" type="application/rss+xml"/>` +
    `<description>Artikel hasil riset opini publik, lengkap dengan metode dan batas tiap angka.</description>` +
    `<language>id</language>${newest}${entries}</channel></rss>`
  );
}
