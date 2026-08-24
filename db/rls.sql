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

-- Sama seperti auth_lookup_user() di atas, tapi lookup by id — dipakai
-- /auth/refresh, yang cuma punya user_id dari klaim refresh token, belum
-- ada app.current_org tersedia. Ditemukan bersamaan (2026-08-24): bug yang
-- persis sama, /auth/refresh juga selalu balas 401 sebelum ini.
CREATE OR REPLACE FUNCTION auth_lookup_user_by_id(p_user_id uuid)
RETURNS TABLE (id uuid, org_id uuid, email text, role text, is_active boolean)
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
  SELECT id, org_id, email, role, is_active FROM users WHERE id = p_user_id
$$;
REVOKE ALL ON FUNCTION auth_lookup_user_by_id(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION auth_lookup_user_by_id(uuid) TO pop_app;

-- /auth/register: sama akar masalahnya, tapi lebih parah — INSERT ke
-- organizations/users lewat sesi tanpa app.current_org melanggar WITH CHECK
-- (org_id = current_org()) dan GAGAL TOTAL (bukan cuma diam-diam kosong
-- seperti SELECT). Belum ada UI yang memakai endpoint ini, jadi baru
-- ketahuan lewat pembacaan kode, belum ada laporan pengguna nyata.
-- Uniqueness slug dicek di dalam fungsi (bukan pre-check terpisah di
-- Python yang juga akan kena RLS yang sama), lalu dilempar sebagai
-- unique_violation supaya app layer bisa tangkap jadi 409 yang rapi.
CREATE OR REPLACE FUNCTION auth_register(
  p_org_name text, p_org_slug text, p_full_name text,
  p_email text, p_password_hash text
) RETURNS TABLE (org_id uuid, user_id uuid, role text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_org_id uuid; v_user_id uuid;
BEGIN
  IF EXISTS (SELECT 1 FROM organizations WHERE slug = p_org_slug) THEN
    RAISE EXCEPTION 'Slug organisasi sudah dipakai.' USING ERRCODE = 'unique_violation';
  END IF;

  INSERT INTO organizations (name, slug) VALUES (p_org_name, p_org_slug)
    RETURNING id INTO v_org_id;
  INSERT INTO users (org_id, email, full_name, password_hash, role)
    VALUES (v_org_id, p_email, p_full_name, p_password_hash, 'SUPER_ADMIN')
    RETURNING id INTO v_user_id;

  RETURN QUERY SELECT v_org_id, v_user_id, 'SUPER_ADMIN'::text;
END;
$$;
REVOKE ALL ON FUNCTION auth_register(text, text, text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION auth_register(text, text, text, text, text) TO pop_app;

-- PII hanya untuk peran tertentu. Ditegakkan lagi di lapisan aplikasi.
REVOKE ALL ON respondent_identities FROM pop_app;
GRANT SELECT, INSERT, DELETE ON respondent_identities TO pop_app;
