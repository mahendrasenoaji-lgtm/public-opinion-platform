"""Penanda emosi ragam baku + informal (`emosi-id-2`). Fungsi murni.

Pengganti saat-baca untuk `sentiment.emotions()` (`lexicon-id-1`), yang hanya
mengenal ejaan baku dan karena itu mengenai sekitar 5% komentar nyata. Yang
ditambah di sini:

- kosakata ragam cakap dan ejaan yang dirapikan (`informal.split_informal`
  memangkas huruf berulang: "kecewaaa" -> "kecewaa" -> cocok lewat `canonical`);
- emoji bermuatan emosi;
- kategori `anticipation` (harapan), yang sering muncul di komentar publik
  ("semoga", "mudah-mudahan") dan tidak tertampung enam kategori lama;
- negasi sederhana: penanda yang tepat didahului kata negasi dilewati
  ("tidak marah" bukan marah). Negasi yang lebih jauh tidak dilihat.

Ini tetap PENANDA KATA, bukan klasifikasi emosi, dan belum dievaluasi
terhadap label manusia. Kata yang maknanya bergantung konteks ("gila",
"parah", "anjir") sengaja TIDAK dimasukkan: di kolom komentar ia sama sering
dipakai untuk kagum maupun marah. Begitu juga emoji tertawa (😂, 🤣), yang di
kolom komentar politik lebih sering berarti ejekan daripada gembira, serta
kata umum seperti "nanti", "minta", "susah", "mundur".

Dihitung saat dibaca, bukan disimpan: kolom `mentions.emotion` tetap berisi
hasil `lexicon-id-1` dari saat ingest, dan mengganti isinya berarti menulis
ulang data riset. Karena penilainya deterministik, hasil saat-baca selalu
bisa diulang.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.services.informal import canonical, emoji_marks, split_informal
from app.services.ingestion import wordset
from app.services.sentiment import NEGATORS

MODEL_VERSION = "emosi-id-2"

METHOD = (
    "leksikon emosi emosi-id-2 (penanda kata ragam baku dan informal + emoji, "
    "negasi satu kata); belum dievaluasi terhadap label manusia"
)

#: Urutan tampil.
KEYS: tuple[str, ...] = (
    "anger",
    "fear",
    "sadness",
    "disgust",
    "joy",
    "trust",
    "anticipation",
)

_WORDS: dict[str, str] = {
    "anger": """
        marah geram kesal benci muak   berang murka jengkel kesel sebel sebal
        dongkol gedek gregetan greget gemas gemes ngamuk mengamuk emosian naik pitam
        keterlaluan kurang ajar kurangajar brengsek bangsat bajingan sialan keparat
        biadab laknat goblok tolol bodoh bego dungu bacot bedebah zalim dzalim zolim
        copot pecat            
    """,
    "fear": """
        takut khawatir cemas was panik ngeri resah waswas gelisah kuatir kawatir
        seram serem horor bahaya berbahaya terancam ancaman ngeri mencekam
        deg degan trauma parno
    """,
    "sadness": """
        sedih kecewa pilu prihatin duka menderita sengsara miris kasihan kasian
        kesian nangis menangis tangis nelangsa merana   sengsara nestapa
        terpuruk pasrah lelah capek cape letih putus asa sakit hati menyedihkan
        memprihatinkan turut berduka malang
    """,
    "disgust": """
        jijik muak risih najis mual eneg enek jijay busuk bobrok bau munafik
        menjijikkan memuakkan memalukan malu maluin tidak tahu malu gak tau malu
        penjilat pencitraan drama lebay alay norak kotor sampah
    """,
    "joy": """
        senang gembira bahagia lega syukur bangga puas alhamdulillah seneng
        hepi happy bersyukur asik asyik mantap mantul keren hebat salut  
        luar biasa terima kasih makasih terimakasih bravo    
    """,
    "trust": """
        percaya yakin amanah   andal dukung mendukung setuju sepakat
        bismillah     tepercaya terpercaya solid kompak tegas adil
        bijak bijaksana peduli merakyat pro rakyat
    """,
    "anticipation": """
        semoga harap berharap harapan mudah mudahan moga amin aamiin amiin
        ditunggu menunggu nunggu   segera secepatnya    
        tolong mohon        
    """,
}

_EMOJI: dict[str, str] = {
    "😡": "anger", "🤬": "anger", "😠": "anger", "👿": "anger", "💢": "anger",
    "😱": "fear", "😨": "fear", "😰": "fear", "😟": "fear",
    "😭": "sadness", "😢": "sadness", "😞": "sadness", "😔": "sadness", "💔": "sadness",
    "🥲": "sadness", "😥": "sadness",
    "🤮": "disgust", "🤢": "disgust", "💩": "disgust",
    "😁": "joy", "😊": "joy", "🥰": "joy", "😍": "joy",
    "🎉": "joy", "👏": "joy",
    "👍": "trust", "💪": "trust", "🤝": "trust", "✊": "trust", "🫡": "trust",
    "🙏": "anticipation", "🤲": "anticipation", "🤞": "anticipation",
}  # fmt: skip


def _build() -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    singles: dict[str, str] = {}
    pairs: dict[tuple[str, str], str] = {}
    for key, block in _WORDS.items():
        for line in block.strip().splitlines():
            words = line.split()
            # Frasa dua kata ditulis berurutan dan dikenali lewat daftar di bawah.
            for word in words:
                singles.setdefault(word, key)
    for a, b, key in _PAIRS:
        pairs[(a, b)] = key
    return singles, pairs


#: Frasa dua kata: dinilai utuh, dan kata penyusunnya TIDAK dihitung sendiri.
_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("naik", "pitam", "anger"),
    ("kurang", "ajar", "anger"),
    ("deg", "degan", "fear"),
    ("putus", "asa", "sadness"),
    ("sakit", "hati", "sadness"),
    ("turut", "berduka", "sadness"),
    ("tahu", "malu", "disgust"),
    ("tau", "malu", "disgust"),
    ("luar", "biasa", "joy"),
    ("terima", "kasih", "joy"),
    ("pro", "rakyat", "trust"),
    ("mudah", "mudahan", "anticipation"),
)

#: Kata yang hanya bermakna emosi sebagai bagian frasa di `_PAIRS`.
_PAIR_ONLY = wordset("""
    naik pitam kurang ajar deg degan putus asa sakit hati turut berduka tahu tau
    luar biasa terima kasih pro rakyat mudah mudahan tidak gak was
