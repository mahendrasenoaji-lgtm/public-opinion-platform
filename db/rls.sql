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

-- PII hanya untuk peran tertentu. Ditegakkan lagi di lapisan aplikasi.
REVOKE ALL ON respondent_identities FROM pop_app;
GRANT SELECT, INSERT, DELETE ON respondent_identities TO pop_app;
