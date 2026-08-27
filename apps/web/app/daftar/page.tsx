"use client";
import { useState, type CSSProperties } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

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
          Daftarkan Organisasi Baru
        </h1>
        <p style={{ fontSize: 12, color: "#888", marginBottom: 16, textAlign: "center" }}>
          Membuat tenant baru dengan Anda sebagai SUPER_ADMIN pertamanya.
        </p>

        <input
          value={orgName}
          onChange={(e) => onOrgNameChange(e.target.value)}
          placeholder="Nama organisasi"
          style={inputStyle}
        />
        <input
          value={orgSlug}
          onChange={(e) => {
            setSlugTouched(true);
            setOrgSlug(e.target.value);
          }}
          placeholder="slug-organisasi"
          style={inputStyle}
        />
        <input
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="Nama lengkap Anda"
          style={inputStyle}
        />
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          style={inputStyle}
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Password (min. 8 karakter)"
          style={inputStyle}
        />

        {err && <div style={{ color: "#c0392b", fontSize: 13, marginBottom: 8 }}>{err}</div>}

        <button
          onClick={submit}
          disabled={loading}
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
            opacity: loading ? 0.4 : 1,
            marginBottom: 12,
          }}
        >
          {loading ? "Mendaftarkan…" : "Daftar"}
        </button>

        <p style={{ fontSize: 12, color: "#888", textAlign: "center" }}>
          Sudah punya akun?{" "}
          <Link href="/masuk" style={{ color: "#111", fontWeight: 600 }}>
            Masuk
          </Link>
        </p>
      </div>
    </div>
  );
}
