"use client";
import { useState, type CSSProperties } from "react";
import { useRouter } from "next/navigation";
import { createFirstProject } from "./actions";

// Halaman berdiri sendiri (di luar (dashboard)/layout.tsx) sengaja: shell
// dashboard itu sendiri butuh proyek aktif untuk dirender (lihat
// (dashboard)/layout.tsx) -- lingkaran setan kalau halaman "belum punya
// proyek" dipaksa masuk ke layout yang mengasumsikan proyek sudah ada.
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

  const inputStyle: CSSProperties = {
    width: "100%",
    padding: "10px 12px",
    fontSize: 14,
    marginBottom: 8,
    borderRadius: 8,
    border: "1px solid #ccc",
    outline: "none",
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <div style={{ width: "100%", maxWidth: 340 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4, textAlign: "center" }}>
          Buat Proyek Pertama
        </h1>
        <p style={{ fontSize: 12, color: "#888", marginBottom: 16, textAlign: "center" }}>
          Organisasi Anda belum punya proyek. Dashboard butuh satu proyek
          untuk dilihat — beri nama dulu, isinya bisa ditambah nanti.
        </p>

        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          autoFocus
          placeholder="Nama proyek (mis. Persepsi Kebijakan 2026)"
          style={inputStyle}
        />

        {err && <div style={{ color: "#c0392b", fontSize: 13, marginBottom: 8 }}>{err}</div>}

        <button
          onClick={submit}
          disabled={loading || !name.trim()}
          style={{
            width: "100%",
            padding: "10px 12px",
            fontSize: 14,
            fontWeight: 600,
            borderRadius: 8,
            border: "none",
            cursor: "pointer",
            background: "#111",
            color: "#fff",
            opacity: loading || !name.trim() ? 0.4 : 1,
          }}
        >
          {loading ? "Membuat…" : "Buat Proyek"}
        </button>
      </div>
    </div>
  );
}
