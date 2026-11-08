"""Kosakata bahasa daerah dan ragam kesukuan untuk penilai ragam informal (informal-3).

Komentar publik Indonesia jarang ditulis dalam satu bahasa. Di komentar BBM
Bali (36.319 komentar YouTube, Okt 2026) makian Bali ("naskleng", "cicing"),
Jawa ("pekok", "taek", "ora becus"), dan logat Medan ("parah kali") muncul
ribuan kali — dan sampai informal-2 semuanya abstain, karena kamus hanya
mengenal Bahasa Indonesia.

## Kenapa per bahasa, bukan satu daftar panjang

Kata yang sama punya arti berbeda di bahasa yang berbeda. Kamus ini disusun
per bahasa supaya setiap entri bisa ditelusuri ke asalnya (kolom bahasa di
Excel proyek), dan supaya tabrakan antarbahasa ketahuan oleh tes, bukan oleh
pembaca laporan:

- "sing" = "tidak" dalam bahasa Bali, tapi = "yang" dalam bahasa Jawa.
- "seng" = "tidak" di Ambon, tapi = "yang" di Jawa Timur ("pejabat seng ...").
- "ambek" = "marah" dalam bahasa Sunda, tapi = "dengan" di Jawa Timur.
- "goreng" = "jelek" dalam bahasa Sunda, tapi "harga digoreng" di Indonesia.

Kata seperti itu TIDAK dimasukkan sama sekali — lihat `EXCLUDED`, yang
mencatat alasannya satu per satu. Kamus yang menebak bahasa komentar dulu
lalu memilih arti adalah perbaikan yang sah, tapi itu butuh pendeteksi bahasa
yang diukur, bukan aturan tangan.

## Aturan penyusunan (sama dengan informal-2)

1. Hanya kata yang maknanya TIDAK bergantung konteks. Kata topik dan kata
   yang bisa pujian atau sindiran ("pinter", "kocak") tidak masuk.
2. Setiap kata dicek pada komentar nyata BBM Bali di luar sampel manual 400:
   kata yang sering muncul bernegasi atau dalam larangan sehingga terbalik
   jadi pujian ("gak usah ...") tidak masuk.
3. Kata yang tidak muncul di data proyek mana pun tetap boleh masuk kalau
   maknanya pasti dan tunggal di bahasanya (makian, kata dasar baik/buruk).
   Data BBM Bali didominasi Bali/Jawa; bahasa lain baru teruji kalau ada
   proyek dari daerahnya.

Bobot mengikuti skala leksikon baku: makian kasar 0,9; penilaian buruk jelas
0,8; kesal/sombong 0,6–0,7; kata ringan 0,4–0,5.

## Yang tetap tidak terbaca

Sarkasme dalam bahasa apa pun, peribahasa dan kiasan ("ber-IQ primata"),
serta bahasa yang tidak tercantum di bawah. Bahasa daerah yang ditulis
dengan ejaan sangat beragam juga hanya terbaca pada ejaan yang tercatat.
"""

from __future__ import annotations

