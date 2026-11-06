import type { IngestItemIn, SignalSourceKey } from "@/app/(dashboard)/sinyal/actions";

export interface Parsed {
  connector: string;
  source: SignalSourceKey;
  items: IngestItemIn[];
}

/**
 * Terima JSON: larik item, atau `{ connector?, source?, items: [...] }`.
 * Tiap item wajib `external_id`, `text`, `published_at`. Fungsi murni.
 */
export function parseUpload(raw: string): Parsed {
  const data: unknown = JSON.parse(raw);
  const obj = (Array.isArray(data) ? { items: data } : data) as Record<string, unknown>;
  const items = obj.items;
  if (!Array.isArray(items) || items.length === 0) {
    throw new Error("Berkas harus berisi larik `items` yang tidak kosong.");
  }
  const source = (obj.source ?? "SOCIAL") as SignalSourceKey;
  if (source !== "SOCIAL" && source !== "MEDIA") {
    throw new Error("`source` hanya boleh SOCIAL atau MEDIA.");
  }
  items.forEach((it, i) => {
    const r = it as Record<string, unknown>;
    if (!r.external_id || !r.text || !r.published_at) {
      throw new Error(`Item ke-${i + 1} tidak punya external_id, text, atau published_at.`);
    }
  });
  return {
    connector: String(obj.connector ?? "manual"),
    source,
    items: items as IngestItemIn[],
  };
}

