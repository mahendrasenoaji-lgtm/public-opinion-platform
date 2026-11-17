import { articleDocx } from "@/lib/docx";
import { getArticle, originOf } from "@/lib/pers";

export const dynamic = "force-dynamic";

/** Artikel terbit sebagai berkas Word, dengan angka, metode, batas, dan sitasi. */
export async function GET(req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const res = await getArticle(slug);
  if (res.state === "missing") return new Response("Artikel tidak ditemukan.", { status: 404 });
  if (res.state !== "ok") return new Response("Artikel belum bisa dimuat.", { status: 503 });
  const a = res.data;
  const bytes = articleDocx(a, `${originOf(req.headers)}/pers/${a.slug}`);
  return new Response(new Blob([bytes as BlobPart]), {
    headers: {
      "content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "content-disposition": `attachment; filename="${a.slug}-v${a.version}.docx"`,
    },
  });
}
