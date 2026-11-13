/**
 * Markdown sangat kecil untuk isi artikel publikasi: `##`/`###` subjudul,
 * paragraf, daftar `- `, dan `**tebal**`. Hasilnya struktur data, BUKAN HTML,
 * sehingga isi artikel tidak pernah bisa menyisipkan markup ke halaman publik.
 */

export type Inline = { text: string; bold: boolean };

export type Block =
  | { type: "h2" | "h3" | "p"; inline: Inline[] }
  | { type: "ul"; items: Inline[][] };

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

  const flush = () => {
    if (para.length > 0) blocks.push({ type: "p", inline: parseInline(para.join(" ")) });
    if (list.length > 0) blocks.push({ type: "ul", items: list });
    para = [];
    list = [];
  };

  for (const raw of source.replace(/\r\n?/g, "\n").split("\n")) {
    const line = raw.trim();
    if (line === "") {
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
