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
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from app.services.ingestion import normalize_text, wordset

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
    "bagus": 0.8, "baik": 0.7, "mantap": 0.9, "hebat": 0.9, "keren": 0.8,
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
    "menumpuk": 0.5, "mangkrak": 0.8, "terbengkalai": 0.8, "asal": 0.5,
}

LEXICON: dict[str, float] = {
    **{w: s for w, s in _POSITIVE.items()},
    **{w: -s for w, s in _NEGATIVE.items()},
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
        if tokens[j] in CLAUSE_BREAKS:
            break
        scope.append(tokens[j])
    return scope


def _modifier(tokens: Sequence[str], i: int) -> float:
    """Faktor dari negator/penguat/pelemah di sekitar posisi i."""
    factor = 1.0
    back = _preceding_scope(tokens, i)
    if any(t in NEGATORS for t in back):
        factor *= NEGATION_FACTOR
    if any(t in PRE_INTENSIFIERS for t in back):
        factor *= INTENSIFY_FACTOR
    if any(t in DIMINISHERS for t in back):
        factor *= DIMINISH_FACTOR
    # Penguat pasca-kata: "bagus sekali". Cukup satu token ke depan.
    if i + 1 < len(tokens) and tokens[i + 1] in POST_INTENSIFIERS:
        factor *= INTENSIFY_FACTOR
    return factor


def score(text: str) -> SentimentResult:
    """Skor sentimen -1..1, atau abstain kalau tak ada dasar.

    Perhatikan bahwa "kurang" ada di NEGATORS sekaligus bukan penanda negatif
    sendirian: "kurang puas" jadi negatif lewat pembalikan, bukan lewat entri
    leksikon terpisah. Itu disengaja — memasukkan "kurang" sebagai kata negatif
    akan menghitungnya dua kali.
    """
    tokens = normalize_text(text).split()
    matched: list[tuple[str, float]] = []

    for i, tok in enumerate(tokens):
        base = LEXICON.get(tok)
        if base is None:
            continue
        matched.append((tok, round(base * _modifier(tokens, i), 3)))

    if not matched:
        return SentimentResult(score=None, label="tidak dinilai", confidence=0.0)

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


def evaluate(labeled: Sequence[tuple[str, str]]) -> EvaluationReport:
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
        r = score(text)
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
        caveat=(
            "Angka ini diukur pada set evaluasi internal yang ditulis tim "
            "pengembang, bukan sampel acak dari percakapan yang sedang "
            "dianalisis. Ia menunjukkan bahwa leksikon berperilaku seperti yang "
            "dimaksudkan, BUKAN bahwa akurasi yang sama berlaku pada data "
            "proyek Anda. Sebelum dipakai untuk keputusan, ukur ulang terhadap "
            "sampel berlabel dari data proyek itu sendiri."
        ),
    )
