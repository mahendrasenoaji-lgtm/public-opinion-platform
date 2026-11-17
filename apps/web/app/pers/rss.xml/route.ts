import { listArticles, originOf } from "@/lib/pers";
import { rssXml } from "@/lib/persExport";

export const dynamic = "force-dynamic";

/** Feed RSS artikel terbit. Publik, baca-saja. */
export async function GET(req: Request) {
  const res = await listArticles(undefined, 1, 50);
  if (res.state !== "ok") {
    return new Response("Feed belum bisa dimuat.", { status: 503 });
  }
  return new Response(rssXml(res.data.items, originOf(req.headers)), {
    headers: {
      "content-type": "application/rss+xml; charset=utf-8",
      "cache-control": "public, max-age=300",
    },
  });
}
