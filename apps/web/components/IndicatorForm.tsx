"use client";

import { useMemo, useState, useTransition } from "react";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { saveScores, type ScoreInput } from "@/app/(dashboard)/kinerja/actions";
import {
  AVAILABILITY_LABEL,
  PERIOD_RE,
  dimensionLabel,
  type Indicator,
  type ScoreItem,
} from "@/app/(dashboard)/kinerja/kinerja";

/** "" = belum diisi, "na" = tidak tersedia, "1".."5" = skor. */
type Choice = "" | "na" | "1" | "2" | "3" | "4" | "5";

interface Row {
  choice: Choice;
  evidence: string;
  reason: string;
}

function toRow(item: ScoreItem | undefined): Row {
  if (!item) return { choice: "", evidence: "", reason: "" };
  if (item.score !== null) return { choice: String(item.score) as Choice, evidence: item.evidence, reason: "" };
  if (item.unavailable_reason) return { choice: "na", evidence: item.evidence, reason: item.unavailable_reason };
  return { choice: "", evidence: "", reason: "" };
}

const EMPTY: Row = { choice: "", evidence: "", reason: "" };

const same = (a: Row, b: Row) => a.choice === b.choice && a.evidence === b.evidence && a.reason === b.reason;

/**
 * Formulir isian indikator. Tiga keadaan per indikator dibedakan dengan
 * sengaja: belum diisi, tidak tersedia (dengan alasan), dan skor 1-5 (dengan
 * bukti). Skor tanpa bukti ditolak, di sini maupun di backend.
 */