#: Kata bermuatan per bahasa: kata -> (bobot bertanda, arti dalam Bahasa Indonesia).
#: Kunci luar adalah nama bahasa/ragam yang tampil di keluaran.
REGIONAL_LEXICON: dict[str, dict[str, tuple[float, str]]] = {
    "Jawa": {
        # buruk / rusak
        "elek": (-0.8, "jelek"),
        "uelek": (-0.8, "jelek sekali"),
        "ajur": (-0.8, "hancur"),
        "rekoso": (-0.7, "susah, sengsara"),
        "sengsoro": (-0.8, "sengsara"),
        "kangelan": (-0.6, "kesulitan"),
        "nggilani": (-0.8, "menjijikkan"),
        "medeni": (-0.6, "menakutkan"),
        "mbelgedes": (-0.8, "omong kosong"),
        "mbelgedhes": (-0.8, "omong kosong"),
        # perasaan
        "nesu": (-0.7, "marah"),
        "mangkel": (-0.7, "kesal"),
        "gething": (-0.8, "benci"),
        "gela": (-0.7, "kecewa"),
        "kesel": (-0.5, "lelah (Jawa) / kesal (cakap) — keduanya negatif"),
        "isin": (-0.5, "malu"),
        # watak
        "kemaki": (-0.7, "sombong, sok"),
        "gumede": (-0.7, "sombong"),
        "kemlinthi": (-0.6, "sok, tengil"),
        "ndableg": (-0.6, "bebal"),
        "ngapusi": (-0.9, "berbohong"),
        "goroh": (-0.9, "bohong"),
        # makian
        "pekok": (-0.8, "bodoh"),
        "gemblung": (-0.7, "gila, bodoh"),
        "kenthir": (-0.6, "gila"),
        "gendeng": (-0.6, "gila"),
        "asu": (-0.8, "anjing (makian)"),
        "kirik": (-0.7, "anak anjing (makian)"),
        "jancuk": (-0.7, "makian Jawa Timur"),
        "jancok": (-0.7, "makian Jawa Timur"),
        "jancik": (-0.7, "makian Jawa Timur"),
        "dancuk": (-0.7, "makian Jawa Timur"),
        "dancok": (-0.7, "makian Jawa Timur"),
        "diancuk": (-0.7, "makian Jawa Timur"),
        "telek": (-0.6, "kotoran"),
        "ndasmu": (-0.7, "kepalamu (makian)"),
        "raimu": (-0.6, "mukamu (makian)"),
        "dapuranmu": (-0.7, "tampangmu (makian)"),
        "cangkem": (-0.7, "mulut (kasar)"),
        "cangkemmu": (-0.7, "mulutmu (kasar)"),
        "sontoloyo": (-0.7, "tidak becus (makian)"),
        "semprul": (-0.6, "makian ringan"),
        # baik
        "apik": (0.8, "bagus"),
        "uapik": (0.8, "bagus sekali"),
        "becik": (0.7, "baik"),
        "ciamik": (0.8, "bagus sekali"),
        "maturnuwun": (0.7, "terima kasih"),
        "suwun": (0.7, "terima kasih"),
    },
    "Sunda": {
        "awon": (-0.8, "jelek"),
        "butut": (-0.6, "jelek, usang"),
        "keuheul": (-0.7, "kesal"),
        "ijid": (-0.8, "jijik"),
        "geuleuh": (-0.8, "jijik"),
        "gelo": (-0.6, "gila"),
        "belegug": (-0.8, "bodoh"),
        "kehed": (-0.8, "makian"),
        "hese": (-0.6, "susah"),
        "riweuh": (-0.5, "repot, ribet"),
        "alus": (0.7, "bagus"),
        "hade": (0.7, "baik"),
        "sae": (0.7, "bagus (juga Jawa krama)"),
        "nuhun": (0.7, "terima kasih"),
        "haturnuhun": (0.7, "terima kasih"),
        "bagja": (0.7, "bahagia"),
    },
    "Bali": {
        "jele": (-0.8, "jelek, buruk"),
        "naskleng": (-0.9, "makian kasar"),
        "kleng": (-0.9, "makian kasar"),
        "keleng": (-0.9, "makian kasar"),
        "cicing": (-0.8, "anjing (makian)"),
        "belog": (-0.8, "bodoh"),
        "lengeh": (-0.6, "bodoh, linglung"),
        "keweh": (-0.7, "susah"),
        "gedeg": (-0.7, "kesal (juga Jawa)"),
        "sebet": (-0.6, "sedih"),
        "kimud": (-0.5, "malu"),
        "mael": (-0.7, "mahal"),
        "usak": (-0.6, "rusak"),
        "melah": (0.7, "bagus, baik"),
        "luung": (0.7, "bagus"),
        "suksma": (0.7, "terima kasih"),
    },
    "Betawi/Jakarta": {
        "ogah": (-0.5, "tidak mau"),
        "rese": (-0.6, "menyebalkan"),
        "nyebelin": (-0.7, "menyebalkan"),
        "ngeselin": (-0.7, "menjengkelkan"),
        "nyolot": (-0.6, "ketus, menantang"),
        "sotoy": (-0.5, "sok tahu"),
        "norak": (-0.6, "kampungan"),
        "kampungan": (-0.6, "kampungan"),
        "ngaco": (-0.6, "ngawur"),
        "nyusahin": (-0.7, "menyusahkan"),
        "ngerepotin": (-0.6, "merepotkan"),
        "lebay": (-0.5, "berlebihan"),
        "kampret": (-0.7, "makian"),
        "sompret": (-0.7, "makian"),
        "kece": (0.7, "keren"),
    },
    "Minang": {
        "buruak": (-0.8, "buruk"),
        "pandia": (-0.7, "bodoh"),
        "ongeh": (-0.6, "sombong"),
        "pantek": (-0.9, "makian kasar"),
        "kalera": (-0.8, "makian"),
        "baruak": (-0.7, "beruk (makian)"),
        "rancak": (0.7, "bagus"),
        "elok": (0.6, "baik, bagus"),
    },
    "Batak/Medan": {
        "bodat": (-0.8, "monyet (makian)"),
        "kimak": (-0.9, "makian kasar (juga Melayu)"),
        "pukimak": (-0.9, "makian kasar (juga Melayu)"),
        "mauliate": (0.7, "terima kasih"),
    },
    "Melayu": {
        "teruk": (-0.8, "parah, buruk"),
        "hampeh": (-0.7, "tak berguna"),
        "bangang": (-0.8, "bodoh"),
        "celaka": (-0.7, "celaka"),
    },
    "Banjar": {
        "bungul": (-0.8, "bodoh"),
        "babal": (-0.7, "bodoh"),
        "harat": (0.6, "hebat"),
    },
    "Palembang": {
        "bongok": (-0.8, "bodoh"),
    },
    "Bugis/Makassar": {
        "sundala": (-0.9, "makian kasar"),
        "telaso": (-0.9, "makian kasar"),
        "tailaso": (-0.9, "makian kasar"),
        "dongo": (-0.8, "bodoh"),
        "pongoro": (-0.7, "gila"),
    },
    "Manado/Maluku/Papua": {
        "cuki": (-0.9, "makian kasar"),
        "puki": (-0.9, "makian kasar"),
        "pukimai": (-0.9, "makian kasar"),
        "bodok": (-0.8, "bodoh"),
        "pamalas": (-0.6, "pemalas"),
        "dangke": (0.7, "terima kasih (Ambon)"),
    },
    "Madura": {
        "sakalangkong": (0.7, "terima kasih"),
    },
    "Sasak": {
        "tampiasih": (0.7, "terima kasih"),
    },
    # Bahasa Indonesia cakap yang muncul di komentar abstain BBM Bali dan maknanya
    # tidak bergantung konteks. Dicatat di sini, bukan di sentiment.py, supaya
    # seluruh tambahan informal-3 terukur bersama.
    "Indonesia (cakap)": {
        "bentak": (-0.6, "membentak"),
        "membentak": (-0.6, "membentak"),
        "dibentak": (-0.6, "dibentak"),
        "rasis": (-0.7, "rasis"),
        "bajingan": (-0.9, "makian"),
        "setan": (-0.7, "setan (makian)"),
        "preman": (-0.6, "preman"),
        "otoriter": (-0.7, "otoriter"),
        "diktator": (-0.7, "diktator"),
        "menindas": (-0.8, "menindas"),
        "penindas": (-0.8, "penindas"),
        "menyusahkan": (-0.8, "menyusahkan"),
        "menyengsarakan": (-0.9, "menyengsarakan"),
        "seenaknya": (-0.7, "seenaknya"),
        "penjajah": (-0.7, "penjajah"),
        "sinting": (-0.6, "gila"),
        "bebal": (-0.6, "bebal"),
        "konyol": (-0.6, "konyol"),
        "palsu": (-0.6, "palsu"),
        "hoax": (-0.6, "kabar bohong"),
        "hoaks": (-0.6, "kabar bohong"),
        "bangkrut": (-0.6, "bangkrut"),
        "gabener": (-0.7, "plesetan 'gubernur tidak benar'"),
        "cuih": (-0.6, "ludah, tanda jijik"),
        "cih": (-0.5, "tanda meremehkan"),
        "konoha": (-0.5, "julukan sinis untuk negara ('pejabat konoha')"),
    },
}

