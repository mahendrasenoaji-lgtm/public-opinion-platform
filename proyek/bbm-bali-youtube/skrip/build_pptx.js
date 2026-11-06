// Deck "Kelangkaan BBM di Bali menurut komentar YouTube" — angka dari laporan versi 4
// (artifact E7TiPtANVW32KoeLQygC7v, stats_informal2.json, sampel_manual_400_label.csv).
// Pakai: npm install pptxgenjs@3.12.0 di folder kerja, lalu
//   NODE_PATH=<folder>/node_modules SKILL_DIR=<folder skill pptx> node skrip/build_pptx.js presentasi_bbm_bali_youtube.pptx
// SKILL_DIR = folder skill pptx Claude (berisi scripts/apply_theme.js, yang menulis warna tema ke berkas).
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.SKILL_DIR + "/scripts/apply_theme.js");

const OUT = process.argv[2] || "deck.pptx";

const THEME = {
  name: "BBM Bali",
  headFontFace: "Arial",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1D2124", lt1: "FFFFFF", dk2: "5D656B", lt2: "F4F4F1",
    accent1: "C4501B", accent2: "0F6B5C", accent3: "F6D9C9",
    accent4: "8F2D1A", accent5: "8A9298", accent6: "DCDFD9",
    hlink: "0F6B5C", folHlink: "8F2D1A",
  },
};
const H = THEME.colors; // hex, hanya untuk opsi yang menolak warna skema (grafik, garis grid)

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.title = "Kelangkaan BBM di Bali menurut komentar YouTube";
pres.author = "Public Opinion Platform";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

const FOOT = "Komentar YouTube · Kelangkaan BBM Bali · 11–20 Oktober 2026";

pres.defineSlideMaster({
  title: "Judul gelap",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "kicker", type: "body", x: 0.6, y: 0.75, w: 8.8, h: 0.4, fontSize: 12, bold: true, color: C.accent3, charSpacing: 2, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.2, w: 8.8, h: 1.75, fontSize: 36, bold: true, color: C.background1, valign: "top", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 3.0, w: 8.4, h: 2.0, fontSize: 16, color: C.accent3, valign: "top", margin: 0 }, text: "" } },
  ],
});

pres.defineSlideMaster({
  title: "Isi",
  background: { color: C.background1 },
  margin: [0.5, 0.5, 0.6, 0.5],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.85, fontSize: 26, bold: true, color: C.text1, valign: "top", align: "left", margin: 0 }, text: "" } },
    { text: { text: FOOT, options: { x: 0.5, y: 5.2, w: 7.5, h: 0.3, fontSize: 10, color: C.text2, margin: 0 } } },
  ],
  slideNumber: { x: 9.0, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: C.text2, align: "right" },
});

let n = 0;
const name = (s) => `${s}-${++n}`;

// angka dasar
const days = ["12 Okt", "13 Okt", "14 Okt", "15 Okt", "16 Okt", "17 Okt", "18 Okt", "19 Okt", "20 Okt"];
const total = [31, 1851, 3881, 11916, 9502, 5498, 2383, 915, 342];
const neg = [9, 515, 1306, 4221, 3407, 2132, 936, 345, 115];
const score = [-0.419, -0.263, -0.291, -0.314, -0.302, -0.326, -0.344, -0.330, -0.300];

const label = (txt) => ({ fontSize: 12, color: C.text2 });

// ---------- 1. Judul ----------
pres.addSection({ title: "Pembuka" });
{
  const s = pres.addSlide({ masterName: "Judul gelap", sectionTitle: "Pembuka" });
  s.addText("KOMENTAR YOUTUBE · 11–20 OKTOBER 2026", { placeholder: "kicker" });
  s.addText("Kelangkaan BBM di Bali, menurut kolom komentar YouTube", { placeholder: "title" });
  s.addText("36.319 komentar dan balasan dari antrean pertama di SPBU sampai pemerintah menyatakan pasokan normal. Pembaruan 6 November 2026: sampel manual 400 komentar, kamus informal-2, dan analisis jaringan.", { placeholder: "body" });
  s.addNotes("Deck ini meringkas komentar YouTube tentang kelangkaan BBM di Bali selama sepuluh hari, 11 sampai 20 Oktober 2026. Sumbernya hanya YouTube; pemberitaan media tidak dihitung. Angka sentimen memakai penilai lexicon-id-1+informal-2 dan sudah sama dengan angka di platform Public Opinion sejak penilaian ulang 6 November.");
}

