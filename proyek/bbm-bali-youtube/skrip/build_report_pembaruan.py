"""Sisipkan bagian "Pembaruan 6 & 8 November" dan "Analisis jaringan sosial" ke laporan dasar.

Versi 6 (8 Nov 2026): angka sentimen dari penilai informal-4 (frasa), peta aktor dan relasi kuasa,
dan bacaan konteks atas komentar yang tetap lolos. Pakai:
    python3 skrip/build_report.py stats_informal4.json laporan_dasar.html
    python3 skrip/build_report_pembaruan.py laporan_dasar.html laporan_pembaruan_sampel_manual.html stats_informal4.json
    python3 -X utf8 skrip/build_report_pembaruan.py laporan_dasar.html laporan_pembaruan_sampel_manual.html

Angka di fragmen ini berasal dari: sampel_manual_400_label.csv, sampel_buta_100_informal2.csv,
UKUR_ULANG_INFORMAL2.md, sampel_buta_100_informal3.csv, UKUR_ULANG_INFORMAL3.md, dan keluaran
skrip/sna_jaringan.py pada CSV berlabel informal-3.
"""

import json
import sys

src, out = sys.argv[1], sys.argv[2]
ST = json.load(open(sys.argv[3], encoding="utf-8"))


def fmt(x, d=0):
    """Angka gaya Indonesia: titik ribuan, koma desimal."""
    t = f"{x:,.{d}f}"
    return t.replace(",", "_").replace(".", ",").replace("_", ".")
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
  <div class="eyebrow">Pembaruan 6 dan 8 November 2026</div>
  <h2 id="upd-h">Komentar yang tidak dinilai alat: sampel manual dan kamus yang diperluas</h2>
  <p>Versi pertama laporan ini memakai penilai <code>lexicon-id-1+informal-1</code>, yang tidak menilai 21.020 dari 36.319 komentar (58%) karena tidak menemukan satu pun kata kamusnya. Makin pendek komentarnya, makin sering ia menyerah: 71–78% untuk komentar sampai lima kata, 32% untuk komentar 21 kata atau lebih. Angka 63% negatif dari versi itu hanya berlaku untuk 42% komentar yang memuat kata kamus. Seluruh angka sentimen di halaman ini (papan angka, grafik harian, tabel tema) sekarang memakai penilai yang diperluas tiga kali: <code>informal-2</code> (6 November, kata kritik kepada pejabat), <code>informal-3</code> (8 November, kosakata bahasa daerah), dan <code>lexicon-id-1+informal-4</code> (8 November, pola frasa).</p>

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

  <h3>Kamus bahasa daerah: informal-3 (8 November)</h3>
  <p>Komentar ini ditulis dalam banyak bahasa: makian Bali (“naskleng”, “cicing”), Jawa (“pekok”, “ora becus”), logat Medan (“parah kali”), dan lain-lain. Kamus kini memuat kata bermuatan dari 13 bahasa daerah (Bali, Jawa, Sunda, Betawi, Minang, Batak/Medan, Melayu, Banjar, Palembang, Bugis/Makassar, Manado/Maluku/Papua, Madura, Sasak) beserta artinya, juga kata “tidak” dan “sangat” versi daerah. Kata yang artinya berbeda antarbahasa sengaja tidak dinilai: “sing” berarti “tidak” dalam bahasa Bali tetapi “yang” dalam bahasa Jawa, dan “seng” berarti “tidak” di Ambon tetapi “yang” di Jawa Timur.</p>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Ukuran (36.319 komentar)</th><th class="num">informal-2</th><th class="num">informal-3</th></tr></thead>
    <tbody>
      <tr><td>Komentar tidak dinilai</td><td class="num">17.727 (48,8%)</td><td class="num">16.965 (46,7%)</td></tr>
      <tr><td>Komentar dinilai</td><td class="num">18.592</td><td class="num">19.354</td></tr>
      <tr><td>Negatif di antara yang dinilai</td><td class="num">69,8%</td><td class="num">71,2%</td></tr>
      <tr><td>Label tetap sama pada komentar yang sudah dinilai</td><td class="num">–</td><td class="num">98,7%</td></tr>
      <tr><td>Komentar negatif di sampel manual yang masih tidak dinilai</td><td class="num">208 dari 279</td><td class="num">198 dari 279</td></tr>
    </tbody>
  </table></div>
  <ul>
    <li><b>Presisi kata baru:</b> dari 100 komentar acak yang baru dinilai <code>informal-3</code>, dilabeli tanpa melihat skor alat, label negatif alat benar 95,6% (86 dari 90; rentang 89–98%).</li>
    <li><b>Lima kata dibuang karena data:</b> “seneng” dan “demen” (dipakai menuduh: “seneng lihat rakyat menderita”), “merakyat” (tuntutan: “coba sedikit merakyat”), “cakep” (menilai benda), dan “rusuh” (sering “warga Bali tidak rusuh”).</li>
    <li><b>Kenaikan kecil:</b> tidak dinilai turun dua poin saja. Komentar yang tersisa sebagian besar tidak memuat makian atau kata penilaian sama sekali; maknanya negatif dari konteks, sindiran, atau kiasan (“ber-IQ primata”), yang tidak bisa ditangkap kamus mana pun.</li>
  </ul>

  <h3>Pola frasa: informal-4 (8 November)</h3>
  <p>Banyak kritik tidak memakai kata sentimen, tetapi susunan kata: “gk bisa mengatasi bbm”, “ganti aja”, “tidak punya otak”, “cari muka”, “biang kerok”, “mulutnya kaya ular berbisa”. Tiap kata di situ netral (“ganti oli”, “antrean kayak ular”); yang bermuatan adalah gabungannya. Kamus kini membaca 20 pola frasa seperti itu. Frasa yang maknanya bergantung konteks sengaja tidak dimasukkan: “rakyat tidak mampu” berarti miskin, dan “diam kamu” adalah kutipan ucapan gubernur.</p>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Ukuran (36.319 komentar)</th><th class="num">informal-3</th><th class="num">informal-4</th></tr></thead>
    <tbody>
      <tr><td>Komentar tidak dinilai</td><td class="num">16.965 (46,7%)</td><td class="num">16.241 (44,7%)</td></tr>
      <tr><td>Komentar dinilai</td><td class="num">19.354</td><td class="num">20.078</td></tr>
      <tr><td>Negatif di antara yang dinilai</td><td class="num">71,2%</td><td class="num">73,0%</td></tr>
      <tr><td>Label tetap sama pada komentar yang sudah dinilai</td><td class="num">–</td><td class="num">98,7%</td></tr>
      <tr><td>Komentar negatif di sampel manual yang masih tidak dinilai</td><td class="num">198 dari 279</td><td class="num">185 dari 279</td></tr>
    </tbody>
  </table></div>
  <ul>
    <li><b>Presisi frasa:</b> dari 100 komentar acak yang baru dinilai karena frasa, dilabeli tanpa melihat skor alat, label negatif alat benar 95% (95 dari 100; rentang 89–98%).</li>
    <li><b>Salah baca lama ikut diperbaiki:</b> “pejabat gak punya malu” dan “dirut gak tau malu” dulu terbaca positif karena negasi membalik kata “malu”; kini terbaca negatif.</li>
    <li><b>Frasa paling sering:</b> “tidak bisa bekerja/mengatasi” (607 komentar), “tidak punya hati/otak/empati” (399), “tidak pantas” (100), “ganti aja” (96), “tidak tahu diri/malu” (84).</li>
  </ul>

  <h3>Yang tetap lolos dari kamus: dibaca satu per satu</h3>
  <p>185 komentar di sampel manual bernada negatif tetapi tetap tidak dinilai kamus. Semuanya dibaca ulang untuk melihat cara kritik itu disampaikan dan kepada siapa. Ini bacaan satu pembaca (agen AI dalam sesi kerja), bukan ukuran akurasi.</p>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Cara kritik disampaikan</th><th class="num">Komentar</th></tr></thead>
    <tbody>
      <tr><td>Penilaian sikap atau kinerja tanpa kata kamus (“judes”, “gak ngurus”, “arogansinya udh keliatan”)</td><td class="num">42 (23%)</td></tr>
      <tr><td>Tuntutan (“suruh dia aja jaga 24 jam”, “tenggelamkan”, “pecad mentrinya”)</td><td class="num">33 (18%)</td></tr>
      <tr><td>Sindiran atau ironi (“INDONESIA MENUJU EMAS😂”, “hasil revolusi mental 10 th?”)</td><td class="num">29 (16%)</td></tr>
      <tr><td>Tuduhan atau kecurigaan (sabotase, KKN, amplop, “pemakan uang rakyat”)</td><td class="num">28 (15%)</td></tr>
      <tr><td>Kiasan dan julukan (“boneka ogoh-ogoh”, “air mata buaya”)</td><td class="num">11 (6%)</td></tr>
      <tr><td>Pertanyaan retoris</td><td class="num">11 (6%)</td></tr>
      <tr><td>Keluhan dampak (antre, ojol, “gajinya dari pajak rakyat”)</td><td class="num">10 (5%)</td></tr>
      <tr><td>Ajakan elektoral atau serangan partai (“2029 PDI-P tamat”)</td><td class="num">8 (4%)</td></tr>
      <tr><td>Bahasa daerah yang belum tercatat</td><td class="num">7 (4%)</td></tr>
      <tr><td>Mengutip “diam kamu” untuk mengejek</td><td class="num">6 (3%)</td></tr>
    </tbody>
  </table></div>
  <p>Sasarannya: pemerintah daerah 68 komentar, pejabat secara umum 51, pemerintah pusat 34, sesama warga (warga Bali, turis, pendatang, atau komentator lain) 15, partai 11, petugas SPBU 6. Untuk jenis kritik ini kamus mana pun tidak cukup; yang bisa membacanya adalah pembaca yang memahami kalimat utuh. Kerangka pembaca berbasis AI sudah disiapkan di platform (setiap bacaan wajib mengutip bukti dari teks komentar itu sendiri), tetapi belum dijalankan karena kunci API belum dipasang.</p>

  <h3>Yang tetap berlaku</h3>
  <ul>
    <li><b>Presisi pada komentar yang baru dinilai:</b> 100 komentar acak yang dulu tidak dinilai dan kini dinilai dilabeli tanpa melihat skor alat. Dari yang alat beri label negatif, 94,4% memang negatif (rentang 87,5–97,6%). (Ukuran <code>informal-2</code>.)</li>
    <li><b>Masih banyak yang terlewat:</b> 66% komentar negatif di sampel manual (185 dari 279) tetap tidak dinilai, juga sesudah kamus bahasa daerah dan frasa. Karena itu perkiraan ±67% dari sampel manual tetap menjadi ukuran terbaik untuk seluruh komentar, dan 73% adalah porsi negatif di antara komentar yang dinilai alat.</li>
    <li><b>Sindiran:</b> komentar positif hampir tidak ada di kelompok yang tidak dinilai (5 dari 400, semuanya pujian untuk petugas SPBU, pemilik SPBU, atau Gubernur Jawa Barat). Sebaliknya sekitar 19% komentar yang dinilai alat berlabel positif, sebagian jelas sindiran seperti “hebat nih Gubenur”.</li>
    <li><b>Jaringan tidak bisa mengisi kekosongan ini:</b> dari 1.584 pasangan komentar induk dan balasan yang sama-sama dinilai <code>informal-4</code>, 56,0% searah, hampir sama dengan peluang kebetulan (53,3%). Hasil analisis jaringan ada di bagian terakhir halaman.</li>
  </ul>
  <p class="meta">Batasan: pelabel tunggal (satu pembaca, tanpa penilai kedua), jadi ini taksiran kasar dan bukan ukuran akurasi. Dugaan atau tuduhan tanpa kata evaluatif (“pasti ada oknum yang bermain”) dihitung negatif; dengan aturan yang lebih ketat porsi negatif turun dan netral naik. Sampel manual hanya mewakili komentar yang tidak dinilai <code>informal-1</code>. Perubahan kamus masuk ke platform Public Opinion lewat PR #46 (6 November 2026), PR #48 dan PR #50 (8 November 2026). PLATFORM_NOTE</p>
