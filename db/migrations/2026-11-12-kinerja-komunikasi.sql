-- Migrasi 2026-11-12: modul Kinerja Komunikasi Pemerintah.
--
-- Menambah DUA tabel baru beserta kebijakan RLS-nya. Tidak mengubah tabel,
-- kolom, atau enum yang sudah ada, jadi aman bagi kode lama dan boleh
-- dijalankan sebelum atau sesudah kode PR-nya digabung:
--   * sebelum digabung: tabel menganggur, tidak ada yang membacanya;
--   * sesudah digabung tanpa migrasi: hanya halaman /kinerja yang menampilkan
--     "tabel belum ada" (API membalas 409); halaman lain tidak terpengaruh.
--
-- CARA MENJALANKAN: Supabase -> SQL Editor, tempel seluruh berkas, jalankan
-- sekali. Idempoten: menjalankan ulang tidak mengubah apa pun.

-- --------------------------------------- kinerja komunikasi pemerintah ----
-- Unggahan akun RESMI lembaga. Sengaja bukan `mentions`: pernyataan lembaga
-- tidak boleh ikut terhitung dalam sentimen publik (CLAUDE.md R1).

CREATE TABLE IF NOT EXISTS official_posts (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id   uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    platform     text NOT NULL CHECK (platform IN ('instagram', 'tiktok', 'x')),
    account      text NOT NULL,             -- nama akun LEMBAGA, bukan warga
    external_id  text NOT NULL,
    url          text,
    posted_at    timestamptz NOT NULL,
    kind         text,
    caption      text,
    likes        integer CHECK (likes >= 0),
    comments     integer CHECK (comments >= 0),
    shares       integer CHECK (shares >= 0),
    views        integer CHECK (views >= 0),
    saves        integer CHECK (saves >= 0),        -- hanya dari insight pemilik akun
    reach        integer CHECK (reach >= 0),        -- idem
    impressions  integer CHECK (impressions >= 0),  -- idem
    followers    integer CHECK (followers >= 0),    -- pengikut saat angka diambil
    captured_at  timestamptz,                       -- kapan angka diambil
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, platform, external_id)
);
CREATE INDEX IF NOT EXISTS official_posts_org_project_idx
    ON official_posts (org_id, project_id, posted_at DESC);

-- Satu baris per (lembaga, periode, indikator). Tepat satu dari `score` dan
-- `unavailable_reason` terisi: data kosong dicatat sebagai kosong, tidak ditebak.
CREATE TABLE IF NOT EXISTS comm_indicator_scores (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id          uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    subject             text NOT NULL,      -- lembaga yang dinilai
    period              text NOT NULL CHECK (period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    indicator           text NOT NULL,
    score               smallint CHECK (score BETWEEN 1 AND 5),
    unavailable_reason  text,
    evidence            text NOT NULL DEFAULT '',
    assessed_by         uuid REFERENCES users(id),
    assessed_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, subject, period, indicator),
    CHECK ((score IS NULL) <> (unavailable_reason IS NULL))
);
CREATE INDEX IF NOT EXISTS comm_indicator_scores_org_project_idx
    ON comm_indicator_scores (org_id, project_id, subject, period);

ALTER TABLE official_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE official_posts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS official_posts_tenant ON official_posts;
CREATE POLICY official_posts_tenant ON official_posts
  USING (org_id = current_org()) WITH CHECK (org_id = current_org());

ALTER TABLE comm_indicator_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE comm_indicator_scores FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS comm_indicator_scores_tenant ON comm_indicator_scores;
CREATE POLICY comm_indicator_scores_tenant ON comm_indicator_scores
  USING (org_id = current_org()) WITH CHECK (org_id = current_org());

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pop_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON official_posts, comm_indicator_scores TO pop_app;
  END IF;
END $$;

-- Pemeriksaan: harus mengembalikan 2 baris, keduanya rowsecurity = true.
SELECT relname, relrowsecurity AS rowsecurity, relforcerowsecurity AS force
FROM   pg_class WHERE relname IN ('official_posts', 'comm_indicator_scores');