// ---------- 2. Ringkasan angka ----------
pres.addSection({ title: "Temuan utama" });
{
  const s = pres.addSlide({ masterName: "Isi", sectionTitle: "Temuan utama" });
  s.addText("Sekitar dua pertiga komentar bernada negatif", { placeholder: "title" });
  // kartu utama
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 1.35, w: 4.1, h: 3.55, fill: { color: C.accent1 }, line: { type: "none" }, rectRadius: 0.08, objectName: name("kartu-utama") });
  s.addText("±67%", { x: 0.8, y: 1.6, w: 3.6, h: 1.25, fontSize: 66, bold: true, color: C.background1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true, objectName: name("angka-utama") });
  s.addText("perkiraan komentar negatif di seluruh 36.319 komentar (rentang 64–70%), dihitung dari sampel manual 400 komentar ditambah hasil alat", { x: 0.8, y: 2.95, w: 3.55, h: 1.7, fontSize: 15, color: C.background1, valign: "top", margin: 0, isTextBox: true, objectName: name("label-utama") });
  // 2x2
  const stats = [
    ["36.319", "komentar dan balasan dalam jendela 11–20 Okt"],
    ["458", "video yang dikomentari (dari 527 video ditemukan)"],
    ["22.803", "akun berbeda, nama diganti kode acak"],
    ["70%", "negatif di antara 18.592 komentar yang bisa dinilai alat (51% dari semua)"],
  ];
  stats.forEach(([big, small], i) => {
    const x = 4.9 + (i % 2) * 2.35, y = 1.35 + Math.floor(i / 2) * 1.85;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.2, h: 1.7, fill: { color: C.background2 }, line: { type: "none" }, rectRadius: 0.08, objectName: name("kartu") });
    s.addText(big, { x: x + 0.2, y: y + 0.15, w: 1.85, h: 0.6, fontSize: 28, bold: true, color: C.text1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true, objectName: name("angka") });
    s.addText(small, { x: x + 0.2, y: y + 0.78, w: 1.85, h: 0.85, fontSize: 12, color: C.text2, valign: "top", margin: 0, isTextBox: true, objectName: name("label") });
  });
  s.addNotes("Angka utama ada dua. 70 persen negatif hanya berlaku untuk komentar yang bisa dinilai alat, yaitu sekitar separuh data. Untuk seluruh komentar, perkiraan terbaik adalah sekitar 67 persen negatif, rentang 64 sampai 70 persen, karena sampel manual menunjukkan komentar yang tidak dinilai alat juga mayoritas negatif.");
}

