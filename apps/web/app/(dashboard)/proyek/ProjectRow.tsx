"use client";

import { useState, useTransition, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { renameProject, deleteProject, activateProject } from "./actions";

interface Props {
  id: string;
  name: string;
  isDemo: boolean;
  createdAt: string;
  isActive: boolean;
}

/**
 * Satu baris proyek di tabel /proyek. Client component karena butuh:
 *   - state lokal untuk mode edit (inline rename)
 *   - state lokal untuk konfirmasi hapus
 *   - useTransition supaya tombol "Simpan" / "Hapus" non-blocking
 *
 * Proyek demo tidak bisa diedit/dihapus — ditampilkan read-only.
 */
export function ProjectRow({ id, name, isDemo, createdAt, isActive }: Props) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [draft, setDraft] = useState(name);
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();
  const inputRef = useRef<HTMLInputElement>(null);

  // Fokus input saat masuk mode edit
  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  function handleStartEdit() {
    setDraft(name);
    setError("");
    setConfirmDelete(false);
    setEditing(true);
  }

  function handleCancelEdit() {
    setEditing(false);
    setError("");
  }

  function handleSave() {
    if (draft.trim() === name) {
      setEditing(false);
      return;
    }
    startTransition(async () => {
      const res = await renameProject(id, draft);
      if (res.ok) {
        setEditing(false);
        setError("");
        router.refresh();
      } else {
        setError(res.error ?? "Gagal menyimpan.");
      }
    });
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleSave();
    if (e.key === "Escape") handleCancelEdit();
  }

  function handleDelete() {
    startTransition(async () => {
      const res = await deleteProject(id);
      if (res.ok) {
        setConfirmDelete(false);
        if (res.cleared) {
          // Proyek aktif dihapus — redirect ke command (fallback demo)
          router.push("/command");
        } else {
          router.refresh();
        }
      } else {
        setError(res.error ?? "Gagal menghapus.");
      }
    });
  }

  function handleActivate() {
    startTransition(async () => {
      await activateProject(id);
      // Tanpa ini, cookie proyek aktif memang berubah di server, tapi Router
      // Cache App Router masih menyajikan RSC halaman lain (Sinyal, Tema,
      // dst.) yang sudah pernah dikunjungi sesi ini -- pengguna klik
      // "Aktifkan", cookie-nya benar berubah, tapi data yang tampil masih
      // milik proyek lama sampai ada navigasi yang memaksa render ulang.
      // handleSave/handleDelete di file ini sudah benar sejak awal; ini
      // satu-satunya handler yang lupa. Ketahuan 2026-09-11 lewat laporan
      // pengguna sungguhan, bukan lewat baca kode.
      router.refresh();
    });
  }

  const dateStr = new Date(createdAt).toLocaleDateString("id-ID", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <>
      <tr>
        {/* Kolom nama — mode tampil vs mode edit */}
        <td className="strong">
          {editing ? (
            <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
              {/* Sebelumnya `var(--bg2, #1a2332)` — token `--bg2` tidak pernah
                  ada di globals.css, jadi nilai fallback gelap itulah yang
                  selalu dipakai. Sekarang pakai kelas .field yang bertema. */}
              <span className="field" style={{ margin: 0, width: 220 }}>
                <input
                  ref={inputRef}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={pending}
                  maxLength={300}
                  aria-label="Nama proyek"
                />
              </span>
              <button onClick={handleSave} disabled={pending} className="btn btn-sm" type="button">
                {pending ? "…" : "Simpan"}
              </button>
              <button
                onClick={handleCancelEdit}
                disabled={pending}
                className="btn btn-sm btn-ghost"
                type="button"
              >
                Batal
              </button>
            </span>
          ) : (
            name
          )}
        </td>

        {/* Jenis */}
        <td className="dim">{isDemo ? "Demo" : "Asli"}</td>

        {/* Tanggal */}
        <td className="dim">{dateStr}</td>

        {/* Aksi */}
        <td>
          <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
            {isActive ? (
              <span className="pill pill-ok">Aktif</span>
            ) : (
              <button onClick={handleActivate} disabled={pending} className="btn btn-sm" type="button">
                Aktifkan
              </button>
            )}

            {/* Edit & hapus — hanya untuk proyek non-demo */}
            {!isDemo && !editing && (
              <>
                <button
                  onClick={handleStartEdit}
                  disabled={pending}
                  className="btn btn-sm btn-ghost"
                  type="button"
                >
                  Ubah nama
                </button>
                {!confirmDelete ? (
                  <button
                    onClick={() => { setConfirmDelete(true); setError(""); }}
                    disabled={pending}
                    className="btn btn-sm btn-danger"
                    type="button"
                  >
                    Hapus
                  </button>
                ) : (
                  <>
                    <button
                      onClick={handleDelete}
                      disabled={pending}
                      className="btn btn-sm btn-danger"
                      style={{ background: "var(--neg-bg)" }}
                      type="button"
                    >
                      {pending ? "…" : "Ya, hapus"}
                    </button>
                    <button
                      onClick={() => setConfirmDelete(false)}
                      disabled={pending}
                      className="btn btn-sm btn-ghost"
                      type="button"
                    >
                      Batal
                    </button>
                  </>
                )}
              </>
            )}
          </span>
        </td>
      </tr>

      {/* Baris error — muncul di bawah baris utama kalau ada */}
      {error && (
        <tr>
          <td colSpan={4} style={{ color: "var(--neg)", fontSize: 11, paddingTop: 0, borderBottom: "none" }}>
            {error}
          </td>
        </tr>
      )}
    </>
  );
}
