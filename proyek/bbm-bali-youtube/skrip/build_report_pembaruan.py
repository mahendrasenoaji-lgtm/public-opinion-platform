"""Sisipkan bagian "Pembaruan 6 November" dan "Analisis jaringan sosial" ke laporan dasar.

Pakai (setelah analyze_bbm.py dan build_report.py dijalankan dengan penilai informal-2):
    python3 -X utf8 skrip/build_report_pembaruan.py laporan_dasar.html laporan_pembaruan_sampel_manual.html

Angka di fragmen ini berasal dari: sampel_manual_400_label.csv, sampel_buta_100_informal2.csv,
UKUR_ULANG_INFORMAL2.md, dan keluaran skrip/sna_jaringan.py pada CSV berlabel informal-2.
"""

import sys

src, out = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def rep(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:70])
    s = s.replace(old, new)


rep("<title>BBM Bali di Kolom YouTube</title>", "<title>BBM Bali Sampel Manual</title>")

CSS = """.upd { background: var(--surface); border: 1px solid var(--line); border-left: 4px solid var(--accent); padding: 18px 20px; display: grid; gap: 14px; }
.upd .eyebrow { color: var(--accent); }
.stack { display: flex; height: 22px; border: 1px solid var(--line); overflow: hidden; }
.stack span { display: block; height: 100%; min-width: 2px; }
.s-neg { background: var(--social); } .s-net { background: var(--muted); } .s-pos { background: var(--accent); } .s-unk { background: var(--social-soft); }
.upd .legend i { border: 1px solid var(--line); }
.upd ul { margin: 0; padding-left: 20px; display: grid; gap: 6px; }
h3 { font-family: var(--display); font-size: 1.15rem; margin: 6px 0 0; text-wrap: balance; }
"""
rep(".note ul { margin: 0;", CSS + ".note ul { margin: 0;")

# papan angka: satu tile tambahan, taksiran dari sampel manual
rep('</span></div>\n</div>\n\n<section>\n  <h2>Percakapan memuncak',
    '</span></div>\n  <div><b>±67%</b><span>perkiraan negatif di seluruh komentar (rentang 64–70%), dari sampel manual 400 komentar</span></div>\n'
    '</div>\n\n<section>\n  <h2>Percakapan memuncak')