// ---------- 3. Grafik harian ----------
{
  const s = pres.addSlide({ masterName: "Isi", sectionTitle: "Temuan utama" });
  s.addText("Puncak 15 Oktober, nada tetap negatif sesudahnya", { placeholder: "title" });
  s.addChart(
    [
      { type: pres.charts.BAR, data: [
          { name: "Dinilai negatif", labels: days, values: neg },
          { name: "Komentar lain", labels: days, values: total.map((t, i) => t - neg[i]) },
        ], options: { barDir: "col", barGrouping: "stacked", chartColors: [H.accent1, H.accent3], barGapWidthPct: 40 } },
      { type: pres.charts.LINE, data: [{ name: "Rata-rata skor (kanan)", labels: days, values: score }],
        options: { chartColors: [H.dk1], lineSize: 2, lineDataSymbol: "circle", lineDataSymbolSize: 7, secondaryValAxis: true, secondaryCatAxis: true } },
    ],
    {
      x: 0.5, y: 1.25, w: 6.3, h: 3.85, objectName: name("grafik-harian"),
      showLegend: true, legendPos: "b", legendFontSize: 11, legendFontFace: "+mn-lt", legendColor: H.dk2,
      valAxes: [
        { showValAxisTitle: true, valAxisTitle: "Komentar per hari", valAxisTitleFontSize: 11, valAxisTitleColor: H.dk2, valAxisMinVal: 0, valAxisMaxVal: 12000, valAxisMajorUnit: 3000, valAxisLabelColor: H.dk2, valAxisLabelFontSize: 11, valAxisLabelFontFace: "+mn-lt", valAxisLabelFormatCode: "#,##0", valGridLine: { color: H.accent6, size: 0.75 } },
        { showValAxisTitle: true, valAxisTitle: "Rata-rata skor", valAxisTitleFontSize: 11, valAxisTitleColor: H.dk2, valAxisMinVal: -0.5, valAxisMaxVal: 0, valAxisMajorUnit: 0.1, valAxisLabelColor: H.dk2, valAxisLabelFontSize: 11, valAxisLabelFontFace: "+mn-lt", valAxisLabelFormatCode: "0.0", valGridLine: { style: "none" } },
      ],
      catAxes: [
        { catAxisLabelColor: H.dk2, catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt", catGridLine: { style: "none" } },
        { catAxisHidden: true },
      ],
    }
  );
  const pts = [
    ["11.916", "komentar pada Kamis 15 Okt, sepertiga seluruh data. Hari itu video Gubernur Koster diprotes petugas SPBU beredar."],
    ["−0,26 – −0,34", "rata-rata skor harian pada hari dengan ratusan komentar, termasuk sesudah pasokan dinyatakan normal 19 Okt."],
  ];
  pts.forEach(([big, small], i) => {
    const y = 1.35 + i * 1.9;
    s.addText(big, { x: 7.1, y, w: 2.4, h: 0.55, fontSize: 22, bold: true, color: C.accent1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true, objectName: name("angka") });
    s.addText(small, { x: 7.1, y: y + 0.6, w: 2.4, h: 1.2, fontSize: 13, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: name("label") });
  });
  s.addNotes("Batang menunjukkan jumlah komentar per hari dalam waktu WITA, bagian gelap adalah yang dinilai negatif oleh alat. Garis adalah rata-rata skor sentimen, hanya dari komentar yang bisa dinilai. Tanggal 11 Oktober tidak ditampilkan karena belum ada video tentang krisis. Penurunan menjelang 20 Oktober sebagian karena video yang terbit sesudah 20 Oktober tidak ikut diambil.");
}

// ---------- 4. Linimasa ----------
{
  const s = pres.addSlide({ masterName: "Isi", sectionTitle: "Temuan utama" });
  s.addText("Lonjakan komentar bertepatan dengan peristiwa", { placeholder: "title" });
  const ev = [
    ["12 Okt", "31", "Antrean mulai dilaporkan; Gubernur memanggil Pertamina"],
    ["13 Okt", "1.851", "Kendala bongkar muat kapal; 92 SPBU buka 24 jam"],
    ["14 Okt", "3.881", "Antrean 3 km, warga pingsan; Dirut Pertamina minta maaf; rapat terbatas Presiden"],
    ["15 Okt", "11.916", "Video Gubernur Koster diprotes petugas SPBU beredar"],
    ["16 Okt", "9.502", "Ganjil-genap pembelian BBM diumumkan untuk 17–19 Okt"],
    ["17 Okt", "5.498", "Ganjil-genap mulai berlaku"],
    ["19 Okt", "915", "Menteri ESDM: distribusi normal, cadangan dinaikkan ke 15 hari"],
  ];
  const x0 = 0.5, step = 1.3, lineY = 1.95;
  s.addShape(pres.shapes.LINE, { x: x0 + 0.3, y: lineY, w: step * (ev.length - 1), h: 0, line: { color: C.accent6, width: 2 }, objectName: name("garis-waktu") });
  ev.forEach(([d, cnt, txt], i) => {
    const x = x0 + i * step;
    const peak = d === "15 Okt";
    s.addShape(pres.shapes.OVAL, { x: x + 0.15, y: lineY - 0.15, w: 0.3, h: 0.3, fill: { color: peak ? C.accent4 : C.accent1 }, line: { color: C.background1, width: 2 }, objectName: name("titik") });
    s.addText(d, { x, y: 1.3, w: 1.2, h: 0.35, fontSize: 14, bold: true, color: C.text1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true, objectName: name("tanggal") });
    s.addText([{ text: cnt, options: { bold: true, fontSize: 18, color: peak ? C.accent4 : C.accent1, breakLine: true } }, { text: "komentar", options: { fontSize: 10, color: C.text2 } }],
      { x, y: 2.3, w: 1.2, h: 0.65, margin: 0, valign: "top", isTextBox: true, objectName: name("jumlah") });
    s.addText(txt, { x, y: 3.05, w: 1.2, h: 1.95, fontSize: 12, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: name("peristiwa") });
  });
  s.addNotes("Peristiwa diambil dari judul video berita pada hari itu, hanya sebagai penanda waktu. Tidak ada klaim sebab-akibat: peristiwa dan lonjakan komentar hanya terjadi pada waktu yang sama. Tanggal 18 dan 20 Oktober tidak punya peristiwa penanda; komentarnya 2.383 dan 342.");
}

// ---------- 5. Komentar terpopuler ----------
{
  const s = pres.addSlide({ masterName: "Isi", sectionTitle: "Temuan utama" });
  s.addText("Komentar terpopuler menyorot sikap Gubernur", { placeholder: "title" });
  const q = [
    ["Ada suara jeritan rakyat \"DIAM KAMU\" hebat nih Gubenur", "1.148 suka", "label alat: positif (sindiran)", C.accent4],
    ["itulah WAJAH ASLI PEJABAT KITA… MEREKA MENGAGGAP DIRINYA SEBAGAI TUAN BUKAN PELAYAN", "849 suka", "label alat: tidak dinilai", C.text2],
    ["No respect, petugas spbu juga manusia bukan robot..", "687 suka", "label alat: tidak dinilai", C.text2],
    ["jika nggak becus ngurus, mundur itu lebih elegan....", "439 suka", "label alat: negatif", C.accent1],
  ];
  q.forEach(([t, likes, lab, col], i) => {
    const x = 0.5 + (i % 2) * 4.6, y = 1.3 + Math.floor(i / 2) * 1.9;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 4.4, h: 1.75, fill: { color: C.background2 }, line: { type: "none" }, rectRadius: 0.08, objectName: name("kartu-kutipan") });
    s.addText("“", { x: x + 0.15, y: y + 0.05, w: 0.5, h: 0.6, fontSize: 40, bold: true, color: C.accent1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true, objectName: name("tanda-kutip") });
    s.addText(t, { x: x + 0.6, y: y + 0.18, w: 3.6, h: 0.95, fontSize: 14, italic: true, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: name("kutipan") });
    s.addText([{ text: likes + "  ·  ", options: { color: C.text2 } }, { text: lab, options: { color: col, bold: true } }],
      { x: x + 0.6, y: y + 1.25, w: 3.6, h: 0.35, fontSize: 11, margin: 0, isTextBox: true, objectName: name("meta") });
  });
  s.addNotes("Semua dari video Liputan6 tanggal 15 Oktober. Komentar teratas jelas sindiran tetapi dibaca positif oleh alat. Dua komentar berikutnya kritik tanpa kata sentimen, jadi tidak dinilai. Karena itu angka sentimen adalah perkiraan nada kasar, bukan ukuran sikap. Setiap kutipan punya tautan langsung ke YouTube di laporan.");
}

