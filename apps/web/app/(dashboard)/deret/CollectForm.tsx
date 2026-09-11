"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { collectSeries, type CollectResult } from "./actions";

export interface MetricConnector {
  key: string;
  label: string;
  source: string;
  requires_credential: string | null;
  config_fields: string[];
  notes: string;
}

/** Label yang dibaca manusia untuk field konfigurasi konektor. */
const FIELD_LABELS: Record<string, string> = {
  project: "Proyek Wikipedia",
  article: "Judul artikel",
  province_code: "Kode provinsi (BPS)",
};

const FIELD_HINTS: Record<string, string> = {
  project: "id.wikipedia untuk pembaca Indonesia.",
  article: "Persis seperti di URL Wikipedia, termasuk huruf besar-kecilnya.",
  province_code: "Mis. 62 untuk Kalimantan Tengah, 14 untuk Riau.",
};

const PLACEHOLDERS: Record<string, string> = {
  project: "id.wikipedia",
  article: "Badan Gizi Nasional",
  province_code: "62",
};

export function CollectForm({
  projectId,
  connectors,
}: {
  projectId: string;
  connectors: MetricConnector[];
}) {
  const router = useRouter();
  const [key, setKey] = useState(connectors[0]?.key ?? "");
  const [config, setConfig] = useState<Record<string, string>>({});
  const [days, setDays] = useState(90);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<CollectResult | null>(null);

  const active = connectors.find((c) => c.key === key);
  if (!active) return null;

  const missing = active.config_fields.filter((f) => !(config[f] ?? "").trim());

  async function submit() {
    if (!active) return;
    setPending(true);
    setError("");
    setResult(null);
    const picked = Object.fromEntries(
      active.config_fields.map((f) => [f, (config[f] ?? "").trim()]),
    );
    const res = await collectSeries(projectId, active.key, picked, days);
    setPending(false);
    if (res.ok) {
      setResult(res.result);
      // Muat ulang server component supaya daftar deret di bawah ikut
      // memperlihatkan hasil tarikan ini, bukan keadaan sebelum klik.
      router.refresh();
    } else {
      setError(res.error);
    }
  }

  return (
    <div>
      <div className="field">
        <label htmlFor="conn">Sumber</label>
        <select
          id="conn"
          value={key}
          onChange={(e) => {
            setKey(e.target.value);
            setConfig({});
            setResult(null);
            setError("");
          }}
        >
          {connectors.map((c) => (
            <option key={c.key} value={c.key}>
              {c.label}
            </option>
          ))}
        </select>
      </div>

      <div className="note" style={{ marginBottom: 14 }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 16v-4M12 8h.01" />
        </svg>
        <span>{active.notes}</span>
      </div>

      {active.config_fields.map((f) => (
        <div className="field" key={f}>
          <label htmlFor={`cfg-${f}`}>{FIELD_LABELS[f] ?? f}</label>
          <input
            id={`cfg-${f}`}
            value={config[f] ?? ""}
            onChange={(e) => setConfig({ ...config, [f]: e.target.value })}
            placeholder={PLACEHOLDERS[f] ?? ""}
          />
          {FIELD_HINTS[f] && <span className="field-hint">{FIELD_HINTS[f]}</span>}
        </div>
      ))}

      <div className="field">
        <label htmlFor="days">Rentang ke belakang</label>
        <select id="days" value={days} onChange={(e) => setDays(Number(e.target.value))}>
          <option value={30}>30 hari</option>
          <option value={90}>90 hari</option>
          <option value={180}>180 hari</option>
          <option value={365}>365 hari</option>
        </select>
        <span className="field-hint">
          Makin panjang, makin banyak pengamatan untuk mem-fit model forecast.
        </span>
      </div>

      {error && <div className="form-err" role="alert">{error}</div>}

      <button
        className="btn"
        onClick={submit}
        disabled={pending || missing.length > 0}
        type="button"
      >
        {pending ? "Menarik…" : "Tarik deret"}
      </button>

      {result && (
        <div className="read" style={{ marginTop: 14 }}>
          <div className="read-t">
            {result.stored} pengamatan baru, {result.replaced} diperbarui
          </div>
          <div className="read-d">
            Deret <span className="mono">{result.metric}</span> sekarang mencakup{" "}
            {result.period_start} sampai {result.period_end}
            {result.provinces.length > 0
              ? ` untuk provinsi ${result.provinces.join(", ")}`
              : " sebagai deret nasional"}
            .
          </div>
          <div className="prov">
            <span><b>SUMBER</b> {result.source}</span>
            <span><b>METODE</b> {result.method}</span>
          </div>
        </div>
      )}
    </div>
  );
}
