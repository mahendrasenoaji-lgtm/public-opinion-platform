-- Migrasi 2026-11-15 (b): Kinerja Komunikasi, keaktifan situs web resmi.
--
-- Menambah DUA tabel baru beserta kebijakan RLS-nya. Tidak mengubah tabel,
-- kolom, atau enum yang sudah ada, jadi aman bagi kode lama dan boleh
-- dijalankan sebelum atau sesudah kode PR-nya digabung. Tanpa migrasi ini
-- hanya bagian "Situs resmi" di /kinerja/analisis yang menampilkan "tabel
-- belum ada" (API membalas 409); bagian lain tidak terpengaruh.
--
-- Tidak bergantung pada migrasi Kinerja lain.
-- CARA MENJALANKAN: Supabase -> SQL Editor, tempel seluruh berkas, jalankan
-- sekali. Idempoten: menjalankan ulang tidak mengubah apa pun.

-- Situs web resmi lembaga yang dipantau keaktifannya. `feed_kind` mencatat
-- sumber yang terbaca: rss, sitemap, halaman (daftar berita), atau none (tidak ada;
-- butir lalu hanya masuk lewat unggahan manual).
CREATE TABLE IF NOT EXISTS official_sites (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id   uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    subject      text NOT NULL,             -- nama lembaga
    base_url     text NOT NULL,
    feed_kind    text NOT NULL DEFAULT 'none'
                 CHECK (feed_kind IN ('rss', 'sitemap', 'halaman', 'none')),
    source_url   text,
    -- Halaman daftar berita yang didaftarkan pengguna (pengecualian tertulis
    -- di connectors/base.py); dibaca hanya bila feed dan sitemap tidak ada.
    list_urls    jsonb NOT NULL DEFAULT '[]'::jsonb,
    check_notes  jsonb NOT NULL DEFAULT '[]'::jsonb,
    checked_at   timestamptz,
    created_by   uuid REFERENCES users(id),
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, base_url)
);
CREATE INDEX IF NOT EXISTS official_sites_org_project_idx
    ON official_sites (org_id, project_id);

-- Satu baris per butir yang terbit di situs resmi (berita, siaran pers,
-- pengumuman). Hanya judul, alamat, tanggal, kategori; isi tidak disimpan.
CREATE TABLE IF NOT EXISTS official_site_items (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    site_id       uuid NOT NULL REFERENCES official_sites(id) ON DELETE CASCADE,
    url           text NOT NULL,
    title         text,
    published_at  timestamptz NOT NULL,
    category      text NOT NULL DEFAULT 'lainnya',
    origin        text NOT NULL CHECK (origin IN ('rss', 'sitemap', 'halaman', 'manual')),
    captured_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (site_id, url)
);
CREATE INDEX IF NOT EXISTS official_site_items_site_idx
    ON official_site_items (org_id, site_id, published_at DESC);

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['official_sites', 'official_site_items'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS %1$s_tenant ON %1$I', t);
    EXECUTE format(
      'CREATE POLICY %1$s_tenant ON %1$I USING (org_id = current_org()) WITH CHECK (org_id = current_org())',
      t
    );
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pop_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON official_sites, official_site_items TO pop_app;
  END IF;
END $$;

-- Pemeriksaan: harus mengembalikan 2 baris, semuanya rowsecurity = true dan force = true.
SELECT relname, relrowsecurity AS rowsecurity, relforcerowsecurity AS force
FROM   pg_class
WHERE  relname IN ('official_sites', 'official_site_items')
ORDER  BY relname;