// ---------- 6. Tema ----------
{
  const s = pres.addSlide({ masterName: "Isi", sectionTitle: "Temuan utama" });
  s.addText("Pemda paling disorot; semua tema negatif", { placeholder: "title" });
  const th = [
    ["Pemerintah daerah (Koster/Pemprov)", 6194, "-0,38"],
    ["Antrean & dampak harian", 5446, "-0,26"],
    ["Pemerintah pusat (Bahlil/ESDM/Presiden)", 4222, "-0,35"],
    ["Pertamina / distribusi", 2711, "-0,26"],
    ["Pariwisata & ekonomi", 1152, "-0,31"],
    ["Pengecer / harga / penimbunan", 1048, "-0,31"],
    ["Permintaan maaf / sudah normal", 921, "-0,03"],
    ["Pertamax / jenis BBM lain", 568, "-0,31"],
  ].reverse();
  s.addChart(pres.charts.BAR, [{ name: "Komentar", labels: th.map((t) => `${t[0]}  (${t[2].replace("-", "−")})`), values: th.map((t) => t[1]) }], {
    x: 0.5, y: 1.25, w: 6.4, h: 3.85, barDir: "bar", objectName: name("grafik-tema"),
    chartColors: [H.accent1], barGapWidthPct: 45, showLegend: false,
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: H.dk1, dataLabelFontSize: 11, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "#,##0",
    catAxisLabelColor: H.dk1, catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt",
    valAxisHidden: true, valAxisMaxVal: 7500, valGridLine: { style: "none" }, catGridLine: { style: "none" },
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.15, y: 1.35, w: 2.35, h: 3.6, fill: { color: C.background2 }, line: { type: "none" }, rectRadius: 0.08, objectName: name("kartu-catatan") });
  s.addText([
    { text: "Angka dalam kurung", options: { bold: true, breakLine: true } },
    { text: "rata-rata skor sentimen tema itu (−1 sampai +1).", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 6 } },
    { text: "Paling dekat netral", options: { bold: true, breakLine: true } },
    { text: "“Permintaan maaf / sudah normal” (−0,03).", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 6 } },
    { text: "Cara menandai", options: { bold: true, breakLine: true } },
    { text: "kata kunci di teks; satu komentar bisa masuk beberapa tema, sebagian besar tidak masuk tema mana pun." },
  ], { x: 7.35, y: 1.5, w: 2.0, h: 3.35, fontSize: 12, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: name("catatan") });
  s.addNotes("Komentar yang menyebut pemerintah daerah lebih banyak daripada yang menyebut Pertamina. Tidak ada tema yang skor rata-ratanya positif. Tiga tema kecil tidak ditampilkan di grafik: curiga atau teori konspirasi 383 komentar (−0,36), ganjil-genap 268 (−0,33), sekolah atau WFH daring 216 (−0,35).");
}

