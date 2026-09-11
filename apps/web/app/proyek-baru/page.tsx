"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createFirstProject } from "./actions";

// Halaman berdiri sendiri (di luar (dashboard)/layout.tsx) sengaja: shell
// dashboard itu sendiri butuh proyek aktif untuk dirender (lihat
// (dashboard)/layout.tsx) -- lingkaran setan kalau halaman "belum punya
// proyek" dipaksa masuk ke layout yang mengasumsikan proyek sudah ada.
//
// Dipakai dua alur: org yang baru daftar (app/daftar, nol proyek) DAN org
// lama yang sudah punya proyek tapi mau tambah lagi (link "+ Buat proyek
// baru" di app/(dashboard)/proyek) -- makanya copy di bawah sengaja netral,
// tidak berasumsi ini proyek pertama.
export default function ProyekBaruPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (name.trim().length < 1) {
      setErr("Nama proyek wajib diisi.");
      return;
    }
    setLoading(true);
    setErr("");
    const result = await createFirstProject(name.trim());
    if (result.ok) {
      router.push("/command");
    } else {
      setErr(result.error);
      setLoading(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <h1 className="auth-title">Buat proyek baru</h1>
        <p className="auth-sub">
          Beri nama dulu — isinya (survei, segmen, narasi) bisa ditambah nanti.
          Proyek ini langsung jadi proyek aktif Anda.
        </p>

        {err && <div className="form-err" role="alert">{err}</div>}

        <div className="field">
          <label htmlFor="proj-name">Nama proyek</label>
          <input
            id="proj-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            autoFocus
            placeholder="Persepsi Kebijakan 2026"
          />
        </div>

        <button
          className="btn btn-block"
          onClick={submit}
          disabled={loading || !name.trim()}
          type="button"
        >
          {loading ? "Membuat…" : "Buat proyek"}
        </button>
      </div>
    </div>
  );
}