</section>
"""
rep("\n<section>\n  <h2>Percakapan memuncak", UPD + "\n<section>\n  <h2>Percakapan memuncak")

A = {a["key"]: a for a in ST["actors"]}
L = {lv["level"]: lv for lv in ST["levels"]}


def _row(name, role, a):
    neg = f"{fmt(100 * a['negatif'] / a['scored'])}%" if a["scored"] else "–"
    mean = fmt(a["mean"], 2).replace("-", "−") if a["mean"] is not None else "–"
    return (f"<tr><td>{name}<div class='meta'>{role}</div></td><td class='num'>{fmt(a['n'])}</td>"
            f"<td class='num'>{fmt(100 * a['abstain'] / a['n'])}%</td><td class='num'>{neg}</td><td class='num'>{mean}</td></tr>")


level_tbl = "".join(_row(lv, "", L[lv]) for lv in ["Pemerintah daerah", "Pemerintah pusat", "BUMN energi", "Petugas lapangan", "Partai politik", "Legislatif"])
actor_tbl = "".join(_row(a["name"], a["role"], a) for a in sorted(ST["actors"], key=lambda a: -a["n"]) if a["n"] >= 50)
co = ST["co_mentions"]
ACTORS_HTML = f"""
<section aria-labelledby="aktor-h">
  <div class="eyebrow">Peta aktor dan relasi kuasa</div>
  <h2 id="aktor-h">Kepada siapa kritik diarahkan</h2>
  <p>Penilai sentimen membaca nada, tidak tahu siapa yang dibicarakan. Peta aktor menandai pejabat, lembaga, dan partai yang disebut, lalu menaruhnya di tingkat kekuasaan: pemerintah pusat, pemerintah daerah, BUMN energi, legislatif, partai, dan petugas lapangan. Jabatan dicatat per Oktober 2026. Afiliasi politik orang yang berkomentar tidak ditebak.</p>
  <div class="board" aria-label="Ringkasan aktor">
    <div><b>{fmt(L['Pemerintah daerah']['n'])}</b><span>komentar menyebut pemerintah daerah (gubernur, pemprov)</span></div>
    <div><b>{fmt(L['Pemerintah pusat']['n'])}</b><span>menyebut pemerintah pusat (presiden, menteri, ESDM)</span></div>
    <div><b>{fmt(L['BUMN energi']['n'])}</b><span>menyebut Pertamina</span></div>
    <div><b>{fmt(100 * co['tanpa_aktor'] / ST['comments'])}%</b><span>komentar tidak menyebut aktor atau jabatan sama sekali</span></div>
  </div>

  <h3>Menurut tingkat kekuasaan</h3>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Tingkat</th><th class="num">Komentar</th><th class="num">Tidak dinilai</th><th class="num">Negatif*</th><th class="num">Skor rata-rata</th></tr></thead>
    <tbody>{level_tbl}</tbody>
  </table></div>

  <h3>Menurut aktor (disebut 50 kali atau lebih)</h3>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Aktor</th><th class="num">Komentar</th><th class="num">Tidak dinilai</th><th class="num">Negatif*</th><th class="num">Skor rata-rata</th></tr></thead>
    <tbody>{actor_tbl}</tbody>
  </table></div>
  <p class="meta">* Negatif di antara komentar yang dinilai alat. Satu komentar bisa menyebut beberapa aktor dan dihitung untuk masing-masing.</p>

  <h3>Yang terlihat</h3>
  <ul class="qs">
    <li><b>Sorotan tidak mengikuti kewenangan formal.</b> Pasokan BBM diurus Pertamina di bawah kebijakan Kementerian ESDM; pemerintah daerah tidak memegang pasokan. Namun pemerintah daerah disebut {fmt(L['Pemerintah daerah']['n'])} kali, lebih banyak daripada pemerintah pusat ({fmt(L['Pemerintah pusat']['n'])}) dan Pertamina ({fmt(L['BUMN energi']['n'])}). Lonjakan ini bertepatan dengan beredarnya video gubernur menegur petugas SPBU pada 15 Oktober; ia menunjukkan ke mana perhatian tertuju, bukan siapa yang bertanggung jawab.</li>
    <li><b>Menteri dan gubernur sama-sama disorot keras.</b> Bahlil Lahadalia (Menteri ESDM, juga Ketua Umum Golkar) disebut {fmt(A['bahlil']['n'])} kali dengan {fmt(100 * A['bahlil']['negatif'] / A['bahlil']['scored'])}% negatif; Wayan Koster (Gubernur Bali) {fmt(A['koster']['n'])} kali dengan {fmt(100 * A['koster']['negatif'] / A['koster']['scored'])}% negatif. {fmt(co['pusat_dan_daerah'])} komentar menyebut pusat dan daerah sekaligus: menuntut keduanya bertanggung jawab (“Bahlil dan Koster harus dipecat”), atau memperdebatkan siapa yang semestinya disalahkan (“cb marahnya ke menteri nya langsung”).</li>
    <li><b>Kritik menjalar ke partai, tidak merata.</b> PDI Perjuangan, partai gubernur, disebut {fmt(A['pdip']['n'])} kali (“petugas partai”, “tenggelamkan PDIP 2029”). Golkar, partai yang dipimpin Menteri ESDM, hanya {fmt(A['golkar']['n'])} kali. Komentator mengaitkan gubernur dengan partainya jauh lebih sering daripada mengaitkan menteri dengan partai yang ia pimpin.</li>
    <li><b>Relasi atas–bawah.</b> {fmt(co['pejabat_dan_petugas'])} komentar menyebut pejabat dan petugas SPBU sekaligus. Dalam 20 contoh acak, 19 membela petugas (“kau kira pegawai SPBU tu robot”, “suruh gubernurnya jadi petugas SPBU seminggu”) dan menempatkan pejabat sebagai pihak yang menekan; satu sisanya saran netral. Nada negatif pada baris “Petugas lapangan” di tabel adalah nada terhadap pejabatnya, bukan terhadap petugas.</li>
    <li><b>Pembanding dari luar.</b> Dedi Mulyadi (Gubernur Jawa Barat) disebut {fmt(A['kdm']['n'])} kali dengan skor rata-rata hampir netral ({fmt(A['kdm']['mean'], 2).replace('-', '−')}): ia dipakai sebagai contoh pemimpin yang “turun dan memberi”, untuk membandingkan.</li>
    <li><b>Relasi antarwarga.</b> Sebagian kritik tidak ditujukan ke atas, melainkan ke samping: warga Bali, turis asing, atau pendatang (“pulau yang dikuasai bule”, sindiran soal rasisme). Di sampel yang dibaca ulang, 15 dari 185 komentar negatif menyasar sesama warga.</li>
  </ul>
  <div class="note">
    <b>Batas membaca peta aktor</b>
    <ul>
      <li>Menyebut tidak sama dengan menyalahkan. Peta ini menghitung siapa yang disebut, bukan arah tuduhan; arah tuduhan butuh pembacaan kalimat utuh.</li>
      <li>Kata jabatan umum (“gubernur”) dihitung ke tingkatnya, bukan ke orang tertentu, karena juga dipakai untuk gubernur provinsi lain.</li>
      <li>Kewenangan formal yang disebut di atas adalah gambaran umum tata kelola BBM, bukan penilaian hukum atas peristiwa ini.</li>
    </ul>
  </div>