// ---------- 7. Sampel manual ----------
pres.addSection({ title: "Pembaruan 6 November" });
{
  const s = pres.addSlide({ masterName: "Isi", sectionTitle: "Pembaruan 6 November" });
  s.addText("Yang tak terbaca alat pun mayoritas negatif", { placeholder: "title" });
  s.addChart(pres.charts.DOUGHNUT, [{ name: "Sampel manual 400", labels: ["Negatif", "Netral / informatif", "Tidak jelas", "Positif"], values: [279, 58, 58, 5] }], {
    x: 0.4, y: 1.2, w: 4.3, h: 3.9, objectName: name("grafik-sampel"), holeSize: 58,
    chartColors: [H.accent1, H.accent5, H.accent3, H.accent2],
    showLegend: true, legendPos: "b", legendFontSize: 11, legendFontFace: "+mn-lt", legendColor: H.dk2,
    showPercent: true, showValue: false, dataLabelColor: H.lt1, dataLabelFontSize: 11, dataLabelFontFace: "+mn-lt",
    showTitle: false,
  });
  const rows = [
    ["69,8%", "negatif dari 400 komentar sampel (65–74%)"],
    ["81,6%", "negatif dari 342 komentar yang nadanya terbaca (77–85%)"],
    ["1,2%", "positif: 5 komentar, semua pujian untuk petugas atau pemilik SPBU"],
  ];
  rows.forEach(([big, small], i) => {
    const y = 1.3 + i * 0.98;
    s.addText(big, { x: 5.0, y, w: 1.6, h: 0.6, fontSize: 28, bold: true, color: i === 2 ? C.accent2 : C.accent1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true, objectName: name("angka") });
    s.addText(small, { x: 6.7, y: y + 0.02, w: 2.8, h: 0.92, fontSize: 13, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: name("label") });
  });
  s.addText("400 komentar dari 21.020 yang tidak dinilai penilai lama (informal-1), diambil acak (seed 20261106) dan dilabeli satu per satu oleh satu pelabel.", { x: 5.0, y: 4.4, w: 4.5, h: 0.65, fontSize: 11, color: C.text2, valign: "top", margin: 0, isTextBox: true, objectName: name("metode") });
  s.addNotes("Versi pertama laporan tidak menilai 58 persen komentar karena alat tidak menemukan kata kamus, terutama pada komentar pendek. Sampel manual menunjukkan kelompok ini juga mayoritas negatif. Dugaan atau tuduhan tanpa kata evaluatif dihitung negatif; dengan aturan yang lebih ketat porsi negatif turun. Ini taksiran kasar dari satu pelabel, bukan ukuran akurasi.");
}

