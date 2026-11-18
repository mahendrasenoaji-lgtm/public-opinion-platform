/**
 * Artikel publikasi sebagai berkas Word (.docx), tanpa pustaka tambahan.
 *
 * Sebuah .docx adalah arsip ZIP berisi beberapa berkas XML. Arsipnya ditulis
 * dengan metode "stored" (tanpa kompresi): artikel hanya teks dan tabel kecil,
 * jadi ukurannya tetap beberapa puluh kilobita, dan kodenya cukup pendek untuk
 * dibaca habis. Isi yang masuk sama dengan halaman publik: tubuh artikel,
 * angka snapshot per sumber (tidak dijumlah, R1), metode, batas, ralat, sitasi.
 */

import { parseMarkdown, type Inline } from "@/lib/miniMarkdown";
import { EMBEDS, citation, dateLabel, dayLabel, dimensionCell, idNum, share, type PersArticle } from "@/lib/pers";
import { xmlEscape } from "@/lib/persExport";
import { SOURCE } from "@/lib/tokens";

// ------------------------------------------------------------------ zip ----

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return table;
})();

export function crc32(bytes: Uint8Array): number {
  let c = 0xffffffff;
  for (const b of bytes) c = (CRC_TABLE[(c ^ b) & 0xff] ?? 0) ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

/** Arsip ZIP tanpa kompresi. Urutan berkas dipertahankan. */
export function zipStore(files: { name: string; data: string }[]): Uint8Array {
  const enc = new TextEncoder();
  const parts: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  let offset = 0;

  for (const f of files) {
    const name = enc.encode(f.name);
    const data = enc.encode(f.data);
    const crc = crc32(data);

    const local = new DataView(new ArrayBuffer(30));
    local.setUint32(0, 0x04034b50, true);
    local.setUint16(4, 20, true); // versi minimal
    local.setUint16(6, 0x0800, true); // nama berkas UTF-8
    local.setUint16(8, 0, true); // stored
    local.setUint16(10, 0, true); // jam
    local.setUint16(12, 0x21, true); // tanggal: 1 Jan 1980 (tetap, supaya keluaran deterministik)
    local.setUint32(14, crc, true);
    local.setUint32(18, data.length, true);
    local.setUint32(22, data.length, true);
    local.setUint16(26, name.length, true);
    local.setUint16(28, 0, true);
    parts.push(new Uint8Array(local.buffer), name, data);

    const dir = new DataView(new ArrayBuffer(46));
    dir.setUint32(0, 0x02014b50, true);
    dir.setUint16(4, 20, true);
    dir.setUint16(6, 20, true);
    dir.setUint16(8, 0x0800, true);
    dir.setUint16(10, 0, true);
    dir.setUint16(12, 0, true);
    dir.setUint16(14, 0x21, true);
    dir.setUint32(16, crc, true);
    dir.setUint32(20, data.length, true);
    dir.setUint32(24, data.length, true);
    dir.setUint16(28, name.length, true);
    dir.setUint32(42, offset, true);
    central.push(new Uint8Array(dir.buffer), name);

    offset += 30 + name.length + data.length;
  }

  const centralSize = central.reduce((n, p) => n + p.length, 0);
  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true);
  end.setUint16(8, files.length, true);
  end.setUint16(10, files.length, true);
  end.setUint32(12, centralSize, true);
  end.setUint32(16, offset, true);

  const all = [...parts, ...central, new Uint8Array(end.buffer)];
  const out = new Uint8Array(all.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const p of all) {
    out.set(p, at);
    at += p.length;
  }
  return out;
}

// ------------------------------------------------------- WordprocessingML ----

const plain = (inline: Inline[]): string => inline.map((p) => p.text).join("");

function run(text: string, bold = false): string {
  return `<w:r>${bold ? "<w:rPr><w:b/></w:rPr>" : ""}<w:t xml:space="preserve">${xmlEscape(text)}</w:t></w:r>`;
}

function para(inline: Inline[] | string, style?: string): string {
  const runs =
    typeof inline === "string" ? run(inline) : inline.map((p) => run(p.text, p.bold)).join("");
  return `<w:p>${style ? `<w:pPr><w:pStyle w:val="${style}"/></w:pPr>` : ""}${runs}</w:p>`;
}

/** Butir daftar: tanda butir diketik, tanpa berkas penomoran. */
function bullet(inline: Inline[] | string): string {
  const items = typeof inline === "string" ? [{ text: inline, bold: false }] : inline;
  return para([{ text: "\u2022 ", bold: false }, ...items], "ListBullet");
}

