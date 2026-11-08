"""Pola frasa bermuatan untuk penilai ragam informal (informal-4).

Kamus kata tunggal tidak bisa membaca kritik yang maknanya ada di gabungan
kata: "gk bisa mengatasi bbm", "ganti aja", "tidak punya otak", "cari muka",
"mulutnya kaya ular berbisa". Tiap kata di situ netral ("ganti oli", "antrean
kayak ular"); yang bermuatan adalah susunannya.

Modul ini mencocokkan susunan itu pada token yang SUDAH dinormalisasi
(`informal.canonical_tokens`), jadi "gk", "ga", "ora", "teu" semuanya sudah
menjadi "tidak". Frasa yang cocok dinilai sebagai satu penanda dan tokennya
dikeluarkan dari penilaian kata per kata, sehingga "tidak" di dalam frasa tidak
ikut membalik kata lain di sekitarnya.

## Aturan penyusunan (sama dengan informal-2/3)

Frasa dipilih dari komentar BBM Bali yang abstain di luar sampel manual 400,
dibaca konteksnya, dan hanya dipertahankan kalau maknanya tidak bergantung
konteks. Yang SENGAJA tidak ada:

- "tidak mampu" tanpa kata kerja: "rakyat tidak mampu" berarti miskin, bukan cela.
- "ular" sendirian: "antrean kayak ular" hanya gambaran panjang antrean.
- "diam kamu": kutipan ucapan gubernur; dikutip untuk mengkritik maupun sekadar
  melaporkan.
- "bukan robot", "petugas partai": bisa membela atau melabeli, tidak tentu nadanya.

Frasa tidak diberi penguat atau negasi dari luar; bobotnya tetap.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

#: Slot kata kerja yang dipakai beberapa pola: kinerja pejabat.
_KERJA = frozenset(
    [
        "kerja", "bekerja", "mengatasi", "atasi", "mengurus", "ngurus", "urus",
        "mengurusi", "ngurusi", "mengayomi", "memimpin", "mimpin", "mengelola",
        "kelola", "menyelesaikan", "selesaikan", "nyelesain", "memenuhi",
    ]  # fmt: skip
)
#: Semua bentuk negator yang bisa keluar dari normalisasi: yang ada di
#: `sentiment.NEGATORS` dibiarkan apa adanya ("gak", "nggak"), sisanya sudah
#: dipetakan ke "tidak" ("gk", "ora", "teu").
_TIDAK = frozenset({"tidak", "tak", "gak", "ga", "nggak", "enggak", "belum"})


@dataclass(frozen=True)
class Pattern:
    """Satu pola: urutan slot, tiap slot himpunan kata yang boleh mengisinya."""

    slots: tuple[frozenset[str], ...]
    weight: float
    label: str


def _p(label: str, weight: float, *slots: str | frozenset[str]) -> Pattern:
    built = tuple(frozenset(s.split()) if isinstance(s, str) else s for s in slots)
    return Pattern(slots=built, weight=weight, label=label)


#: Diurutkan dari yang terpanjang supaya "tidak bisa mengatasi" menang atas
#: pola yang lebih pendek di posisi yang sama.
PATTERNS: tuple[Pattern, ...] = tuple(
    sorted(
        [
            # kinerja: "gk bisa mengatasi", "tidak mampu ngurus", "ga becus kerja"
            _p("tidak bisa bekerja/mengatasi", -0.7, _TIDAK, "bisa mampu becus sanggup", _KERJA),
            # watak: "tidak punya otak/hati/empati/malu/adab"
            _p(
                "tidak punya hati/otak/empati",
                -0.7,
                _TIDAK,
                "punya ada",
                "otak hati empati adab etika malu nurani akhlak moral wibawa wibawanya",
            ),
            _p("tidak ada/punya solusi", -0.6, _TIDAK, "punya ada kasih", "solusi"),
            _p("tidak tahu diri/malu", -0.8, _TIDAK, "tau tahu", "diri malu"),
            _p("tidak masuk akal", -0.6, _TIDAK, "masuk", "akal"),
            _p("tidak pro rakyat", -0.6, _TIDAK, "pro", "rakyat"),
            _p("tidak pantas", -0.6, _TIDAK, "pantas pantes"),
            _p("tidak peka", -0.6, _TIDAK, "peka"),
            _p("tidak kompeten", -0.6, _TIDAK, "kompeten"),
            # tuntutan
            _p("ganti aja", -0.6, "ganti diganti gantiin", "aja saja ajah dong"),
            _p("jangan pilih lagi", -0.6, "jangan", "pilih dipilih milih", "lagi"),
            _p("jangan pilih", -0.5, "jangan", "pilih dipilih milih"),
            # tuduhan dan kiasan
            _p("cari muka", -0.6, "cari", "muka"),
            _p("asal ngomong", -0.6, "asal", "ngomong bunyi bicara jeplak"),
            _p("pengalihan isu", -0.5, "pengalihan", "isu"),
            _p("biang kerok", -0.7, "biang", "kerok"),
            _p("muka tembok", -0.7, "muka", "tembok"),
            _p("lepas tangan", -0.6, "lepas", "tangan"),
            _p("ular berbisa", -0.7, "ular", "berbisa"),
            _p(
                "cuma bisa memerintah/marah",
                -0.5,
                "cuma hanya bisanya cuman",
                "bisa",
                "nyuruh menyuruh perintah memerintah marah bentak janji klarifikasi pencitraan",
            ),
        ],
        key=lambda pat: -len(pat.slots),
    )
)

#: Semua kata yang muncul di pola, supaya normalisasi mengenalinya (pelepasan
#: klitik: "keroknya" -> "kerok").
VOCAB: frozenset[str] = frozenset(w for pat in PATTERNS for slot in pat.slots for w in slot)

#: Pengganti token frasa yang sudah dinilai. Bukan kata, bukan negator, dan
#: tidak ada di leksikon, jadi tidak memengaruhi penilaian kata di sekitarnya.
PLACEHOLDER = "⟨frasa⟩"


def match(tokens: Sequence[str]) -> tuple[list[str], list[tuple[str, float]]]:
    """Cari pola di `tokens`.

    Kembalikan token baru (frasa diganti PLACEHOLDER) dan penanda frasa.
    """
    out: list[str] = []
    found: list[tuple[str, float]] = []
    i = 0
    while i < len(tokens):
        for pat in PATTERNS:
            n = len(pat.slots)
            window = tokens[i : i + n]
            if len(window) == n and all(
                t in slot for t, slot in zip(window, pat.slots, strict=True)
            ):
                out.append(PLACEHOLDER)
                found.append((pat.label, pat.weight))
                i += n
                break
        else:
            out.append(tokens[i])
            i += 1
    return out, found