// ---------- 8. Kamus informal-2 ----------
{
  const s = pres.addSlide({ masterName: "Isi", sectionTitle: "Pembaruan 6 November" });
  s.addText("Kamus baru: tak terbaca turun 58% → 49%", { placeholder: "title" });
  const cols = [
    ["informal-1", "penilai lama", ["57,9%", "tidak dinilai"], ["15.299", "komentar dinilai"], ["63,3%", "negatif di antara yang dinilai"], C.background2, C.text1],
    ["informal-2", "dipakai sekarang, juga di platform", ["48,8%", "tidak dinilai"], ["18.592", "komentar dinilai"], ["69,8%", "negatif di antara yang dinilai"], C.text1, C.background1],
  ];
  cols.forEach(([nm, sub, a, b, c, bg, fg], i) => {
    const x = 0.5 + i * 3.05;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.3, w: 2.85, h: 3.7, fill: { color: bg }, line: { type: "none" }, rectRadius: 0.08, objectName: name("kolom") });
    s.addText([{ text: nm, options: { bold: true, fontSize: 18, breakLine: true } }, { text: sub, options: { fontSize: 11 } }], { x: x + 0.25, y: 1.45, w: 2.4, h: 0.7, color: fg, margin: 0, valign: "top", isTextBox: true, objectName: name("nama") });
    [a, b, c].forEach(([big, small], k) => {
      const y = 2.3 + k * 0.9;
      s.addText([{ text: big, options: { bold: true, fontSize: 24, breakLine: true } }, { text: small, options: { fontSize: 11 } }], { x: x + 0.25, y, w: 2.4, h: 0.8, color: fg, margin: 0, valign: "top", isTextBox: true, objectName: name("nilai") });
    });
  });
  const notes = [
    ["94,4%", "label negatif yang benar pada komentar yang baru dinilai (100 komentar dilabeli tanpa melihat skor alat; 87,5–97,6%)"],
    ["75%", "komentar negatif di sampel manual yang tetap tidak dinilai: kritik tanpa kata sentimen, bahasa daerah, sindiran"],
    ["+33", "kata kritik kepada pejabat (arogan, memalukan, mundur, copot, omon-omon) ditambah bentuk berimbuhan"],
  ];
  notes.forEach(([big, small], i) => {
    const y = 1.35 + i * 1.25;
    s.addText(big, { x: 6.75, y, w: 2.75, h: 0.45, fontSize: 22, bold: true, color: C.accent1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true, objectName: name("angka") });
    s.addText(small, { x: 6.75, y: y + 0.45, w: 2.75, h: 0.75, fontSize: 11, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: name("label") });
  });
  s.addNotes("Tidak ada komentar yang dulu dinilai lalu kini tidak dinilai, dan 94,9 persen label lama tetap sama. Platform Public Opinion sudah memakai informal-2 sejak 6 November dan seluruh komentar proyek ini sudah dinilai ulang: 18.358 dari 35.772 konten sesudah duplikat dibuang, 51 persen. Kelemahan yang belum diperbaiki: sindiran masih terbaca positif dan aturan negasi bisa membalik kata kedua.");
}

