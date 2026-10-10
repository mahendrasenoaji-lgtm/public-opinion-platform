"""Sentiment dan emosi Bahasa Indonesia — baseline berbasis leksikon.

`docs/roadmap.md` menandai bagian ini sebagai "yang paling mudah salah" dan
mensyaratkan dua hal sebelum dinyalakan di proyek nyata: set evaluasi berlabel
manual, dan akurasinya dilaporkan di UI. Keduanya ada — lihat
`services/sentiment_eval.py` dan `evaluate()` di bawah.

## Kenapa leksikon, bukan model

Bukan karena leksikon lebih baik. Ia lebih buruk: ia tidak paham sarkasme,
tidak paham konteks, dan menganggap "korupsi" negatif walaupun kalimatnya
memuji pemberantasannya. Yang membuatnya dipilih untuk baseline adalah tiga
sifat yang bisa dipertanggungjawabkan: deterministik (hasil yang sama untuk
teks yang sama, selamanya), bisa diaudit (setiap skor bisa ditelusuri ke kata
yang memicunya, lihat `matched`), dan tidak memerlukan pengiriman percakapan
warga ke API pihak ketiga.

Menggantinya dengan model terlatih adalah peningkatan yang jelas — tapi
penggantinya harus dibandingkan terhadap set evaluasi yang sama, bukan
dipasang karena "model pasti lebih pintar".

## Abstain adalah jawaban yang sah

`score()` mengembalikan `None` kalau tidak ada satu pun kata leksikon yang
cocok. Itu BUKAN sama dengan netral. Netral berarti "diukur, hasilnya di
tengah"; abstain berarti "metode ini tidak punya dasar untuk menilai teks
ini". Menggabungkan keduanya jadi 0.0 akan membuat rata-rata sentimen terlihat
tenang justru ketika alatnya sedang buta — persis kesalahan yang paling mahal
di platform ini.

## Dua ragam

`score(text)` menilai ejaan baku, dan perilakunya untuk liputan media TIDAK
berubah sejak `lexicon-id-1` — deret sentimen media tetap sinambung.

`score(text, register="informal")` dipakai untuk sumber `SOCIAL`. Ia menambah
tiga hal di atas leksikon yang sama: ejaan dikembalikan ke bentuk baku
(`services/informal.py`), kosakata ragam cakap (`_INFORMAL_*` di bawah), dan
emoji bermuatan (`EMOJI_LEXICON`). Kosakata tambahan itu SENGAJA tidak
dipakai untuk media: "hebat", "stop", "anjing", "tutup" bermuatan di kolom
komentar tapi netral atau berbalik makna di judul berita ("kebakaran hebat",
"polisi hentikan pencarian").

Mutunya diukur pada komentar nyata, bukan kalimat buatan — lihat
`services/sentiment_eval_field.py:evaluate_field()`.

Yang TIDAK diperbaiki ragam informal, dan tidak bisa diperbaiki kamus mana
pun: sarkasme ("sukses pak dengan program beracunnya, bangga saya" tetap
terbaca positif), dan selisih antara NADA dan SIKAP — komentar yang memuji
seorang pengkritik program bernada positif padahal menolak programnya.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from app.services.informal import CLAUSE_BOUNDARY, PHRASES, canonical_tokens, emoji_marks
from app.services.ingestion import normalize_text, wordset

#: Ragam teks yang dinilai. "baku" = ejaan media (RSS); "informal" = komentar
#: media sosial. Lihat bagian "Dua ragam" di docstring modul.
Register = Literal["baku", "informal"]

#: Ambang label. Di antara keduanya dianggap netral.
POSITIVE_THRESHOLD = 0.15
NEGATIVE_THRESHOLD = -0.15

#: Kata yang membalik polaritas kata sesudahnya.
NEGATORS = wordset("tidak tak bukan belum jangan enggak nggak gak ga tanpa kurang")

#: Pembalikan tidak simetris: "tidak bagus" lebih lemah daripada "buruk".
#: Orang memakai negasi untuk memperhalus, bukan untuk menyatakan lawan penuh.
NEGATION_FACTOR = -0.75

#: Penguat yang mendahului kata sifat ("sangat bagus").
PRE_INTENSIFIERS = wordset("sangat amat paling begitu benar sungguh terlalu makin semakin")
#: Penguat yang mengikuti kata sifat — pola khas Bahasa Indonesia ("bagus sekali").
POST_INTENSIFIERS = wordset("sekali banget bener pisan")
#: Pelemah.
DIMINISHERS = wordset("agak sedikit lumayan cukup rada")

INTENSIFY_FACTOR = 1.5
DIMINISH_FACTOR = 0.6

#: Jarak pandang ke belakang untuk mencari negator/penguat.
_WINDOW = 3

#: Kata yang MENUTUP cakupan negasi/penguat sebelumnya.
#:
#: Tanpa ini, "tidak ribet, malah cepat" membuat negasi dari klausa pertama
#: ikut membalik "cepat" di klausa kedua — kalimat positif terbaca netral.
#: Cakupan negasi memang berhenti di batas klausa; jendela kata mentah tidak
#: tahu itu. Tanda baca sudah hilang di normalize_text(), jadi penanda yang
#: tersisa adalah kata penghubungnya sendiri.
CLAUSE_BREAKS = wordset("""
    tapi tetapi namun melainkan malah sedangkan walaupun meskipun meski
    sayangnya padahal kecuali sementara
