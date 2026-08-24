-- ============================================================================
-- Row Level Security — isolasi tenant di lapisan database.
-- Aplikasi menyetel: SET LOCAL app.current_org = '<uuid>' per transaksi.
-- Lihat apps/api/app/deps.py dan CLAUDE.md aturan R3.
-- ============================================================================

CREATE OR REPLACE FUNCTION current_org() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.current_org', true), '')::uuid
$$;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'users','projects','surveys','questions','respondents','respondent_identities',
    'responses','data_sources','mentions','topics','narratives','metric_snapshots',
    'segments','timeline_events','forecasts','ai_outputs','audit_logs',
    'data_quality_scores'
  ] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format($f$
      CREATE POLICY %1$s_tenant ON %1$I
      USING (org_id = current_org())
      WITH CHECK (org_id = current_org())
    $f$, t);
  END LOOP;
END $$;

-- organizations dibaca lewat kolom id, bukan org_id
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
CREATE POLICY organizations_tenant ON organizations
  USING (id = current_org()) WITH CHECK (id = current_org());

-- Peran aplikasi. JANGAN pakai superuser untuk query aplikasi: RLS diabaikan.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pop_app') THEN
    CREATE ROLE pop_app LOGIN PASSWORD 'change-me';
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO pop_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO pop_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO pop_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pop_app;

-- ============================================================================
-- Bootstrap RLS untuk /auth/login — ditemukan 2026-08-24.
--
-- /auth/login mencari user lewat email SEBELUM org_id-nya diketahui (ayam-
-- telur: org_id baru ketahuan SETELAH user ditemukan). Karena `users`
-- FORCE ROW LEVEL SECURITY dan endpoint ini memakai get_session() biasa
-- (bukan TenantSession yang men-set app.current_org), current_org() selalu
-- NULL saat query ini jalan -> policy users_tenant (org_id = current_org())
-- menyaring HABIS semua baris -> login selalu balas 401 "salah" apa pun
-- passwordnya. Bug lama, baru ketahuan sekarang karena baru sekarang ada
-- yang benar-benar coba login pakai password asli (bukan token demo).
--
-- Perbaikannya BUKAN melonggarkan policy users_tenant (itu akan membocorkan
-- seluruh tabel users lintas tenant untuk SETIAP query tanpa app.current_org
-- ter-set, bukan cuma untuk login). Polanya: fungsi SECURITY DEFINER yang
-- SEMPIT — cuma kolom yang dibutuhkan alur auth, dipanggil lewat GRANT
-- EXECUTE eksplisit ke pop_app, bukan akses tabel langsung.
-- ============================================================================
CREATE OR REPLACE FUNCTION auth_lookup_user(p_email text)
RETURNS TABLE (
  id uuid, org_id uuid, email text, password_hash text,
  role text, is_active boolean
)
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
  SELECT id, org_id, email, password_hash, role, is_active
  FROM users WHERE email = p_email
$$;
REVOKE ALL ON FUNCTION auth_lookup_user(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION auth_lookup_user(text) TO pop_app;

-- PII hanya untuk peran tertentu. Ditegakkan lagi di lapisan aplikasi.
REVOKE ALL ON respondent_identities FROM pop_app;
GRANT SELECT, INSERT, DELETE ON respondent_identities TO pop_app;
