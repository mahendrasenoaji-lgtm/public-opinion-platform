import { getArticle, originOf } from "@/lib/pers";
import { aggregateCsv } from "@/lib/persExport";

export const dynamic = "force-dynamic";

/** Data agregat artikel (snapshot beku) sebagai CSV. Tanpa teks konten warga. */
export async function GET(req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const res = await getArticle(slug);
  if (res.state === "missing") return new Response("Artikel tidak ditemukan.", { status: 404 });
  if (res.state !== "ok") return new Response("Data belum bisa dimuat.", { status: 503 });
  const a = res.data;
  return new Response(aggregateCsv(a, `${originOf(req.headers)}/pers/${a.slug}`), {
    headers: {
      "content-type": "text/csv; charset=utf-8",
      "content-disposition": `attachment; filename="${a.slug}-v${a.version}.csv"`,
    },
  });
}
