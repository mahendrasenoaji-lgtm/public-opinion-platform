/**
 * Markdown sangat kecil untuk isi artikel publikasi: `##`/`###` subjudul,
 * paragraf, daftar `- `, `**tebal**`, tabel pipa (`| a | b |` + baris
 * `|---|---|`), dan penanda blok `[[nama]]` sendirian di satu baris (grafik
 * atau tabel dari snapshot, lihat `components/PersEmbed.tsx`). Hasilnya
 * struktur data, BUKAN HTML, sehingga isi artikel tidak pernah bisa
 * menyisipkan markup ke halaman publik.
 */

export type Inline = { text: string; bold: boolean };

export type Block =
  | { type: "h2" | "h3" | "p"; inline: Inline[] }
  | { type: "ul"; items: Inline[][] }
  | { type: "table"; head: Inline[][]; rows: Inline[][][] }
  | { type: "embed"; name: string };

const EMBED = /^\[\[([a-z][a-z0-9-]{1,40})\]\]$/;
const TABLE_RULE = /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$/;

function cells(line: string): string[] {
  return line.replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}

export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  text.split(/(\*\*[^*]+\*\*)/).forEach((part) => {
    if (part === "") return;
    const bold = part.length > 4 && part.startsWith("**") && part.endsWith("**");
    out.push({ text: bold ? part.slice(2, -2) : part, bold });
  });
  return out;
}

export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  let list: Inline[][] = [];
  let table: string[] = [];

  const flushTable = () => {
    // Tabel sah = kepala + garis pemisah; selain itu dibaca sebagai paragraf.
    if (table.length >= 2 && TABLE_RULE.test(table[1])) {
      const head = cells(table[0]);
      blocks.push({
        type: "table",
        head: head.map(parseInline),
        rows: table.slice(2).map((r) => {
          const row = cells(r);
          return head.map((_, i) => parseInline(row[i] ?? ""));
        }),
      });
    } else if (table.length > 0) {
      blocks.push({ type: "p", inline: parseInline(table.join(" ")) });
    }
    table = [];
  };

  const flush = () => {
    if (para.length > 0) blocks.push({ type: "p", inline: parseInline(para.join(" ")) });
    if (list.length > 0) blocks.push({ type: "ul", items: list });
    flushTable();
    para = [];
    list = [];
  };

  for (const raw of source.replace(/\r\n?/g, "\n").split("\n")) {
    const line = raw.trim();
    if (line.startsWith("|")) {
      if (para.length > 0 || list.length > 0) {
        const keep = table;
        table = [];
        flush();
        table = keep;
      }
      table.push(line);
      continue;
    }
    if (table.length > 0) flushTable();
    const embed = EMBED.exec(line);
    if (embed) {
      flush();
      blocks.push({ type: "embed", name: embed[1] });
    } else if (line === "") {
      flush();
    } else if (line.startsWith("### ")) {
      flush();
      blocks.push({ type: "h3", inline: parseInline(line.slice(4).trim()) });
    } else if (line.startsWith("## ")) {
      flush();
      blocks.push({ type: "h2", inline: parseInline(line.slice(3).trim()) });
    } else if (line.startsWith("- ")) {
      if (para.length > 0) flush();
      list.push(parseInline(line.slice(2).trim()));
    } else {
      if (list.length > 0) flush();
      para.push(line);
    }
  }
  flush();
  return blocks;
}
