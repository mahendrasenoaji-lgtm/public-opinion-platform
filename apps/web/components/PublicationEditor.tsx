"use client";

import { useState, useTransition } from "react";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import {
  deleteDraft,
  editPublication,
  setPublicationStatus,
} from "@/app/(dashboard)/publikasi/actions";
import {
  STATUS_LABEL,
  nextSteps,
  parseTags,
  type PubStatus,
  type Publication,
} from "@/app/(dashboard)/publikasi/publikasi";

const STEP_LABEL: Record<PubStatus, string> = {
  review: "Ajukan untuk ditinjau",
  draft: "Kembalikan ke draf",
  published: "Terbitkan",
};

/**
 * Penyunting satu artikel. Isi ditulis manusia (Markdown sederhana); angka
 * berasal dari snapshot dan tidak bisa diubah di sini. Mengubah artikel yang
 * sudah terbit adalah ralat: wajib catatan, dan versinya naik.
 */
export function PublicationEditor({
  projectId,
  publication,
  canEdit,
  canPublish,
}: {
  projectId: string;
  publication: Publication;
  canEdit: boolean;
  canPublish: boolean;
}) {
  const router = useRouter();
  const [pub, setPub] = useState(publication);
  const [title, setTitle] = useState(publication.title);
  const [summary, setSummary] = useState(publication.summary);
  const [tags, setTags] = useState(publication.tags.join(", "));
  const [body, setBody] = useState(publication.body);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const [pending, startTransition] = useTransition();

  const published = pub.status === "published";
  const editable = canEdit && (!published || canPublish);
  const dirty =
    title !== pub.title || summary !== pub.summary || body !== pub.body || tags !== pub.tags.join(", ");

  function save(then?: () => void) {
    setError("");
    setDone("");
    if (published && !note.trim()) return setError("Artikel sudah terbit. Isi catatan ralat untuk mengubahnya.");
    startTransition(async () => {
      const res = await editPublication(projectId, pub.id, {
        title,
        summary,
        body,
        tags: parseTags(tags),
        ...(published ? { correction_note: note.trim() } : {}),
      });
      if (!res.ok) {
        setError(res.error);
        return;
      }
      setPub(res.result);
      setTags(res.result.tags.join(", "));
      setNote("");
      setDone(published ? `Ralat tersimpan sebagai versi ${res.result.version}.` : "Tersimpan.");
      then?.();
    });
  }

  function move(target: PubStatus) {
    setError("");
    setDone("");
    if (dirty) return setError("Simpan perubahan dulu sebelum mengubah status.");
    startTransition(async () => {
      const res = await setPublicationStatus(projectId, pub.id, target);
      if (!res.ok) {
        setError(res.error);
        return;
      }
      setPub(res.result);
      setDone(`Status: ${STATUS_LABEL[res.result.status]}.`);
      router.refresh();
    });
  }

  function remove() {
    setError("");
    startTransition(async () => {
      const res = await deleteDraft(projectId, pub.id);
      if (!res.ok) {
        setError(res.error);
        return;
      }
      router.push("/publikasi" as Route);
      router.refresh();
    });
  }

  return (
    <div>
      <div className="field">
        <label htmlFor="pub-title">Judul</label>
        <input id="pub-title" value={title} maxLength={200} disabled={!editable || pending} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="pub-summary">Ringkasan (tampil di daftar artikel)</label>
        <textarea id="pub-summary" rows={2} value={summary} maxLength={600} disabled={!editable || pending} onChange={(e) => setSummary(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="pub-tags">Tag (pisahkan dengan koma, maksimal 8)</label>
        <input id="pub-tags" value={tags} disabled={!editable || pending} onChange={(e) => setTags(e.target.value)} placeholder="kebijakan, energi" />
      </div>
      <div className="field">
        <label htmlFor="pub-body">Isi artikel (Markdown: ## subjudul, paragraf, - butir)</label>
        <textarea id="pub-body" rows={18} value={body} maxLength={200000} disabled={!editable || pending} onChange={(e) => setBody(e.target.value)} className="mono" />
        <span className="field-hint">
          Tulis &quot;berkaitan dengan&quot;, bukan &quot;menyebabkan&quot;. Jangan menyebut akun warga. Grafik dan
          angka dari snapshot ditampilkan otomatis di bawah artikel.
        </span>
      </div>
      {published && editable && (
        <div className="field">
          <label htmlFor="pub-note">Catatan ralat (wajib, tampil ke publik)</label>
          <input id="pub-note" value={note} maxLength={1000} disabled={pending} onChange={(e) => setNote(e.target.value)} placeholder="mis. Jumlah konten pada paragraf 2 diperbaiki" />
        </div>
      )}

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

      {editable ? (
        <div className="row-actions" style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <button type="button" className="btn" disabled={pending || !dirty} onClick={() => save()}>
            {pending ? "Menyimpan…" : published ? "Simpan ralat" : "Simpan"}
          </button>
          {nextSteps(pub.status, canPublish).map((target) => (
            <button key={target} type="button" className="btn btn-ghost" disabled={pending} onClick={() => move(target)}>
              {STEP_LABEL[target]}
            </button>
          ))}
          {!published && (
            <button type="button" className="btn btn-danger" disabled={pending} onClick={remove}>
              Hapus draf
            </button>
          )}
        </div>
      ) : (
        <p className="field-hint">
          {published
            ? "Artikel sudah terbit. Ralat hanya oleh Research Director."
            : "Peran Anda hanya bisa membaca."}
        </p>
      )}
      {pub.status === "review" && !canPublish && canEdit && (
        <p className="field-hint" style={{ marginTop: 8 }}>
          Menerbitkan hanya bisa dilakukan Research Director.
        </p>
      )}
    </div>
  );
}
