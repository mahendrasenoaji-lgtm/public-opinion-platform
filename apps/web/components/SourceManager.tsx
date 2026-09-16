"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SOURCE, type SignalSource } from "@/lib/tokens";
import {
  addSource,
  removeSource,
  runCollectAll,
  issueToken,
  revokeToken,
  type CollectAllOut,
  type CollectorTokenStatus,
} from "@/app/(dashboard)/sinyal/actions";

interface ConnectorInfo {
  key: string;
  label: string;
  source: SignalSource;
  requires_credential: string | null;
  credential_configured: boolean;
  config_fields: string[];
  optional_fields: string[];
  notes: string;
}

interface SourceRow {
  id: string;
  connector: string;
  source: SignalSource;
  config: Record<string, string>;
  is_active: boolean;
  last_sync_at: string | null;
}

/** Label yang dibaca manusia untuk field konfigurasi konektor -- sama gaya
 * dengan FIELD_LABELS di app/(dashboard)/deret/CollectForm.tsx. */
const FIELD_LABELS: Record<string, string> = {
  feed_url: "URL feed RSS",
  keywords: "Kata kunci (opsional, dipisah koma)",
  label: "Label (opsional)",
  video_id: "ID video YouTube",
  query: "Kueri pencarian X",
};

const FIELD_PLACEHOLDERS: Record<string, string> = {
  feed_url: "https://www.antaranews.com/rss/terkini.xml",
  keywords: "makan bergizi gratis, mbg, badan gizi nasional",
  label: "Antara nasional",
  video_id: "dQw4w9WgXcQ",
  query: "#pemilu2029 lang:id",
};

function fmtDate(iso: string | null): string {
  return iso ? iso.slice(0, 16).replace("T", " ") : "belum pernah";
}

/**
 * Kelola sumber data + token pengumpul terjadwal langsung dari /sinyal (K6,
 * 2026-09-16). Sebelum ini semua jalur di bawah cuma bisa lewat curl -- lihat
 * app/(dashboard)/sinyal/actions.ts untuk kenapa endpoint-endpointnya sendiri
 * sudah ada sejak PR #15.
 *
 * `canManage`/`canManageTokens` cuma UX (sembunyikan kontrol yang toh akan
 * ditolak server) -- cermin RANK[RESEARCHER]/RANK[RESEARCH_DIRECTOR] di
 * app/routers/signals.py. Batas keamanan sungguhan tetap di backend, sama
 * seperti CAN_APPROVE_ROLES di app/(dashboard)/brief/page.tsx.
 */
export function SourceManager({
  projectId,
  sources,
  connectors,
  canManage,
  canManageTokens,
  tokenStatus,
}: {
  projectId: string;
  sources: SourceRow[];
  connectors: ConnectorInfo[];
  canManage: boolean;
  canManageTokens: boolean;
  tokenStatus: CollectorTokenStatus | null;
}) {
  return (
    <>
      <SourceTable sources={sources} canManage={canManage} projectId={projectId} />
      {canManage && connectors.length > 0 && (
        <AddSourceForm projectId={projectId} connectors={connectors} />
      )}
      {canManage && sources.length > 0 && <CollectAllButton projectId={projectId} />}
      {canManageTokens && <TokenPanel projectId={projectId} status={tokenStatus} />}
    </>
  );
}

