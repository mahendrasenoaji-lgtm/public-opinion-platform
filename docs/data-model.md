# Model data

## Pemisahan yang disengaja

**`respondents` vs `respondent_identities`.**
Analisis hanya menyentuh `respondents`, yang berisi variabel demografis dan
bobot tetapi tidak berisi PII. Identitas hidup terpisah dengan `purge_after`
sendiri, sehingga penghapusan PII tidak merusak dataset analisis. Konsekuensi:
menghubungkan responden lintas gelombang memerlukan proses eksplisit, bukan
join biasa. Ini memang diinginkan.

**`metric_snapshots` sebagai satu tabel untuk semua metrik.**
Kolom `source` dan `method` wajib. Ini yang membuat aturan R1 bisa ditegakkan:
tidak mungkin menyimpan angka tanpa menyatakan asalnya. `province_code` dan
`segment` bernilai NULL untuk angka nasional/seluruh sampel, sehingga satu query
bisa mengambil nasional dan rincian sekaligus.

**`mentions.author_hash`, bukan `author_id`.**
Analisis jaringan tetap mungkin karena hash-nya konsisten, tetapi basis data
tidak menyimpan identitas akun. Untuk kebutuhan yang benar-benar memerlukan
identitas (mis. verifikasi opinion leader publik), simpan di tabel terpisah
dengan dasar hukum yang jelas.

**`ai_outputs` dengan constraint.**
Tabel ini punya CHECK constraint pada bukti dan batasan. Validasi di Pydantic
melindungi jalur API; constraint melindungi dari jalur lain — skrip, migrasi,
worker.

## Konvensi

- Semua tabel bertenant punya `org_id uuid NOT NULL` dan kebijakan RLS.
- Timestamp memakai `timestamptz`; tanggal periode memakai `date`.
- Nilai indeks disimpan `numeric(8,3)`; jangan memakai float untuk angka yang
  akan ditampilkan.
- Bobot responden `numeric(8,4)`, default 1.0 sebelum pembobotan.
- Enum di database, bukan string bebas — supaya `SignalSource` tidak melar
  diam-diam.

## Menambah tabel bertenant

1. Tambahkan `org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE`
2. Tambahkan nama tabel ke array di `db/rls.sql`
3. Tambahkan indeks yang diawali `org_id`
4. Tambahkan tes ke `tests/test_tenant_isolation.py`

Keempatnya di commit yang sama.