// ---------- 9. Organik atau buzzer ----------
pres.addSection({ title: "Akun dan jaringan" });
{
  const s = pres.addSlide({ masterName: "Isi", sectionTitle: "Akun dan jaringan" });
  s.addText("Percakapan tampak organik, bukan kampanye", { placeholder: "title" });
  const hdr = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text1 }, fontSize: 12 } });
  const rows = [
    [hdr("Pola yang diperiksa"), hdr("Hasil"), hdr("Bacaan")],
    ["Akun yang hanya berkomentar sekali", "16.912 akun (74%)", "Pola khas percakapan organik"],
    ["Porsi komentar dari 20 akun teraktif", "1,8%", "Tidak ada segelintir akun yang mendominasi"],
    ["Teks sama persis (≥30 huruf) dari ≥3 akun", "0", "Tanda salin-tempel tidak ditemukan"],
    ["Akun yang mengulang teks sama ≥3 kali", "104 akun · 1.001 komentar", "Ada penyebar narasi berulang; perlu dibaca manual"],
    ["Akun dengan ≥10 komentar dalam satu jam", "32 akun", "Bisa debat di utas, bisa penyebar pesan"],
    ["Akun yang muncul di ≥20 video", "19 akun", "Aktif tidak sama dengan dibayar"],
  ];
  s.addTable(rows, {
    x: 0.5, y: 1.35, w: 9.0, colW: [3.4, 2.1, 3.5], objectName: name("tabel-buzzer"),
    fontSize: 12, color: C.text1, fontFace: THEME.bodyFontFace,
    border: { type: "solid", pt: 0.75, color: H.accent6 }, rowH: 0.42, valign: "middle", margin: [0.04, 0.1, 0.04, 0.1],
  });
  s.addText("Satu akun tidak bisa dipastikan buzzer dari komentar saja. Yang diukur hanya pola agregat, tanpa menunjuk akun tertentu.", { x: 0.5, y: 4.55, w: 9.0, h: 0.5, fontSize: 12, italic: true, color: C.text2, margin: 0, isTextBox: true, objectName: name("catatan") });
  s.addNotes("Kelompok akun yang sangat aktif dan mengulang pesan menulis sekitar 3 persen komentar. Itu layak ditinjau manual, tetapi belum cukup untuk menyebut mereka buzzer. Pemeriksaan yang lebih kuat butuh data profil kanal seperti tanggal dibuat dan jumlah video, yang tidak ikut disimpan.");
}

// ---------- 10. Jaringan ----------
{
  const s = pres.addSlide({ masterName: "Isi", sectionTitle: "Akun dan jaringan" });
  s.addText("Seperlima akun menulis hampir separuh komentar", { placeholder: "title" });
  s.addChart(pres.charts.BAR, [{ name: "Akun", labels: ["1 video", "2", "3", "4", "5", "6+"], values: [17993, 2873, 961, 400, 207, 369] }], {
    x: 0.5, y: 1.25, w: 4.8, h: 3.85, barDir: "col", objectName: name("grafik-akun"),
    showTitle: true, title: "Akun menurut jumlah video yang dikomentari", titleFontSize: 12, titleColor: H.dk1, titleFontFace: "+mn-lt",
    chartColors: [H.accent1], barGapWidthPct: 40, showLegend: false,
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: H.dk1, dataLabelFontSize: 11, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "#,##0",
    catAxisLabelColor: H.dk2, catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt",
    valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: 20500, valGridLine: { style: "none" }, catGridLine: { style: "none" },
  });
  const pts = [
    ["21% → 46%", "4.810 akun yang berkomentar di 2 video atau lebih menulis 46% komentar"],
    ["0,07", "tumpang-tindih pengomentar tertinggi antara dua video: tidak ada gugus kanal berisi akun yang sama"],
    ["8,3%", "balasan yang diterima 10 akun teratas: tidak ada pusat tunggal"],
    ["≈70%", "porsi negatif sama untuk pengomentar sekali lewat maupun yang rajin"],
  ];
  pts.forEach(([big, small], i) => {
    const y = 1.3 + i * 0.95;
    s.addText(big, { x: 5.6, y, w: 1.6, h: 0.5, fontSize: 20, bold: true, color: C.accent1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true, objectName: name("angka") });
    s.addText(small, { x: 7.25, y, w: 2.25, h: 0.88, fontSize: 11, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: name("label") });
  });
  s.addNotes("Jaringan dibangun dari kode akun acak, video yang dikomentari, dan tautan balasan. Jaringan tidak bisa dipakai menebak nada komentar yang belum dinilai: balasan searah dengan induknya hanya 49 persen, sama dengan peluang kebetulan. Timbal balik antarakun tidak bisa diukur karena YouTube menyatukan balasan atas balasan ke komentar induk.");
}

