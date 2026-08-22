"use client";
import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/";
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true); setErr("");
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      // `typedRoutes` only accepts known literal routes; `next` is a
      // runtime-computed redirect target, so it's cast past that check.
      if (data.ok) router.push(next as never);
      else setErr(data.error || "Gagal masuk.");
    } catch {
      setErr("Terjadi kesalahan jaringan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ width: "100%", maxWidth: 340 }}>
      <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16, textAlign: "center" }}>
        Akses Terproteksi
      </h1>
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        autoFocus
        placeholder="Masukkan password"
        style={{
          width: "100%", padding: "10px 12px", fontSize: 14, marginBottom: 8,
          borderRadius: 8, border: "1px solid #ccc", outline: "none",
        }}
      />
      {err && <div style={{ color: "#c0392b", fontSize: 13, marginBottom: 8 }}>{err}</div>}
      <button
        onClick={submit}
        disabled={loading || !password}
        style={{
          width: "100%", padding: "10px 12px", fontSize: 14, fontWeight: 600,
          borderRadius: 8, border: "none", cursor: "pointer",
          background: "#111", color: "#fff", opacity: loading || !password ? 0.4 : 1,
        }}
      >
        {loading ? "Memeriksa…" : "Masuk"}
      </button>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <Suspense fallback={null}><LoginForm /></Suspense>
    </div>
  );
}
