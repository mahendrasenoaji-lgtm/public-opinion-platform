import { dateLabel, getArticle } from "@/lib/pers";
import { OG_SIZE, persOgImage } from "@/lib/persOg";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Artikel riset opini publik";
export const dynamic = "force-dynamic";

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const res = await getArticle((await params).slug);
  if (res.state !== "ok") return persOgImage("Publikasi hasil riset", "");
  const a = res.data;
  return persOgImage(a.title, `${a.author_name} · ${dateLabel(a.published_at)}`);
}