</section>
"""

rep("ada di folder <code>~/Documents/bbm-bali-youtube</code>", "ada di repo Public Opinion, folder <code>proyek/bbm-bali-youtube</code>,")
rep("pada platform Public Opinion.</p>\n</section>\n</div>", "pada platform Public Opinion (angka platform: PLATFORM_VERSION). Sampel manual 400 baris berlabel: berkas sampel_manual_400_label.csv; label per komentar informal-4 (dengan kata penanda, bahasanya, aktor, dan tingkat kekuasaan): berkas komentar_youtube_bbm_bali_11-20okt2026.csv/.xlsx; label versi lama: label_informal2_per_komentar.csv, label_informal3_per_komentar.csv.</p>\n</section>\n" + """
""" + ACTORS_HTML + """
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
    <li><b>Nada tidak berbeda menurut pola.</b> Di antara komentar yang dinilai alat (<code>informal-4</code>), 73,6% negatif untuk akun yang berkomentar sekali, 71,6% untuk akun yang berkomentar lebih dari sekali di satu video, dan 72,0% untuk akun yang berkomentar di tiga video atau lebih. Pengomentar yang rajin tidak lebih negatif daripada pengomentar sekali lewat.</li>
  </ul>

  <div class="note">
    <b>Bacaannya dan batasnya</b>
    <ul>
      <li>Temuan ini searah dengan pemeriksaan buzzer di atas: tidak ada pola gugus akun yang tertutup, tidak ada hub tunggal, dan nada tidak berbeda menurut keaktifan. Itu bukan bukti bahwa tidak ada koordinasi. Jaringan ini tidak memuat data profil kanal atau waktu pembuatan akun.</li>
      <li>YouTube menyatukan balasan atas balasan ke komentar induknya, sehingga hanya satu tingkat tautan yang terlihat. Karena itu timbal balik antarakun (A membalas B, B membalas A) tidak bisa diukur, dan nilainya nol di data ini.</li>
      <li>Persentase negatif pada butir terakhir berasal dari alat, jadi hanya berlaku untuk 55% komentar yang dinilai.</li>
      <li>Jaringan menjelaskan siapa berada di mana. Ia tidak dipakai untuk menebak nada komentar yang belum dinilai, karena balasan hanya searah dengan induknya hampir sebesar peluang kebetulan (56,0% berbanding 53,3%).</li>
    </ul>
  </div>
</section>
</div>""")

import os  # noqa: E402

s = s.replace("PLATFORM_NOTE", os.environ.get("PLATFORM_NOTE", "Penilaian ulang di platform dengan <code>informal-3</code> belum selesai; angka platform bisa berbeda sementara."))
s = s.replace("PLATFORM_VERSION", os.environ.get("PLATFORM_VERSION", "sedang dinilai ulang ke <code>informal-3</code>"))
assert "PLATFORM_" not in s
open(out, "w", encoding="utf-8").write(s)
print("ok", len(s))
