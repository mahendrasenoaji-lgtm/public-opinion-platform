import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Delta } from "@/components/Delta";
import { DivergenceBand } from "@/components/DivergenceBand";
import { Panel } from "@/components/Panel";
import { InsufficientData, Provenance } from "@/components/Provenance";
import { SOURCE } from "@/lib/tokens";

const html = (node: React.ReactElement) => renderToStaticMarkup(node);

describe("Provenance (R2: kaki wajib setiap kartu)", () => {
  it("selalu menampilkan metode, confidence, dan batasan", () => {
    const out = html(<Provenance method="CATI" confidence="Sedang" limits="Self-selected" />);
    expect(out).toContain("METODE");
    expect(out).toContain("CATI");
    expect(out).toContain("CONFIDENCE");
    expect(out).toContain("Sedang");
    expect(out).toContain("BATASAN");
    expect(out).toContain("Self-selected");
  });

  it("n dan CI hanya muncul bila diberikan", () => {
    const bare = html(<Provenance method="m" confidence="c" limits="l" />);
    expect(bare).not.toContain("CI 95%");
    expect(bare).not.toMatch(/<b>n<\/b>/);

    const full = html(<Provenance method="m" confidence="c" limits="l" n={1234} ci="±2,8" />);
    expect(full).toContain("CI 95%");
    expect(full).toContain("±2,8");
    expect(full).toMatch(/<b>n<\/b> 1234/);
  });

  it("n = 0 tetap ditampilkan (nol bukan 'tidak ada')", () => {
    expect(html(<Provenance method="m" confidence="c" limits="l" n={0} />)).toMatch(
      /<b>n<\/b> 0/,
    );
  });
});

describe("InsufficientData", () => {
  it("mengatakan 'Data tidak cukup' beserta alasannya, tanpa angka", () => {
    const out = html(<InsufficientData reason="achieved_n 120 < 250" />);
    expect(out).toContain("Data tidak cukup");
    expect(out).toContain("achieved_n 120 &lt; 250");
  });
});

describe("Delta", () => {
  it("naik: kelas up dan tanda +", () => {
    const out = html(<Delta value={3.2} suffix=" pt" />);
    expect(out).toContain("delta up");
    expect(out).toContain("+3.2 pt");
  });
  it("turun: kelas down tanpa tanda + ganda", () => {
    const out = html(<Delta value={-1.5} />);
    expect(out).toContain("delta down");
    expect(out).toContain("-1.5");
    expect(out).not.toContain("+-");
  });
  it("nol: kelas flat", () => {
    expect(html(<Delta value={0} />)).toContain("delta flat");
  });
});

describe("Panel", () => {
  it("tanpa title/right tidak merender header", () => {
    const out = html(<Panel>isi</Panel>);
    expect(out).not.toContain("panel-head");
    expect(out).toContain("isi");
  });
  it("kicker dan title muncul di header; tone light menambah kelas", () => {
    const out = html(<Panel kicker="K" title="T" tone="light">x</Panel>);
    expect(out).toContain("panel-head");
    expect(out).toContain("panel-light");
    expect(out).toContain(">K<");
    expect(out).toContain(">T<");
  });
});

describe("DivergenceBand", () => {
  const readings = [
    { source: "SOCIAL" as const, value: 41, n: 1599 },
    { source: "SURVEY" as const, value: 68, n: 1200 },
  ];

  it("tanpa pembacaan tidak merender apa pun", () => {
    expect(html(<DivergenceBand readings={[]} gap={0} explanationLead="x" />)).toBe("");
  });

  it("menampilkan selisih sebagai objek utama dan kaki Provenance", () => {
    const out = html(<DivergenceBand readings={readings} gap={27} explanationLead="Beda populasi" />);
    expect(out).toContain(">27<");
    expect(out).toContain("poin selisih");
    expect(out).toContain("Beda populasi");
    expect(out).toContain("METODE");
    expect(out).toContain("BATASAN");
  });

  it("rentang membentang dari nilai terendah ke tertinggi, urut naik", () => {
    const out = html(<DivergenceBand readings={readings} gap={27} explanationLead="x" />);
    expect(out).toContain("left:41%;width:27%");
    expect(out.indexOf(SOURCE.SOCIAL.label)).toBeLessThan(out.indexOf(SOURCE.SURVEY.label));
  });

  it("warna sumber mengikuti token R1", () => {
    const out = html(<DivergenceBand readings={readings} gap={27} explanationLead="x" />);
    // jsdom-less: renderToStaticMarkup menulis warna hex sebagai-adanya
    expect(out.toLowerCase()).toContain(SOURCE.SOCIAL.color.toLowerCase());
    expect(out.toLowerCase()).toContain(SOURCE.SURVEY.color.toLowerCase());
  });
});
