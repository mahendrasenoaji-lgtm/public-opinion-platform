# AI Governance

## Kontrak keluaran

Setiap keluaran AI melewati `AIEnvelope` (`apps/api/app/ai/envelope.py`) dan
tercatat di tabel `ai_outputs`. Envelope menolak divalidasi bila:

| Kondisi | Alasan |
|---|---|
| `evidence` kosong | Klaim tanpa rujukan tidak bisa diaudit |
| `limitations` kosong | Setiap metode punya batas; menyembunyikannya adalah overclaim |
| Memuat kata kausal tanpa desain pembanding | Data observasional tidak menghasilkan sebab-akibat |
| Memuat "dipastikan", "mengendalikan opini", "menjamin" | Klaim determinasi |
| `is_simulation` tanpa penanda di `limitations` | Simulasi mudah dibaca sebagai prediksi |
| `confidence=HIGH` dengan bukti hanya `SOCIAL` | Data self-selected tidak menopang keyakinan tinggi |
| `EvidenceRef.n` antara 1 dan 4 | Risiko re-identifikasi responden |

Constraint yang sama diulang di database (`ai_outputs_evidence_not_empty`,
`ai_outputs_limitations_not_blank`) supaya jalur lain ke tabel itu tetap aman.

## ReviewAgent

Berjalan terakhir pada setiap rantai agen. Wewenangnya:

- Menurunkan confidence bila tidak ada bukti probabilistik.
- Menurunkan ke LOW bila ada bukti dengan n < 250.
- Menandai `NEEDS_REVIEW` bila bukti menyentuh isu sensitif (pemilu, kandidat,
  partai, agama, etnis).

ReviewAgent tidak bisa menaikkan confidence. Ia hanya bisa memperketat.

## Yang tidak dilakukan platform

1. **Tidak menginferensi atribut sensitif.** Segmentasi hanya memakai variabel
   yang dikumpulkan dengan consent eksplisit. Tidak ada model yang memprediksi
   agama, etnisitas, orientasi, kondisi kesehatan, atau afiliasi politik.
2. **Tidak menyimpan identitas bersama jawaban.** `respondents` dan `responses`
   tidak memuat PII. PII hidup di `respondent_identities` dengan `purge_after`
   sendiri dan akses terbatas pada kapabilitas `respondent_pii:read`.
3. **Tidak menyimpulkan kecurangan.** `services/quality.py` menghasilkan
   `quality_flag` untuk ditinjau. Keputusan mengeluarkan responden dari analisis
   dibuat manusia dan tercatat di `audit_logs`.
4. **Tidak menyatakan seseorang mengendalikan opini.** Istilah yang dipakai:
   *influence estimate*, selalu disertai metodenya.
5. **Tidak mengambil keputusan otomatis yang berdampak pada individu.**
6. **Tidak memperlakukan media sosial sebagai representasi populasi.**

## Ambang publikasi

| Ambang | Nilai | Konsekuensi |
|---|---|---|
| Sampel efektif minimum per wilayah | 250 | Di bawah ini: "data tidak cukup", bukan angka |
| Sel agregat minimum | 5 | Di bawah ini: tidak boleh jadi bukti |
| Toleransi deviasi strata | 3 pp | Di atas ini: pembobotan wajib sebelum publikasi |

Ambang boleh diperketat per deployment. Melonggarkannya memerlukan persetujuan
tertulis dan tercatat di audit log.

## Jejak audit

`ai_outputs` menyimpan `prompt_hash`, `model_version`, `method`, payload, bukti,
dan status tinjauan. Dengan itu, sebuah laporan yang terbit enam bulan lalu bisa
direkonstruksi: model mana, prompt mana, data mana, siapa yang menyetujui.