export function IndicatorForm({
  projectId,
  indicators,
  dimensions,
  initialSubject,
  initialPeriod,
  initialItems,
  canEdit,
}: {
  projectId: string;
  indicators: Indicator[];
  dimensions: string[];
  initialSubject: string;
  initialPeriod: string;
  initialItems: ScoreItem[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const saved = useMemo(() => {
    const byCode = new Map(initialItems.map((i) => [i.indicator, i]));
    return Object.fromEntries(indicators.map((i) => [i.code, toRow(byCode.get(i.code))]));
  }, [indicators, initialItems]);

  const [subject, setSubject] = useState(initialSubject);
  const [period, setPeriod] = useState(initialPeriod);
  const [rows, setRows] = useState<Record<string, Row>>(saved);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const [pending, startTransition] = useTransition();

  const targetChanged = subject.trim() !== initialSubject || period !== initialPeriod;

  function update(code: string, patch: Partial<Row>) {
    setDone("");
    setRows((r) => ({ ...r, [code]: { ...(r[code] ?? EMPTY), ...patch } }));
  }

  function submit() {
    setError("");
    setDone("");
    if (!subject.trim()) return setError("Isi nama lembaga yang dinilai.");
    if (!PERIOD_RE.test(period)) return setError("Periode harus berbentuk TTTT-BB, misalnya 2026-10.");

    const items: ScoreInput[] = [];
    for (const ind of indicators) {
      const row = rows[ind.code] ?? EMPTY;
      // Lembaga atau periode lain = lembar baru: kirim semua yang terisi.
      if (row.choice === "" || (!targetChanged && same(row, saved[ind.code] ?? EMPTY))) continue;
      if (row.choice === "na") {
        if (!row.reason.trim()) return setError(`${ind.code}: tulis alasan mengapa datanya tidak tersedia.`);
        items.push({ indicator: ind.code, score: null, unavailable_reason: row.reason.trim(), evidence: row.evidence.trim() });
      } else {
        if (!row.evidence.trim()) return setError(`${ind.code}: skor harus disertai bukti.`);
        items.push({ indicator: ind.code, score: Number(row.choice), unavailable_reason: null, evidence: row.evidence.trim() });
      }
    }
    if (items.length === 0) return setError("Belum ada isian yang berubah.");

    startTransition(async () => {
      const res = await saveScores(projectId, subject.trim(), period, items);
      if (!res.ok) {
        setError(res.error);
        return;
      }
      setDone(`${items.length} indikator tersimpan.`);
      const q = new URLSearchParams({ lembaga: subject.trim(), periode: period });
      router.push(`/kinerja?${q.toString()}#kartu` as Route);
      router.refresh();
    });
  }

  return (
    <div>
      <div className="period-bar" style={{ marginBottom: 16 }}>
        <div className="field">
          <label htmlFor="kin-subject">Lembaga yang dinilai</label>
          <input
            id="kin-subject"
            value={subject}
            maxLength={120}
            disabled={!canEdit || pending}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="mis. Kemenko Polkam"
          />
        </div>
        <div className="field">
          <label htmlFor="kin-period">Periode (bulan)</label>
          <input
            id="kin-period"
            type="month"
            value={period}
            disabled={!canEdit || pending}
            onChange={(e) => setPeriod(e.target.value)}
          />
        </div>
      </div>

      {dimensions.map((dim) => (
        <div key={dim} style={{ marginBottom: 22 }}>
          <h3 className="kicker" style={{ marginBottom: 8 }}>{dimensionLabel(dim)}</h3>
          <div style={{ overflowX: "auto" }}>
            <table className="tbl kin-form">
              <thead>
                <tr>
                  <th scope="col">Indikator</th>
                  <th scope="col">Skor</th>
                  <th scope="col">Bukti atau alasan</th>
                </tr>
              </thead>
              <tbody>
                {indicators
                  .filter((i) => i.dimension === dim)
                  .map((ind) => {
                    const row = rows[ind.code] ?? EMPTY;
                    return (
                      <tr key={ind.code}>
                        <td style={{ minWidth: 220 }}>
                          <div className="strong">
                            <span className="mono">{ind.code}</span> {ind.name}
                          </div>
                          <div className="field-hint">{ind.definition}</div>
                          <div className="field-hint">
                            Rubrik: {ind.rubric}. Sumber: {AVAILABILITY_LABEL[ind.availability]}.
                          </div>
                        </td>
                        <td style={{ minWidth: 150 }}>
                          <select
                            aria-label={`Skor ${ind.code} ${ind.name}`}
                            value={row.choice}
                            disabled={!canEdit || pending}
                            onChange={(e) => update(ind.code, { choice: e.target.value as Choice })}
                          >
                            <option value="">belum diisi</option>
                            <option value="na">tidak tersedia</option>
                            {["1", "2", "3", "4", "5"].map((s) => (
                              <option key={s} value={s}>{s}</option>
                            ))}
                          </select>
                        </td>
                        <td style={{ minWidth: 240 }}>
                          {row.choice === "na" ? (
                            <input
                              aria-label={`Alasan ${ind.code} tidak tersedia`}
                              value={row.reason}
                              maxLength={500}
                              disabled={!canEdit || pending}
                              onChange={(e) => update(ind.code, { reason: e.target.value })}
                              placeholder="mis. tidak ada akses insight akun"
                            />
                          ) : (
                            <textarea
                              aria-label={`Bukti ${ind.code}`}
                              rows={2}
                              value={row.evidence}
                              maxLength={4000}
                              disabled={!canEdit || pending || row.choice === ""}
                              onChange={(e) => update(ind.code, { evidence: e.target.value })}
                              placeholder={row.choice === "" ? "" : "dokumen, nomor, tanggal, atau angka yang mendasari skor"}
                            />
                          )}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {error && (
        <div className="form-err" role="alert" style={{ marginBottom: 10 }}>
          {error}
        </div>
      )}
      {done && (
        <div className="field-hint" role="status" style={{ marginBottom: 10 }}>
          {done}
        </div>
      )}
      {canEdit ? (
        <button type="button" className="btn" disabled={pending} onClick={submit}>
          {pending ? "Menyimpan…" : "Simpan isian"}
        </button>
      ) : (
        <p className="field-hint">Peran Anda hanya bisa membaca. Pengisian memerlukan peran Researcher atau lebih tinggi.</p>
      )}
    </div>
  );
}
