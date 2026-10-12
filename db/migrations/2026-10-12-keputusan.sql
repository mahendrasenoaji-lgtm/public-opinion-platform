-- Migrasi 2026-10-12 — keputusan pengguna 12 Oktober:
--   butir 5  versi penilai sentimen per baris + kolom skor pendamping
--   butir 4  skor ragam berita disimpan BERDAMPINGAN (deret MEDIA tidak digeser)
--   butir 8  nilai enum SENSOR untuk data kualitas udara
--   butir 9  hapus tiga organisasi uji yang kosong
--
-- CARA MENJALANKAN (Supabase → SQL Editor), SEBELUM kode PR-nya di-merge:
--   1. Tempel dan jalankan BAGIAN A saja.
--   2. Tempel dan jalankan BAGIAN B saja.
-- Dua kali jalan, bukan satu: Postgres menolak memakai nilai enum baru di
-- transaksi yang sama dengan `ALTER TYPE ... ADD VALUE`.
--
-- Seluruhnya idempoten: menjalankan ulang tidak mengubah apa pun.
-- Seluruhnya aman untuk kode LAMA: hanya menambah (kolom nullable, satu nilai
-- enum) — itu sebabnya urutannya migrasi dulu, baru merge. Kebalikannya
-- (kode dulu) membuat ingest dan ringkasan sentimen liputan gagal sampai
-- migrasi dijalankan.

-- =========================================================== BAGIAN A ====

ALTER TYPE signal_source ADD VALUE IF NOT EXISTS 'SENSOR';

ALTER TABLE mentions ADD COLUMN IF NOT EXISTS sentiment_model     text;
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS sentiment_alt       numeric(4,3);
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS sentiment_alt_model text;

-- =========================================================== BAGIAN B ====

-- Kualitas udara dulu dititipkan di DIGITAL karena SENSOR belum ada.
UPDATE metric_snapshots SET source = 'SENSOR'
WHERE  metric = 'airquality_pm25' AND source = 'DIGITAL';

UPDATE data_sources SET source = 'SENSOR'
WHERE  connector = 'openmeteo_air_quality' AND source = 'DIGITAL';

-- Tiga org sisa verifikasi production (8–10 Okt 2026). Dihapus HANYA bila
-- memang masih kosong: org yang ternyata punya proyek dibiarkan, dan itu
-- terlihat dari jumlah baris yang dikembalikan (harus 3).
DELETE FROM organizations o
WHERE  o.slug IN ('uji-yt-1791474316', 'uji-sentimen-1791645465', 'uji-verif-1791647047')
  AND  NOT EXISTS (SELECT 1 FROM projects p WHERE p.org_id = o.id)
RETURNING o.slug;