""")

#: Leksikon sentimen. Bobot 0..1 menyatakan kekuatan, bukan frekuensi.
#: Kata yang maknanya bergantung konteks (naik, turun, besar, banyak) SENGAJA
#: tidak dimasukkan — "harga naik" negatif tapi "bantuan naik" positif, dan
#: leksikon tidak bisa membedakannya.
_POSITIVE: dict[str, float] = {
    "bagus": 0.8, "baik": 0.7, "mantap": 0.9, "keren": 0.8,
    "puas": 0.8, "senang": 0.8, "gembira": 0.8, "lega": 0.7, "bangga": 0.8,
    "setuju": 0.7, "mendukung": 0.8, "dukung": 0.7, "apresiasi": 0.8,
    "berhasil": 0.8, "sukses": 0.8, "membantu": 0.7, "bermanfaat": 0.8,
    "manfaat": 0.6, "adil": 0.8, "jujur": 0.8, "transparan": 0.8,
    "amanah": 0.8, "bersih": 0.6, "tepat": 0.6, "efektif": 0.7, "efisien": 0.7,
    "cepat": 0.5, "mudah": 0.6, "lancar": 0.7, "nyaman": 0.7, "aman": 0.6,
    "peduli": 0.7, "ramah": 0.6, "optimis": 0.7, "harapan": 0.5,
    "maju": 0.6, "meningkat": 0.4, "membaik": 0.7, "solutif": 0.7,
    "terjangkau": 0.7, "murah": 0.6, "salut": 0.8, "terimakasih": 0.7,
    "sepakat": 0.6, "tepatsasaran": 0.8, "profesional": 0.7, "responsif": 0.7,
    "memuaskan": 0.8, "memadai": 0.6, "layak": 0.6, "berkualitas": 0.7,
    "andal": 0.7, "tuntas": 0.6, "akurat": 0.7,
}

#: "asal" (arti "asal-asalan"/asal-asalan, ceroboh) SENGAJA tidak dimasukkan
#: lagi ke sini (dihapus 2026-09-02). Kata yang sama jauh lebih sering muncul
#: dalam arti "berasal dari"/"asal negara-X" yang netral sepenuhnya (mis.
#: "aktor asal Inggris") — dikonfirmasi via 215 item nyata dari 5 feed RSS
#: media Indonesia (bukan 52 kalimat set evaluasi): 2/2 kemunculan token
#: "asal" adalah makna "dari", 0/2 makna "ceroboh". Tokenizer memisahkan
#: hubung ("asal-asalan" -> "asal" "asalan"), jadi entri tunggal ini tidak
#: bisa membedakan kedua makna tanpa konteks kata di sekitarnya — di luar
#: kemampuan leksikon kata-tunggal ini (lihat docstring modul).
#:
#: "hebat" (arti "sangat"/pujian, mis. "dia hebat!") SENGAJA tidak
#: dimasukkan lagi ke sini (dihapus 2026-09-11). Dalam liputan media
#: Indonesia kata ini jauh lebih sering dipakai sebagai penguat keparahan
#: di depan kata NEGATIF ("kebakaran hebat", "muntah hebat") daripada
#: sebagai pujian berdiri sendiri — dikonfirmasi via 445 item nyata dari
#: 7 feed RSS media Indonesia (sesi verifikasi production 2026-09-11,
#: bukan 52 kalimat set evaluasi): 3/3 kemunculan token "hebat" adalah
#: penguat keparahan (kebakaran sekolah 17 tewas +0.9, kebakaran kantor
#: +0.9, muntah hebat +0.9), 0/3 makna pujian. Sama persis pola "asal" di
#: atas — kata yang maknanya berbalik total tergantung kata benda/kerja
#: yang mengikutinya, di luar kemampuan leksikon kata-tunggal ini.
_NEGATIVE: dict[str, float] = {
    "buruk": 0.8, "jelek": 0.8, "parah": 0.9, "hancur": 0.9, "kacau": 0.9,
    "amburadul": 0.9, "gagal": 0.9, "kecewa": 0.8, "mengecewakan": 0.9,
    "marah": 0.8, "kesal": 0.7, "benci": 0.9, "muak": 0.9, "geram": 0.8,
    "tolak": 0.8, "menolak": 0.8, "protes": 0.7, "demo": 0.4,
    "korupsi": 0.9, "korup": 0.9, "curang": 0.9, "bohong": 0.9, "dusta": 0.9,
    "menipu": 0.9, "manipulasi": 0.8, "zalim": 0.9, "sewenang": 0.8,
    "mahal": 0.7, "susah": 0.7, "sulit": 0.6, "ribet": 0.6, "lambat": 0.6,
    "lelet": 0.7, "rumit": 0.5, "berbelit": 0.7,
    "rugi": 0.7, "merugikan": 0.8, "membebani": 0.8, "memberatkan": 0.8,
    "beban": 0.6, "sengsara": 0.9, "menderita": 0.9, "susahnya": 0.7,
    "khawatir": 0.6, "cemas": 0.7, "resah": 0.7, "takut": 0.7, "panik": 0.8,
    "bingung": 0.5, "ragu": 0.5, "pesimis": 0.7, "putusasa": 0.9,
    "diskriminatif": 0.8, "tidakadil": 0.9, "abai": 0.7, "mengabaikan": 0.8,
    "omongkosong": 0.9, "percuma": 0.8, "sia": 0.6, "memburuk": 0.8,
    "krisis": 0.7, "darurat": 0.6, "bermasalah": 0.7, "cacat": 0.7,
    "telat": 0.6, "terlambat": 0.6, "menyulitkan": 0.8, "mempersulit": 0.8,
    "menumpuk": 0.5, "mangkrak": 0.8, "terbengkalai": 0.8,
}

LEXICON: dict[str, float] = {
    **{w: s for w, s in _POSITIVE.items()},
    **{w: -s for w, s in _NEGATIVE.items()},
}

#: Kosakata ragam cakap — HANYA untuk `register="informal"`. Disusun dari
#: belahan `kembang` set lapangan (`sentiment_eval_field.py`) ditambah bentuk
#: sekerabatnya; belahan `uji` tidak dibuka selama penyusunan.
#:
#: "hebat" ada di sini padahal dihapus dari leksikon baku: di kolom komentar
#: ia pujian ("ibu hebat"), di judul berita ia penguat keparahan.
_INFORMAL_POSITIVE: dict[str, float] = {
    "betul": 0.5, "bener": 0.5, "benar": 0.4, "semangat": 0.6, "sehat": 0.4,
    "syukur": 0.6, "bersyukur": 0.6, "alhamdulillah": 0.6, "cerdas": 0.6,
    "hebat": 0.7, "terbaik": 0.7, "lanjutkan": 0.5, "mewakili": 0.4,
    "suka": 0.6, "cinta": 0.6, "good": 0.6, "terbantu": 0.7, "sependapat": 0.5,
    # Hampir selalu muncul bernegasi ("gak becus", "gak waras"); nilainya
    # positif supaya pembalikan negasi yang menghasilkan tanda yang benar.
    "becus": 0.6, "waras": 0.4, "tanggungjawab": 0.5,
}

_INFORMAL_NEGATIVE: dict[str, float] = {
    # makian
    "goblok": 0.9, "tolol": 0.9, "bodoh": 0.8, "bego": 0.8, "dungu": 0.8,
    "biadab": 0.9, "bangsat": 0.9, "brengsek": 0.9, "anjing": 0.8, "babi": 0.7,
    "kontol": 0.9, "bacot": 0.7, "laknat": 0.9, "iblis": 0.8, "najis": 0.8,
    "jijik": 0.8, "sampah": 0.6, "mampus": 0.8, "sial": 0.6, "payah": 0.7,
    "gila": 0.5, "stres": 0.5, "edan": 0.5, "ngawur": 0.7, "ngeyel": 0.6,
    "tuli": 0.6, "budek": 0.6, "buta": 0.5, "bobrok": 0.9, "busuk": 0.8,
    # tuduhan
    "serakah": 0.8, "rakus": 0.8, "maruk": 0.7, "maling": 0.8, "koruptor": 0.9,
    "penjilat": 0.8, "mafia": 0.7, "kroni": 0.6, "menzalimi": 0.9,
    "jahat": 0.8, "kejam": 0.8, "sadis": 0.8, "tega": 0.6, "munafik": 0.8,
    "pembohong": 0.9, "penipu": 0.9, "tipu": 0.8, "khianat": 0.9,
    "pengkhianat": 0.9, "penjahat": 0.9, "penjajahan": 0.7, "pembunuh": 0.8,
    "membunuh": 0.8, "bunuh": 0.8, "menghina": 0.7, "penghinaan": 0.7,
    "hina": 0.7, "mengejek": 0.5, "ngejek": 0.5, "ejek": 0.5,
    # bahaya dan penderitaan
    "racun": 0.7, "beracun": 0.8, "keracunan": 0.6, "meracuni": 0.8,
    "diracuni": 0.8, "basi": 0.6, "belatung": 0.7, "korban": 0.5,
    "trauma": 0.7, "sakit": 0.5, "mati": 0.5, "meninggal": 0.5,
    "bahaya": 0.6, "berbahaya": 0.6, "membahayakan": 0.6, "kelaparan": 0.6,
    "miris": 0.7, "ngeri": 0.6, "seram": 0.6, "kasihan": 0.4, "sedih": 0.6,
    "nangis": 0.4, "malu": 0.5, "menyesal": 0.7, "emosi": 0.5,
    "merusak": 0.7, "rusak": 0.6, "menghancurkan": 0.8, "hancurkan": 0.8,
    "mubazir": 0.6, "boros": 0.6, "utang": 0.4, "ngutang": 0.4, "phk": 0.5,
    # tuntutan penolakan — sikap menolak yang dinyatakan sebagai perintah
    "stop": 0.6, "hentikan": 0.6, "dihentikan": 0.5, "bubarkan": 0.7,
    "bubar": 0.6, "dibubarkan": 0.6, "tutup": 0.4, "ditutup": 0.4,
    "hapus": 0.5, "dihapus": 0.5, "pecat": 0.6, "dipecat": 0.5,
    "lengserkan": 0.7, "dilengserkan": 0.7, "melengserkan": 0.7,
    "tuntut": 0.5, "penjara": 0.5, "dipenjara": 0.5, "adili": 0.5,
    "tangkap": 0.5, "dihukum": 0.4,
    # lain-lain
    "hujat": 0.6, "ruwet": 0.5, "banci": 0.7, "belagu": 0.6, "malas": 0.5,
    "pemalas": 0.6, "mencuri": 0.7, "pencuri": 0.8, "curi": 0.7,
}

INFORMAL_LEXICON: dict[str, float] = {
    **LEXICON,
    **{w: s for w, s in _INFORMAL_POSITIVE.items()},
    **{w: -s for w, s in _INFORMAL_NEGATIVE.items()},
}

#: Emoji bermuatan, hanya untuk ragam informal. Yang maknanya bergantung
#: konteks SENGAJA tidak ada: 😂 (tertawa geli atau mengejek), 🙏 (terima kasih
#: atau memohon), 👏 dan 😊 (keduanya sering dipakai menyindir di data
#: lapangan), 🔥.
EMOJI_LEXICON: dict[str, float] = {
    **dict.fromkeys("😡🤬👿😠💩🖕☠👎🤮🤢", -0.8),
    **dict.fromkeys("😢😥😩☹😞😔🥺😰😱", -0.5),
    "😭": -0.4,
    "👍": 0.6,
    **dict.fromkeys("❤♥💕💖🥰😍🎉", 0.5),
}

#: Leksikon emosi. Jauh lebih kasar daripada sentimen: ia menghitung kehadiran
#: kata penanda, bukan menyimpulkan keadaan afektif penulisnya. Dilaporkan
#: sebagai proporsi penanda yang ditemukan, dan kosong kalau tidak ada.
EMOTION_LEXICON: dict[str, tuple[str, ...]] = {
    "anger": ("marah", "geram", "kesal", "benci", "muak", "emosi", "berang", "murka"),
    "fear": ("takut", "khawatir", "cemas", "was", "panik", "ngeri", "resah"),
    "sadness": ("sedih", "kecewa", "pilu", "prihatin", "duka", "menderita", "sengsara"),
    "joy": ("senang", "gembira", "bahagia", "lega", "syukur", "bangga", "puas"),
    "disgust": ("jijik", "muak", "risih", "najis"),
    "trust": ("percaya", "yakin", "amanah", "jujur", "andal"),
}

MODEL_VERSION = "lexicon-id-1"
#: Versi ragam informal. Dinaikkan setiap kali `_INFORMAL_*`, `EMOJI_LEXICON`,
#: atau `services/informal.py` berubah dengan cara yang menggeser skor.
INFORMAL_MODEL_VERSION = "lexicon-id-1+informal-1"

#: Semua bentuk yang perlu dikenali normalisasi: kata bermuatan, pengubah,
#: penghubung klausa, dan kata penyusun frasa serangkai.
_INFORMAL_VOCAB: frozenset[str] = (
    frozenset(INFORMAL_LEXICON)
    | NEGATORS
    | PRE_INTENSIFIERS
    | POST_INTENSIFIERS
    | DIMINISHERS
    | CLAUSE_BREAKS
    | frozenset(word for pair in PHRASES for word in pair)
)


def method_for(register: Register) -> str:
    if register == "informal":
        return (
            "leksikon berbobot + negasi + normalisasi ragam informal "
            f"({INFORMAL_MODEL_VERSION})"
        )
    return f"leksikon berbobot + negasi ({MODEL_VERSION})"


@dataclass(frozen=True, slots=True)
class SentimentResult:
    """Skor sentimen satu teks.

    `score` None berarti abstain — lihat catatan modul. `matched` disimpan agar
    setiap skor bisa ditelusuri ke kata pemicunya saat ada yang menyanggah.
    """

    score: float | None
    label: str
    confidence: float
    matched: list[tuple[str, float]] = field(default_factory=list)
    method: str = f"leksikon berbobot + negasi ({MODEL_VERSION})"

    @property
    def abstained(self) -> bool:
        return self.score is None


def label_for(score: float) -> str:
    if score > POSITIVE_THRESHOLD:
        return "positif"
    if score < NEGATIVE_THRESHOLD:
        return "negatif"
    return "netral"


def _preceding_scope(tokens: Sequence[str], i: int) -> list[str]:
    """Kata sebelum posisi i yang masih satu klausa dengannya.

    Dipindai mundur dan BERHENTI di kata penghubung — lihat CLAUSE_BREAKS.
    """
    scope: list[str] = []
    for j in range(i - 1, max(-1, i - _WINDOW - 1), -1):
        if tokens[j] in CLAUSE_BREAKS or tokens[j] == CLAUSE_BOUNDARY:
            break
        scope.append(tokens[j])
    return scope


#: Larangan, bukan penyangkalan. "tidak korupsi" menyangkal; "jangan korupsi"
#: menegur — nadanya tetap negatif. Hanya dipakai ragam informal: di sana
#: "jangan ngeyel", "jangan hina dia" terbaca POSITIF kalau larangan
#: diperlakukan sebagai negasi (ditemukan di set lapangan, belahan kembang).
PROHIBITIVES = wordset("jangan")


def _modifier(
    tokens: Sequence[str], i: int, *, base: float = 0.0, informal: bool = False
) -> float:
    """Faktor dari negator/penguat/pelemah di sekitar posisi i."""
    factor = 1.0
    back = _preceding_scope(tokens, i)
    negators = [t for t in back if t in NEGATORS]
    if informal and base < 0 and negators and all(t in PROHIBITIVES for t in negators):
        negators = []
    if negators:
        factor *= NEGATION_FACTOR
    if any(t in PRE_INTENSIFIERS for t in back):
        factor *= INTENSIFY_FACTOR
    if any(t in DIMINISHERS for t in back):
        factor *= DIMINISH_FACTOR
    # Penguat pasca-kata: "bagus sekali". Cukup satu token ke depan.
    if i + 1 < len(tokens) and tokens[i + 1] in POST_INTENSIFIERS:
        factor *= INTENSIFY_FACTOR
    return factor


def score(text: str, *, register: Register = "baku") -> SentimentResult:
    """Skor sentimen -1..1, atau abstain kalau tak ada dasar.

    Perhatikan bahwa "kurang" ada di NEGATORS sekaligus bukan penanda negatif
    sendirian: "kurang puas" jadi negatif lewat pembalikan, bukan lewat entri
    leksikon terpisah. Itu disengaja — memasukkan "kurang" sebagai kata negatif
    akan menghitungnya dua kali.

    `register="informal"` untuk komentar media sosial — lihat "Dua ragam" di
    docstring modul. Di `matched`, kata tampil dalam bentuk SESUDAH
    normalisasi ("gk becus" tercatat sebagai `becus`), dan emoji tampil apa
    adanya.
    """
    informal = register == "informal"
    if informal:
        tokens = canonical_tokens(text, _INFORMAL_VOCAB)
        lexicon = INFORMAL_LEXICON
    else:
        tokens = normalize_text(text).split()
        lexicon = LEXICON
    matched: list[tuple[str, float]] = []

    for i, tok in enumerate(tokens):
        base = lexicon.get(tok)
        if base is None:
            continue
        factor = _modifier(tokens, i, base=base, informal=informal)
        matched.append((tok, round(base * factor, 3)))

    if informal:
        matched.extend((e, EMOJI_LEXICON[e]) for e in emoji_marks(text, EMOJI_LEXICON))

    if not matched:
        return SentimentResult(
            score=None, label="tidak dinilai", confidence=0.0, method=method_for(register)
        )

    values = [v for _, v in matched]
    raw = sum(values) / len(values)
    clipped = max(-1.0, min(1.0, raw))

    # Keyakinan turun kalau penanda saling bertentangan, dan naik pelan seiring
    # jumlah penanda. Dua penanda searah lebih meyakinkan daripada satu.
    magnitude = sum(abs(v) for v in values)
    agreement = abs(sum(values)) / magnitude if magnitude else 0.0
    evidence = min(1.0, len(matched) / 3)

    return SentimentResult(
        score=round(clipped, 3),
        label=label_for(clipped),
        confidence=round(agreement * evidence, 3),
        matched=matched,
        method=method_for(register),
    )


def emotions(text: str) -> dict[str, float]:
    """Proporsi penanda emosi yang ditemukan. Kosong kalau tidak ada.

    Bukan klasifikasi emosi. Kalimat "saya tidak marah" akan tetap menyumbang
    ke `anger` karena metode ini tidak melihat negasi — batasan yang sengaja
    dibiarkan daripada ditambal setengah jalan, dan wajib disebut di UI.
    """
    tokens = set(normalize_text(text).split())
    hits = {k: len(tokens & set(v)) for k, v in EMOTION_LEXICON.items()}
    total = sum(hits.values())
    if total == 0:
        return {}
    return {k: round(v / total, 3) for k, v in hits.items() if v}


def aggregate(results: Iterable[SentimentResult]) -> dict[str, object]:
    """Ringkas banyak skor menjadi satu angka + berapa yang tidak dinilai.

    `abstain_rate` bukan metadata pelengkap: ia menentukan apakah rata-ratanya
    layak dipercaya sama sekali. Rata-rata dari 12% teks yang kebetulan memuat
    kata leksikon bukan sentimen publik, itu sentimen dari 12% teks.
    """
    items = list(results)
    scored = [r.score for r in items if r.score is not None]
    n = len(items)
    if not scored:
        return {
            "mean": None,
            "n": n,
            "n_scored": 0,
            "abstain_rate": 1.0 if n else 0.0,
            "positive_pct": None,
            "negative_pct": None,
            "neutral_pct": None,
        }

    mean = sum(scored) / len(scored)
    labels = [label_for(s) for s in scored]
    return {
        "mean": round(mean, 3),
        "n": n,
        "n_scored": len(scored),
        "abstain_rate": round((n - len(scored)) / n, 3) if n else 0.0,
        "positive_pct": round(100 * labels.count("positif") / len(labels), 1),
        "negative_pct": round(100 * labels.count("negatif") / len(labels), 1),
        "neutral_pct": round(100 * labels.count("netral") / len(labels), 1),
    }


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Hasil pengukuran leksikon terhadap set berlabel manual."""

    n: int
    n_scored: int
    accuracy: float
    #: Akurasi hanya di antara teks yang benar-benar dinilai (abstain dibuang
    #: dari penyebut). Menjawab pertanyaan berbeda dari `accuracy`: "kalau alat
    #: ini bersuara, seberapa sering ia benar" — bukan "seberapa banyak teks
    #: yang berhasil ia nilai dengan benar". Keduanya perlu: yang pertama
    #: menentukan apakah skor per-teks layak dipercaya, yang kedua menentukan
    #: apakah rata-rata agregatnya layak dipercaya.
    accuracy_scored_only: float
    macro_f1: float
    per_class: dict[str, dict[str, float]]
    abstain_rate: float
    #: Di kelas mana abstain terjadi. Ini yang membuat `abstain_rate` bisa
    #: ditafsirkan: abstain pada kalimat yang memang netral (pengumuman,
    #: jadwal, pertanyaan administratif) adalah perilaku benar; abstain pada
    #: kalimat bermuatan adalah kebutaan yang sesungguhnya.
    abstain_by_class: dict[str, int]
    confusion: dict[str, dict[str, int]]
    #: Peringatan yang WAJIB ikut ditampilkan bersama angka di atas.
    caveat: str


