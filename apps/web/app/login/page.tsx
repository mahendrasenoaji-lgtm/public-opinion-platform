import { Suspense } from "react";
import { redirect } from "next/navigation";
import { siteGateEnabled } from "@/lib/auth";
import { LoginForm } from "./LoginForm";

// Dibaca per permintaan: SITE_GATE adalah env runtime, bukan nilai build.
export const dynamic = "force-dynamic";

export default function LoginPage() {
  // Gerbang dilepas (lib/auth.ts): halaman ini tidak punya apa pun untuk
  // dijaga, jadi tautan lama ke /login diteruskan ke login pengguna.
  if (!siteGateEnabled()) redirect("/masuk");
  return (
    <div className="auth-wrap">
      <Suspense fallback={null}><LoginForm /></Suspense>
    </div>
  );
}