UPD = """
<section class="upd" aria-labelledby="upd-h">
  <div class="eyebrow">Pembaruan 6 November 2026</div>
  <h2 id="upd-h">Komentar yang tidak dinilai alat: sampel manual dan kamus yang diperluas</h2>
  <p>Versi pertama laporan ini memakai penilai <code>lexicon-id-1+informal-1</code>, yang tidak menilai 21.020 dari 36.319 komentar (58%) karena tidak menemukan satu pun kata kamusnya. Makin pendek komentarnya, makin sering ia menyerah: 71–78% untuk komentar sampai lima kata, 32% untuk komentar 21 kata atau lebih. Angka 63% negatif dari versi itu hanya berlaku untuk 42% komentar yang memuat kata kamus. Seluruh angka sentimen di halaman ini (papan angka, grafik harian, tabel tema) sekarang memakai penilai yang diperluas, <code>lexicon-id-1+informal-2</code>.</p>

  <h3>Sampel manual: apa isi komentar yang tidak dinilai</h3>
  <p>400 komentar yang tidak dinilai <code>informal-1</code> diambil acak (seed 20261106), dibaca satu per satu, dan diberi label nada.</p>
  <div class="stack" role="img" aria-label="Dari 400 komentar sampel: negatif 69,8%, netral atau informatif 14,5%, tidak jelas 14,5%, positif 1,2%">
    <span class="s-neg" style="width:69.8%"></span><span class="s-net" style="width:14.5%"></span><span class="s-unk" style="width:14.5%"></span><span class="s-pos" style="width:1.2%"></span>
  </div>
  <div class="legend"><span><i class="s-neg"></i>negatif 279 (69,8%)</span><span><i class="s-net"></i>netral atau informatif 58 (14,5%)</span><span><i class="s-unk"></i>tidak jelas 58 (14,5%)</span><span><i class="s-pos"></i>positif 5 (1,2%)</span></div>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Ukuran</th><th class="num">Hasil</th><th class="num">Rentang 95%</th></tr></thead>
    <tbody>
      <tr><td>Negatif, dari 400 komentar sampel</td><td class="num">69,8%</td><td class="num">65–74%</td></tr>
      <tr><td>Negatif, dari 342 komentar yang nadanya terbaca</td><td class="num">81,6%</td><td class="num">77–85%</td></tr>
      <tr><td>Positif, dari 400 komentar sampel</td><td class="num">1,2%</td><td class="num">0,5–2,9%</td></tr>
      <tr><td>Negatif di seluruh 36.319 komentar (komentar “tidak jelas” dihitung bukan negatif)</td><td class="num">±67%</td><td class="num">64–70%</td></tr>
    </tbody>
  </table></div>

  <h3>Kamus informal diperluas: informal-2</h3>
  <p>Kata yang lolos dari alat berupa kritik tanpa kata sentimen baku: “arogan”, “memalukan”, “mundur”, “copot”, “omon-omon”, juga bentuk berimbuhan seperti “kebohongan” atau “dimarahin”. Kamus informal ditambah 33 kata kritik kepada pejabat dan sejumlah bentuk berimbuhan. Kata dipilih dari komentar di luar sampel manual dan dari maknanya; kata positif yang di komentar ini sering dipakai dalam tuntutan (“harusnya mengayomi rakyat”) sengaja tidak ditambahkan.</p>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Ukuran (36.319 komentar)</th><th class="num">informal-1</th><th class="num">informal-2</th></tr></thead>
    <tbody>
      <tr><td>Komentar tidak dinilai</td><td class="num">21.020 (57,9%)</td><td class="num">17.727 (48,8%)</td></tr>
      <tr><td>Komentar dinilai</td><td class="num">15.299</td><td class="num">18.592</td></tr>
      <tr><td>Negatif di antara yang dinilai</td><td class="num">63,3%</td><td class="num">69,8%</td></tr>
      <tr><td>Komentar yang dulu dinilai lalu kini tidak dinilai</td><td class="num">–</td><td class="num">0</td></tr>
      <tr><td>Label tetap sama pada komentar yang dulu sudah dinilai</td><td class="num">–</td><td class="num">94,9%</td></tr>
    </tbody>
  </table></div>
  <ul>
    <li><b>Presisi pada komentar yang baru dinilai:</b> 100 komentar acak yang dulu tidak dinilai dan kini dinilai dilabeli tanpa melihat skor alat. Dari yang alat beri label negatif, 94,4% memang negatif (rentang 87,5–97,6%).</li>
    <li><b>Masih banyak yang terlewat:</b> 75% komentar negatif di sampel manual (208 dari 279) tetap tidak dinilai. Kamus tidak bisa menutup kritik tanpa kata sentimen, bahasa daerah, atau sindiran. Karena itu perkiraan ±67% dari sampel manual tetap menjadi ukuran terbaik untuk seluruh komentar, dan 70% adalah porsi negatif di antara komentar yang dinilai alat.</li>
    <li><b>Sindiran:</b> komentar positif hampir tidak ada di kelompok yang tidak dinilai (5 dari 400, semuanya pujian untuk petugas SPBU, pemilik SPBU, atau Gubernur Jawa Barat). Sebaliknya sekitar 22% komentar yang dinilai alat berlabel positif, sebagian jelas sindiran seperti “hebat nih Gubenur”.</li>
    <li><b>Jaringan tidak bisa mengisi kekosongan ini:</b> dari 962 pasangan komentar induk dan balasan yang sama-sama dinilai, hanya 49% searah, sama dengan peluang kebetulan (±49%). Hasil analisis jaringan ada di bagian terakhir halaman.</li>
  </ul>
  <p class="meta">Batasan: pelabel tunggal (satu pembaca, tanpa penilai kedua), jadi ini taksiran kasar dan bukan ukuran akurasi. Dugaan atau tuduhan tanpa kata evaluatif (“pasti ada oknum yang bermain”) dihitung negatif; dengan aturan yang lebih ketat porsi negatif turun dan netral naik. Sampel manual hanya mewakili komentar yang tidak dinilai <code>informal-1</code>. Perubahan kamus masuk ke platform Public Opinion lewat PR #46 (digabung 6 November 2026), dan seluruh komentar proyek ini di platform sudah dinilai ulang dengan <code>informal-2</code> pada hari yang sama. Platform menghitung 35.772 komentar karena duplikat dibuang; 18.358 di antaranya dinilai (51%), sejalan dengan angka di halaman ini.</p>
</section>
"""
rep("\n<section>\n  <h2>Percakapan memuncak", UPD + "\n<section>\n  <h2>Percakapan memuncak")

