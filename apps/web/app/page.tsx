import { redirect } from "next/navigation";

/** Root domain belum punya halaman sendiri — arahkan ke Command Center. */
export default function RootPage() {
  redirect("/command");
}