function table(head: string[], rows: string[][]): string {
  const cell = (text: string, bold: boolean) =>
    `<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr><w:p>${run(text, bold)}</w:p></w:tc>`;
  const row = (cells: string[], bold: boolean) =>
    `<w:tr>${cells.map((c) => cell(c, bold)).join("")}</w:tr>`;
  const border = (side: string) => `<w:${side} w:val="single" w:sz="4" w:space="0" w:color="999999"/>`;
  return (
    `<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>` +
    ["top", "left", "bottom", "right", "insideH", "insideV"].map(border).join("") +
    `</w:tblBorders></w:tblPr>${row(head, true)}${rows.map((r) => row(r, false)).join("")}</w:tbl>` +
    // Word menuntut paragraf sesudah tabel.
    `<w:p/>`
  );
}

const num = (n: number) => n.toLocaleString("id-ID");

/** Isi `word/document.xml` untuk satu artikel. */
export function documentXml(a: PersArticle, url: string): string {
  const report = a.snapshot.report;
  const body: string[] = [
    para(a.title, "Title"),
    para(
      `${a.author_name} · ${dateLabel(a.published_at)}${a.version > 1 ? ` · versi ${a.version}` : ""}`,
      "Subtitle",
    ),
  ];
  if (a.summary) body.push(para([{ text: a.summary, bold: true }]));
  const embeds = a.snapshot.kind === "kinerja" ? EMBEDS.kinerja : EMBEDS.laporan;

  for (const b of parseMarkdown(a.body)) {
    if (b.type === "ul") body.push(...b.items.map((item) => bullet(item)));
    else if (b.type === "table") body.push(table(b.head.map(plain), b.rows.map((r) => r.map(plain))));
    else if (b.type === "embed") {
      // Grafik tidak ikut ke Word; angkanya ada di bagian "Angka di balik artikel ini".
      const label = (embeds as Record<string, string>)[b.name];
      if (label) body.push(para(`[${label}: lihat versi daring, ${url}]`));
    } else body.push(para(b.inline, b.type === "h2" ? "Heading1" : b.type === "h3" ? "Heading2" : undefined));
  }

  const k = a.snapshot.kind === "kinerja" ? a.snapshot.kinerja : undefined;
  if (k) {
    body.push(
      para("Angka di balik artikel ini", "Heading1"),
      para(
        `Periode ${a.snapshot.period_start} s.d. ${a.snapshot.period_end} (${a.snapshot.timezone}), ` +
          `dibekukan ${dateLabel(a.snapshot.frozen_at)}. Model ${k.model_version}. ${k.disclaimer}`,
      ),
      para("Kartu skor per lembaga", "Heading2"),
      table(
        ["Lembaga", "Input", "Process", "Output", "Outcome", "Skor total"],
        k.scorecards.map((c) => [
          c.subject,
          ...(["INPUT", "PROCESS", "OUTPUT", "OUTCOME"] as const).map((d) => {
            const dim = c.dimensions.find((x) => x.dimension === d);
            return dim ? dimensionCell(dim) : "–";
          }),
          c.total === null ? "tidak terbit" : `${c.total.toFixed(2).replace(".", ",")} (${c.label})`,
        ]),
      ),
    );
    if (k.accounts.accounts.length > 0) {
      body.push(
        para("Akun resmi", "Heading2"),
        table(
          ["Akun", "Platform", "Unggahan", "Median tayangan", "Engagement per pengikut"],
          k.accounts.accounts.map((x) => [
            x.account,
            x.platform,
            idNum(x.n_posts),
            idNum(x.median_views, 1),
            x.median_engagement_rate === null ? "–" : `${idNum(x.median_engagement_rate, 3)}%`,
          ]),
        ),
      );
    }
    if (k.sites.sites.length > 0) {
      body.push(
        para("Situs web resmi", "Heading2"),
        table(
          ["Lembaga", "Terbitan 30 hari", "Terakhir terbit", "Bacaan"],
          k.sites.sites.map((x) => [x.subject, idNum(x.n_30), x.last_published ?? "tidak tercatat", x.status]),
        ),
      );
    }
  } else body.push(
    para("Angka di balik artikel ini", "Heading1"),
    para(
      `Periode ${a.snapshot.period_start} s.d. ${a.snapshot.period_end} (${a.snapshot.timezone}), ` +
        `dibekukan ${dateLabel(a.snapshot.frozen_at)}. Sumber tidak dijumlahkan: satu baris per sumber.`,
    ),
    table(
      ["Sumber", "Konten", "Bernilai sentimen", "Negatif", "Netral", "Positif"],
      report.sources.map((s) => [
        SOURCE[s.source as keyof typeof SOURCE]?.label ?? s.source,
        num(s.n),
        num(s.scored),
        ...(["negatif", "netral", "positif"] as const).map(
          (k) => share(s.labels, k, s.scored) ?? "data tidak cukup",
        ),
      ]),
    ),
  );

  for (const s of report.sources) {
    if (!s.days || s.days.length === 0) continue;
    const label = SOURCE[s.source as keyof typeof SOURCE]?.label ?? s.source;
    body.push(
      para(`Per hari: ${label}`, "Heading2"),
      table(
        ["Hari", "Konten", "Bernilai sentimen", "Porsi negatif"],
        s.days.map((d) => [
          dayLabel(d.day),
          num(d.volume),
          num(d.scored),
          d.negative_share === null
            ? "data tidak cukup"
            : `${(d.negative_share * 100).toFixed(1).replace(".", ",")}%`,
        ]),
      ),
    );
  }

  const methods = Object.entries(report.methods ?? {});
  if (methods.length > 0) {
    body.push(para("Metode", "Heading2"));
    body.push(...methods.map(([k, v]) => bullet([{ text: `${k}: `, bold: true }, { text: v, bold: false }])));
  }
  body.push(para("Batas", "Heading2"));
  body.push(...[a.snapshot.note, ...(report.limitations ?? [])].map((l) => bullet(l)));

  if (a.corrections.length > 0) {
    body.push(para("Riwayat ralat", "Heading2"));
    body.push(
      ...a.corrections.map((c) =>
        bullet(`Versi ${c.version} diganti pada ${dateLabel(c.at)}: ${c.note}`),
      ),
    );
  }
  body.push(para("Cara mengutip", "Heading2"), para(citation(a, url)));

  return (
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>` +
    body.join("") +
    `<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>` +
    `<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>` +
    `</w:sectPr></w:body></w:document>`
  );
}

const STYLE = (id: string, name: string, size: number, bold: boolean, extra = "") =>
  `<w:style w:type="paragraph" w:styleId="${id}"><w:name w:val="${name}"/><w:basedOn w:val="Normal"/>` +
  `<w:pPr><w:keepNext/><w:spacing w:before="${extra ? 0 : 280}" w:after="120"/>${extra}</w:pPr>` +
  `<w:rPr>${bold ? "<w:b/>" : ""}<w:sz w:val="${size}"/></w:rPr></w:style>`;

const STYLES_XML =
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
  `<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>` +
  `<w:sz w:val="22"/><w:lang w:val="id-ID"/></w:rPr></w:rPrDefault>` +
  `<w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>` +
  `<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>` +
  STYLE("Title", "Title", 40, true) +
  `<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/>` +
  `<w:rPr><w:color w:val="595959"/><w:sz w:val="20"/></w:rPr></w:style>` +
  STYLE("Heading1", "heading 1", 30, true) +
  STYLE("Heading2", "heading 2", 25, true) +
  // Butir daftar tanpa berkas penomoran: tanda butir diketik, indentasi menggantung.
  `<w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/><w:basedOn w:val="Normal"/>` +
  `<w:pPr><w:ind w:left="360" w:hanging="240"/><w:spacing w:after="80"/></w:pPr></w:style>` +
  `</w:styles>`;

const CONTENT_TYPES =
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">` +
  `<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>` +
  `<Default Extension="xml" ContentType="application/xml"/>` +
  `<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>` +
  `<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>` +
  `</Types>`;

const ROOT_RELS =
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
  `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>` +
  `</Relationships>`;

const DOC_RELS =
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
  `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>` +
  `</Relationships>`;

/** Berkas .docx utuh untuk satu artikel terbit. */
export function articleDocx(a: PersArticle, url: string): Uint8Array {
  return zipStore([
    { name: "[Content_Types].xml", data: CONTENT_TYPES },
    { name: "_rels/.rels", data: ROOT_RELS },
    { name: "word/document.xml", data: documentXml(a, url) },
    { name: "word/styles.xml", data: STYLES_XML },
    { name: "word/_rels/document.xml.rels", data: DOC_RELS },
  ]);
}
