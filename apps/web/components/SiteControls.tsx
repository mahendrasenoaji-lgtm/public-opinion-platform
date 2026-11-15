"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { addSite, deleteSite, refreshSite, uploadSiteItems } from "@/app/(dashboard)/kinerja/analisis/actions";
import { SITE_CSV_TEMPLATE, siteItemsFromRows } from "@/app/(dashboard)/kinerja/analisis/analisis";
import { parseCsv } from "@/lib/officialPosts";

const CHUNK = 300;

/** Daftarkan situs web resmi sebuah lembaga; pembacaan pertama langsung dijalankan. */
export function SiteAddForm({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [subject, setSubject] = useState("");
  const [url, setUrl] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [notes, setNotes] = useState<string[] | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setNotes(null);
    setPending(true);
    const res = await addSite(projectId, subject.trim(), url.trim());
    setPending(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setNotes([`${res.result.result.stored} butir tersimpan.`, ...res.result.notes]);
    setSubject("");
    setUrl("");
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit}>
      <div className="period-bar" style={{ alignItems: "flex-end" }}>
        <label className="field" style={{ flex: "1 1 200px" }}>
          <span className="kicker">Lembaga</span>
          <input value={subject} onChange={(e) => setSubject(e.target.value)} required maxLength={120} disabled={pending} />
        </label>
        <label className="field" style={{ flex: "1 1 240px" }}>
          <span className="kicker">Alamat situs resmi</span>
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="lembaga.go.id" required maxLength={300} disabled={pending} />
        </label>
        <button className="btn btn-sm" type="submit" disabled={pending || !subject.trim() || !url.trim()}>
          {pending ? "Membaca situs…" : "Daftarkan dan baca"}
        </button>
      </div>
      <p className="field-hint">
        Yang dibaca hanya robots.txt, feed RSS/Atom, dan sitemap situs itu: judul, alamat, dan tanggal.
        Halaman berita dan isi artikel tidak diambil. Pastikan alamatnya memang situs resmi lembaga.
      </p>
      {error && <div className="form-err" role="alert" style={{ marginTop: 8 }}>{error}</div>}
      {notes && (
        <ul className="read-d" role="status" style={{ marginTop: 8, paddingLeft: 18 }}>
          {notes.map((n) => <li key={n}>{n}</li>)}
        </ul>
      )}
    </form>
  );
}

/** Baca ulang, unggah CSV butir, dan hapus untuk satu situs. */
export function SiteActions({ projectId, siteId, baseUrl }: { projectId: string; siteId: string; baseUrl: string }) {
  const router = useRouter();
  const [pending, setPending] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [armed, setArmed] = useState(false);

  async function onRefresh() {
    setError("");
    setMessage("");
    setPending("Membaca situs…");
    const res = await refreshSite(projectId, siteId);
    setPending("");
    if (!res.ok) return setError(res.error);
    setMessage(`${res.result.result.stored} butir baru, ${res.result.result.updated} diperbarui.`);
    router.refresh();
  }

  async function onFile(file: File) {
    setError("");
    setMessage("");
    let items;
    try {
      items = siteItemsFromRows(parseCsv(await file.text()));
    } catch (e) {
      return setError(e instanceof Error ? e.message : "Berkas tidak bisa dibaca.");
    }
    let stored = 0;
    let updated = 0;
    for (let start = 0; start < items.length; start += CHUNK) {
      setPending(`Mengunggah ${Math.min(start + CHUNK, items.length)} / ${items.length}…`);
      const res = await uploadSiteItems(projectId, siteId, items.slice(start, start + CHUNK));
      if (!res.ok) {
        setPending("");
        setError(`Berhenti di baris ${start + 2}: ${res.error}`);
        router.refresh();
        return;
      }
      stored += res.result.stored;
      updated += res.result.updated;
    }
    setPending("");
    setMessage(`${stored} butir baru, ${updated} diperbarui.`);
    router.refresh();
  }

  async function onDelete() {
    setPending("Menghapus…");
    const res = await deleteSite(projectId, siteId);
    setPending("");
    if (!res.ok) return setError(res.error);
    router.refresh();
  }

  const busy = pending !== "";
  return (
    <div className="site-actions">
      <button type="button" className="btn btn-ghost btn-sm" onClick={onRefresh} disabled={busy}>
        Baca ulang
      </button>
      <label className={"btn btn-ghost btn-sm" + (busy ? " is-disabled" : "")}>
        Unggah CSV butir
        <input
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) void onFile(file);
          }}
        />
      </label>
      <a
        className="btn btn-ghost btn-sm"
        href={`data:text/csv;charset=utf-8,${encodeURIComponent(SITE_CSV_TEMPLATE.replaceAll("https://lembaga.go.id", baseUrl))}`}
        download="templat-butir-situs.csv"
      >
        Templat CSV
      </a>
      {armed ? (
        <>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onDelete} disabled={busy}>Ya, hapus situs dan butirnya</button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setArmed(false)} disabled={busy}>Batal</button>
        </>
      ) : (
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setArmed(true)} disabled={busy}>Hapus</button>
      )}
      {pending && <span className="proj-s" role="status">{pending}</span>}
      {message && <span className="proj-s" role="status">{message}</span>}
      {error && <span className="form-err" role="alert">{error}</span>}
    </div>
  );
}
