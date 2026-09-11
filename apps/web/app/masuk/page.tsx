"use client";
import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import type { Route } from "next";
import { Activity } from "lucide-react";

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
    <div className="auth-card">
      <div className="auth-brand">
        <Activity size={18} strokeWidth={2.5} />
        <span className="brand-n">PUBLIC OPINION</span>
      </div>
      <h1 className="auth-title">Masuk</h1>
      <p className="auth-sub">Gunakan akun organisasi Anda.</p>

      {err && <div className="form-err" role="alert">{err}</div>}

      <div className="field">
        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          autoFocus
          autoComplete="email"
          placeholder="nama@organisasi.id"
        />
      </div>
      <div className="field">
        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          autoComplete="current-password"
          placeholder="••••••••"
        />
      </div>

      <button
        className="btn btn-block"
        onClick={submit}
        disabled={loading || !email || !password}
        type="button"
      >
        {loading ? "Memeriksa…" : "Masuk"}
      </button>

      <p className="auth-alt">
        Belum punya organisasi? <Link href={"/daftar" as Route}>Daftar</Link>
      </p>
    </div>
  );
}

export default function MasukPage() {
  return (
    <div className="auth-wrap">
      <Suspense fallback={null}><LoginForm /></Suspense>
    </div>
  );
}