function SourceTable({
  sources,
  canManage,
  projectId,
}: {
  sources: SourceRow[];
  canManage: boolean;
  projectId: string;
}) {
  const router = useRouter();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function onDelete(id: string) {
    setBusyId(id);
    setError("");
    const res = await removeSource(projectId, id);
    setBusyId(null);
    if (res.ok) router.refresh();
    else setError(res.error);
  }

  if (sources.length === 0) return null;

  return (
    <div style={{ marginTop: 18 }}>
      <table className="tbl">
        <thead>
          <tr>
            <th>Konektor</th>
            <th>Sumber</th>
            <th>Konfigurasi</th>
            <th>Sinkron terakhir</th>
            {canManage && <th />}
          </tr>
        </thead>
        <tbody>
          {sources.map((s) => (
            <tr key={s.id}>
              <td>{s.connector}</td>
              <td>
                <span className="pill" style={{ color: SOURCE[s.source].color }}>
                  {SOURCE[s.source].label}
                </span>
              </td>
              <td className="mono">
                {Object.entries(s.config)
                  .map(([k, v]) => `${k}=${v}`)
                  .join(" ") || "—"}
              </td>
              <td className="mono">{fmtDate(s.last_sync_at)}</td>
              {canManage && (
                <td style={{ textAlign: "right" }}>
                  <button
                    type="button"
                    className="btn btn-danger btn-sm"
                    disabled={busyId === s.id}
                    onClick={() => onDelete(s.id)}
                  >
                    {busyId === s.id ? "Menghapus…" : "Hapus"}
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {error && <div className="form-err" role="alert" style={{ marginTop: 10 }}>{error}</div>}
    </div>
  );
}

function AddSourceForm({
  projectId,
  connectors,
}: {
  projectId: string;
  connectors: ConnectorInfo[];
}) {
  const router = useRouter();
  const [key, setKey] = useState(connectors[0]?.key ?? "");
  const [config, setConfig] = useState<Record<string, string>>({});
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);

  const active = connectors.find((c) => c.key === key);

  async function submit() {
    if (!active) return;
    setPending(true);
    setError("");
    setOk(false);
    const fields = [...active.config_fields, ...active.optional_fields];
    const picked = Object.fromEntries(
      fields
        .map((f) => [f, (config[f] ?? "").trim()])
        .filter(([, v]) => v !== ""),
    );
    const res = await addSource(projectId, active.key, picked);
    setPending(false);
    if (res.ok) {
      setOk(true);
      setConfig({});
      router.refresh();
    } else {
      setError(res.error);
    }
  }

  if (!active) return null;

  const missing = active.config_fields.filter((f) => !(config[f] ?? "").trim());
  const blockedByCredential = active.requires_credential !== null && !active.credential_configured;

  return (
    <div style={{ marginTop: 22 }}>
      <h3 className="kicker">Tambah sumber</h3>

      <div className="field" style={{ marginTop: 10 }}>
        <label htmlFor="src-conn">Konektor</label>
        <select
          id="src-conn"
          value={key}
          onChange={(e) => {
            setKey(e.target.value);
            setConfig({});
            setError("");
            setOk(false);
          }}
        >
          {connectors.map((c) => (
            <option key={c.key} value={c.key}>
              {c.label}
            </option>
          ))}
        </select>
      </div>

      <p className="note">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 16v-4M12 8h.01" />
        </svg>
        <span>{active.notes}</span>
      </p>

      {blockedByCredential && (
        <div className="form-err" role="alert">
          Konektor ini butuh {active.requires_credential} yang belum diset di deployment ini.
          Sumber tetap bisa didaftarkan, tapi pengambilan akan gagal 503 sampai kredensialnya ada.
        </div>
      )}

      {active.config_fields.map((f) => (
        <div className="field" key={f}>
          <label htmlFor={`src-${f}`}>{FIELD_LABELS[f] ?? f}</label>
          <input
            id={`src-${f}`}
            value={config[f] ?? ""}
            onChange={(e) => setConfig({ ...config, [f]: e.target.value })}
            placeholder={FIELD_PLACEHOLDERS[f] ?? ""}
          />
        </div>
      ))}
      {active.optional_fields.map((f) => (
        <div className="field" key={f}>
          <label htmlFor={`src-${f}`}>{FIELD_LABELS[f] ?? f}</label>
          <input
            id={`src-${f}`}
            value={config[f] ?? ""}
            onChange={(e) => setConfig({ ...config, [f]: e.target.value })}
            placeholder={FIELD_PLACEHOLDERS[f] ?? ""}
          />
        </div>
      ))}

      {error && <div className="form-err" role="alert">{error}</div>}
      {ok && (
        <div className="read" style={{ marginBottom: 14 }}>
          <div className="read-t">Sumber ditambahkan.</div>
        </div>
      )}

      <button
        type="button"
        className="btn"
        onClick={submit}
        disabled={pending || missing.length > 0}
      >
        {pending ? "Menambahkan…" : "Tambah sumber"}
      </button>
    </div>
  );
}

function CollectAllButton({ projectId }: { projectId: string }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<CollectAllOut | null>(null);

  async function submit() {
    setPending(true);
    setError("");
    setSummary(null);
    const res = await runCollectAll(projectId);
    setPending(false);
    if (res.ok) setSummary(res.result);
    else setError(res.error);
  }

  return (
    <div style={{ marginTop: 22 }}>
      <h3 className="kicker">Pengumpulan manual</h3>
      <p className="field-hint" style={{ marginBottom: 10 }}>
        Jalur yang sama dengan yang dipicu otomatis tiap 30 menit lewat GitHub Actions -- lihat
        docs/deployment-status.md. Berguna untuk menguji sumber yang baru ditambahkan tanpa
        menunggu jadwal berikutnya.
      </p>
      <button type="button" className="btn btn-ghost" onClick={submit} disabled={pending}>
        {pending ? "Menarik semua sumber…" : "Tarik semua sekarang"}
      </button>

      {error && <div className="form-err" role="alert" style={{ marginTop: 10 }}>{error}</div>}

      {summary && (
        <div style={{ marginTop: 14 }}>
          <div className="read">
            <div className="read-t">
              {summary.sources_ok}/{summary.sources_total} sumber berhasil, {summary.stored_total}{" "}
              item baru tersimpan
              {summary.sources_inactive > 0 && `, ${summary.sources_inactive} sumber nonaktif`}
              {summary.coverage_gaps > 0 &&
                ` — ${summary.coverage_gaps} sumber punya celah cakupan (jadwal terlalu jarang untuk feed itu)`}
              .
            </div>
          </div>
          <table className="tbl" style={{ marginTop: 10 }}>
            <thead>
              <tr>
                <th>Sumber</th>
                <th>Status</th>
                <th>Ditawarkan / cocok</th>
                <th>Tersimpan</th>
              </tr>
            </thead>
            <tbody>
              {summary.results.map((r) => (
                <tr key={r.source_id}>
                  <td>{r.label ?? r.connector}</td>
                  <td>
                    {r.ok ? (
                      <span className="pill pill-ok">ok{r.coverage_gap ? " · celah" : ""}</span>
                    ) : (
                      <span className="pill pill-warn" title={r.error ?? ""}>
                        gagal
                      </span>
                    )}
                  </td>
                  <td className="mono">
                    {r.offered ?? "—"} / {r.matched ?? "—"}
                  </td>
                  <td className="mono">{r.result?.stored ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function TokenPanel({
  projectId,
  status,
}: {
  projectId: string;
  status: CollectorTokenStatus | null;
}) {
  const router = useRouter();
  const [days, setDays] = useState(180);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [freshToken, setFreshToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirmingIssue, setConfirmingIssue] = useState(false);
  const [confirmingRevoke, setConfirmingRevoke] = useState(false);

  async function onIssue() {
    setPending(true);
    setError("");
    setFreshToken(null);
    setConfirmingIssue(false);
    const res = await issueToken(projectId, days);
    setPending(false);
    if (res.ok) {
      setFreshToken(res.result.token);
      router.refresh();
    } else {
      setError(res.error);
    }
  }

  async function onRevoke() {
    setPending(true);
    setError("");
    setConfirmingRevoke(false);
    const res = await revokeToken(projectId);
    setPending(false);
    if (res.ok) router.refresh();
    else setError(res.error);
  }

  return (
    <div style={{ marginTop: 22 }}>
      <h3 className="kicker">Token pengumpul terjadwal</h3>
      <p className="field-hint" style={{ marginBottom: 10 }}>
        Dipakai penjadwal eksternal (GitHub Actions) untuk memanggil{" "}
        <span className="mono">collect-all</span> tanpa membawa sesi pengguna. Hanya bisa satu
        hal: menarik sumber yang sudah terdaftar, untuk proyek ini saja.
      </p>

      {status?.active ? (
        <div className="read" style={{ marginBottom: 14 }}>
          <div className="read-t">Token aktif</div>
          <div className="read-d">
            Diterbitkan {fmtDate(status.issued_at)}, berlaku sampai {fmtDate(status.expires_at)}.
          </div>
        </div>
      ) : (
        <div className="read" style={{ marginBottom: 14 }}>
          <div className="read-t">Tidak ada token aktif</div>
          <div className="read-d">Penjadwal manapun yang memanggil collect-all akan menerima 401.</div>
        </div>
      )}

      {freshToken && (
        <div className="err" style={{ marginBottom: 14 }}>
          <div className="err-t">Simpan token ini sekarang — tidak akan ditampilkan lagi</div>
          <div className="err-d">
            Tempelkan sebagai baris baru di secret <span className="mono">POP_COLLECTOR_TOKENS</span>{" "}
            (GitHub → Settings → Secrets and variables → Actions), lalu tutup panel ini.
          </div>
          <div
            className="mono"
            style={{
              marginTop: 10,
              padding: "8px 10px",
              background: "var(--panel2)",
              borderRadius: 4,
              wordBreak: "break-all",
              fontSize: 11,
            }}
          >
            {freshToken}
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            style={{ marginTop: 8 }}
            onClick={async () => {
              await navigator.clipboard.writeText(freshToken);
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            }}
          >
            {copied ? "Tersalin ✓" : "Salin"}
          </button>
        </div>
      )}

      {error && <div className="form-err" role="alert" style={{ marginBottom: 10 }}>{error}</div>}

      {!confirmingIssue ? (
        <button
          type="button"
          className="btn"
          disabled={pending}
          onClick={() => setConfirmingIssue(true)}
        >
          Terbitkan token baru
        </button>
      ) : (
        <div className="read" style={{ marginBottom: 10 }}>
          <div className="read-t">
            {status?.active
              ? "Ini akan mematikan token yang sedang aktif sekarang juga."
              : "Terbitkan token baru?"}
          </div>
          <div className="field" style={{ marginTop: 10, maxWidth: 160 }}>
            <label htmlFor="tok-days">Masa berlaku (hari)</label>
            <input
              id="tok-days"
              type="number"
              min={1}
              max={365}
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
            />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" className="btn" disabled={pending} onClick={onIssue}>
              {pending ? "Menerbitkan…" : "Ya, terbitkan"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={pending}
              onClick={() => setConfirmingIssue(false)}
            >
              Batal
            </button>
          </div>
        </div>
      )}

      {status?.active && (
        <div style={{ marginTop: 10 }}>
          {!confirmingRevoke ? (
            <button
              type="button"
              className="btn btn-danger btn-sm"
              disabled={pending}
              onClick={() => setConfirmingRevoke(true)}
            >
              Cabut token
            </button>
          ) : (
            <div className="read">
              <div className="read-t">
                Penjadwal akan mulai menerima 401 pada panggilan berikutnya. Yakin?
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  className="btn btn-danger"
                  disabled={pending}
                  onClick={onRevoke}
                >
                  {pending ? "Mencabut…" : "Ya, cabut"}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  disabled={pending}
                  onClick={() => setConfirmingRevoke(false)}
                >
                  Batal
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