#: Negator, larangan, dan penguat daerah -> padanan yang sudah dikenali penilai.
#: Dipetakan lewat normalisasi (`services/informal.py`), BUKAN ditambahkan ke
#: daftar negator baku, supaya penilaian liputan media tidak bergeser.
REGIONAL_MODIFIERS: dict[str, tuple[str, str]] = {
    # negator
    "ora": ("tidak", "Jawa"),
    "orak": ("tidak", "Jawa"),
    "ra": ("tidak", "Jawa"),
    "mboten": ("tidak", "Jawa"),
    "boten": ("tidak", "Jawa"),
    "durung": ("belum", "Jawa"),
    "dudu": ("bukan", "Jawa"),
    "teu": ("tidak", "Sunda"),
    "henteu": ("tidak", "Sunda"),
    "moal": ("tidak", "Sunda"),
    "tusing": ("tidak", "Bali"),
    "kaga": ("tidak", "Betawi/Jakarta"),
    "indak": ("tidak", "Minang"),
    "dak": ("tidak", "Palembang/Melayu"),
    "kada": ("tidak", "Banjar"),
    "nyanda": ("tidak", "Manado/Maluku/Papua"),
    "sonde": ("tidak", "Kupang"),
    "tra": ("tidak", "Manado/Maluku/Papua"),
    "trada": ("tidak", "Manado/Maluku/Papua"),
    "bukang": ("bukan", "Manado/Maluku/Papua"),
    # larangan
    "ojo": ("jangan", "Jawa"),
    "ojok": ("jangan", "Jawa"),
    # penguat
    "tenan": ("banget", "Jawa"),
    "nemen": ("banget", "Jawa"),
    "bes": ("terlalu", "Bali"),
    "bana": ("banget", "Minang"),
    "nian": ("banget", "Palembang"),
    "kali": ("banget", "Batak/Medan"),
    "kacida": ("sangat", "Sunda"),
    # ejaan lain dari kata yang sudah ada di leksikon
    "pecus": ("becus", "ejaan cakap"),
    "bahlol": ("bahlul", "ejaan cakap"),
    "taek": ("tai", "Jawa"),
    "taik": ("tai", "Jawa"),
    "anying": ("anjing", "Sunda"),
    "njing": ("anjing", "cakap"),
    "ancur": ("hancur", "cakap"),
    "ancor": ("hancur", "Manado/Maluku/Papua"),
    "gile": ("gila", "Betawi/Jakarta"),
    "bodho": ("bodoh", "Jawa"),
    "nyesek": ("sedih", "cakap"),
}

