# Referensi desain

`prototype.jsx` adalah prototipe yang disetujui: satu berkas React dengan data
sintetis, mencakup Command Center, Opinion Index, Signal Consistency, Narrative
Map, Public Segments, peta provinsi, Forecast + What-If, Executive Brief, dan AI
Governance.

Ia bukan kode produksi dan tidak di-bundle. Fungsinya sebagai acuan visual dan
interaksi ketika memecah tampilan menjadi komponen Next.js. Kalau ada
pertanyaan "bagaimana seharusnya ini terlihat", jawabannya ada di sini.

Yang sudah diangkat ke produksi:
- `app/globals.css` — seluruh sistem desain
- `lib/tokens.ts` — token warna, tipografi, ambang publikasi
- `components/DivergenceBand.tsx` — elemen tanda tangan
- `components/Provenance.tsx` — kaki wajib setiap kartu

Yang belum: sisa layar. Pindahkan satu per satu, jangan menyalin data sintetis
dari sini — ambil dari API.
