"""Peta aktor: kepada siapa sebuah komentar diarahkan, dan di tingkat kekuasaan mana.

Penilai sentimen membaca NADA. Ia tidak tahu bahwa "Bahlil" adalah Menteri ESDM
yang bertanggung jawab atas kebijakan pasokan BBM sekaligus ketua umum partai,
atau bahwa "pak Yan" adalah Gubernur Bali. Modul ini menandai aktor yang
disebut di teks, lalu memetakannya ke tingkat kekuasaan (pusat, daerah, BUMN,
legislatif, partai, petugas lapangan), sehingga nada bisa dibaca per sasaran:
siapa yang paling banyak disorot, di tingkat mana, dan dengan nada apa.

## Batas yang disengaja

- Hanya PEJABAT PUBLIK, LEMBAGA, dan PARTAI yang dipetakan, dengan jabatan yang
  merupakan fakta umum. Afiliasi politik ORANG YANG BERKOMENTAR tidak pernah
  ditebak (CLAUDE.md, bagian 3).
- Pencocokan memakai nama dan julukan yang tercatat di sini, bukan tebakan.
  Kata jabatan umum ("gubernur", "menteri", "presiden") dicatat sebagai tingkat
  kekuasaan, BUKAN sebagai orang tertentu: "gubernur" di komentar BBM Bali
  kebanyakan berarti Koster, tapi juga dipakai untuk Gubernur Jawa Barat
  sebagai pembanding.
- Menyebut tidak sama dengan menyalahkan. Komentar yang menyebut dua aktor
  dihitung untuk keduanya; arah tuduhan tidak dibaca.
- Jabatan berlaku per Oktober 2026 dan perlu diperbarui untuk proyek lain.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.services.ingestion import normalize_text


@dataclass(frozen=True)
class Actor:
    key: str
    name: str
    role: str
    level: str
    aliases: tuple[str, ...]


#: Tingkat kekuasaan, urut dari atas. Dipakai juga untuk kata jabatan umum.
LEVELS: tuple[str, ...] = (
    "Pemerintah pusat",
    "Pemerintah daerah",
    "BUMN energi",
    "Legislatif",
    "Partai politik",
    "Petugas lapangan",
)

ACTORS: tuple[Actor, ...] = (
    Actor(
        "bahlil",
        "Bahlil Lahadalia",
        "Menteri ESDM; Ketua Umum Partai Golkar",
        "Pemerintah pusat",
        ("bahlil", "bahlul", "bahlol", "balil"),
    ),
    Actor(
        "prabowo",
        "Prabowo Subianto",
        "Presiden RI; Ketua Umum Partai Gerindra",
        "Pemerintah pusat",
        ("prabowo", "wowo", "bowo"),
    ),
    Actor("gibran", "Gibran Rakabuming Raka", "Wakil Presiden RI", "Pemerintah pusat", ("gibran",)),
    Actor(
        "jokowi",
        "Joko Widodo",
        "Presiden RI 2014–2024 (sudah tidak menjabat)",
        "Pemerintah pusat",
        ("jokowi", "mulyono"),
    ),
    Actor(
        "koster",
        "Wayan Koster",
        "Gubernur Bali; kader PDI Perjuangan",
        "Pemerintah daerah",
        ("koster", "coster", "pak yan", "gubernur bali", "gub bali", "gubernur koster"),
    ),
    Actor(
        "kdm",
        "Dedi Mulyadi (KDM)",
        "Gubernur Jawa Barat; disebut sebagai pembanding",
        "Pemerintah daerah",
        ("kdm", "dedi mulyadi", "kang dedi"),
    ),
    Actor(
        "pertamina",
        "Pertamina",
        "BUMN penyalur BBM",
        "BUMN energi",
        ("pertamina", "patra niaga", "dirut pertamina"),
    ),
    Actor(
        "awk",
        "Arya Wedakarna (AWK)",
        "Tokoh Bali; disebut 'senator' atau DPD dalam komentar",
        "Legislatif",
        ("wedakarna", "wedhakarna", "awk", "arya weda"),
    ),
    Actor(
        "pdip",
        "PDI Perjuangan",
        "Partai politik (partai Gubernur Bali)",
        "Partai politik",
        ("pdip", "pdi p", "pdi perjuangan", "banteng", "partai banteng"),
    ),
    Actor(
        "golkar",
        "Partai Golkar",
        "Partai politik (partai Menteri ESDM)",
        "Partai politik",
        ("golkar",),
    ),
    Actor(
        "gerindra",
        "Partai Gerindra",
        "Partai politik (partai Presiden)",
        "Partai politik",
        ("gerindra",),
    ),
)

#: Kata jabatan atau lembaga umum -> tingkat kekuasaan, tanpa menunjuk orang.
GENERIC: dict[str, str] = {
    "presiden": "Pemerintah pusat",
    "menteri": "Pemerintah pusat",
    "mentri": "Pemerintah pusat",
    "esdm": "Pemerintah pusat",
    "kementerian": "Pemerintah pusat",
    "pemerintah pusat": "Pemerintah pusat",
    "istana": "Pemerintah pusat",
    "gubernur": "Pemerintah daerah",
    "gubenur": "Pemerintah daerah",
    "gabener": "Pemerintah daerah",
    "gub": "Pemerintah daerah",
    "pemprov": "Pemerintah daerah",
    "pemda": "Pemerintah daerah",
    "bupati": "Pemerintah daerah",
    "walikota": "Pemerintah daerah",
    "wali kota": "Pemerintah daerah",
    "dpr": "Legislatif",
    "dprd": "Legislatif",
    "dpd": "Legislatif",
    "senator": "Legislatif",
    "partai": "Partai politik",
    "petugas spbu": "Petugas lapangan",
    "pegawai spbu": "Petugas lapangan",
    "operator spbu": "Petugas lapangan",
    "karyawan spbu": "Petugas lapangan",
    "petugas pom": "Petugas lapangan",
    "pegawai pom": "Petugas lapangan",
    "mbak spbu": "Petugas lapangan",
}

_BY_KEY: dict[str, Actor] = {a.key: a for a in ACTORS}


def _phrases(text: str) -> set[str]:
    """Semua kata dan pasangan kata berurutan di teks yang sudah dinormalisasi."""
    tokens = normalize_text(text).split()
    grams = set(tokens)
    grams.update(f"{a} {b}" for a, b in zip(tokens, tokens[1:], strict=False))
    # "gubernurnya", "bahlilnya", "kosternya": klitik -nya dilepas untuk pencocokan nama
    grams.update(t[:-3] for t in tokens if t.endswith("nya") and len(t) > 6)
    return grams


def detect(text: str) -> list[str]:
    """Kunci aktor yang disebut di teks, urut seperti di `ACTORS`."""
    grams = _phrases(text)
    return [a.key for a in ACTORS if any(alias in grams for alias in a.aliases)]


def levels(text: str) -> list[str]:
    """Tingkat kekuasaan yang disebut, dari aktor bernama maupun kata jabatan umum."""
    grams = _phrases(text)
    found = {_BY_KEY[k].level for k in detect(text)}
    found.update(level for word, level in GENERIC.items() if word in grams)
    return [lv for lv in LEVELS if lv in found]


def actor(key: str) -> Actor:
    return _BY_KEY[key]


@dataclass(frozen=True, slots=True)
class Tally:
    """Berapa konten menyebut sesuatu, dan nada konten-konten itu."""

    key: str
    n: int
    scored: int
    #: Rata-rata nada konten yang menyebutnya dan bisa dinilai; None bila tidak ada.
    mean: float | None


@dataclass(frozen=True, slots=True)
class ActorSummary:
    n_total: int
    #: Konten yang menyebut minimal satu aktor bernama.
    n_with_actor: int
    actors: list[Tally]
    levels: list[Tally]


def summarize(rows: Iterable[tuple[str, float | None]]) -> ActorSummary:
    """Hitung penyebutan aktor dan tingkat kekuasaan atas `(teks, sentimen)`.

    Nada yang dilaporkan adalah nada KONTEN yang menyebut aktor itu, bukan
    nada terhadap aktornya: komentar yang membela Gubernur sambil memaki
    Menteri terhitung untuk keduanya dengan skor yang sama. Konten yang
    menyebut dua aktor dihitung untuk keduanya, jadi jumlah per aktor bisa
    melebihi `n_with_actor`.
    """
    n_total = n_with = 0
    counts: dict[str, list[float]] = {}
    seen: dict[str, int] = {}
    level_counts: dict[str, list[float]] = {}
    level_seen: dict[str, int] = {}

    for text, sentiment in rows:
        n_total += 1
        grams = _phrases(text)
        keys = [a.key for a in ACTORS if any(alias in grams for alias in a.aliases)]
        found_levels = {_BY_KEY[k].level for k in keys}
        found_levels.update(level for word, level in GENERIC.items() if word in grams)
        if keys:
            n_with += 1
        for key in keys:
            seen[key] = seen.get(key, 0) + 1
            if sentiment is not None:
                counts.setdefault(key, []).append(sentiment)
        for level in found_levels:
            level_seen[level] = level_seen.get(level, 0) + 1
            if sentiment is not None:
                level_counts.setdefault(level, []).append(sentiment)

    def _tally(key: str, n: int, values: list[float]) -> Tally:
        mean = round(sum(values) / len(values), 3) if values else None
        return Tally(key=key, n=n, scored=len(values), mean=mean)

    actor_rows = sorted(
        (_tally(k, n, counts.get(k, [])) for k, n in seen.items()),
        key=lambda t: (-t.n, t.key),
    )
    level_rows = [
        _tally(lv, level_seen[lv], level_counts.get(lv, [])) for lv in LEVELS if lv in level_seen
    ]
    return ActorSummary(
        n_total=n_total, n_with_actor=n_with, actors=actor_rows, levels=level_rows
    )
