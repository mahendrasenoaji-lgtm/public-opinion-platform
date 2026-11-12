/** Tipe dan pembantu tampilan publikasi hasil riset. Fungsi murni. */

export type PubStatus = "draft" | "review" | "published";

export interface PublicationRef {
  id: string;
  slug: string;
  title: string;
  summary: string;
  tags: string[];
  author_name: string;
  status: PubStatus;
  version: number;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SnapshotSource {
  source: string;
  n: number;
  scored: number;
  labels: Record<string, number>;
}

export interface Snapshot {
  snapshot_version: number;
  frozen_at: string;
  project_name: string;
  period_start: string | null;
  period_end: string | null;
  timezone: string;
  note: string;
  report: { sources: SnapshotSource[]; limitations?: string[]; methods?: Record<string, string> };
}

export interface Publication extends PublicationRef {
  body: string;
  snapshot: Snapshot;
  corrections: { version: number; at: string; note: string }[];
}

export const STATUS_LABEL: Record<PubStatus, string> = {
  draft: "Draf",
  review: "Menunggu tinjauan",
  published: "Terbit",
};

export const PUBLISHER_ROLES = new Set(["SUPER_ADMIN", "RESEARCH_DIRECTOR"]);
export const EDITOR_ROLES = new Set(["SUPER_ADMIN", "RESEARCH_DIRECTOR", "RESEARCHER"]);

/** "kebijakan, Energi BBM" -> ["kebijakan", "Energi BBM"]; backend yang menormalkan. */
export function parseTags(raw: string): string[] {
  return raw
    .split(",")
    .map((t) => t.trim())
    .filter((t) => t !== "");
}

/** Langkah status berikutnya yang boleh ditawarkan kepada peran ini. */
export function nextSteps(status: PubStatus, canPublish: boolean): PubStatus[] {
  if (status === "draft") return ["review"];
  if (status === "review") return canPublish ? ["published", "draft"] : ["draft"];
  return [];
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Jakarta",
  });
}
