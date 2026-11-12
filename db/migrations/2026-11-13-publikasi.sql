-- Migrasi 2026-11-13: publikasi hasil riset (tahap 1 situs publikasi).
--
-- Menambah SATU tabel (`publications`) + RLS + dua fungsi baca-publik. Tidak
-- mengubah tabel, kolom, atau enum yang ada; aman bagi kode lama; idempoten.
-- Tanpa migrasi ini, hanya halaman /publikasi dan API publik yang membalas
-- "tabel belum ada" (409); halaman lain tidak terpengaruh.
--
-- CARA MENJALANKAN: Supabase -> SQL Editor, tempel seluruh berkas, jalankan sekali.

-- ------------------------------------------------- publikasi hasil riset ----
-- Artikel dengan snapshot angka yang dibekukan. Situs publik TIDAK membaca
-- tabel proyek; ia hanya membaca baris berstatus 'published' lewat dua fungsi
-- SECURITY DEFINER sempit di db/rls.sql.

CREATE TABLE IF NOT EXISTS publications (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    slug          text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    title         text NOT NULL,
    summary       text NOT NULL DEFAULT '',
    body          text NOT NULL DEFAULT '',
    tags          text[] NOT NULL DEFAULT '{}',
    author_name   text NOT NULL,
    status        text NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft', 'review', 'published')),
    snapshot      jsonb NOT NULL,
    version       integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    corrections   jsonb NOT NULL DEFAULT '[]',
    created_by    uuid REFERENCES users(id),
    published_by  uuid REFERENCES users(id),
    published_at  timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    CHECK ((status = 'published') = (published_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS publications_org_project_idx
    ON publications (org_id, project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS publications_published_idx
    ON publications (published_at DESC) WHERE status = 'published';

ALTER TABLE publications ENABLE ROW LEVEL SECURITY;
ALTER TABLE publications FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS publications_tenant ON publications;
CREATE POLICY publications_tenant ON publications
  USING (org_id = current_org()) WITH CHECK (org_id = current_org());

-- ============================================================================
-- Situs publikasi: baca-saja, tanpa login, HANYA artikel berstatus 'published'.
--
-- Pembaca publik tidak punya organisasi, jadi current_org() NULL dan kebijakan
-- publications_tenant menyaring semua baris. Seperti auth_lookup_user(): bukan
-- kebijakannya yang dilonggarkan, melainkan dua fungsi SECURITY DEFINER sempit
-- yang hanya mengembalikan kolom artikel terbit. Tidak ada kolom org_id,
-- project_id, atau pengguna yang keluar, dan tidak ada tabel lain yang terbaca.
-- ============================================================================
CREATE OR REPLACE FUNCTION public_publications(p_tag text, p_limit integer, p_offset integer)
RETURNS TABLE (
  slug text, title text, summary text, tags text[], author_name text,
  published_at timestamptz, version integer, total bigint
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT slug, title, summary, tags, author_name, published_at, version,
         count(*) OVER () AS total
  FROM publications
  WHERE status = 'published' AND (p_tag IS NULL OR p_tag = ANY (tags))
  ORDER BY published_at DESC
  LIMIT LEAST(GREATEST(p_limit, 1), 100) OFFSET GREATEST(p_offset, 0)
$$;
REVOKE ALL ON FUNCTION public_publications(text, integer, integer) FROM PUBLIC;

CREATE OR REPLACE FUNCTION public_publication(p_slug text)
RETURNS TABLE (
  slug text, title text, summary text, body text, tags text[], author_name text,
  published_at timestamptz, updated_at timestamptz, version integer,
  snapshot jsonb, corrections jsonb
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT slug, title, summary, body, tags, author_name, published_at, updated_at,
         version, snapshot, corrections
  FROM publications
  WHERE status = 'published' AND slug = p_slug
$$;
REVOKE ALL ON FUNCTION public_publication(text) FROM PUBLIC;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pop_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON publications TO pop_app;
    GRANT EXECUTE ON FUNCTION public_publications(text, integer, integer) TO pop_app;
    GRANT EXECUTE ON FUNCTION public_publication(text) TO pop_app;
  END IF;
END $$;

-- Pemeriksaan: harus 1 baris, rowsecurity = true, force = true.
SELECT relname, relrowsecurity AS rowsecurity, relforcerowsecurity AS force
FROM   pg_class WHERE relname = 'publications';
