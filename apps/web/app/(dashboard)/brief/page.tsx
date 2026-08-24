import { cookies } from "next/headers";
import { PageHeader } from "@/components/PageHeader";
import { BriefGenerator } from "@/components/BriefGenerator";
import { api, ApiError } from "@/lib/api";
import { SESSION_COOKIE, decodeJwtPayload } from "@/lib/session";
import type { BriefOut } from "./actions";

export const dynamic = "force-dynamic";

//: Peran yang boleh menyetujui keluaran AI — cermin persis
//: app/deps.py:CAPABILITIES["ai_output:approve"] di backend. Ini cuma UX
//: (sembunyikan tombol yang toh akan ditolak server); batas keamanan
//: sungguhan tetap require_capability() di backend.
const CAN_APPROVE_ROLES = new Set(["SUPER_ADMIN", "RESEARCH_DIRECTOR", "RESEARCHER"]);

export default async function BriefPage() {
  const projectId = process.env.DEMO_PROJECT_ID!;

  let brief: BriefOut | null = null;
  try {
    brief = await api<BriefOut>(`/projects/${projectId}/brief/latest`);
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 404) throw e;
  }

  const sessionToken = (await cookies()).get(SESSION_COOKIE)?.value;
  const role = sessionToken ? decodeJwtPayload(sessionToken)?.role : undefined;
  const canApprove = typeof role === "string" && CAN_APPROVE_ROLES.has(role);

  return (
    <>
      <PageHeader kicker="Executive Brief" title="Persepsi Kebijakan Nasional 2026" />
      <div className="body">
        <BriefGenerator projectId={projectId} initial={brief} canApprove={canApprove} />
      </div>
    </>
  );
}