def evaluate(
    labeled: Sequence[tuple[str, str]],
    *,
    register: Register = "baku",
    caveat: str | None = None,
) -> EvaluationReport:
    """Ukur leksikon terhadap pasangan (teks, label_benar).

    Pada `accuracy`, abstain dihitung SALAH, bukan dikeluarkan dari penyebut.
    Kalau tidak, akurasi bisa dinaikkan hanya dengan membuat alatnya lebih
    sering menyerah — angka yang naik sambil kegunaannya turun. Akurasi versi
    longgarnya tetap dilaporkan terpisah lewat `accuracy_scored_only`, karena
    abstain pada kalimat yang memang tidak bermuatan sentimen adalah perilaku
    yang benar, bukan kegagalan.
    """
    classes = ("positif", "netral", "negatif")
    confusion: dict[str, dict[str, int]] = {a: dict.fromkeys(classes, 0) for a in classes}
    abstain_by_class: dict[str, int] = dict.fromkeys(classes, 0)
    abstained = 0
    correct = 0

    for text, truth in labeled:
        if truth not in classes:
            raise ValueError(f"label tidak dikenal: {truth}")
        r = score(text, register=register)
        if r.score is None:
            abstained += 1
            abstain_by_class[truth] += 1
            predicted = "netral"  # abstain diperlakukan sebagai tebakan netral
        else:
            predicted = r.label
        confusion[truth][predicted] += 1
        if r.score is not None and predicted == truth:
            correct += 1

    n = len(labeled)
    per_class: dict[str, dict[str, float]] = {}
    f1s: list[float] = []
    for c in classes:
        tp = confusion[c][c]
        fp = sum(confusion[o][c] for o in classes if o != c)
        fn = sum(confusion[c][o] for o in classes if o != c)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[c] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": float(sum(confusion[c].values())),
        }
        f1s.append(f1)

    scored = n - abstained
    return EvaluationReport(
        n=n,
        n_scored=scored,
        accuracy=round(correct / n, 3) if n else 0.0,
        accuracy_scored_only=round(correct / scored, 3) if scored else 0.0,
        macro_f1=round(sum(f1s) / len(f1s), 3) if f1s else 0.0,
        per_class=per_class,
        abstain_rate=round(abstained / n, 3) if n else 0.0,
        abstain_by_class=abstain_by_class,
        confusion=confusion,
        caveat=caveat
        or (
            "Angka ini diukur pada set evaluasi internal yang ditulis tim "
            "pengembang, bukan sampel acak dari percakapan yang sedang "
            "dianalisis. Ia menunjukkan bahwa leksikon berperilaku seperti yang "
            "dimaksudkan, BUKAN bahwa akurasi yang sama berlaku pada data "
            "proyek Anda. Sebelum dipakai untuk keputusan, ukur ulang terhadap "
            "sampel berlabel dari data proyek itu sendiri."
        ),
    )