#: Frasa dua kata yang di kamus ditulis serangkai.
REGIONAL_PHRASES: dict[tuple[str, str], str] = {
    ("matur", "nuwun"): "maturnuwun",
    ("hatur", "nuhun"): "haturnuhun",
}

#: Kata yang SENGAJA tidak dimasukkan, dengan alasannya. Tes memastikan tidak ada
#: satu pun yang ikut masuk kamus lewat jalur lain.
EXCLUDED: dict[str, str] = {
    "sing": "Bali 'tidak', Jawa 'yang' ('sing goblok iku' akan terbalik jadi pujian)",
    "seng": "Ambon 'tidak', Jawa Timur 'yang' (di data: 'pejabat seng ...'); juga atap seng",
    "ambek": "Sunda 'marah', Jawa Timur 'dengan'",
    "goreng": "Sunda 'jelek', Indonesia 'goreng'/'digoreng'",
    "lain": "Sunda/Minang 'bukan', Indonesia 'lain'",
    "aja": "Jawa 'jangan', cakap Indonesia 'saja' (1.128 kali di data, hampir semua 'saja')",
    "ulah": "Sunda 'jangan', Indonesia 'ulah' (sudah negatif di informal-2)",
    "lek": "Bali 'malu', Jawa 'paman'/'kalau'",
    "ndek": "Sasak 'tidak', Jawa Timur 'di'",
    "tara": "Papua 'tidak', juga nama orang",
    "temen": "Jawa 'sungguh', Indonesia cakap 'teman'",
    "embung": "Sunda 'tidak mau', Indonesia 'embung' (waduk kecil)",
    "resep": "Sunda 'suka', Indonesia 'resep' (masakan/dokter)",
    "lembab": "Melayu 'lamban', Indonesia 'lembap'",
    "parlente": "Ambon 'penipu', Indonesia 'perlente' (necis)",
    "matamu": "Jawa makian, Indonesia 'matamu' harfiah",
    "pol": "Jawa 'sangat', juga 'Pol PP' dan 'Pak Pol' (di data)",
    "san": "Bali 'sangat', terlalu jarang dan bertabrakan dengan potongan kata",
    "cok": "Jawa Timur: makian dan sapaan akrab sekaligus ('karepmu cok')",
    "cuk": "sama dengan 'cok'",
    "mumet": "Jawa 'pusing'; seperti 'pusing' (informal-2) sering dalam larangan",
    "pinter": "pujian atau sindiran ('paling pinter ngomong'), tidak bisa dibedakan",
    "rendahan": "sering bernada simpati ('pegawai rendahan'), bukan cela",
    "kocak": "lucu (pujian) atau konyol (cela)",
    "mutu": "'ra mutu' negatif, tapi 'mutu' di berita netral",
    "jago": "pujian atau sindiran ('jago ngomong')",
    "celeng": "makian Jawa/Bali, tapi juga harfiah babi hutan",
    "aing": "Sunda 'saya', netral ('bapak aing' = julukan tokoh)",
    "rusuh": "21% kemunculan di BBM Bali bernegasi ('warga Bali tidak rusuh'), terbaca pujian",
    "seneng": "Jawa 'senang', tapi di data hampir selalu tuduhan ('seneng lihat rakyat menderita')",
    "demen": "Bali/Betawi 'suka', pola tuduhan yang sama ('demen banget bikin rakyat susah')",
    "merakyat": (
        "tuntutan/pembanding ('coba sedikit merakyat'), seperti 'mengayomi' di informal-2"
    ),
    "cakep": "lebih sering menilai benda/orang ('motornya cakep') daripada sikap",
    "primata": "harfiah netral; hinaan lewat kiasan ('ber-IQ primata') di luar jangkauan kamus",
}


def lexicon() -> dict[str, float]:
    """Semua kata bermuatan daerah dalam satu kamus kata -> bobot."""
    out: dict[str, float] = {}
    for words in REGIONAL_LEXICON.values():
        for word, (weight, _meaning) in words.items():
            out[word] = weight
    return out


def slang() -> dict[str, str]:
    """Pemetaan ejaan daerah -> bentuk yang dikenali, untuk `informal.SLANG`."""
    return {word: target for word, (target, _language) in REGIONAL_MODIFIERS.items()}


def origin(word: str) -> str | None:
    """Bahasa asal sebuah kata bermuatan daerah, atau None kalau bukan kata daerah."""
    for language, words in REGIONAL_LEXICON.items():
        if word in words:
            return language
    return None
