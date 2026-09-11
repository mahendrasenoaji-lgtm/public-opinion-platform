"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Activity } from "lucide-react";

// Field & aturan validasi di sini SENGAJA harus persis sama dengan
// app/schemas/auth.py:RegisterRequest -- validasi klien cuma UX (pesan
// instan sebelum round-trip), batas sungguhan tetap di backend (Pydantic).
const SLUG_PATTERN = /^[a-z0-9-]+$/;

function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

export default function DaftarPage() {
  const router = useRouter();
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  function onOrgNameChange(value: string) {
    setOrgName(value);
    // Auto-isi slug dari nama organisasi selama pengguna belum pernah
    // mengetik slug-nya sendiri -- begitu disentuh manual, berhenti
    // menimpa supaya tidak mengganggu ketikan yang sedang berlangsung.
    if (!slugTouched) setOrgSlug(slugify(value));
  }

  function validate(): string | null {
    if (orgName.trim().length < 2) return "Nama organisasi minimal 2 karakter.";
    if (orgSlug.length < 2) return "Slug organisasi minimal 2 karakter.";
    if (!SLUG_PATTERN.test(orgSlug)) return "Slug cuma boleh huruf kecil, angka, dan tanda hubung.";
    if (fullName.trim().length < 1) return "Nama lengkap wajib diisi.";
    if (password.length < 8) return "Password minimal 8 karakter.";
    return null;
  }

  async function submit() {
    const problem = validate();
    if (problem) {
      setErr(problem);
      return;
    }
    setLoading(true);
    setErr("");
    try {
      const res = await fetch("/api/session/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ orgName, orgSlug, fullName, email, password }),
      });
      const data = await res.json();
      // Org yang baru daftar dijamin nol proyek (auth_register() cuma
      // membuat org+user) -- lewat /proyek-baru dulu, bukan langsung ke
      // /command, supaya tidak mendarat di dashboard kosong tanpa jalan
      // keluar. Lihat app/proyek-baru/page.tsx.
      if (data.ok) router.push("/proyek-baru" as never);
      else setErr(data.error || "Pendaftaran gagal.");
    } catch {
      setErr("Terjadi kesalahan jaringan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card wide">
        <div className="auth-brand">
          <Activity size={18} strokeWidth={2.5} />
          <span className="brand-n">PUBLIC OPINION</span>
        </div>
        <h1 className="auth-title">Daftarkan organisasi baru</h1>
        <p className="auth-sub">
          Membuat tenant baru dengan Anda sebagai SUPER_ADMIN pertamanya.
        </p>

        {err && <div className="form-err" role="alert">{err}</div>}

        <div className="field">
          <label htmlFor="reg-org">Nama organisasi</label>
          <input
            id="reg-org"
            value={orgName}
            onChange={(e) => onOrgNameChange(e.target.value)}
            placeholder="Lembaga Riset Opini Publik"
          />
        </div>
        <div className="field">
          <label htmlFor="reg-slug">Slug organisasi</label>
          <input
            id="reg-slug"
            value={orgSlug}
            onChange={(e) => {
              setSlugTouched(true);
              setOrgSlug(e.target.value);
            }}
            placeholder="lembaga-riset"
          />
          <span className="field-hint">Huruf kecil, angka, dan tanda hubung saja.</span>
        </div>
        <div className="field">
          <label htmlFor="reg-name">Nama lengkap Anda</label>
          <input
            id="reg-name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            autoComplete="name"
            placeholder="Nama lengkap"
          />
        </div>
        <div className="field">
          <label htmlFor="reg-email">Email</label>
          <input
            id="reg-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            placeholder="nama@organisasi.id"
          />
        </div>
        <div className="field">
          <label htmlFor="reg-password">Password</label>
          <input
            id="reg-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            autoComplete="new-password"
            placeholder="••••••••"
          />
          <span className="field-hint">Minimal 8 karakter.</span>
        </div>

        <button className="btn btn-block" onClick={submit} disabled={loading} type="button">
          {loading ? "Mendaftarkan…" : "Daftar"}
        </button>

        <p className="auth-alt">
          Sudah punya akun? <Link href="/masuk">Masuk</Link>
        </p>
      </div>
    </div>
  );
}