rep("ada di folder <code>~/Documents/bbm-bali-youtube</code>", "ada di repo Public Opinion, folder <code>proyek/bbm-bali-youtube</code>,")
rep("pada platform Public Opinion.</p>\n</section>\n</div>", "pada platform Public Opinion (angka platform: <code>informal-2</code>, dinilai ulang 6 November 2026). Sampel manual 400 baris berlabel: berkas sampel_manual_400_label.csv; label per komentar dari informal-2: berkas label_informal2_per_komentar.csv.</p>\n</section>\n" + """
<section aria-labelledby="sna-h">
  <div class="eyebrow">Analisis jaringan sosial</div>
  <h2 id="sna-h">Siapa berkomentar di mana, dan siapa membalas siapa</h2>
  <p>Jaringan dibangun dari data yang sudah ada: kode akun acak, video yang dikomentari, dan tautan balasan ke komentar induk. Tidak ada nama akun. Yang diukur adalah bentuk percakapannya, bukan niat atau afiliasi akun.</p>
  <div class="board" aria-label="Ringkasan jaringan">
    <div><b>21%</b><span>akun (4.810) berkomentar di 2 video atau lebih; mereka menulis 46% komentar</span></div>
    <div><b>105</b><span>akun muncul di 10 video atau lebih</span></div>
    <div><b>0,07</b><span>tumpang-tindih pengomentar tertinggi antara dua video (indeks Jaccard)</span></div>
    <div><b>8,3%</b><span>balasan diterima oleh 10 akun teratas</span></div>
  </div>

  <h3>Akun menurut jumlah video yang dikomentari</h3>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Jumlah video</th><th class="num">Akun</th><th></th><th class="num">Porsi akun</th></tr></thead>
    <tbody>
      <tr><td>1</td><td class="num">17.993</td><td class="barcell"><span style="width:100%"></span></td><td class="num">78,9%</td></tr>
      <tr><td>2</td><td class="num">2.873</td><td class="barcell"><span style="width:16.0%"></span></td><td class="num">12,6%</td></tr>
      <tr><td>3</td><td class="num">961</td><td class="barcell"><span style="width:5.3%"></span></td><td class="num">4,2%</td></tr>
      <tr><td>4</td><td class="num">400</td><td class="barcell"><span style="width:2.2%"></span></td><td class="num">1,8%</td></tr>
      <tr><td>5</td><td class="num">207</td><td class="barcell"><span style="width:1.2%"></span></td><td class="num">0,9%</td></tr>
      <tr><td>6 atau lebih</td><td class="num">369</td><td class="barcell"><span style="width:2.1%"></span></td><td class="num">1,6%</td></tr>
    </tbody>
  </table></div>

  <h3>Yang terlihat</h3>
  <ul class="qs">
    <li><b>Dua lapisan pengomentar.</b> Empat dari lima akun hanya muncul di satu video. Seperlima akun berpindah-pindah video dan menghasilkan hampir separuh komentar, jadi sebagian besar suara datang dari pengomentar yang ikut banyak video, bukan dari penonton sekali lewat.</li>
    <li><b>Penonton tiap video hampir terpisah.</b> Dari pasangan video yang masing-masing punya minimal 100 pengomentar, tumpang-tindih tertinggi hanya 0,07 (dua video dari satu kanal berita langsung), dan tidak ada gugus video yang saling berbagi pengomentar dalam jumlah besar. Tidak tampak kelompok kanal yang dihuni akun yang sama.</li>
    <li><b>Balasan menyebar.</b> Ada 5.062 balasan, 4.275 pasangan akun yang unik, dan 4.561 akun terlibat. Sepuluh akun yang paling sering dibalas hanya menerima 8,3% balasan, sehingga tidak ada satu atau dua akun yang menjadi pusat. 453 akun menerima tiga balasan atau lebih. 330 balasan ditulis akun untuk komentarnya sendiri.</li>
    <li><b>Satu gugus besar, banyak gugus kecil.</b> Jaringan balasan terpecah menjadi 597 gugus. Yang terbesar berisi 3.047 akun (67% dari akun yang terlibat) dan tersambung karena akun yang sama muncul di banyak utas. Gugus lain paling banyak 10 akun.</li>
    <li><b>Nada tidak berbeda menurut pola.</b> Di antara komentar yang dinilai alat (<code>informal-2</code>), 70,2% negatif untuk akun yang berkomentar sekali, 69,4% untuk akun yang berkomentar lebih dari sekali di satu video, dan 69,1% untuk akun yang berkomentar di tiga video atau lebih. Pengomentar yang rajin tidak lebih negatif daripada pengomentar sekali lewat.</li>
  </ul>

  <div class="note">
    <b>Bacaannya dan batasnya</b>
    <ul>
      <li>Temuan ini searah dengan pemeriksaan buzzer di atas: tidak ada pola gugus akun yang tertutup, tidak ada hub tunggal, dan nada tidak berbeda menurut keaktifan. Itu bukan bukti bahwa tidak ada koordinasi. Jaringan ini tidak memuat data profil kanal atau waktu pembuatan akun.</li>
      <li>YouTube menyatukan balasan atas balasan ke komentar induknya, sehingga hanya satu tingkat tautan yang terlihat. Karena itu timbal balik antarakun (A membalas B, B membalas A) tidak bisa diukur, dan nilainya nol di data ini.</li>
      <li>Persentase negatif pada butir terakhir berasal dari alat, jadi hanya berlaku untuk 51% komentar yang dinilai.</li>
      <li>Jaringan menjelaskan siapa berada di mana. Ia tidak dipakai untuk menebak nada komentar yang belum dinilai, karena balasan hanya searah dengan induknya sebesar peluang kebetulan (49%).</li>
    </ul>
  </div>
</section>
</div>""")

open(out, "w", encoding="utf-8").write(s)
print("ok", len(s))
