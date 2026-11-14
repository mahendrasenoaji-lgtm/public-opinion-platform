-- Migrasi 2026-11-14: modul Kinerja Komunikasi menerima platform YouTube.
--
-- Hanya melonggarkan CHECK kolom official_posts.platform supaya menerima
-- 'youtube' (video kanal resmi lembaga yang diambil lewat YouTube Data API).
-- Tidak menyentuh baris yang ada; nilai lama tetap lolos CHECK baru.
--
-- Prasyarat: 2026-11-12-kinerja-komunikasi.sql sudah dijalankan.
-- Tanpa migrasi ini, hanya pengambilan YouTube di /kinerja yang membalas 409
-- "jalankan migrasi"; unggahan Instagram/TikTok/X tetap jalan.
--
-- CARA MENJALANKAN: Supabase -> SQL Editor, tempel seluruh berkas, jalankan
-- sekali. Idempoten. SQL Editor akan memperingatkan "destructive operation"
-- karena DROP CONSTRAINT; constraint yang sama langsung dibuat ulang dengan
-- daftar yang lebih longgar di transaksi yang sama.

BEGIN;

DO $$ BEGIN
  IF to_regclass('public.official_posts') IS NULL THEN
    RAISE EXCEPTION 'Tabel official_posts belum ada. Jalankan dulu 2026-11-12-kinerja-komunikasi.sql.';
  END IF;
END $$;

ALTER TABLE official_posts DROP CONSTRAINT IF EXISTS official_posts_platform_check;
ALTER TABLE official_posts ADD CONSTRAINT official_posts_platform_check
  CHECK (platform IN ('instagram', 'tiktok', 'x', 'youtube'));

COMMIT;

-- Pemeriksaan: harus 1 baris yang memuat 'youtube'.
SELECT conname, pg_get_constraintdef(oid) AS definisi
FROM   pg_constraint
WHERE  conrelid = 'public.official_posts'::regclass AND contype = 'c'
  AND  pg_get_constraintdef(oid) LIKE '%platform%';
