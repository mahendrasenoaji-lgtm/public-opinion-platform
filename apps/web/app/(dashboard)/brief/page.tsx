import { cookies } from "next/headers";
import { PageHeader } from "@/components/PageHeader";
import { BriefGenerator } from "@/components/BriefGenerator";
import { apiOrNullLenient } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";
import { SESSION_COOKIE, decodeJwtPayload } from "@/lib/session";
import type { BriefOut } from "./actions";

export const dynamic = "force-dynamic";

//: Peran yang boleh menyetujui keluaran AI — cermin persis
//: app/deps.py:CAPABILITIES["ai_output:approve"] di backend. Ini cuma UX
//: (sembunyikan tombol yang toh akan ditolak server); batas keamanan
//: sungguhan tetap require_capability() di backend.
const CAN_APPROVE_ROLES = new Set(["SUPER_ADMIN", "RESEARCH_DIRECTOR", "RESEARCHER"]);

export default async function BriefPage() {
  const { id: projectId, name: projectName, is_demo: isDemo } = await getCurrentProject();

  // apiOrNullLenient, bukan api+try/catch-404-saja: error backend APA PUN
  // (bukan cuma "belum ada brief" 404) tidak boleh menjatuhkan seluruh
  // halaman -- lihat catatan yang sama di /command untuk /topics & /alerts.
  const brief = await apiOrNullLenient<BriefOut>(`/projects/${projectId}/brief/latest`);

  const sessionToken = (await cookies()).get(SESSION_COOKIE)?.value;
  const role = sessionToken ? decodeJwtPayload(sessionToken)?.role : undefined;
  const canApprove = typeof role === "string" && CAN_APPROVE_ROLES.has(role);

  return (
    <>
      <PageHeader kicker="Executive Brief" title={projectName} isDemo={isDemo} />
      <div className="body">
        <BriefGenerator projectId={projectId} initial={brief} canApprove={canApprove} />
      </div>
    </>
  );
}
