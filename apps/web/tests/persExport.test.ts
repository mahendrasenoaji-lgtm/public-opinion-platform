import { describe, expect, it } from "vitest";
import { articleDocx, crc32, documentXml, zipStore } from "@/lib/docx";
import { dayLabel, originOf, pageNumber, type PersArticle } from "@/lib/pers";
import { aggregateCsv, csvCell, rssXml, xmlEscape } from "@/lib/persExport";

const article: PersArticle = {
  slug: "bbm-bali-a1b2c3",
  title: "Sepuluh hari <BBM> & antrean",
  summary: "Ringkas.",
  tags: ["energi"],
  author_name: "Tim riset",
  published_at: "2026-11-15T03:00:00Z",
  updated_at: "2026-11-15T03:00:00Z",
  version: 2,
  body: "## Temuan\n\nIsi **tebal**.\n\n- butir satu",
  snapshot: {
    frozen_at: "2026-11-14T00:00:00Z",
    period_start: "2026-10-11",
    period_end: "2026-10-20",
    timezone: "WITA",
    note: "Angka dibekukan.",
    report: {
      sources: [
        {
          source: "SOCIAL",
          n: 100,
          scored: 60,
          labels: { negatif: 40, netral: 5, positif: 15, "tidak dinilai": 40 },
          days: [
            { day: "2026-10-11", volume: 70, scored: 45, mean: -0.3, negative_share: 0.667 },
            { day: "2026-10-12", volume: 30, scored: 15, mean: null, negative_share: null },
          ],
          peaks: [
            {
              day: "2026-10-11", volume: 70, ratio: 1.4, is_spike: false,
              top_content: [{ engagement: 9, published_at: "2026-10-11T01:00:00Z" }],
              same_day_media: [],
            },
          ],
          words: [["antre", 30], ["=cmd()", 2]],
          hashtags: [["#bbm", 4]],
        },
        { source: "MEDIA", n: 3, scored: 0, labels: { "tidak dinilai": 3 } },
      ],
      outlets: [{ domain: "antaranews.com", n: 3 }],
      methods: { kata: "jumlah konten, tanpa kata umum" },
      limitations: ["Bukan sebab."],
    },
  },
  corrections: [{ version: 1, at: "2026-11-15T04:00:00Z", note: "Salah ketik." }],
};

describe("csvCell", () => {
  it("mengutip koma, petik, dan baris baru", () => {
    expect(csvCell('a,"b"')).toBe('"a,""b"""');
    expect(csvCell("a\nb")).toBe('"a\nb"');
  });
  it("menetralkan sel yang akan dibaca Excel sebagai rumus", () => {
    expect(csvCell("=1+1")).toBe("'=1+1");
    expect(csvCell("@x")).toBe("'@x");
    expect(csvCell("-5")).toBe("'-5");
  });
  it("angka apa adanya; null kosong, bukan 0", () => {
    expect(csvCell(-0.3)).toBe("-0.3");
    expect(csvCell(null)).toBe("");
  });
});

describe("aggregateCsv", () => {
  const csv = aggregateCsv(article, "https://x.test/pers/bbm-bali-a1b2c3");
  const lines = csv.replace(/^﻿/, "").trimEnd().split("\r\n");

  it("berkepala dan setiap baris lima kolom sederhana membawa sumber", () => {
    expect(lines[0]).toBe("bagian,sumber,butir,ukuran,nilai");
    expect(lines).toContain("ringkasan,SOCIAL,semua,konten,100");
    expect(lines).toContain("ringkasan,MEDIA,semua,konten,3");
    expect(lines).toContain("sentimen,SOCIAL,negatif,konten,40");
    expect(lines).toContain("media,MEDIA,antaranews.com,liputan,3");
  });
  it("tidak pernah menjumlah lintas sumber", () => {
    expect(lines.some((l) => l.endsWith(",103"))).toBe(false);
  });
  it("hari yang ditahan tampil kosong, bukan nol", () => {
    expect(lines).toContain("harian,SOCIAL,2026-10-11,porsi_negatif,0.667");
    expect(lines).toContain("harian,SOCIAL,2026-10-12,porsi_negatif,");
  });
  it("kata yang menyerupai rumus dinetralkan", () => {
    expect(lines).toContain("kata,SOCIAL,'=cmd(),konten,2");
  });
  it("diawali BOM supaya Excel membaca UTF-8", () => {
    expect(csv.charCodeAt(0)).toBe(0xfeff);
  });
});

describe("rssXml", () => {
  const xml = rssXml([article], "https://x.test");
  it("memuat tautan, guid, dan tanggal RFC 822", () => {
    expect(xml).toContain("<link>https://x.test/pers/bbm-bali-a1b2c3</link>");
    expect(xml).toContain("<pubDate>Sun, 15 Nov 2026 03:00:00 GMT</pubDate>");
    expect(xml).toContain("<category>energi</category>");
  });
  it("judul di-escape, tidak pernah menjadi markup", () => {
    expect(xml).toContain("<title>Sepuluh hari &lt;BBM&gt; &amp; antrean</title>");
  });
  it("daftar kosong tetap feed yang sah", () => {
    const empty = rssXml([], "https://x.test");
    expect(empty).toContain("<channel>");
    expect(empty).not.toContain("<item>");
  });
});

describe("xmlEscape", () => {
  it("membuang karakter kendali yang tidak sah di XML", () => {
    expect(xmlEscape("a\u0001b\u000Bc")).toBe("abc");
  });
});

