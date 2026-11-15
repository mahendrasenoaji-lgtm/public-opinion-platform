-- Migrasi 2026-11-15: Kinerja Komunikasi, pengodean isi, arus informasi, keselarasan.
--
-- Menambah TIGA tabel baru beserta kebijakan RLS-nya. Tidak mengubah tabel,
-- kolom, atau enum yang sudah ada, jadi aman bagi kode lama dan boleh
-- dijalankan sebelum atau sesudah kode PR-nya digabung. Tanpa migrasi ini
-- hanya bagian "Pengodean isi", "Arus informasi", dan "Keselarasan pesan" di
-- /kinerja yang menampilkan "tabel belum ada" (API membalas 409); bagian lain
-- /kinerja dan halaman lain tidak terpengaruh.
--
-- Prasyarat: 2026-11-12-kinerja-komunikasi.sql sudah dijalankan.
-- CARA MENJALANKAN: Supabase -> SQL Editor, tempel seluruh berkas, jalankan
-- sekali. Idempoten: menjalankan ulang tidak mengubah apa pun.

DO $$ BEGIN
  IF to_regclass('public.official_posts') IS NULL THEN
    RAISE EXCEPTION 'Tabel official_posts belum ada. Jalankan dulu 2026-11-12-kinerja-komunikasi.sql.';
  END IF;
END $$;

-- Kode isi per unggahan akun resmi (Lampiran A kerangka). `coder` adalah
-- lembar pengode 1 atau 2, bukan akun login: dua pengode boleh memakai satu
-- login, dan `coded_by` mencatat siapa yang menyimpan.
CREATE TABLE IF NOT EXISTS official_post_codings (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    post_id     uuid NOT NULL REFERENCES official_posts(id) ON DELETE CASCADE,
    coder       smallint NOT NULL CHECK (coder IN (1, 2)),
    coder_name  text NOT NULL DEFAULT '',
    codes       jsonb NOT NULL,             -- {"A9": 1, "A14": 3, ...}
    note        text NOT NULL DEFAULT '',
    coded_by    uuid REFERENCES users(id),
    coded_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (post_id, coder)
);
CREATE INDEX IF NOT EXISTS official_post_codings_org_project_idx
    ON official_post_codings (org_id, project_id);

-- Penelusuran arus informasi satu konten (T1-T4). Cap waktu yang tidak
-- dicatat auditor dibiarkan NULL; selangnya tidak dihitung.
CREATE TABLE IF NOT EXISTS comm_flow_records (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id            uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id        uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    subject           text NOT NULL,        -- lembaga yang diaudit
    label             text NOT NULL,        -- konten yang ditelusuri
    kind              text NOT NULL CHECK (kind IN ('rutin', 'klarifikasi')),
    requested_at      timestamptz,
    received_at       timestamptz,
    verified_at       timestamptz,
    drafted_at        timestamptz,
    approved_at       timestamptz,
    published_at      timestamptz,
    bottleneck_stage  smallint CHECK (bottleneck_stage BETWEEN 1 AND 11),
    note              text NOT NULL DEFAULT '',
    created_by        uuid REFERENCES users(id),
    created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS comm_flow_records_org_project_idx
    ON comm_flow_records (org_id, project_id, subject);

-- Pasangan pernyataan dua lembaga tentang satu isu (indikator C3).
CREATE TABLE IF NOT EXISTS comm_alignment_pairs (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    issue       text NOT NULL,
    subject_a   text NOT NULL,
    url_a       text,
    subject_b   text NOT NULL,
    url_b       text,
    coder       smallint NOT NULL CHECK (coder IN (1, 2)),
    code        text NOT NULL CHECK (code IN ('selaras', 'beda_penekanan', 'bertentangan')),
    corrected   boolean NOT NULL DEFAULT false,   -- pernyataan bertentangan sudah diralat
    note        text NOT NULL DEFAULT '',
    coded_by    uuid REFERENCES users(id),
    coded_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, issue, subject_a, subject_b, coder)
);
CREATE INDEX IF NOT EXISTS comm_alignment_pairs_org_project_idx
    ON comm_alignment_pairs (org_id, project_id);

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['official_post_codings', 'comm_flow_records', 'comm_alignment_pairs'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS %1$s_tenant ON %1$I', t);
    EXECUTE format(
      'CREATE POLICY %1$s_tenant ON %1$I USING (org_id = current_org()) WITH CHECK (org_id = current_org())',
      t
    );
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pop_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE
      ON official_post_codings, comm_flow_records, comm_alignment_pairs TO pop_app;
  END IF;
END $$;

-- Pemeriksaan: harus mengembalikan 3 baris, semuanya rowsecurity = true dan force = true.
SELECT relname, relrowsecurity AS rowsecurity, relforcerowsecurity AS force
FROM   pg_class
WHERE  relname IN ('official_post_codings', 'comm_flow_records', 'comm_alignment_pairs')
ORDER  BY relname;
