"""Pengodean isi unggahan akun resmi dan kesepakatan antar-pengode.

Lembar coding: `docs/kerangka-kinerja-komunikasi-pemerintah.md` Lampiran A.
Variabel A9-A18 dikode manusia; modul ini hanya memeriksa nilainya, meringkas
sebarannya, dan menghitung Krippendorff alpha (Hayes & Krippendorff, 2007;
Krippendorff, 2019) pada unggahan yang dikode lebih dari satu orang.

Fungsi murni, tanpa I/O. Tiga hal yang dijaga:

1. Kode tidak pernah diisi mesin. Variabel yang dikosongkan pengode tetap
   kosong dan diperlakukan sebagai data hilang oleh alpha.
2. Alpha tidak terbit bila unggahan yang dikode ganda kurang dari
   `MIN_DOUBLE_CODED`; angka dari segelintir unggahan menyesatkan.
3. Sebaran kode tidak terbit untuk variabel yang alphanya di bawah
   `ALPHA_TENTATIVE`: kategorinya harus diperbaiki dulu.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

Level = Literal["nominal", "ordinal"]

#: Ambang Krippendorff (2019): >= 0,800 dapat diandalkan; 0,667-0,800 hanya
#: untuk kesimpulan sementara; di bawah itu kategorinya diperbaiki dulu.
ALPHA_RELIABLE: Final = 0.8
ALPHA_TENTATIVE: Final = 0.667

#: Unggahan dikode ganda paling sedikit supaya alpha ditampilkan.
MIN_DOUBLE_CODED: Final = 20

#: Porsi data yang dianjurkan dikode ganda (Lampiran A).
TARGET_DOUBLE_SHARE: Final = 0.10


@dataclass(frozen=True)
class Variable:
    code: str
    name: str
    level: Level
    #: Nilai sah dan labelnya, urut. Untuk variabel ordinal urutan = peringkat.
    values: tuple[tuple[int, str], ...]


def _v(code: str, name: str, level: Level, *values: tuple[int, str]) -> Variable:
    return Variable(code, name, level, values)


VARIABLES: Final[tuple[Variable, ...]] = (
    _v("A9", "Kategori konten", "nominal",
       (1, "informasi kebijakan"), (2, "kegiatan pimpinan (seremonial)"),
       (3, "klarifikasi atau bantahan"), (4, "layanan dan imbauan"),
       (5, "ucapan dan hari besar"), (6, "ajakan partisipasi"), (7, "lain-lain")),
    _v("A11", "Jenis komunikasi", "nominal",
       (1, "satu arah (memberi tahu)"), (2, "meminta tanggapan"),
       (3, "menjawab publik"), (4, "presentasi diri")),
    _v("A12", "Sumber informasi disebut", "nominal", (0, "tidak"), (1, "ya")),
    _v("A14", "Kelengkapan informasi", "ordinal",
       (0, "0 unsur"), (1, "1 unsur"), (2, "2 unsur"), (3, "3 unsur"),
       (4, "4 unsur"), (5, "5 unsur")),
    _v("A15", "Bahasa", "ordinal",
       (1, "birokratis"), (2, "campuran"), (3, "mudah dipahami")),
    _v("A16", "Ajakan bertindak yang jelas", "nominal", (0, "tidak"), (1, "ya")),
    _v("A17", "Mutu visual atau cerita", "ordinal",
       (1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")),
    _v("A18", "Identitas visual konsisten", "nominal", (0, "tidak"), (1, "ya")),
)

VARIABLE_BY_CODE: Final[dict[str, Variable]] = {v.code: v for v in VARIABLES}


def validate_codes(codes: Mapping[str, int | None]) -> dict[str, int]:
    """Buang yang kosong, tolak variabel atau nilai yang tidak dikenal."""
    out: dict[str, int] = {}
    for code, value in codes.items():
        variable = VARIABLE_BY_CODE.get(code)
        if variable is None:
            raise ValueError(f"Variabel tidak dikenal: {code}.")
        if value is None:
            continue
        if value not in {v for v, _ in variable.values}:
            raise ValueError(f"Nilai {value} tidak sah untuk {code} ({variable.name}).")
        out[code] = value
    if not out:
        raise ValueError("Isi paling sedikit satu variabel.")
    return out


# ----------------------------------------------------- Krippendorff alpha ----


def krippendorff_alpha(
    units: Iterable[Sequence[int]], *, level: Level = "nominal"
) -> float | None:
    """Alpha untuk data dengan jumlah pengode berapa pun dan data hilang.

    `units`: satu urutan nilai per unggahan, satu nilai per pengode yang
    mengisinya. Unggahan dengan kurang dari dua nilai tidak bisa dipasangkan
    dan dilewati. Mengembalikan None bila tidak ada pasangan, atau bila semua
    nilai sama (tanpa variasi, kesepakatan tidak bisa dibedakan dari
    kebetulan).
    """
    pairable = [list(u) for u in units if len(u) >= 2]
    if not pairable:
        return None

    # Matriks koinsidensi: tiap pasangan berurut dalam satu unggahan berbobot
    # 1/(m-1), m = jumlah nilai pada unggahan itu.
    coincidence: defaultdict[tuple[int, int], float] = defaultdict(float)
    for values in pairable:
        weight = 1.0 / (len(values) - 1)
        for i, a in enumerate(values):
            for j, b in enumerate(values):
                if i != j:
                    coincidence[(a, b)] += weight

    totals: defaultdict[int, float] = defaultdict(float)
    for (a, _), w in coincidence.items():
        totals[a] += w
    n = sum(totals.values())
    categories = sorted(totals)
    if len(categories) < 2 or n <= 1:
        return None

    def delta(a: int, b: int) -> float:
        if a == b:
            return 0.0
        if level == "nominal":
            return 1.0
        lo, hi = (a, b) if a < b else (b, a)
        between = sum(totals[g] for g in categories if lo <= g <= hi)
        return float((between - (totals[lo] + totals[hi]) / 2) ** 2)

    observed = sum(w * delta(a, b) for (a, b), w in coincidence.items())
    expected = sum(
        totals[a] * totals[b] * delta(a, b) for a in categories for b in categories
    ) / (n - 1)
    if expected == 0:
        return None
    return round(1 - observed / expected, 3)


def reliability_label(alpha: float | None) -> str:
    if alpha is None:
        return "tidak bisa dihitung"
    if alpha >= ALPHA_RELIABLE:
        return "dapat diandalkan"
    if alpha >= ALPHA_TENTATIVE:
        return "hanya untuk kesimpulan sementara"
    return "kategori perlu diperbaiki"


@dataclass(frozen=True)
class VariableReliability:
    code: str
    name: str
    level: Level
    #: Unggahan yang variabel ini diisi minimal dua pengode.
    n_double_coded: int
    #: None bila `n_double_coded` di bawah ambang atau tanpa variasi.
    alpha: float | None
    label: str
    #: Porsi unggahan dikode ganda yang SEMUA pengodenya memberi nilai sama.
    percent_agreement: float | None


@dataclass(frozen=True)
class Reliability:
    n_posts: int
    n_coded: int
    n_double_coded: int
    n_coders: int
    #: Dikode ganda dibagi seluruh unggahan; dibanding `TARGET_DOUBLE_SHARE`.
    double_share: float
    meets_target: bool
    variables: tuple[VariableReliability, ...]


def reliability(
    codings: Mapping[Hashable, Mapping[Hashable, Mapping[str, int]]], *, n_posts: int
) -> Reliability:
    """`codings[unggahan][pengode] = {variabel: nilai}` menjadi alpha per variabel."""
    coders = {coder for per_post in codings.values() for coder in per_post}
    double = sum(1 for per_post in codings.values() if len(per_post) >= 2)
    variables: list[VariableReliability] = []
    for variable in VARIABLES:
        units = [
            [c[variable.code] for c in per_post.values() if variable.code in c]
            for per_post in codings.values()
        ]
        paired = [u for u in units if len(u) >= 2]
        enough = len(paired) >= MIN_DOUBLE_CODED
        alpha = krippendorff_alpha(paired, level=variable.level) if enough else None
        variables.append(
            VariableReliability(
                code=variable.code,
                name=variable.name,
                level=variable.level,
                n_double_coded=len(paired),
                alpha=alpha,
                label=(
                    reliability_label(alpha)
                    if enough
                    else f"data tidak cukup (butuh {MIN_DOUBLE_CODED} unggahan dikode ganda)"
                ),
                percent_agreement=(
                    round(sum(len(set(u)) == 1 for u in paired) / len(paired), 3)
                    if enough
                    else None
                ),
            )
        )
    share = double / n_posts if n_posts > 0 else 0.0
    return Reliability(
        n_posts=n_posts,
        n_coded=len(codings),
        n_double_coded=double,
        n_coders=len(coders),
        double_share=round(share, 3),
        meets_target=share >= TARGET_DOUBLE_SHARE and double >= MIN_DOUBLE_CODED,
        variables=tuple(variables),
    )


# ------------------------------------------------------------ sebaran ----


@dataclass(frozen=True)
class Distribution:
    code: str
    name: str
    n: int
    #: (nilai, label, jumlah unggahan), urut nilai.
    counts: tuple[tuple[int, str, int], ...]


def distributions(
    first_codings: Iterable[Mapping[str, int]],
) -> tuple[Distribution, ...]:
    """Sebaran nilai per variabel dari SATU kode per unggahan.

    Pemanggil memilih kode mana yang mewakili (pengode pertama); kode pengode
    kedua dipakai untuk alpha, bukan untuk menggandakan hitungan.
    """
    tallies: dict[str, Counter[int]] = {v.code: Counter() for v in VARIABLES}
    for codes in first_codings:
        for code, value in codes.items():
            if code in tallies:
                tallies[code][value] += 1
    return tuple(
        Distribution(
            code=v.code,
            name=v.name,
            n=sum(tallies[v.code].values()),
            counts=tuple((value, label, tallies[v.code][value]) for value, label in v.values),
        )
        for v in VARIABLES
    )
