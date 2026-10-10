"""Set evaluasi LAPANGAN: komentar YouTube nyata, dilabeli manual.

Pelengkap `sentiment_eval.py`, bukan penggantinya. Set yang itu ditulis tim
pengembang dan hanya memberi batas ATAS; set ini memberi perkiraan lapangan
untuk satu ragam (komentar YouTube berbahasa Indonesia tentang kebijakan).

## Asal data

440 komentar tingkat atas dari 8 video bertema Makan Bergizi Gratis, ditarik
2026-10-10 lewat konektor resmi (`connectors/youtube.py`, endpoint
`commentThreads`, urut waktu, jendela 90 hari, maksimum 70 per video) dari
deployment production ke proyek uji yang langsung dihapus lagi. Yang disimpan
di sini HANYA teks: tanpa nama akun, tanpa ID komentar, tanpa ID video, dan
`@sebutan` di dalam teks dibuang. Ejaan dibiarkan apa adanya — justru itulah
yang diukur.

## Cara pelabelan, dan batasnya

- Yang dilabeli adalah NADA teks (positif / netral / negatif), sama dengan
  yang diklaim `sentiment.score()`. BUKAN sikap terhadap program.
- Sarkasme dilabeli menurut maksudnya, bukan kata-katanya.
- Satu penilai, dan penilai itu agen yang juga menulis normalisasinya. Tidak
  ada penilai kedua, jadi tidak ada angka kesepakatan antarpenilai. Ini lebih
  lemah daripada pelabelan independen yang diminta `docs/progress.md`; ia
  menggantikan "tidak ada ukuran lapangan sama sekali", bukan menggantikan
  pelabelan independen.
- Label dibuat SEBELUM kode normalisasi ditulis.
- Sampelnya 8 video yang dipilih karena ramai, hampir semuanya bernada kritik.
  Sebaran kelasnya (71% negatif) menggambarkan sampel ini, bukan opini publik.

## Belahan

`kembang` dipakai untuk menyusun kamus ragam informal; `uji` tidak dibuka
selama penyusunan dan hanya dipakai untuk melapor. Pembagiannya dari digit
pertama sha256 teks, jadi tetap dan tidak bisa dipilih-pilih. Angka yang boleh
dikutip sebagai mutu lapangan adalah angka belahan `uji`.

## Penanda

- `s` sarkasme/ironi: kata-katanya memuji, maksudnya mencela.
- `d` dukungan kepada pengkritik: komentar menyetujui atau memuji ORANG yang
  sedang mengkritik program. Nadanya bisa positif padahal sikapnya terhadap
  program menolak. Penanda ini ada supaya selisih nada-vs-sikap bisa DIHITUNG,
  bukan sekadar disebut.
- `c` campuran: memuat pujian dan celaan sekaligus; label mengikuti yang
  dominan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NamedTuple

from app.services.sentiment import EvaluationReport, evaluate, score

Split = Literal["kembang", "uji"]

FIELD_CAVEAT = (
    "Diukur pada komentar YouTube nyata tentang satu isu (Makan Bergizi "
    "Gratis), dilabeli satu penilai yang juga menyusun kamusnya. Ini perkiraan "
    "lapangan untuk ragam itu, bukan jaminan untuk isu atau platform lain. "
    "Yang dinilai adalah NADA teks, bukan sikap terhadap program."
)


class FieldItem(NamedTuple):
    text: str
    label: str
    split: Split
    flags: str = ""


def labeled(split: Split) -> list[tuple[str, str]]:
    """Pasangan (teks, label) satu belahan — bentuk yang diterima `evaluate()`."""
    return [(i.text, i.label) for i in FIELD if i.split == split]


@dataclass(frozen=True, slots=True)
class FieldReport:
    """Mutu ragam informal pada belahan `uji`, berdampingan dengan leksikon baku.

    `baseline` ada supaya perbaikannya bisa dibaca sebagai selisih pada data
    yang SAMA, bukan dua angka dari dua set berbeda.
    """

    n_total: int
    n_dev: int
    informal: EvaluationReport
    baseline: EvaluationReport
    #: Dari komentar belahan `uji` yang DIPREDIKSI positif: berapa banyak,
    #: berapa yang sebenarnya dukungan kepada pengkritik (penanda `d`), dan
    #: berapa yang label nadanya justru negatif. Inilah alasan persentase
    #: "positif" pada komentar tidak boleh dibaca sebagai dukungan.
    predicted_positive: int
    predicted_positive_supporting_critic: int
    predicted_positive_actually_negative: int
    #: Sarkasme dihitung pada SELURUH set (kedua belahan): jumlahnya terlalu
    #: sedikit untuk dibelah, dan tidak ada aturan yang disetel untuknya.
    sarcasm_n: int
    sarcasm_correct: int


def evaluate_field() -> FieldReport:
    """Ukur ragam informal pada komentar nyata. Fungsi murni, tanpa I/O."""
    test = [i for i in FIELD if i.split == "uji"]
    pairs = [(i.text, i.label) for i in test]
    predicted_positive = [i for i in test if score(i.text, register="informal").label == "positif"]
    sarcasm = [i for i in FIELD if "s" in i.flags]
    return FieldReport(
        n_total=len(FIELD),
        n_dev=len(FIELD) - len(test),
        informal=evaluate(pairs, register="informal", caveat=FIELD_CAVEAT),
        baseline=evaluate(pairs, register="baku", caveat=FIELD_CAVEAT),
        predicted_positive=len(predicted_positive),
        predicted_positive_supporting_critic=sum("d" in i.flags for i in predicted_positive),
        predicted_positive_actually_negative=sum(
            i.label == "negatif" for i in predicted_positive
        ),
        sarcasm_n=len(sarcasm),
        sarcasm_correct=sum(
            score(i.text, register="informal").label == i.label for i in sarcasm
        ),
    )


# ruff: noqa: E501, RUF001
FIELD: list[FieldItem] = [
    FieldItem("Peralatannya bekas semua seperti chiler bekas kulkas bekas dll pantas menciptakan ladang baru korupsi mbg😮😮", "negatif", "uji"),
    FieldItem("Semua gara2 keserakahan mereka. Banyak korban mereka gk perduli. Uang yg lebih penting buat mereka yg punya kuasa", "negatif", "uji"),
    FieldItem("Percumah dpr gak mungkin dengar", "negatif", "uji"),
    FieldItem("Kariawan mbh kontol", "negatif", "uji"),
    FieldItem("dasar anak abah", "negatif", "uji"),
    FieldItem("Jangan cuma pintar bicara,bicarala untuk kesejahteraan rakyat, bicara cuma ingris² trus, rakyat butuh yang berbobot untuk rakyat.", "negatif", "uji"),
    FieldItem("Pecat. Aja. Lah. 😡", "negatif", "uji"),
    FieldItem("Hgfghfefgdfbddffsrggfethg😢😢😢😢😢😢rggffdb", "netral", "uji"),
    FieldItem("Plesse ikut komika juga pak ..", "netral", "uji"),
    FieldItem("Lo bukan hilang ingatan 70% tapi hilang kewarasan 70% tapi kayak nya itu Masi Fress chiken katsu nya", "negatif", "uji"),
    FieldItem("BRENGSEK.....UDA MATI HATINYA...LEBIH BICARA,SAMA LEMBU DARI PADA SAMA MANUSIA", "negatif", "uji"),
    FieldItem("Mulut cemot/ buruk , saya guru nyata yang sekolah anak rakyat Indonesia", "negatif", "uji"),
    FieldItem("Kenapa prabowo bilang sakit perut biasa", "netral", "uji"),
    FieldItem("SUMPAH AKU SAMPE NANGIS😢MBG HARUS DIBUBARKAN!", "negatif", "uji"),
    FieldItem("Emang mbg menghina kaum ibu kayak ortu nya gak bisa masak malah kercunan", "negatif", "uji"),
    FieldItem("Ayolah media\" indonesia jgn kau makan uang nya soros", "negatif", "uji"),
    FieldItem("Alhamdulillh ada yg mewakili keluhan rkyt ..❤❤❤❤❤", "positif", "uji", "d"),
    FieldItem("apalah", "netral", "uji"),
    FieldItem("Sakarepmu congormu podo bosok tujuane opo to wingi gk ribut terus digawe keracunan haram nguntal gajian buta picek solusine opo munyuk tuo", "negatif", "uji"),
    FieldItem("minus 100%>> MBG gagal..", "negatif", "uji"),
    FieldItem("Maaaaataaaaaap betuuuuuuul sekaliiiiiiiii❤❤❤❤❤❤❤❤❤", "positif", "uji", "d"),
    FieldItem("Woi Prabowo aji** udah deh kokumsi makanan mbg", "negatif", "uji"),
    FieldItem("Alaaahh...paling ujung\"nya bica MBG wo..wo..saya SDH muak sama presiden spt kamu", "negatif", "uji"),
    FieldItem("itu jidat atau apa😂", "negatif", "uji"),
    FieldItem("menejek nati kena karma mbg kenakkarma", "negatif", "uji"),
    FieldItem("bang dia itu cuma pura pura hilang ingatan biar diperhatiin jadi kita diprank bg aduh🤦", "netral", "uji"),
    FieldItem("Tidak mnjawab, msih membanggakan diri. Gila sii", "negatif", "uji"),
    FieldItem("Ayo viralkan lagi", "netral", "uji"),
    FieldItem("kenapa harus memaksakan ngasih mbg udah tau banyak yg keracunan bukan bergiji terus memaksakan mau membunuh warga indonesia pak persiden hentikan tida ada mangpaatnya malahan dampaknya segala bahan baku pada naik harganya pada mahal apalagi sekarang melihat banyak yg keracunan banyak mbg yg di buang tida di makan di rumah buatan mamah2nya yg higenis bersih belum pernah ada berita keracunan hentikan pak prabowo jangan memaksakan", "negatif", "uji"),
    FieldItem("Inilah suara ibu mamak bunda yang sebenarnya", "positif", "uji", "d"),
    FieldItem("Hanya TAMBAH HUTANG..... Apapun ALASANNYA....", "negatif", "uji"),
    FieldItem("Yg mmbobolkan BUMN. Adili PK.", "negatif", "uji"),
    FieldItem("Prabowo keras kepala mengapa MBG tidak cepat di hentikan.", "negatif", "uji"),
    FieldItem("yg keras diatas dengar, joget2 ok gas , parahh. ndas mu", "negatif", "uji"),
    FieldItem("MBG di hapus ajalah tida aman takut nya ada korban lagi bapa pejabat kasian orang tua", "negatif", "uji"),
    FieldItem("Bener bgt bu smga aja ajab dri allh cepet di buktikan ma umat nya yg serakah", "negatif", "uji", "d"),
    FieldItem("Binatang saja ndk gitu", "negatif", "uji"),
    FieldItem("Berarti Indonesia 🇮🇩 cuma ikut²an atau meniru mereka.Tapi Indonesia 🇮🇩 gagal dan amburadul karena malah menjadi ladang korupsi orang² yg katanya beragama 🤔", "negatif", "uji"),
    FieldItem("Hulu sia tah jenong", "negatif", "uji"),
    FieldItem("Iya bu ,ukt gk d lihat penghasilan ortu nya ,pdhal sy 1 bln cm 1,5 ,pendapatan tp kok ukt 4,5 juta berat bagi sy kerja cr ayam keliling aja sdh umur 60 ,anak minta kuliah semoga sy d beri sehat biar bs cari ,uang untuk byr ukt di unesa srby", "negatif", "uji"),
    FieldItem("Gini katanya pemimpin kentir hanya 0.00 % yg keracunan, walau cuma 1 nyawa itu nyawa manusia tir..kentir", "negatif", "uji"),
    FieldItem("😭😭😭😭😭😭😭😭😭😭😭 😭😭😭😭😭😭😭😭😭😭😭", "negatif", "uji"),
    FieldItem("Ini semua muka2.penjilat ini manusia 2 mantan koruptor dan ada yg belum pernah diproses.", "negatif", "uji"),
    FieldItem("Betul nu Annete...ayo suarakan terus...biar mata nya prabowo terbuka sbgai presiden jangan terlalu bdoh dan tolol", "negatif", "uji", "d"),
    FieldItem("Situasi skrang. rakyat kcil lgi sulit. Cari krja. Sulit cari makan . ini sriuss PK. mhn brilah Klayakan. Ciptkn lpngan krja. Kades pantau anggaran. Byk yg dikorup. Direkayasa. Diglmbungkankn. Bikin jln asal jdi. TDK brkwalitas. Jln CPT rusak. Disaat periode PK jkw. Mhn diaudit. Turunkan Tim KPK. Byk lurah yg Kya mndadak. Pemda bungkam. TDK ada respon. TKS.", "negatif", "uji"),
    FieldItem("Betul", "positif", "uji", "d"),
    FieldItem("BIADAD & tidak punya simpati ke korban", "negatif", "uji"),
    FieldItem("Gua doain di penjara", "negatif", "uji"),
    FieldItem("Dasar manu sia tak bradap ah malas lah aku ke marin aku makan mbg ikan nila ju ga ada belatung nya 😢😢😢", "negatif", "uji"),
    FieldItem("Bukan 70% tapi orang yang ngeledek 100%", "negatif", "uji"),
    FieldItem("Betul v👍👍👍👍👍👍", "positif", "uji", "d"),
    FieldItem("sangat di stop MBG Jagan sampai anak cucu kt lemah pasca keracunan", "negatif", "uji"),
    FieldItem("Terima kasih perhatian BP PTESIDEN dan BPM KEU.Semoga para pensiunan mendapatkan bantuan tambhan gaji pensiun uang dihaharapkan dari.para pensiun yg umurnya sudah pada tua(60 _80 th) jangan dikibuli Yang mana diumumkan tgl 15_9_26 masuk rekening yernyata belum.kan menjadi kecewa padahal hsrga kebituhan pokok.sudah membumbunh tiggi ,demikian harapan kami. Demikian ada banyak salahnya kamohon maaf.", "negatif", "uji", "c"),
    FieldItem("Yang setuju dia di penjara kumpul 👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻👇🏻", "negatif", "uji"),
    FieldItem("Parah banget kariyawan ny", "negatif", "uji"),
    FieldItem("Share lok Biar tak tonyor tuh mulut", "negatif", "uji"),
    FieldItem("Yg membuat kita orang tua macam mau gila, anak2 kita sehat makan bergizi, lihatlah pintar2 mereka dan tumbuh besar, kami org tua yg kasih makan bahkan negara kami rakyat yg kasih makan, kalimat makan bergizi gratis itu saja sudah menghina kami sebagai rakyat, seolah miskin dan ga pernah makan enak padahal murahan kali menu mbg itu daripada makanan kami setiap hari, ga malu pemerintah berkoar koar di pbb menyebut rakyatnya miskin padahal kamilah rakyat dgn pajak yg brutal itu telah membuat negri ini masih hidup, seharusnya pemerintah malu karena kekayaan negri Indonesia yg super kaya paling kaya didunia ini tapi rakyat miskin, pinjaman luar negri sana sini, kemana perginya kekayaan negri kami? Kapan kalian akan merasa cukup? Umur semakin tua, usia tak bisa dibeli, kalau mati ga berguna triliunan harta itu jd utk apa kalian menimbun harta? Harta kotor lagi, setelah membuat malu dan kacau harga pasar akibat mbg, ada racun pula, ya Allah beri kesabaran biar ga gilak kami sebagai orang tua juga rakyat", "negatif", "uji"),
    FieldItem("Yess...good", "positif", "uji"),
    FieldItem("MBG ajang bagi² duit antar gerombolan MAFIA", "negatif", "uji"),
    FieldItem("Bantuan gizi berikan uang ke ortunya, aman", "netral", "uji"),
    FieldItem("Banyak untung Danantara Berarti bunga tinggi menyulitkan Rakyat InsyaAllah coleb", "negatif", "uji"),
    FieldItem("❤UNTUK PEENGUSAHA NAKAL DAN PEJABAT NAKAL PERLU REGULASI APA DI UPGRADE ❤", "netral", "uji"),
    FieldItem("Lu mau juga kaya gitu🤬🤬🤬", "negatif", "uji"),
    FieldItem("Harus di gitalisasi : Solusi Sistem MBG \"Anti-Korupsi & Anti-Keracunan\": 1. Persiapan & Pengelolaan Makanan Vendor wajib belanja bahan baku transparan ke Kopdes via QRIS/Barcode manifest, proses masak diawasi Smart AI-CCTV (higienitas & kematangan), serta absensi online siswa pukul 07.30 (ala BPJS) untuk mengunci porsi akurat agar tidak mubazir (sisa porsi untuk satpam). 2. Penyajian & Penerimaan Makanan ( cod system / Pembayaran): Makanan dikemas dalam tray bersekat, lalu dana cair sesuai ketentuan hanya jika siswa/guru melakukan Foto Unboxing & Scan QR di sekolah. (Tidak ada kehadiran/barang, uang negara tidak keluar).", "netral", "uji"),
    FieldItem("Presiden Prabowo Ganti Presiden Pemilu 2029 iya 👍", "negatif", "uji"),
    FieldItem("Mbg segera di tindak kan tegas di hentikan lihat itu yang keracunan mau mbunuh orang pake makanan nama nya", "negatif", "uji"),
    FieldItem("Manik tidak memiliki kapasitas dia hanya mantan wartawan", "negatif", "uji"),
    FieldItem("MBG itu memang buat ladang korupsi para pajabat , makanya biar di demo di kritik tidak mau dengar, indonesia sudah di penuhi hama tikus berdasi.", "negatif", "uji"),
    FieldItem("ada yang masih waras, kalaupun mbg mencegah stunting emang sehari sekali bisa kah 😂😂😂", "negatif", "uji"),
    FieldItem("MBG di Indonesia hanya memberikan kesempatan pejabat untuk berbuat korupsi karena pejabat nya masih lapar dan rakus , maka nya di Indonesia tidak cocok adanya MBG.", "negatif", "uji"),
    FieldItem("Siapa sih yg memulai proses MBG nya tega banget sih,udah kayak koruptor aja 😡😡", "negatif", "uji"),
    FieldItem("Ada ada saja Indonesia", "netral", "uji"),
    FieldItem("Bomon tadiiii lagi", "netral", "uji"),
    FieldItem("MBG sebenarnya bagus Tp sayangnya harga kebutuhan sehari ganti harga smua tnpa d imbangi kenaikan gaji .. Sebelum ada MBG harga2 tidak seperti ini", "negatif", "uji", "c"),
    FieldItem("Bismillah assalamualaikum bu semangat buat suara rakyat kecil sembako mahal rakyat kelaparan aku dukung hayu buk", "positif", "uji", "dc"),
    FieldItem("Wawancara exsekutif semoga kami berdoa bp Prabowo diberi kesehatan seklga besar bp berjuang trs untuk bangsa amiin ya robbal,alamin", "positif", "uji"),
    FieldItem("Langsung aja di diskualifikasi tidak boleh melamar kerja dimanapun", "negatif", "uji"),
    FieldItem("c", "netral", "uji"),
    FieldItem("Apalagi anak aku SD tapi ada yang beracun tapi ternyata ada stiker yang kalau mau makan mdg itu harus jamnya mau makan 9", "netral", "uji"),
    FieldItem("Saya mau menyampaikan tentang keracunan MBG kenapa MBG makanan bergizi gratis tapi kalo beracun MBG lebih baik dibilang makanan beracun gratis lebih baik di tutup aja MBG karena sudah banyak yang keracunan MBG karena itu saya setuju di tutup MBG ini banyak anak kita yang keracunan apa kita tidak kasihan harusnya kita sayang kepada anak-anak saya setuju yang bilang tutup MBG saya setuju dan Meding bawa bekal dari Rumah masing masing kenapa saya bilang kayak gitu karena banyak keracunan dan saya hanya bilang tutup MBG TERIMA KASIH 😡🤬🤬😡🤬😡😡🤬😡", "negatif", "uji"),
    FieldItem("Di kaplok ae rai ne col", "negatif", "uji"),
    FieldItem("😢 Aku dua hari dua malam diare berat usai makan makanan mbg. Dan beberapa siswa saya sakit perut setelah rutin makan mbg. Aih mbg....kehadiranmu telah banyak mengurai cerita duka dan sampai kini penyelenggara tetap diam", "negatif", "uji"),
    FieldItem("Macamnya sengaja meracuni anak2.", "negatif", "uji"),
    FieldItem("MAmPUS KAMU DI ISTANA INILAH ISI HATI RAKYAT SEKARANG APAKAH DIISTANA MAU MENDENGAR PALING KATA BOWO ,,MASA BODO PALING JAWAB PIMPIANA ,ME MANG GW PIKIRIN ,ITULAH JAWABNY DARI ISTANA PANTASKAH ,PIMPINANA MENJAWAB RAKYAT BEGITU HAMPIR 1 THN ,TAK ADA RAKYAT SEJATERA ,MALA TSK ADA PERJAAN ,USAHA KECIL DIMINTA PAJAK ,MBG DIRACUNI , APA MEMANG MSU MEMBUNUH ANAK SISWA , SUPAYA BODOH SDHLAH ,RAKYAT MINTA DIGANTI DG PURBAYA DN SYUKUR MANDAR ATU SDM GUBERNUR BANDUNG AHOK JUGA BOLEH MACMUD MD INILAH KAMI PILIH YG BISA MEM PERHATIKN EKONOMI RAKYAT YG TDK MINTA PAJAK RAKYAT BOWO UDAH CUKUPLAH PIMPINANA MU SMPAI SINI CUKUP", "negatif", "uji"),
    FieldItem("Yg jlas hnya MBK Najwa yg hebat. Yg lain hnya snyum. trtawa. Takut. Seakan Brgetar. Hal ini kan cuma skdar Konsultasi dlm pmbnahan\"", "positif", "uji", "c"),
    FieldItem("Banyak mulut kau.ingin juga dilantik luuuu.keistana. cari jalan lain luuu ikut SJ Anis luuu", "negatif", "uji"),
    FieldItem("MBG😢😢😢", "negatif", "uji"),
    FieldItem("Pak.udah stop aja mbg nya", "negatif", "uji"),
    FieldItem("Kalau negara lain mungkin tidak dikorup, klau Indonesia MBG jadi ladang korupsi AKIRNYA tidak bergizi", "negatif", "uji"),
    FieldItem("🐖🐖🐖🐖🐖🐖🐖", "negatif", "uji"),
    FieldItem("#MakanBeracunGratis , tagar", "negatif", "uji"),
    FieldItem("Hentikan MBG...stop..kurup...", "negatif", "uji"),
    FieldItem("Ya gak kesitu lah bu , \"menghina dunia pendidikan dan seorang perempuan\" kejauhan Bu... seperti dipaksakan ..! Carilah kalimat yang gampang di cerna , Bu", "negatif", "uji"),
    FieldItem("Kalau di Indonesia mbg diganti Viking atau makanan snake", "netral", "uji"),
    FieldItem("Dengan pemutakhiran, program nggak buang-buang sumber daya", "positif", "uji"),
    FieldItem("INDONESIA ITU SEBUAH BRAND, GARUDA ITU LOGONYA. MERAH PUTIH ITU BENDERA, PANCASILA ITU IDEOLOGINYA. DENGAN SUMBER DAYA ALAMNYA YG MELIMPAH HARUSNYA INDONESIA MAMPU MEMBANGUN EKOSISTEM SENDIRI, SEPERTI ARSENAL, BELAJARLAH DARI ARSENAL!!", "netral", "uji"),
    FieldItem("Empok stres", "negatif", "uji"),
    FieldItem("DALAM KONTEKS BERNEGARA MBA NANA SANGAT PERRR. PELAKU HARUS HUKUMAN BERAT.", "negatif", "uji"),
    FieldItem("Critanya ttng negara luar Mulu PK. Yg rakyat nya PDA makmur.", "negatif", "uji"),
    FieldItem(". apa.lupa . p.prabowo.bilang.indonesia.2029.suram.2030 akan. bubar", "netral", "uji"),
    FieldItem("Karyawan mbg nya kok kaya yg anterin mbg di skolah gw yak😭", "netral", "uji"),
    FieldItem("Harus di he tikan tu mbg pak buk kasihan anak 2 buk", "negatif", "uji"),
    FieldItem("Mengurangi populasi manusia ky nya MBG ini gw punya anak gw pesenin jgn di mkn dan sekolah nya pun udh gw blgn kepalah sekolah jgn terima MBG Lg SDH byk korban keracunan,.", "negatif", "uji"),
    FieldItem("Dikurbanin aja bang buat idul adha thn depan lumayan jadi bakso enak tuh", "negatif", "uji"),
    FieldItem("doraemon aja udah hilang dr chanel tv indonesia tp doraemon cacat produk satu ini semoga cepet nyusul", "negatif", "uji"),
    FieldItem("Makanan yang seharusnya bergizi tetapi menjadi mencelakai,", "negatif", "uji"),
    FieldItem("Iya lah loh ga kebagian sih , coba kalau loh ikut utung , pasti ga mbacot bgtu 😂😂😂", "negatif", "uji"),
    FieldItem("Memang sudah di rencanakan. Rakyat Indonesia di buat skr menderita ini penjajahan kepada rakyat ganti semua dr MPR DPR dan presiden serta para menterinya ganti semua SMP kroni kroninya", "negatif", "uji"),
    FieldItem("Aduh rambutku hilang 70%", "netral", "uji"),
    FieldItem("heh pala lapa nga pola diam🤬", "negatif", "uji"),
    FieldItem("Jahat bngt, semoga karma nya cepet datang ke orang\"yang hati nya jahat. Biadab semua maruk sama uang. Semoga balasan nya cepat datang", "negatif", "uji"),
    FieldItem("MBK Najwa. Mhn smpaikn jga ttng kmu 50. Dan amanat dri publik. Mhn tunjukn ijsh PK jkw. Agar kmlut. Gumerang slma ini. Bubarr. Mhn adili. Lintas hukum. Scra trbuka. Agar rakyat tentram. TDK ikut curiga. Dsb.", "netral", "uji"),
    FieldItem("Mudah2an suara ibu di dengar prabowo dan kroni2nya", "positif", "uji", "d"),
    FieldItem("Di luar sana niatnya tulus demi mencerdaskan rakytnya beda sama di sini bnyk tikusnya", "negatif", "uji"),
    FieldItem("Setuju rakyat tidak membayar pajak", "positif", "uji", "d"),
    FieldItem("Bubarkan mbg.", "negatif", "uji"),
    FieldItem("Sangat2 setuju bun...", "positif", "uji", "d"),
    FieldItem("Gila negara di urus orang tida bener", "negatif", "uji"),
    FieldItem("BETUL KORUPSI SEMAKIN MERAJALELA mbak", "negatif", "uji", "d"),
    FieldItem("Mental sudah koruptor... apapun programnya tidak akan bisa berjalan sukses .", "negatif", "uji"),
    FieldItem("Semogah sehat selalu Bu karna ibu yg selalu koar2 memperjuangkan rakyat", "positif", "uji", "d"),
    FieldItem("NKRI kan banyak komisi,DPR ada komisi artinya bagi2 rupiah", "negatif", "uji"),
    FieldItem("Hapus saja mbg. Itu", "negatif", "uji"),
    FieldItem("Bang minimal pake wik ke tu kepala lu hilang setega botak di muka", "negatif", "uji"),
    FieldItem("DAMPAK yg paling pasti Prabowo \"tidak akan terpilih lagi\" di Pilpres 2029. Presiden Prabowo memang tegas tetapi tidak cerdas. Ketika melantik Kapolri yg baru, Prabowo berpesan agar meneruskan memberantas mavia Narkoba dan Judol (judi one line). TETAPI \"tidak sama sekali\" menyebut meningkatan memberantas Korupsi yg digembar gemborkan sendiri oleh Prabowo.😂", "negatif", "uji"),
    FieldItem("Raja😮", "netral", "uji"),
    FieldItem("Ya Allah kok tega tega nya SPPG diam saja.", "negatif", "uji"),
    FieldItem("TUNTUT DAN LENGSERKAN PRESIDEN RI KLO MASIH TERUS MENJALANKAN PROGRAM MBG. BUBARKAN MBG. KLO PRESIDEN TIDAK MAU DILENGSERKAN.", "negatif", "uji"),
    FieldItem("Dah duit nya aja kasi ke ibunya biar efesiensi", "netral", "uji"),
    FieldItem("Klau sebut prabowo persiden keliru. Yg betol lawak yg betol", "negatif", "uji"),
    FieldItem("Pak can we cut the bullshiets Kalo Kita bisa Cari tahu secara super gampang ya. Go Mbak Nana", "negatif", "uji", "c"),
    FieldItem("Stop MBG anak2 banyak yang keracunan ❗❗ dari pada korban meninggal dunia ❗❗ stop MBG", "negatif", "uji"),
    FieldItem("Betul sekali IBu 🔥🔥👍👍👍", "positif", "uji", "d"),
    FieldItem("Sppg nya harus bertanggung jawab, kalau tidak mau ditutp dan diganti dengan yg lebih baik dan bertanggung jawab", "negatif", "uji"),
    FieldItem("Gelut yuk", "negatif", "uji"),
    FieldItem("Banyak anak2 pejabat pasti sekolahnya gak ada yg nerima MBG, kalo ada MBG pun mereka pasti sama kayak orangtua murid lainnya yang jadi korban MBG", "negatif", "uji"),
    FieldItem("Makan beracun gratis...terjadi di mana-mana...banyak membawa korban...mengapa tetap bersikukuh melanjutkan mbg yg banyak masalah?", "negatif", "uji"),
    FieldItem("Mbg bubarkan aja,rakyat sekarang udah cerdas,Gisi udah cukup,gak usah mbg,", "negatif", "uji"),
    FieldItem("Ini di racuin ...makan basi bau dah kecium..rasa ga enak", "negatif", "uji"),
    FieldItem("Betul banget ibu ini...Krn kami para ibu lebih cinta dan tau gmn hemat nya bikin makanan sehat..wlo dg dana seadanya...", "positif", "uji", "d"),
    FieldItem("Disana ada keracunan juga ya ?", "netral", "uji"),
    FieldItem("Tapi tetap aja berjalan anda di abaikan bu", "negatif", "uji"),
    FieldItem("Bangsa indonesia bisa keluar dari. Musibah. Dan medapatka. Sulusi yg baik. Amin", "positif", "uji"),
    FieldItem("Susah melawas penguasa ini bu", "negatif", "uji"),
    FieldItem("Pakkk pakkk. rakyat kalaw cari uangnya lancar masalah makan gampang pak. Masalahnya rakyat cari kerja ajah susah, misinya mensejahterakan rakyat tpi pajak dinaikin terus. Memang kita sekarang tidak perang sama segara lain, tapi perang pemerintah Bpk sama rakyat pak😢", "negatif", "uji"),
    FieldItem("Etless jidat gua gak jendol cetas😂😂😂😂😂", "netral", "uji"),
    FieldItem("Deleu ku sia Prabowo...kalakuan sia Tah , nte becus pisan jadi pemimpin..ges tutup.mbg .nepi KA iraha oge baleg", "negatif", "uji"),
    FieldItem("👍", "positif", "uji"),
    FieldItem("Harus nya gini oh tidak otakku ilang😛😛😛😛😛😛😛", "netral", "uji"),
    FieldItem("Sudah hampir menyeluruh rakyat indonesia menyuarakan tutup mbg, krn tdk ada nilai plusnya bagi murid bahkan malah meracuni para siswa dari makanan gratis tsb, sementara para korban keracunan makanan pemerintah seakan akan lepas tanggung jawab dari kejadian tsb.", "negatif", "uji"),
    FieldItem("Ttep kalo blm ngerasain . Ibu2 komplek ibu2 desa yg dpt MBG merasa bangga trus ..", "netral", "uji"),
    FieldItem("Diskusi ke presiden Prabowo.11 sept 2026.", "netral", "uji"),
    FieldItem("Gk suka MBG ya udah gk usah diterima biar yg mau aja, toh bnyk jg yg bersyukur, kl org ini kan org kya js gk mwrasa dibantu , coba liat org miskin pasti sangat terbantu, pagi2 gk repot bikin bekal buat anaknya", "positif", "uji"),
    FieldItem("Makin hari pubg makin serem ya 😥 Aku emosi jadinya sama mbj Jadi makin banyak murid keracunan kan 🤬🤬 Enggak bisa ini harus ditangani ini 🤬", "negatif", "uji"),
    FieldItem("Itulah akibat penguasanya tak berijazah. TDK sekolah. Jokowi dan Termul termulnya TDK peduli akan pentingnya pendidikan. Krn dia dan anaknya TDK sekolah bisa jadi penguasa???? Utk maling SDA milik bangsa ini.", "negatif", "uji"),
    FieldItem("Kapau rapat pbb tau kan ngarah nya kmna, bukan semua negara itu dian akan merdeka nya Palestina melainkan mereka lagi berjuang, good job pak presiden ku pak prabowo, semnagat iya pak sehat sehat great of you", "positif", "uji"),
    FieldItem("Sial betul kita bisa lahir di indonesia", "negatif", "uji"),
    FieldItem("Mantap MBG maju terus pecahkan rekor dunia 🌏 biar capai 10 juta. Orang 😊😊😊😊😊😊😅😅😅😅", "negatif", "uji", "s"),
    FieldItem("MBG ganti uang saja minta ganti rugi ke pemerintah pusat", "negatif", "uji"),
    FieldItem("1 keluarga d kasih 15ribu pasti lebih bermanfaatnya keluarga tinggal nambahi 15ribu makan sampai 3 kali bergizi, manfaatnya lebih luas keluarga terbantu ekonominya makan gax akan terbuang sia sia karna setiap keluarga tau cara agar anaknya makan, sekarang gara gara MBG bahan pokok mahal beras dan minyak goreng naik trs", "negatif", "uji"),
    FieldItem("Pemerintah sekarang menjerat rakyat , menghidupkankoroptor .", "negatif", "uji"),
    FieldItem("Anda buat susah semua orang", "negatif", "uji"),
    FieldItem("Tangkap aja ibu ini", "negatif", "uji"),
    FieldItem("Bukan saya ikut urusan orang kalau itu terjadi asli pada diri elu kalau mau hilang igatan 70 persen saya dan orang orang doa kan yang setuju komen amin❤❤", "netral", "uji"),
    FieldItem("Aduh kasihan anak dan Orang tuanys", "negatif", "uji"),
    FieldItem("Kok marah marah terus .seharusnya dadi awal di jelaskan dan pasang cctv .makanan yg di salurkan(ditata sedikit tapi banyak yg lebih untuk dibagi bagi ke karyawan mbg yg banyak", "negatif", "uji"),
    FieldItem("Program PKI PART 3", "negatif", "uji"),
    FieldItem("Rakyat berharap Prabowo harus dinon aktifkan atau diperhentikan dari kepresidenan , karna pemerintah dijadikan buta dan tuli", "negatif", "uji"),
    FieldItem("Wowo yg tanggung jawab", "negatif", "uji"),
    FieldItem("Tidak tepat sasaran MBG bukan makan bergizi", "negatif", "uji"),
    FieldItem("Makanya jangan menerima mbg, apapun yg dibuat secara besar\"an pd makanan tidak akan selalu baik😢", "negatif", "uji"),
    FieldItem("KLO di indo mah di dahuluin untung", "negatif", "uji"),
    FieldItem("Astaghfirulloh halngadim Betul ibu ini ,Cerdas Membela kebenaran Untuk anak Rayat Demi Negara Indonesia MBG stop ❤️❤️🙏🏼", "positif", "uji", "dc"),
    FieldItem("Bangsat si bang,Amin semoga bapak ya 100000000000000000000000000000000000000000000000000000000000000000 persen Amin ya rabbal", "negatif", "uji"),
    FieldItem("Rakyat harus bersatu", "netral", "uji"),
    FieldItem("Bubar mbg", "negatif", "uji"),
    FieldItem("Betul sekali Ibu ini, saya salut, berjuanglah Ibu Pertiwi", "positif", "uji", "d"),
    FieldItem("Astaghfirullah... Suruh makan yg bikin!!!!!!!!", "negatif", "uji"),
    FieldItem("Semangat terus bunda untuk rakyat Indonesia maju terus", "positif", "uji", "d"),
    FieldItem("Ya Allah", "netral", "uji"),
    FieldItem("PERCUMA BUK,KOAR\" SAMPE BERBUSA,CUMAN DIKETAWAIN DOANG SAMA SI JENDRAL GEMOY DAN ANAK BUAHNYA", "negatif", "uji"),
    FieldItem("MasyaAllah bu terus lah dukung terus ibu\" Indonesia", "positif", "uji", "d"),
    FieldItem("Cuma Prabowo yg mau terbuka, hanya Prabowo!!!", "positif", "uji"),
    FieldItem("MBG : makanan beracun gratis", "negatif", "uji"),
    FieldItem("Begooo", "negatif", "uji"),
    FieldItem("Parah Luh bang gak rispek", "negatif", "uji"),
    FieldItem("Oh tidak Rambutku hilang 70%", "netral", "uji"),
    FieldItem("terimakasih bu..mewakili suara rakyat...sehat selalu...lanjutkan...❤❤", "positif", "uji", "d"),
    FieldItem("Penjara 100 tahun bang", "negatif", "uji"),
    FieldItem("Eh bangsat jangan gitu emang lu mau Kaya gitu go***k", "negatif", "uji"),
    FieldItem("Padahal di negara luar pun presiden sering n di acuhkan hanya membesarkan n aa ma sendiri itu jadi tak benar semua", "netral", "uji"),
    FieldItem("Ya Allah tolong kami..toling orang tua dan anak2 Indonesia..Tolong turunkan segera adzabMu yg pedih di dunia dan akherat bagi Penguasa dan Pengusaha yg sgt dzolim pada kami rakyat..trutama ttg MBG, Pajak, kesewenang2an merampas hasil bumi, korupsi dstnya", "negatif", "uji"),
    FieldItem("inilah pemerintah merasa hebat pembunuh rakyat sendiri secara tak langsung..", "negatif", "uji"),
    FieldItem("Stop MBG", "negatif", "uji"),
    FieldItem("Semoga Allah memanggil menghadap para pejabat serakah.. aminnn....🤲🤲", "negatif", "uji"),
    FieldItem("sedih sekali denger cerita ibu...dduuhh si wowo itu RUSUH", "negatif", "uji"),
    FieldItem("GK baik itu itumah orang bego", "negatif", "uji"),
    FieldItem("Mantap Bu ,1hari 1t,keumana tuh uang nya masa ,tiap hari keracunan dimna mna,", "negatif", "uji", "dc"),
    FieldItem("Enga usa H makan mbg la gi woy😮", "negatif", "uji"),
    FieldItem("#mbg #prabowosubianto #dpr", "netral", "uji"),
    FieldItem("Harusnya diskusi sama para Mentri bayangan.bukan orang\" pilihan protokol istana", "negatif", "uji"),
    FieldItem("𝚃𝚄𝙽𝚃𝚄𝚃 & 𝙶𝚄𝙶𝙰𝚃 𝙿𝚁𝙰𝙱𝙾𝚆𝙾 𝙰𝚃𝙰𝚂 𝙺𝙴𝚁𝙰𝙲𝚄𝙽𝙰𝙽 𝙼𝙰𝚂𝚂𝙰𝙻 𝙰𝙺𝙸𝙱𝙰𝚃 𝙼𝙱𝙶 !!! 𝙿𝙴𝙲𝙰𝚃 𝙿𝚁𝙰𝙱𝙾𝚆𝙾 !!!", "negatif", "uji"),
    FieldItem("di pecat aja orang gitu", "negatif", "uji"),
    FieldItem("20 persen saja jika makanan itu tidak habis di makan, maka akan ada penghabisan anggaran 40T. Ngeri banget buang-buang anggarannya.", "negatif", "uji"),
    FieldItem("Gak semua MBG begitu", "netral", "uji"),
    FieldItem("Mewakili kami", "positif", "uji", "d"),
    FieldItem("Iya..kak susah bnget hidup saat ini", "negatif", "uji"),
    FieldItem("Presiden heran klu orang kaya masih mau curi, saya gak heran pak 😂😂", "negatif", "uji"),
    FieldItem("Bener sekali buk, inilah yg dirasakan emak emak.. 15 RB di tangan kami bisa menjadi makanan yg bergizi dan bisa makan sampai 3 kali sehari. Karna anak saya 2 orang, jadi klo dlm bentuk uang sudah 30 RB di tangan orang tua dan bisa makan satu keluarga satu hari", "positif", "uji", "d"),
    FieldItem("Anak sy semenjak makan MBG. Skrg KLO KLO diajak bicara jawabnya hah..hah..sy watir KLO MBG berjalan lama.anak Sy jadi tuli", "negatif", "kembang", "s"),
    FieldItem("Sudah di suruh bayar ending keracunan bahkan mening**** aku setuju mbg berhenti", "negatif", "kembang"),
    FieldItem("Sukses pak prabowo dengan program beracun nya, bangga saya", "negatif", "kembang", "s"),
    FieldItem("Tega anak2 diracuni pejabat hanya demi politik dn kekuasaan", "negatif", "kembang"),
    FieldItem("Ini Program jokowi", "netral", "kembang"),
    FieldItem("Doa astaghfirullahaladzim itu aduh anak-anak banyak tahu apalagi bisa sampai mencapai ribuan ya ih serem amit-amit ah audzubillah ya Allah semoga mereka masih keadaannya masih baik-baik aja insya Allah semoga Allah mudahkanlah rezeki dan hidupkanlah kembali mereka seperti semula dan jadikanlah jantung mereka dan bisa bernafas ih serem banget guys makanya jangan makan banyak mbg soalnya mbg itu memang ada yang banyak beracun soalnya tuh beracun memang nggak enak ada kalau di luar negeri itu memang kayak banyak yang racun", "negatif", "kembang"),
    FieldItem("Mbg.program.pemghinaan", "negatif", "kembang"),
    FieldItem("Penjelasan ibu ini jadi ingat simbok. ,jadi nangis , materi yg dimasak sederhana , tapi disajikan masih hangat", "netral", "kembang"),
    FieldItem("Otaknyatidaka da", "negatif", "kembang"),
    FieldItem("Kata bang prabuwo biasa saja itu mah", "netral", "kembang"),
    FieldItem("Saya simak dari semua jawaban presiden tidak ada solusi yg pasti buat semua pertanyaan dari mba Najwa .", "negatif", "kembang"),
    FieldItem("Karena program presiden jadi biasa2 saja.. Andaikata program saya sudah dari kemarin dapur di sita", "negatif", "kembang"),
    FieldItem("Mksh Bu sdh mewakili kami ...", "positif", "kembang", "d"),
    FieldItem("Memberikan pangan tapi menaikan pajak ya sama aja wo", "negatif", "kembang"),
    FieldItem("KENAPA KEPALA KELUARGA KORBAN KERACUNAN GAK ADA YG DEMO SIH", "netral", "kembang"),
    FieldItem("Hati hati Bu kena PETRUS! Mulai skrng ke mana mana harap dikawal", "netral", "kembang"),
    FieldItem("SEHAT SELALU PAK PRESIDEN SEMOGA ALLAH LINDUNGI BAPAK DIMANAPUN 🤲🔥💕", "positif", "kembang"),
    FieldItem("Saya percaya jika anggota parlemen yang hadir saat itu memiliki hati Nurani. akan tetapi jangan kita lupa bahwa mereka hanyalah pegawai dari Partai. Keputusan ada ditangan Ketua Partai. Dan itu fakta yang menyakitkan.", "negatif", "kembang"),
    FieldItem("Rasanya GK cocok jawabanx apa yg d tx mbkretno", "negatif", "kembang"),
    FieldItem("TUNTUT...BUBARKAN MBG!!", "negatif", "kembang"),
    FieldItem("kayawan mbg memang kgk ada hati ya nanti tunggu tanggal main aj", "negatif", "kembang"),
    FieldItem("Ini gimana sih cara mengatasi MBG ya sudah saja mbg di uangkan saja", "netral", "kembang"),
    FieldItem("MBG malah bikin repot orang ,bukan nya ngebantu i ini malah Mao Nge bunuh orang", "negatif", "kembang"),
    FieldItem("To the poin. Paksa prabowo turun. Aki aki ga layak jd presiden. Cuma ambisi menguasai negara demi kepentingan diri. Pidato ga becus. Memimpin negara boro2. Yg ada negara hancur perlahan. Jahatnya lbh jahat dr suharto", "negatif", "kembang"),
    FieldItem("Untunglah boleh ketawa besar..happy nye😂😂😂😂😂", "netral", "kembang"),
    FieldItem("Tutup saja ..kok pemerintah tidak mau dengar masalah ini...Tuli...budekk ...buta..mana hati nurani pemerintah ...", "negatif", "kembang"),
    FieldItem("Miriss emang,,katanya makan gratis,,wong duit negara ngutang lg,,emang duit wowo", "negatif", "kembang"),
    FieldItem("Mbg peluang kurup😂😂😂", "negatif", "kembang"),
    FieldItem("Itu dia tolol + goblok", "negatif", "kembang"),
    FieldItem("MBG di negri lain GK ada keracunan GK ada ulat jg GK ada koropsi makanya enak\"bergizi GK kyok Konoha penuh drama😅😮", "negatif", "kembang"),
    FieldItem("Sanggat setuju👍👍👍", "positif", "kembang", "d"),
    FieldItem("Amiiiiin ya Allaaaaaah,,... Kunfayakun terjadi lah apa yg kamu parodikan sama diri kamu....", "negatif", "kembang"),
    FieldItem("cuman mbak nana yg kritis yg lain manggut2 aja", "positif", "kembang", "c"),
    FieldItem("Kasihan banget sampai keracunan semua😢", "negatif", "kembang"),
    FieldItem("Rezim paling bobrok", "negatif", "kembang"),
    FieldItem("MAAP BU IBU BIIANG TERUS DUIT NEGARA,,MAAP BU ITU DUIT RAKYAT", "negatif", "kembang"),
    FieldItem("betul itu Bu setelah adanya program mbg dan kdmp insentif para RT d pedesaan d pangkas habis", "negatif", "kembang", "d"),
    FieldItem("Ingat peristiwa Corona..ternyata konspirasi tingkat besar kan.kami betul 2 khawatir dg MBG ada nya pro kontra diteruskan akhirnya murid2 yg jd korban krn konspirasi politik.ini munkin misal ada pihak yg sengaja masukin sesuatu secara masal msh gejala mual diare pusing terus kalo msh ndak ada respon kami cuma khawatir dan semoga tidak lah ada oknum 2 yg sengaja memberi dan hal2 yg lebih extrim demi suatu tujuan...bgmn kalo sementara sekali lg sementara istirahat dulu berbenah dulu dari segala lini akan perjalann MBG...", "negatif", "kembang"),
    FieldItem("Kata Prabowo Orang sudah kaya kok masih mau mencuri ya. Tapi pencurinya malah di pelihara.Yg jujur dipecat", "negatif", "kembang"),
    FieldItem("Sennang klian melihat itu kan iblis?dan berhasil racun praktek klian itu binatang?masak bisnis racun klian buat, itupun untk generasi bangsa pula itu?selidiki si pengolah ini bpk² masyarakat?ini bisnis baru sperti korona dulu?ttpi lbh sadis racunnya yg ini?", "negatif", "kembang"),
    FieldItem("Hmmm, inilah acara meja bundar, acara yg penuh banyak rencana , wacana, rencana yg banyak sekali omongan tetapi semuanya dongen/asalan Ngomong, Krn kerjanya hanya bisah ngomong tapi tindakannya kosong.", "negatif", "kembang"),
    FieldItem("Jangan pilih Prabowo lagi Yooo.... 🙏... Jangan mau 2 periode... ✋", "negatif", "kembang"),
    FieldItem("Suara ibu ini bisa mewakili kami semua,tapi semua akan sirna kalau ibunya gak ada power/dukungan dari DPR, Semangat terus IBU .", "positif", "kembang", "dc"),
    FieldItem("Ngaji belajar membaca peduli Fiona itu dia ingat ingatan itu coba pikirin deh anak itu apa kamu bahagiain di rumah sakit itu yang hilang ingatan", "netral", "kembang"),
    FieldItem("Miskin belaguu", "negatif", "kembang"),
    FieldItem("Mantapp Ibu Annette ❤❤❤🎉🎉🎉", "positif", "kembang", "d"),
    FieldItem("Najis bangat ' gue Liat peMbawa Acaranya ( Hasan Nasbi )😂😂😂😂😂", "negatif", "kembang"),
    FieldItem("yg disalah kan disini adalah pemberi mbg dan kepala sekolah ygmau Terima mbg.", "negatif", "kembang"),
    FieldItem("Mntap ibu ..mana negara hancur sudah negara ini", "negatif", "kembang", "dc"),
    FieldItem("ini br kritis ,mantap lanjtkan perjuangan tuk bela orang kecil ,smoga ibu ,keadaan sehat wal'afiat. 🤲 Amin", "positif", "kembang", "d"),
    FieldItem("Bapaa kesian anak2 ya Allahhh buka mata hati para pejabaaaa", "negatif", "kembang"),
    FieldItem("prabowo dengarkan , jangan ngeyel aja", "negatif", "kembang"),
    FieldItem("MBG d indonesia sering terjadi keracunan massal serta makanan MBG sering mubazir (terbuang)", "negatif", "kembang"),
    FieldItem("Indonesia timur siap berapatkan barisan untuk melengserkan prabowo gibran.", "negatif", "kembang"),
    FieldItem("Namanya saja bu pejabat haram yang tumbuh buta haram jiwanya", "negatif", "kembang"),
    FieldItem("Para ulama ulah cicing bae", "netral", "kembang"),
    FieldItem("Kesenjangan 2.kemanusiaan yang adil dan beradaptasi When yaaa", "netral", "kembang"),
    FieldItem("EMG benar pak Prabowo Subianto tegas kalau berbicara tapi kalah dengan orang orang yang menjadi pendukung nya", "netral", "kembang", "c"),
    FieldItem("Masak sih MBG kok kalah berkualitas dari masakan buatan pedagang makanan UKM (Usaha Kecil Menengah) yg merakyat ???🤨🤔😲🤭😩🤦🙈🙊😌 Kenapa makanan MBG masakan buatan SPPG dg arahan BGN bisa beracun / berpatogen walau sudah matang ??? 🤨🤔 Ini aneh, gk masuk akal, gk rasional..... Jika makanan yg higienis sudah dimasak matang yg diolahnya bersih terjaga kebersihannya oleh SPPG, walau sudah dimasak cukup lama waktunya (bisa membunuh patogennya) ternyata kok masih juga beracun / berpatogen ??? 🤨🤔😲😩🤦🙈🙊 Gk usah pakai cara satgas pengawas MBG segala lagi, memangnya satgas nya mau cicipi MBG beracun / berpatogen gk ??? 😩🤦🙊🙈 Karena racun atau patogen itu gk kelihatan mata lho.....🤨🤔 Jika ada orang yg racuni / cemari makanannya dg sembunyi-sembunyi tetap saja gk kelihatan satgasnya karena yg kasih racun / patogen nya juga punya akal bulus bisa pikirkan caranya. 😩🤦 Bisa saja caranya kasih racun saat pencucian bahan masakan, atau bahannya dipasok sudah diracuni lebih dulu saat di kirim atau saat di pasar, kan yg benar saja satgas nya harus periksakan setiap semua bahannya ???🤨🤔😩🤦 Jika pakai cara dicemari dg patogen beda lagi, yaitu dg penularan pada alat, wadah, air, bahkan sampai tangan pun bisa jadi penularannya. 🤨🤔😲 Mau periksa gimana satgasnya??? 🤨🤔 Kan kudu dibawa ke laboratorium dulu baru bisa ketahuan, dan perlu waktu berapa lama satgasnya beraksi ??? 🤨🤔😲😩🤦🙊🙈😌 Program MBG dihentikan saja dan diganti dg <program sekolah gratis> dg membayar para guru pengajarnya yg layak nilai upahnya, program ini bisa mencerdaskan bangsa, jika gizi untuk anak sekolah ini bisa dg BGN diusahakan bersama UKM rakyat pedagang makanan saja guna memajukan aktivitas ekonomi rakyat juga (bisa juga untuk kemajuan gizi masyarakat umum). 🙏🏼 Mudah-mudahan berjalan lancar dan bagus. Jika masalah memang masih bisa terjadi namun akan minim dan kecil. 💪🏼👍🏼 Keracunan dari Makanan Beracun / Berpatogen Gempar (MBG) korbannya harus diobati juga dg obat detox herbal untuk keluarkan racun dari dalam tubuhnya, contoh obat detox herbal seperti: kumis kucing, akar bajakah, daun sirsak, benalu, mengkudu, dll. Banyak orang bangsa kita yg bawahan pejabat pun tidak amanah juga, makanya pemimpin teratas lah yg juga kena batunya. Itu termul nya perjuangkan jilatannya untuk majikannya (geng solo) walaupun dongengan / fiksi namun sangat semangat dan bangga banget ya 😩🤦🙊🙈💩 Orang wapresnya saat ini kerjanya cuma MAGABU (makan Gaji Buta), atau jadi mandor pengangguran (mandor yg malas kerja kecuali kulinya saja yg kerja keras sedangkan mandor cuma santai nunggu hasil kulinya selesai kerja). 😩🤦🙈🙊💩 Kerjanya hanya pencitraan (pamer diri dg gaya dan hiasan dirinya supaya tampak dilihat publik dirinya itu wibawa, berprestasi, berintelektual, kompeten, dan kerja bagus. Pejuang dan pembela ijazah palsu udah kayak aktor komedi saja perkaranya yg janggal menggelitik gk masuk akal 🤭😩🤦🙈🙊💩 mereka kelabakan oleh urusan usaha penyelundupan pembajakan ijazah golongannya sendiri 🤭😩🤦🙈🙊💩", "negatif", "kembang"),
    FieldItem("MBG yang bermasalah ganti pengawasnya Di kampung saya MBG aman sentosa DPR sama koruptor diam semua DPR bubarkan MBG tegas amat", "netral", "kembang", "c"),
    FieldItem("tong Kitu anjing", "negatif", "kembang"),
    FieldItem("KITA TUNTUT AJA BGN.... Rp. 100 T Rupiah.... RAKYAT HARUS KOMPAK", "negatif", "kembang"),
    FieldItem("Mbg 50 prsen mubadir sing duwe utek ISO mikir", "negatif", "kembang"),
    FieldItem("yg ini nih MBG salah sasaran seharusnya yg mampu tidak perlu dikasih, harusnya ibu ini menyatakan perwakilannya dari ibu2 yang mampu jgn menyatakan atas nama aliansi ibu indonesia . nyatanya di daerah masih banyak orang tua yg merasa bersyukur dengan adanya program MBG ini. untuk masalah keracunan di MBG ini tidak masuk akal, sepertinya ingin menjatuhkan pemerintah. logikanya banyak kok rumah makan yg utk kelayakan tempat dan kwalitasnya jauh dari standar tidak pernah terdengar keracunan.", "netral", "kembang", "c"),
    FieldItem("DPR.. Dewan PENGHIANAT Rakyat.", "negatif", "kembang"),
    FieldItem("Setelah ngerasain efek keracunan makanan, tau banget apa yg dirasa anak-anak ini. 😢😢", "negatif", "kembang"),
    FieldItem("Sy mendukungmu bu,,,,STOP MBG,,,,!!!!", "positif", "kembang", "dc"),
    FieldItem("Beliau bilang dirjen,, keingat pak pur", "netral", "kembang"),
    FieldItem("Pejabatnya gk ngerasa betapa rasa sakit milk ibunya melihat anaknya lemah dirumah", "negatif", "kembang"),
    FieldItem("Di tanya ke barat jawab ke timur,,wo wo wo wo menit 1:35", "negatif", "kembang"),
    FieldItem("APBN CUMA DIHABISKAN UNTUK PROGRAM MBG DAN KOPERASI DESA MERAH PUTIH , KARENA SEBAGAI PUSAT LINGKARAN KORUPSI. HANYA MENGUNTUNGKAN KELOMPOK SERAGAM HIJAU , SERAGAM COKLAT , SERAGAM COKLAT TUA. SERAGAM PUTIH , SERAGAM DORENG DORENG DAN SERAGAM LAINNYA . PENJAHAT BENER NIH...😢😢 COBA LIHAT SETIAP HARI SPPG DAPAT UANG 6 JUTA RUPIAH SEBAGAI UANG INSENTIF ( GRATISAN ) , COBA UNTUK 1 BULAN DAN UNTUK 1 TAHUN DAN UNTUK SEMUA SPPG YANG JUMLAHNYA RIBUAN SPPG. TERUS JUMLAH NYA BERAPA MILYAR RUPIAH. UH ... BAJINGAN BENER ...!!!", "negatif", "kembang"),
    FieldItem("Buangkan saja kalau d antarnya k sekolah jangan d berikan kepada anak didik kalau membahayakan", "negatif", "kembang"),
    FieldItem("Mantap maju terus pantang mundur ❤❤❤❤❤", "positif", "kembang", "d"),
    FieldItem("Di Atas dadang Ada prabowo dan gibran dan jokowi dadang menjadi tumbal jokowi dan prabowo dan gibran kong galikong berjamaah lewat MBG dan kopdes dan sekolah gratis ha ha ha ha haaaaaaaaah", "negatif", "kembang"),
    FieldItem("Nggedabrusss😂😂hairnetnya dipake", "negatif", "kembang"),
    FieldItem("Di Konoha.. para pejabat dan berpangkat berjamaah untuk membangun dapur sppg.. karena banyak cuan tidak perduli , menu nya bikin anak anak keracunan", "negatif", "kembang"),
    FieldItem("Petugas mbg tolong ya makananya di komsumsi dengan baik untuk anak anak sekolah ya tolong di perbaiki menubgnya ya 😊😊😊😊😊 jangan sampai ada korban lagi ya ingat !!! 🙆🙆🙆🙅🙅🙅", "netral", "kembang"),
    FieldItem("harusnya karyawan mbg nya bilan OH TIDAK OTAK KU HILAG 70%", "netral", "kembang"),
    FieldItem("Di kono g onok setan dah nang indonesia tambah ngelemok no koruptor", "negatif", "kembang"),
    FieldItem("Hancurkan generasi muda dengan uang rakyat 😂😂😂,keruk sda sampe habis niscaya generasi muda sudah hancur tidak ada yg bisa komplen lagi 🤣🤣🤣", "negatif", "kembang", "s"),
    FieldItem("😭😭", "negatif", "kembang"),
    FieldItem("mbak nana blm selesai ngomong udah dipotong2", "negatif", "kembang"),
    FieldItem("Omong kosong", "negatif", "kembang"),
    FieldItem("Sebaik nya tersangka di hukum seberat berat nya", "negatif", "kembang"),
    FieldItem("ya Allah miris banget dgr suara ibu,aku juga punya anak mungkin JK aku diposisinya jg sedih dan sakit banget,hentikan mbg GK da manfaatnya pemerintah GK punya hati semoga mereka merasakan apa yg ibu ini rasakan", "negatif", "kembang"),
    FieldItem("mereka hanya kejar keuntungan semata luar biasa ini kejadian terulang dan terulang lagi", "negatif", "kembang"),
    FieldItem("Napalkan", "netral", "kembang"),
    FieldItem("Gimanapun Rakyat Protes kalau yg Punya Programm Kekeh Gak Bakal Ada Perubahan. Mereka tdk Mendengar Suara dan Jeritan Rakyat. Yg penting Ada celah Utk Korupsi dan memperkaya Diri sendiri dan Keluarga mereka", "negatif", "kembang"),
    FieldItem("Bagus ibu aku suka😊", "positif", "kembang", "d"),
    FieldItem("Yg tuli dan bodoh itu pelaksananya mbok, bukan pemerintahnya", "negatif", "kembang"),
    FieldItem("Aku jadi takutdeh😢", "negatif", "kembang"),
    FieldItem("Politik sangatlah kejam... ternyata rakyat Indonesia semua sama ya bodohnya wkwkwk...setelah kovit kita tambah bodoh wkwwkwkkw hantu saja sekarang bisa mati wkwkwkwkkangka kemtian sangat banyak kuburan nya dimana woiiiii", "negatif", "kembang"),
    FieldItem("Betol KK itu pejabat\" laknatulloh Krn pemimpin dan pejabat\" sudah bergandeng tangan rakyt sangat menderita mereka pesta pora hentikanmembyr pajak semua rkyt sangat setuju program pemerintah tidak disetujui rakyt", "negatif", "kembang", "d"),
    FieldItem("Bukan hilang ingatan tapi hilang rambut nya", "netral", "kembang"),
    FieldItem("PALOK LO KAYAK BAKSO MARCON SUARAYA KAYAK CEWK", "negatif", "kembang"),
    FieldItem("Mksh ibu...sdh mewakili kami utk bisa didengar ...klo mau dengar", "positif", "kembang", "d"),
    FieldItem("Cerita hanya untuk kedok kepemerintahan Padahal lain di bibir lain dihati.", "negatif", "kembang"),
    FieldItem("Di MBG tdk ada jaminan hukum bagi anak anak korban MBG oleh pemerintah", "negatif", "kembang"),
    FieldItem("Astagfirulloh.... Saya yang punya anak sekolah jadi ngeri kalo kejadian ini selalu terulang ulang,sampe anak di suruh ga makan mbg aja,, Semoga yang sudah terkena musibah,lekas di beri kesembuhan,selalu waspada kedepannya.", "negatif", "kembang"),
    FieldItem("Sy sbagai org tua melarang keras kepada anak2 saya tuk mengkonsumsi MBG jika telah hadir disekolah anak2 sy, drpada masa depan dan mental anak2 saya hancur gara2 program ini, krn kita tidak bisa prediksi ada atau tidak adanya racun dalam MBG tsb serta efek2 apa aja yg akan timbul dr racun2 yg ada di MBG tsb. Sayangilah anak2 kalian wagai seluruh orang tua🙏🙏🙏", "negatif", "kembang"),
    FieldItem("MBG (Makan Beracun Nasional) Walau banyak Murid Keracunan, Pemerintah Masih mempertahankan karena untuk membantu Pejabat2 pengelola Dapur MBG bisa Korupsi Milliaran krennn !!! 👏👏👏", "negatif", "kembang", "s"),
    FieldItem("Huhuhu pecat pecat Prabowo pecat pecat", "negatif", "kembang"),
    FieldItem("MBG ini gmn seh,,,merusak generasi muda,,,ini merusak nama baik Prabowo,,, Sdh hentikan MBG pak,,,", "negatif", "kembang"),
    FieldItem("Bubarkan MBG, diganti bantuan tunai ke orang tua namun manfaat penerima tentunya dipilih hanya yang membutuhkan dengan pengawasan guru ( jika orang tua ngga sanggup atau menyalahgunakan, bisa dialihkan ke orang tua lain atau kantin sekolah usaha UMKM yang sekarang gulung tikar berkat MBG ). Benar ngga logikanya? Dengan cara ini jauh lebih hemat dan tidak mubazir makanan terbuang ( yang ngga butuh ngga akan membuang makanan karena tidak perlu dapat ). uang rakyat akan lebih sisa banyak. Sudah cukup memperkaya SPPG. Tanpa SPPG sisa Uang rakyat bisa dialihkan ke pendidikan gratis mulai dari TK sampai universitas atau bahkan sampai S2 dan Kedokteran Spesialis, fasilitas kesehatan BPJS kelas dunia di seluruh provinsi, investasi ke automisasi untuk melawan birokrasi atau oknum, pembangunan pabrik pakan ternak dan pupuk untuk semua yang masih import, pembangunan transportasi terintegrasi murah di seluruh provinsi, perluasan infrastruktur jalan di seluruh provinsi. Semua itu adalah pembangunan untuk meningkatkan ekonomi rakyat bukan meningkatkan ekonomi golongan tertentu seperti SPPG. Dengan cara diatas kemiskinan akan berkurang dan angka stunting juga akan turun, dan penanganan stunting lebih tepat sasaran. Ayo dong dengerin rakyat jangan keras kepala... ( kecuali ada udang dibalik batu ).", "negatif", "kembang"),
    FieldItem("Tau tuh gimana sih kepala sppg masa gak di periksa makanannya kan yang rugi juga masyarakat setempat lagi kan itu juga bukan uang pribadi pelayan sppg harusnya lebih teliti lagi lain kali", "negatif", "kembang"),
    FieldItem("Seperti nya disini dapurnya di tiap sekolah", "netral", "kembang"),
    FieldItem("Yg mimpin kn!! dk punya hati nurani! Akal ny kn hanya untuk anak keturunan ny!!", "negatif", "kembang"),
    FieldItem("Sehat2 kalian....☺🤗", "positif", "kembang"),
    FieldItem("Lebih untuk makan bebek bu", "netral", "kembang"),
    FieldItem("pemerintah sepertinya ga mau punya generasi penerus yg cerdas. dgn MBG anak2 diracuni pelan2 . dilemahkan otaknya, di matikan organ tubuhnya pelan2 . saya merasakan sakit hatinya ibu ini yg kecewa berat dgn MBG yg ngeracunin anak2", "negatif", "kembang"),
    FieldItem("Gimana Pak Presiden, program ini apa menyehatkan anak bangsa atau membunuh anak bangsa tolong periksa pejabat negara yg bermain² dengan program MBG dan hukum seberat²nya para pejabat yg hanya utk membunuh anak bangsa demi korupsi pribadi.", "negatif", "kembang"),
    FieldItem("kesro teruuuus😂😂😂", "netral", "kembang"),
    FieldItem("Kasihan Anak2 diracun ,menganyanya Anak2 sekolah ,Kasihan Spain keracunan itu sangat parah Lho \"😎😎😎🦾🦾🦾👹👹👹👿👿👿🙄🙄🙄😱😱😱😱😱", "negatif", "kembang"),
    FieldItem("Maklum yg punja progran duda jadi ga ada yg masak", "negatif", "kembang"),
    FieldItem("sengaja itu anak anak pinter biar jadi bodoh ,hentikan MBG 2 ngeyel wae kompak semua MBGnya jangan di makan buang aja", "negatif", "kembang"),
    FieldItem("Gokil \"dengan perang harga pangan bisa naik\". Sumpah semakin malu aku sama bowok satu ini", "negatif", "kembang"),
    FieldItem("Disaat pemerintah negara lain mengutamakan pendidikan rezim konoha malah Meracuni generasinya 😢", "negatif", "kembang"),
    FieldItem("Wah bahaya Ki", "negatif", "kembang"),
    FieldItem("Mbg nya tolong stop☹️☹️", "negatif", "kembang"),
    FieldItem("selain dana mbg ... coba sekali kali tanya juga dana BOS.. faktual penggunaannya utk siswa.. transparansi dana persemester yg di glontorkan oleh pusat ..", "netral", "kembang"),
    FieldItem("Pejabat dan pengusaha nya paling serakah Menzalimi Rakyat.", "negatif", "kembang"),
    FieldItem("Boxing lawan gua aja sini 3 lawan 1 gw tampung lu jangan hina dia anjing", "negatif", "kembang"),
    FieldItem("Benar sekali kata ibu ini.mbg penghinaan bagi para ibu2 di negeri ini.setuju.cerdas Program bagi2 proyek. Program memperkaya orng2 tertentu.", "negatif", "kembang", "dc"),
    FieldItem("Ehhh Prabowo minimal tunggu orang selesai ngomong itu adab, mba Nana aja nunggu lu selesai ngomong baru bertanya lagi", "negatif", "kembang"),
    FieldItem("atuk wowo nonton tuk.. jng denger kata kata anak buah mu yg kebelinger..", "negatif", "kembang"),
    FieldItem("😢", "negatif", "kembang"),
    FieldItem("Lu jangan ejek jir", "negatif", "kembang"),
    FieldItem("Ini pelajaran buat pak Prabowo rakyat mulai brontak mulai zalim pemimpin sekarang akan datang bencana besar lagi ini kalau tidak di perduli kandengan Masya rakat hancur lah negeri ini", "negatif", "kembang"),
    FieldItem("30%tolol 70%bukan hilang ingatan hilang otak", "negatif", "kembang"),
    FieldItem("Betul sekali Bu...mantabbbbb....gassss terussss...emang brengsek..", "positif", "kembang", "dc"),
    FieldItem("Pemimpin iyakan", "netral", "kembang"),
    FieldItem("MbG sangat2 menyelakan Negara,... Tolong di Hapus...", "negatif", "kembang"),
    FieldItem("Di Negara ini para Pejabat nya banyak yang harus di Nepalkan terutama para wakil rakyat yang rakus Uang dan kehormatan !!!!", "negatif", "kembang"),
    FieldItem("Sangat setuju rakyat indonesiya .gak mau bayar pajak .😮😮😮😮😮😮", "positif", "kembang", "d"),
    FieldItem("Dari dulu tak ada rakyat yg mati kelaparan.bowo.", "negatif", "kembang"),
    FieldItem("Anak sy juga kena keracunan MBG 1 bln yg lalu, dampaknya sampai sekarang anak saya setiap bangun pagi mau ke sekolah muntah2 terus, selera makan menurun drastis, setiap ke tempat yg ramai langsung pusing dan mual muntah. Trauma psikis anak sy sampai sekarang belum pulih dan akhirnya sy memutuskan utk bawa anak sy berobat ke luar negeri. Tolong lah pemerintah, hentikan aja MBG ini. Jgn kalian korbankan masa dpn anak2 ini demi keegoisan kalian. Sudah muak kami dengan program MBG gak jelas ini.", "negatif", "kembang"),
    FieldItem("Makin ke sini makin keliatan cara kerja nya si wowo..........ternyata negara bisa hancur d tangan presiden gemoy, sarangya korupsi di presiden skrng!!!", "negatif", "kembang"),
    FieldItem("KENYATAAN PRIBUMI PEMALAS APALAGI SUDAH DUDUK DIKURSI EMPUK LANGSUNG LES TIDUR MEETING SAMA ATASAN SAJA BISA TIDUR BULE ATAU ASING DUNIA DUDUK KURSI EMPUK MIKIR KEBIJAKAN APA TERBAIK BUAT PERUSAHAAN SAYA NEGARA SAYA KALAU SEORANG PIMIMPIN .", "negatif", "kembang"),
    FieldItem("Gop bok bagat🤬🖕🤬🤬", "negatif", "kembang"),
    FieldItem("Betul......bu tutup MBG....kasian anak2 kita......suruh anak2 pejabat tu makan MBG........tujuannya pembunuh pelan pelan", "negatif", "kembang", "d"),
    FieldItem("Betul..kondisi sekarang makin terasa sulit.", "negatif", "kembang", "d"),
    FieldItem("ERA. PRABOWO. SEMUA SENDI. AMBORADOL", "negatif", "kembang"),
    FieldItem("gak boleh itu", "negatif", "kembang"),
    FieldItem("Sumpah itu orang malah ngejek orang sadar diri itu masakan lu goblok", "negatif", "kembang"),
    FieldItem("Keracunan MBG yg sdh banyak mengambil korban siswa/siswi, maka seharusnya pemerintah sdh mengeta hui penyebabnya. Tapi sampai saat ini blm ada penjelasan resmi faktor2 penye bab keracunan pada MBG tsb.", "negatif", "kembang"),
    FieldItem("Stop MBG..stop MBG...anak2 aman, APBN aman", "negatif", "kembang"),
    FieldItem("setuju........", "positif", "kembang"),
    FieldItem("Parah banget,,, seumur hidup baru kali ini phk massal dimana-mana, dan aku terdampak... Gila, sih pemerintahan sekarang.", "negatif", "kembang"),
    FieldItem("Hati hati mencari pemimpin yg akan datang jgn karna uang karna itu melanggar agama dan UUD 45", "netral", "kembang"),
    FieldItem("Angkat najwa jadi salah satu menteri agar bisa tahu intrik intrik dalam pemerintahan..", "positif", "kembang"),
    FieldItem("Presiden Prabowo bilang sekolah Seperti pikir Makan ( MBG ) Stop Jangan iya", "netral", "kembang"),
    FieldItem("Semestinya pemerintah mendengarkan suara rakyat klau sdh muak bahaya bagi pemerintah.klau sdh turun gunung jutaan rakyat bisa hukum rimba berjalan bisa mati konyol", "negatif", "kembang"),
    FieldItem("woi! si kepala lonjong bisa diam gak si 😡😡😡", "negatif", "kembang"),
    FieldItem("Sudahlah kirim uang Langsung ke orang tua murid masing2 Pak Prabowo", "netral", "kembang"),
    FieldItem("Prabowo Prabowo ...", "netral", "kembang"),
    FieldItem("ya Allah piye tooo.... P presiden hentikan aja pak dari pd banyak yg sakit", "negatif", "kembang"),
    FieldItem("Wong kowe yo mbuh to", "netral", "kembang"),
    FieldItem("Di sekolah ku ada mbg tapi gakpapa kok aku", "netral", "kembang"),
    FieldItem("Relawan pengolah Berkah sehat berprestasi timbang reja 01 Tegal Jateng hadir menyimak", "netral", "kembang"),
    FieldItem("Ganti presiden sekarang bisa gk sih udh bikin hampir semua siswa siswi indonesia kena racun Dan meninggal", "negatif", "kembang"),
    FieldItem("otak jumbo otak jumbo🤣🤣🤣🤣🤣🤣🤣🤣", "negatif", "kembang"),
    FieldItem("DPR kan wakel rakyat seharusnya menolak program mbg yang meracuni anak bangsa kok malah mendukung wakel rakyat macam apa itu program mbg bikin hancur negara dan menghabiskan uang rakyat hancurkan DPR yang pro pemerintah", "negatif", "kembang"),
    FieldItem("Dimane itu ya Allah semoga narik kalau mbg tidak keracunan amin", "netral", "kembang"),
    FieldItem("Tega kalian yg berbuat jahat😢😢😢,,,, sungguh BIADAB,", "negatif", "kembang"),
    FieldItem("Betul banget Buu....?? KL presiden pengin di hormati pengin di segani masarakat sekolahan yng PD rusak di bangun terus anak sekolah di gratiskan itu baru yng nmnya presiden..", "negatif", "kembang", "d"),
    FieldItem("Ini kenapa saya tidak pernah makan mbg.", "negatif", "kembang"),
    FieldItem("Semangat bukkk.... Parah pemerintah sekarang, phk besar2ran dan aku bersama istri terkena dampaknya.... Gilaa", "negatif", "kembang", "c"),
    FieldItem("GK semudah omongannya di desa2 GK gitu,cuman narasi tok,cb urus seluruh desa se ind,jongos kapitalis y gitu maunya semua dikelola perusahaan besar,,,omong tok cb cermati", "negatif", "kembang"),
    FieldItem("Dari sini aku melihat bahwa pak jokowi masih baik menjadi presiden", "positif", "kembang", "c"),
    FieldItem("Sampai sekarang blm ada tanggapan yang jelas pak persiden ku", "negatif", "kembang"),
    FieldItem("Ini baru ibu yang cerdas udah mewakili ibu ibu yang lain", "positif", "kembang", "d"),
    FieldItem("😂", "netral", "kembang"),
    FieldItem("Terbaik bu terus perjuangan pulitk agar bep❤uas hati rakyat ,rakyatvmesti bersatu menatang salah me gunakan kuasa kepentingan peribadi dan krluarga", "positif", "kembang", "d"),
    FieldItem("Emang biadap", "negatif", "kembang"),
    FieldItem("Jawaban yg bagusss dari ibu najwa❤", "positif", "kembang"),
    FieldItem("Mba Nazwa selalu bisa memberikan pertanyaan kritis. Memancing jawaban para politisi yang akhirnya bikin mereka blunder. Inilah bedanya Mbak Najwa dengan kebanyakan jurnalis lain.", "positif", "kembang"),
    FieldItem("Pecat pecat", "negatif", "kembang"),
    FieldItem("Jangan berhentiin sementara, tapi selamanya aja", "negatif", "kembang"),
    FieldItem("Astaghfirullah halazim Ya Allah gimana ya pemerintah G bertanggung jawab ampun 😭😭", "negatif", "kembang"),
    FieldItem("Pr3sidennya udah tua, pikirannya kembali kayak anak2, emosian", "negatif", "kembang"),
    FieldItem("MBG dan KDMP adalah ladang korupsi memang sengaja biar semakin banyak upeti Bos. MBG bukan gratis,karena biaya dari anggaran negara yang di ambil dari pajak rakyat. Dgn ada nya MBG dan KDMP semua bahan pokok mahal. Rakyat menjerit Bos Bahagia, laporan ok,setoran ok Lanjutkan Bu, rakyat 70%mendukungmu Dan 30% yg tidak mendukung Para tikus-tikus. Memang sengaja memberi Makanan Beracun utk Generasi Agar semua ilang ingatan biar kedepan tidak ada persaingan dan mudah di atur.", "negatif", "kembang", "d"),
    FieldItem("Salah pilih persiden sekarang nyesel pilih Prabowo", "negatif", "kembang"),
    FieldItem("(M)akan (B)eracun (G)ratis ☠️ Korban dari Pemimpin Keras Kepala", "negatif", "kembang"),
    FieldItem("Kalau kalian yang atur 15kx26Hari bisa turun 200 juga kok 😂😂😂", "netral", "kembang"),
    FieldItem("setuju kli mbg di tutup, dan pajak di hapus", "negatif", "kembang"),
    FieldItem("Pov wowo: mbg bagus tidak 🗣", "netral", "kembang"),
    FieldItem("Anjing penjilat", "negatif", "kembang"),
    FieldItem("Para ibu lebih tau ,,,yg terbaik untuk anak2 nya, pemerintah lebih mementikan gizi untuk para pejabat nya,,tp racun siap saji di berikan untuk anak2 kita,", "negatif", "kembang"),
    FieldItem("Jidatnya lebar banget😊", "negatif", "kembang"),
    FieldItem("Dipecat sih😅", "negatif", "kembang"),
    FieldItem("Trima kasih Ibu Hebat penuh perhatian Kepada anak2 Indonesia", "positif", "kembang", "d"),
    FieldItem("Bagaimana pak daerah kami belum dapat MBG kami daerah pedalaman Kalimantan Barat desa Nanga Tangkit, Desa' Nanga Libas,Desa Nanga ora dan Desa penyengkuang hanya lihat di tv dan yutub saja", "netral", "kembang"),
    FieldItem("Astaghfillah .", "netral", "kembang"),
    FieldItem("Tolol", "negatif", "kembang"),
    FieldItem("Bohong SD tidak menampung rakyat Indonesia, saya kan nya ta rakyat Indonesia yang sekolah. Mulut ibu pembohong", "negatif", "kembang"),
    FieldItem("Pelaksana MBG GK dihukum pula itu,belum ada beritanya terus masuk penjara kl kjadian bgini.", "negatif", "kembang"),
    FieldItem("Mba nana the real jadi cahaya disitu", "positif", "kembang"),
    FieldItem("Konoha yg ter baik dalam segala hal, kata sebelah tapi 😂😂😂", "negatif", "kembang", "s"),
    FieldItem("Benar Bu .byk oknum .yg di lindungi", "negatif", "kembang", "d"),
    FieldItem("Trimakasih ibu udah mewakili rakyat yang sengsara ini sehat selalu Bu terus maju", "positif", "kembang", "d"),
    FieldItem("Ih ko orang gila di kerjain sih di mbg ternyata ini nih orang gila nya kalo mau bikin makanan itu jangan pake kacamata nanti salah masukin makanan lagi btw kepalanya besar tapi ko otak nya kecil kalo di hujat pasti kacamatanya itu ada air airnya karena nangis iya iya elu engak kehilangan ingatan soalnya di dalam perut lu itu ada cacing nya jadinya yang keracunan itu cacing di dalam perut lu yang bulat itu", "negatif", "kembang"),
    FieldItem("Saya setuju penghapusan MBG karena hampir setiap hari makanannya aq buang, tidak sesuai selera & yg tau selera makan kita ya kita sendiri.... Tapi memang males ngomong karena sering tidak didengar...", "negatif", "kembang"),
    FieldItem("Astagfirullahaladziim 😢", "negatif", "kembang"),
    FieldItem("Yaaaaaa begini negara kalau di pimpin orang yang super gobloknya ....segoblok goblok nya anak TK ada yang lebih goblok ....ya itu...dia", "negatif", "kembang"),
    FieldItem("MBG membunuh genrus bangsa", "negatif", "kembang"),
    FieldItem("Mbg ada belatung...ada racun.... hentikan mbg....", "negatif", "kembang"),
    FieldItem("Orang jujur d pecat mau d bawa kemana negara ini", "negatif", "kembang"),
    FieldItem("Mending di hujat aja si bg", "negatif", "kembang"),
    FieldItem("Dasar botak lenang", "negatif", "kembang"),
    FieldItem("Mbg bikit ruwet mending digenti Karo duwet", "negatif", "kembang"),
    FieldItem("Prabowo banci sangat tidak berani dn me ngolor,,waktu rakyat sudah kritis masih saja menunggu,,dan menunggu momen yg pas hai Prabowo kamu sudah terkepung geng solo ,ayo tunjuk kan Kostrad mu ,", "negatif", "kembang"),
    FieldItem("SETUJU BANGET.... SAYA DAN KELURGA JUGA MENJADI KORBAN MBG.... USAHA SAYA COLAPS KARNA MBG....", "negatif", "kembang", "d"),
    FieldItem("menurutku kariawan kontolllllllll.............", "negatif", "kembang"),
    FieldItem("Babi", "negatif", "kembang"),
    FieldItem("siapayangsetujuakunkitabelokiryangsetuju 👇🏻", "netral", "kembang"),
    FieldItem("Acara sekadar untuk memetik jawapan Probowo soalan lain jawab lain merapu", "negatif", "kembang"),
    FieldItem("Diibaratkan ibu ini hanya mengetuk dinding besar tinggi dan tebal, yg ga mungkin ketukan bisa terdengar, apa lagi sampai roboh dinding itu.", "negatif", "kembang"),
    FieldItem("MB hanya untuk membungkam kasus Jampidsus pejabat jadi penjahat rakyat rugi banyak bayar gaji sia2", "negatif", "kembang"),
    FieldItem("Tapi kalau di negara lain engak ada yg keropsi bahkan mendukung. Nah kalau di Indonesia pejabatnya maling i", "negatif", "kembang"),
    FieldItem("Bahkan TUHAN pun TACK SUDI Program SAMPAH YG PENUH KORUP INI....😂😂😂 Kata PRABOWO Kalo Anda Mati \"TINGGAL KUBUR\" Program Tidak akan BERHENTI.. Yg Penting KORUPPPP!!!", "negatif", "kembang"),
    FieldItem("Ngoceh doang kaoyg buta bu", "negatif", "kembang"),
    FieldItem("Mbak najwa izin nge clip videonya yaa🙏🙏🙏", "netral", "kembang"),
    FieldItem("Mantap100 persen q sangat bangga dengan ibu. Anette miu. Lanjutkan bu. Biar mbgnya bubar saja", "positif", "kembang", "dc"),
    FieldItem("Saya sependapat dgn aspirasi ibu ini pemerintah memang blm mensejaterahkan rakyat cb kt analogi bersama BBM naik semua di pajakin sembakau melambung tinggi", "negatif", "kembang", "d"),
    FieldItem("Michael Jackson - Smooth Criminal era pak sby pak", "netral", "kembang"),
    FieldItem("Siapa yang setuju mbg di hentikan🫗", "negatif", "kembang"),
    FieldItem("W", "netral", "kembang"),
    FieldItem("Betul sekali ibu. 😢maju terus ibu perjuankan hak kami sebagai perempuan . Sembako makin tdk terjangkau.akibat MBG. PROGRAM YG CUMA MENGUNTUNGKAN PENJILAT PARA PENGUASA RAKUS.", "negatif", "kembang", "dc"),
    FieldItem("Wowo pidato di forum internasional Rusia membahas & membanggakan mbg nya Kalau mereka tau kualitas mbg kita sudah ditertawakan Atau mera sudah tau 😂", "negatif", "kembang"),
    FieldItem("No satu kuadrat konoha makan penuh racun... Siswa bnyk keracunan terbesar no 1 di konoha", "negatif", "kembang"),
    FieldItem("Simbok dulu masak sehari dua kali ,", "netral", "kembang"),
]
