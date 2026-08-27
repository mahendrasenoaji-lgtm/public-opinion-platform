"use client";
import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import type { Route } from "next";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/command";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true); setErr("");
    try {
      const res = await fetch("/api/session/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      // `typedRoutes` cuma menerima literal rute yang dikenal; `next` dihitung
      // saat runtime, jadi di-cast lewat pemeriksaan itu.
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
        Masuk ke Public Opinion Platform
      </h1>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        autoFocus
        placeholder="Email"
        style={{
          width: "100%", padding: "10px 12px", fontSize: 14, marginBottom: 8,
          borderRadius: 8, border: "1px solid #ccc", outline: "none",
        }}
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        placeholder="Password"
        style={{
          width: "100%", padding: "10px 12px", fontSize: 14, marginBottom: 8,
          borderRadius: 8, border: "1px solid #ccc", outline: "none",
        }}
      />
      {err && <div style={{ color: "#c0392b", fontSize: 13, marginBottom: 8 }}>{err}</div>}
      <button
        onClick={submit}
        disabled={loading || !email || !password}
        style={{
          width: "100%", padding: "10px 12px", fontSize: 14, fontWeight: 600,
          borderRadius: 8, border: "none", cursor: "pointer",
          background: "#111", color: "#fff", opacity: loading || !email || !password ? 0.4 : 1,
        }}
      >
        {loading ? "Memeriksa…" : "Masuk"}
      </button>
      <p style={{ fontSize: 12, color: "#888", textAlign: "center", marginTop: 12 }}>
        Belum punya organisasi?{" "}
        <Link href={"/daftar" as Route} style={{ color: "#111", fontWeight: 600 }}>
          Daftar
        </Link>
      </p>
    </div>
  );
}

export default function MasukPage() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <Suspense fallback={null}><LoginForm /></Suspense>
    </div>
  );
}