// ---------- 11. Metode dan batas ----------
pres.addSection({ title: "Penutup" });
{
  const s = pres.addSlide({ masterName: "Isi", sectionTitle: "Penutup" });
  s.addText("Cara data diambil dan batas membacanya", { placeholder: "title" });
  const blocks = [
    ["Cara data diambil", [
      "YouTube Data API v3 resmi, 12 kata kunci (mis. “bbm langka bali”, “antrean spbu bali”)",
      "Video terbit 11–20 Okt yang menyebut Bali dan BBM/SPBU/Pertamina",
      "Semua komentar dan balasan, disaring 11 Okt 00:00 – 20 Okt 23:59 WITA",
      "Nama akun diganti kode acak",
    ]],
    ["Batas membacanya", [
      "Nada teks bukan sikap terhadap kebijakan; sindiran sering terbaca positif",
      "49% komentar tidak bisa dinilai alat",
      "Pengomentar memilih sendiri; tidak mewakili warga Bali",
      "Tidak ada klaim sebab-akibat antara peristiwa dan lonjakan",
    ]],
  ];
  blocks.forEach(([head, items], i) => {
    const x = 0.5 + i * 4.6;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.3, w: 4.4, h: 3.2, fill: { color: C.background2 }, line: { type: "none" }, rectRadius: 0.08, objectName: name("kartu") });
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: 1.5, w: 0.45, h: 0.45, fill: { color: i ? C.accent1 : C.accent2 }, line: { type: "none" }, objectName: name("lingkaran") });
    s.addText(String(i + 1), { x: x + 0.25, y: 1.5, w: 0.45, h: 0.45, fontSize: 16, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: name("nomor") });
    s.addText(head, { x: x + 0.85, y: 1.5, w: 3.3, h: 0.45, fontSize: 18, bold: true, color: C.text1, fontFace: THEME.headFontFace, valign: "middle", margin: 0, isTextBox: true, objectName: name("judul-kartu") });
    s.addText(items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1 } })),
      { x: x + 0.25, y: 2.15, w: 3.95, h: 2.7, fontSize: 14, color: C.text1, valign: "top", paraSpaceAfter: 6, margin: 0, isTextBox: true, objectName: name("daftar") });
  });
  s.addNotes("Data dikumpulkan 5 November 2026 pukul 13.27 UTC: 527 video, 36.319 komentar dan balasan; 425 komentar yang ditulis sesudah 20 Oktober dibuang. Data lengkap, skrip, dan laporan ada di repo Public Opinion, folder proyek/bbm-bali-youtube, dan di proyek KELANGKAAN BBM BALI pada platform.");
}

// ---------- 12. Kesimpulan ----------
{
  const s = pres.addSlide({ masterName: "Judul gelap", sectionTitle: "Penutup" });
  s.addText("KESIMPULAN", { placeholder: "kicker" });
  s.addText("Kritik terarah pada sikap pejabat, bukan hanya antrean", { placeholder: "title" });
  s.addText([
    { text: "Sekitar 67% komentar negatif; tidak ada tema yang bernada positif.", options: { bullet: true, breakLine: true } },
    { text: "Puncak 15 Okt bertepatan dengan beredarnya video Gubernur Koster; nada tetap negatif setelah pasokan normal.", options: { bullet: true, breakLine: true } },
    { text: "Tidak tampak kampanye terkoordinasi; sekelompok kecil akun mengulang pesan dan perlu dibaca manual.", options: { bullet: true } },
  ], { placeholder: "body" });
  s.addNotes("Tiga pesan utama. Pertama, nada komentar didominasi kritik. Kedua, lonjakan dan kritik paling tajam muncul ketika video Gubernur menegur petugas SPBU beredar, dan nada tidak membaik setelah pemerintah menyatakan pasokan normal. Ketiga, pola akun tampak organik. Langkah lanjut yang mungkin: penilai kedua untuk sampel manual, dan pemeriksaan profil kanal untuk akun yang mengulang pesan.");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("ok", OUT);
})();
