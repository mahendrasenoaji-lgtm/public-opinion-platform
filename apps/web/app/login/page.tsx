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
    <div className="auth-card">
      <h1 className="auth-title">Akses Terproteksi</h1>
      <p className="auth-sub">Situs ini belum dibuka untuk umum.</p>

      {err && <div className="form-err" role="alert">{err}</div>}

      <div className="field">
        <label htmlFor="gate-password">Password</label>
        <input
          id="gate-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          autoFocus
          autoComplete="current-password"
          placeholder="••••••••"
        />
      </div>

      <button className="btn btn-block" onClick={submit} disabled={loading || !password} type="button">
        {loading ? "Memeriksa…" : "Masuk"}
      </button>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="auth-wrap">
      <Suspense fallback={null}><LoginForm /></Suspense>
    </div>
  );
}
