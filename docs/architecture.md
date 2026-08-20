# Arsitektur

## Bentuk sistem

```
Next.js (App Router)
      │  REST /v1, JWT
      ▼
FastAPI ──► services/   logika domain murni, tanpa I/O, mudah dites
      │  └► ai/         provider LLM + agen + envelope
      ▼
Postgres 16 + pgvector          Redis            OpenSearch
  RLS per tenant                cache/queue      pencarian teks
      ▲
Worker (Celery/arq): ingestion konektor, embedding, clustering,
                     estimasi model forecast, generasi laporan
```

## Keputusan dan alasannya

**Postgres + pgvector, bukan vector database terpisah.**
Volume mention untuk satu proyek riset berada di kisaran ratusan ribu sampai
beberapa juta baris — pgvector dengan indeks HNSW menanganinya tanpa masalah,
dan mempertahankan satu sumber kebenaran menghindari kelas bug "embedding ada,
barisnya sudah dihapus". Pindah ke vector store khusus adalah keputusan yang
bisa ditunda sampai ada bukti kebutuhan.

**RLS, bukan filter aplikasi.**
Deployment pemerintah dan BUMN akan diaudit. Isolasi yang bergantung pada
setiap developer mengingat menulis `WHERE org_id = ...` akan gagal suatu saat.
RLS memindahkan jaminan itu ke tempat yang tidak bisa dilupakan. Konsekuensinya:
aplikasi wajib memakai peran non-superuser, dan setiap tabel bertenant wajib
punya kebijakan.

**Logika domain sebagai fungsi murni.**
`services/poi.py`, `sampling.py`, `forecast.py`, `risk.py` tidak menyentuh
database dan tidak memanggil LLM. Ini membuat bagian yang paling perlu benar —
statistiknya — bisa dites dalam milidetik dan bisa diaudit oleh metodolog yang
tidak membaca kode FastAPI.

**Abstraksi provider LLM.**
Sebagian calon pengguna tidak boleh mengirim data ke luar yurisdiksi. Semua
pemanggilan model lewat `ai/provider.py`, sehingga menukar ke model on-premise
tidak menyentuh kode domain. `EchoProvider` membuat tes berjalan tanpa jaringan.

**Envelope sebagai kontrak, bukan konvensi.**
`AIEnvelope` menolak divalidasi tanpa bukti dan batasan, dan memblokir klaim
kausal tanpa desain pembanding. Diletakkan di validator karena konvensi yang
hanya ditulis di dokumen akan dilanggar saat tenggat mendekat.

## Alur data

```
COLLECT   konektor → mentions (mentah, author di-hash)
CLEAN     dedup, deteksi bahasa, normalisasi
UNDERSTAND embedding → pgvector
CLASSIFY  sentiment, emotion, topic, narrative
ANALYZE   statistik di services/, bukan di LLM
MAP       agregasi per provinsi, hanya bila n ≥ 250
PREDICT   worker mengestimasi; API menerapkan skenario
SIMULATE  ditandai is_simulation, interval melebar
RECOMMEND opsi tindakan, keputusan tetap di manusia
MEASURE   communication impact dengan kelompok pembanding
```

Statistik dihitung oleh kode statistik, bukan oleh LLM. LLM dipakai untuk
menjelaskan hasil, memberi label pada klaster, dan menyusun narasi laporan —
selalu di atas angka yang sudah dihitung deterministik.

## Skala

Untuk satu proyek nasional dengan 12 gelombang dan ~250k mention per bulan:
satu instance Postgres, dua replika API, satu worker. Pemisahan menjadi layanan
terpisah baru relevan saat ingestion melampaui kapasitas satu worker; jangan
memecah lebih awal.