""")

_SINGLES, _PAIR_MAP = _build()
for _word in _PAIR_ONLY:
    _SINGLES.pop(_word, None)
#: "was" hanya sebagai "was was"/"waswas"; "malu" sendiri tetap disgust.
_PAIR_MAP[("was", "was")] = "fear"

_VOCAB = frozenset(_SINGLES) | {w for pair in _PAIR_MAP for w in pair} | NEGATORS


@dataclass(frozen=True, slots=True)
class EmotionHit:
    key: str
    marker: str


def markers(text: str) -> list[EmotionHit]:
    """Penanda emosi di `text`, masing-masing penanda sekali."""
    tokens = [canonical(t, _VOCAB) for t in split_informal(text)]
    hits: list[EmotionHit] = []
    seen: set[str] = set()
    skip = False
    for i, tok in enumerate(tokens):
        if skip:
            skip = False
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        negated = i > 0 and tokens[i - 1] in NEGATORS
        key: str | None = None
        marker = tok
        if nxt is not None and (tok, nxt) in _PAIR_MAP:
            key = _PAIR_MAP[(tok, nxt)]
            marker = f"{tok} {nxt}"
            skip = True
            # "tidak tahu malu" adalah frasa jijik, bukan negasi.
            negated = negated and marker not in {"tahu malu", "tau malu"}
        elif tok in _SINGLES:
            key = _SINGLES[tok]
        if key is None or negated or marker in seen:
            continue
        seen.add(marker)
        hits.append(EmotionHit(key=key, marker=marker))
    for mark in emoji_marks(text, _EMOJI):
        hits.append(EmotionHit(key=_EMOJI[mark], marker=mark))
    return hits


def emotions(text: str) -> dict[str, float]:
    """Porsi tiap emosi di antara penanda yang ditemukan. Kosong bila tidak ada."""
    hits = markers(text)
    if not hits:
        return {}
    counts: dict[str, int] = {}
    for hit in hits:
        counts[hit.key] = counts.get(hit.key, 0) + 1
    total = sum(counts.values())
    return {k: round(v / total, 3) for k, v in counts.items()}


def top_markers(texts: Iterable[str], *, limit: int = 5) -> dict[str, list[tuple[str, int]]]:
    """Penanda paling sering per emosi (jumlah konten yang memuatnya)."""
    counts: dict[str, dict[str, int]] = {k: {} for k in KEYS}
    for text in texts:
        for hit in markers(text):
            bucket = counts[hit.key]
            bucket[hit.marker] = bucket.get(hit.marker, 0) + 1
    return {
        key: sorted(bucket.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
        for key, bucket in counts.items()
    }


def analyse(
    texts: Iterable[str], *, limit: int = 5
) -> tuple[list[dict[str, float]], dict[str, list[tuple[str, int]]]]:
    """Satu lintasan: porsi emosi per teks + penanda paling sering per emosi."""
    shares: list[dict[str, float]] = []
    counts: dict[str, dict[str, int]] = {k: {} for k in KEYS}
    for text in texts:
        hits = markers(text)
        per: dict[str, int] = {}
        for hit in hits:
            per[hit.key] = per.get(hit.key, 0) + 1
            bucket = counts[hit.key]
            bucket[hit.marker] = bucket.get(hit.marker, 0) + 1
        total = sum(per.values())
        shares.append({k: round(v / total, 3) for k, v in per.items()} if total else {})
    top = {
        key: sorted(bucket.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
        for key, bucket in counts.items()
    }
    return shares, top
