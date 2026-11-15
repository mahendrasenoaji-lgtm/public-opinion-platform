import { OG_SIZE, persOgImage } from "@/lib/persOg";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Riset opini publik";

export default function Image() {
  return persOgImage("Publikasi hasil riset", "Angka dibekukan, lengkap dengan sumber, metode, dan batasnya");
}
