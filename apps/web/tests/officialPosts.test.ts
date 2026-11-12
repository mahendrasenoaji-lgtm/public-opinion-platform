import { describe, expect, it } from "vitest";
import { parseCsv, parseOfficialPosts } from "@/lib/officialPosts";
import { coverageText, dimensionLabel, formatMedian } from "@/app/(dashboard)/kinerja/kinerja";

const row = { platform: "instagram", account: "akun", external_id: "p1", posted_at: "2026-10-01T03:00:00Z" };

describe("parseOfficialPosts (JSON)", () => {
  it("menerima larik polos dan membiarkan angka kosong tetap tidak ada", () => {
    const p = parseOfficialPosts(JSON.stringify([{ ...row, likes: 10, views: null }]))[0]!;
    expect(p).toEqual({ ...row, likes: 10 });
    expect("views" in p).toBe(false);
  });

  it("memakai account di tingkat berkas bila baris tidak punya", () => {
    const { account: _a, ...noAccount } = row;
    const p = parseOfficialPosts(JSON.stringify({ account: "kemenko", items: [noAccount] }))[0]!;
    expect(p.account).toBe("kemenko");
  });

  it("menolak platform asing, field wajib kosong, tanggal rusak, dan angka negatif", () => {
    expect(() => parseOfficialPosts(JSON.stringify([{ ...row, platform: "facebook" }]))).toThrow(/platform/);
    expect(() => parseOfficialPosts(JSON.stringify([{ ...row, external_id: "" }]))).toThrow(/ke-1/);
    expect(() => parseOfficialPosts(JSON.stringify([{ ...row, posted_at: "kemarin" }]))).toThrow(/posted_at/);
    expect(() => parseOfficialPosts(JSON.stringify([{ ...row, likes: -3 }]))).toThrow(/likes/);
    expect(() => parseOfficialPosts("[]")).toThrow(/items/);
    expect(() => parseOfficialPosts("  ")).toThrow(/kosong/);
  });
});

describe("parseOfficialPosts (CSV)", () => {
  it("membaca kepala, sel kosong menjadi tidak ada, platform tidak peka huruf besar", () => {
    const csv = "platform,account,external_id,posted_at,likes,views\nTikTok,akun,v1,2026-10-02T01:00:00Z,25,\n";
    expect(parseOfficialPosts(csv)).toEqual([
      { platform: "tiktok", account: "akun", external_id: "v1", posted_at: "2026-10-02T01:00:00Z", likes: 25 },
    ]);
  });

  it("menerima titik koma, BOM, dan koma di dalam tanda kutip", () => {
    const csv = '﻿platform;account;external_id;posted_at;caption\nx;akun;t1;2026-10-03;"Halo; ""warga"", apa kabar"\n';
    const p = parseOfficialPosts(csv)[0]!;
    expect(p.caption).toBe('Halo; "warga", apa kabar');
  });

  it("menyebut nomor baris berkas saat ada yang salah", () => {
    const csv = "platform,account,external_id,posted_at,likes\nx,akun,t1,2026-10-03,1.5\n";
    expect(() => parseOfficialPosts(csv)).toThrow(/Baris ke-2.*likes/);
  });

  it("menolak CSV tanpa kolom wajib atau tanpa baris", () => {
    expect(() => parseOfficialPosts("platform,account\nx,a\n")).toThrow(/external_id/);
    expect(() => parseOfficialPosts("platform,account,external_id,posted_at\n")).toThrow(/baris data/);
  });

  it("parseCsv menjaga baris baru di dalam kutip", () => {
    expect(parseCsv('a,b\n"1\n2",3\n')).toEqual([["a", "b"], ["1\n2", "3"]]);
  });
});

describe("pembantu tampilan kinerja", () => {
  it("median kosong ditulis apa adanya, bukan nol", () => {
    expect(formatMedian(null)).toBe("tidak tersedia");
    expect(formatMedian(102.5)).toBe("102,5");
    expect(formatMedian(1500)).toBe("1.500");
  });

  it("cakupan dan label dimensi", () => {
    expect(coverageText({ n_available: 5, n_total: 9, coverage: 0.556 })).toBe("5 dari 9 indikator (56%)");
    expect(dimensionLabel("OUTCOME")).toBe("Outcome");
  });
});