describe("docx", () => {
  it("crc32 cocok dengan nilai acuan", () => {
    expect(crc32(new TextEncoder().encode("123456789"))).toBe(0xcbf43926);
  });

  it("zipStore menulis kepala lokal, direktori pusat, dan penutup", () => {
    const zip = zipStore([{ name: "a.txt", data: "halo" }]);
    const view = new DataView(zip.buffer);
    expect(view.getUint32(0, true)).toBe(0x04034b50);
    expect(view.getUint32(zip.length - 22, true)).toBe(0x06054b50);
    expect(view.getUint16(zip.length - 22 + 10, true)).toBe(1);
    // Ofset direktori pusat menunjuk tepat ke tanda direktori pusat.
    expect(view.getUint32(view.getUint32(zip.length - 22 + 16, true), true)).toBe(0x02014b50);
  });

  it("dokumen memuat isi, angka per sumber, ralat, dan sitasi; markup di-escape", () => {
    const xml = documentXml(article, "https://x.test/pers/bbm-bali-a1b2c3");
    expect(xml).toContain("Sepuluh hari &lt;BBM&gt; &amp; antrean");
    expect(xml).toContain('<w:pStyle w:val="Heading1"/>');
    expect(xml).toContain("SOSIAL");
    expect(xml).toContain("66,7%");
    expect(xml).toContain("data tidak cukup");
    expect(xml).toContain("Salah ketik.");
    expect(xml).toContain("(versi 2)");
  });

  it("arsip memuat kelima bagian yang dibutuhkan Word", () => {
    const text = new TextDecoder().decode(articleDocx(article, "https://x.test/p"));
    for (const part of ["[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml", "word/_rels/document.xml.rels"]) {
      expect(text).toContain(part);
    }
  });
});

describe("pembantu halaman", () => {
  it("pageNumber menolak selain bilangan bulat positif", () => {
    expect(pageNumber("3")).toBe(3);
    expect(pageNumber("0")).toBe(1);
    expect(pageNumber("-2")).toBe(1);
    expect(pageNumber("2abc")).toBe(1);
    expect(pageNumber(undefined)).toBe(1);
  });
  it("dayLabel tidak bergeser karena zona waktu", () => {
    expect(dayLabel("2026-10-11")).toMatch(/^11 Okt/);
  });
  it("originOf memakai http hanya untuk localhost", () => {
    const h = (m: Record<string, string>) => ({ get: (k: string) => m[k] ?? null });
    expect(originOf(h({ host: "localhost:3000" }))).toBe("http://localhost:3000");
    expect(originOf(h({ host: "a.vercel.app" }))).toBe("https://a.vercel.app");
    expect(originOf(h({ host: "x", "x-forwarded-proto": "https", "x-forwarded-host": "b.id" }))).toBe("https://b.id");
  });
});

describe("artikel kinerja", () => {
  const kinerja: PersArticle = {
    ...article,
    snapshot: {
      ...article.snapshot,
      kind: "kinerja",
      report: { sources: [] },
      kinerja: {
        model_version: "gcp-rancangan-1",
        disclaimer: "Rancangan.",
        scorecards: [
          {
            subject: "KKP",
            period: "2026-10",
            total: null,
            label: null,
            n_scored: 2,
            n_unavailable: 26,
            n_empty: 0,
            dimensions: [
              { dimension: "OUTPUT", score: null, coverage: 0.222, n_available: 2, n_total: 9, published: false, weight: 0.2 },
            ],
            items: [
              { indicator: "O4", name: "Views", dimension: "OUTPUT", score: 4, unavailable_reason: null, evidence: "median 1.829" },
              { indicator: "I1", name: "SDM", dimension: "INPUT", score: null, unavailable_reason: "butuh data internal", evidence: "" },
              { indicator: "C3", name: "Keselarasan", dimension: "OUTCOME", score: null, unavailable_reason: null, evidence: "" },
            ],
          },
        ],
        accounts: {
          method: "median",
          n_posts: 11,
          accounts: [
            { account: "@kkp_ri", platform: "youtube", n_posts: 11, median_views: 1829, median_likes: 20, median_comments: 3, median_engagement_rate: 0.199, insufficient_data: false },
          ],
          limitations: [],
        },
        sites: { method: "butir", as_of: "2026-11-18", sites: [], limitations: [] },
        coding: { n_posts: 159, n_coded: 159, n_double_coded: 0, variables: [{ code: "A9", name: "Kategori", alpha: null, label: "belum diuji", n_double_coded: 0 }], distributions: [] },
      },
    },
  };

  it("CSV memuat kartu skor, indikator, dan akun; dimensi yang tidak terbit kosong", () => {
    const csv = aggregateCsv(kinerja, "https://x/pers/k");
    expect(csv).toContain("kartu_skor,KKP,OUTPUT,skor,\r\n");
    expect(csv).toContain("kartu_skor,KKP,OUTPUT,cakupan,0.222");
    expect(csv).toContain("indikator,KKP,O4,skor,4");
    expect(csv).toContain("indikator,KKP,I1,alasan_tidak_tersedia,butuh data internal");
    // Indikator yang belum diisi tidak dicetak sebagai nol.
    expect(csv).not.toContain("indikator,KKP,C3");
    // Diawali @ sehingga dinetralkan dari injeksi rumus Excel.
    expect(csv).toContain("akun,youtube,'@kkp_ri,median_tayangan,1829");
  });

  it("Word memuat tabel kartu skor tanpa tabel sumber kosong", () => {
    const xml = documentXml(kinerja, "https://x/pers/k");
    expect(xml).toContain("Kartu skor per lembaga");
    expect(xml).toContain("tidak terbit (cakupan 22%)");
    expect(xml).not.toContain("Sumber tidak dijumlahkan");
  });
});
