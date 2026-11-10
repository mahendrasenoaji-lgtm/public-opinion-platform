"""Kutipan langsung dan penuturnya dari teks berita. Fungsi murni.

Yang diambil hanya yang TERTULIS: kalimat di dalam tanda petik, dan nama
penutur bila teksnya menyebutkannya dengan pola atribusi baku berita
Indonesia ("…," kata Budi Santoso / Budi Santoso mengatakan, "…"). Tidak ada
penebakan: kutipan tanpa atribusi yang dikenali dikembalikan dengan
`speaker=None`, dan parafrase tanpa tanda petik tidak dianggap kutipan.

Batas yang perlu diketahui pemakai:

- Feed RSS umumnya hanya memuat judul dan ringkasan, jadi kebanyakan kutipan
  di badan artikel tidak pernah sampai ke sini.
- Tanda petik juga dipakai untuk istilah ("program 'makan gratis'"). Karena
  itu kutipan di bawah `MIN_WORDS` kata dibuang.
- Nama penutur diambil apa adanya dari teks (huruf besar di awal kata),
  termasuk jabatan yang menempel di depannya; tidak dicocokkan ke daftar
  orang mana pun.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Di bawah ini, isi tanda petik lebih sering istilah daripada ucapan.
MIN_WORDS = 4
MAX_QUOTE_CHARS = 400

_SAY_AFTER = (
    "kata|ujar|ucap|tutur|tegas|jelas|ungkap|imbuh|tambah|sebut|papar|terang|tandas|"
    "pungkas|tukas|cetus"
)
_SAY_BEFORE = (
    "mengatakan|menyatakan|menegaskan|menyebut|menyebutkan|menjelaskan|mengungkapkan|"
    "menambahkan|menuturkan|berkata|berujar|menilai|mengaku|meminta|memastikan"
)

#: Kata berhuruf besar (boleh berinisial/bertitik: "M.", "H.") atau singkatan.
_CAP = r"[A-Z][\w.'-]*"
_NAME = rf"{_CAP}(?:\s+{_CAP}){{0,5}}"

_QUOTE = re.compile(rf"[\"“”]([^\"“”]{{8,{MAX_QUOTE_CHARS}}})[\"“”]")
_AFTER = re.compile(rf"^\s*,?\s*(?:{_SAY_AFTER})(?:nya)?\s+({_NAME})")
_BEFORE = re.compile(rf"({_NAME})\s+(?:{_SAY_BEFORE})\s*[,:]?\s*$")

#: Kata berhuruf besar yang bukan nama bila berdiri di awal "nama".
_NOT_NAMES = frozenset(
    {"Ia", "Dia", "Mereka", "Kami", "Kita", "Saya", "Menurut", "Namun", "Selain", "Hal", "Itu"}
)


@dataclass(frozen=True, slots=True)
class Quote:
    text: str
    #: Nama penutur seperti tertulis, atau None bila atribusinya tidak dikenali.
    speaker: str | None


#: Keterangan waktu berhuruf besar yang sering menempel sesudah nama.
_TRAILING = frozenset(
    {"Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Jum'at", "Sabtu", "Minggu", "Ahad"}
)


def _clean_name(raw: str) -> str | None:
    words = raw.strip(" .,").split()
    while words and words[0] in _NOT_NAMES:
        words = words[1:]
    while words and words[-1].strip(".,") in _TRAILING:
        words = words[:-1]
    name = " ".join(words).strip(" .,")
    return name if len(name) >= 3 else None


def extract_quotes(text: str) -> list[Quote]:
    """Kutipan langsung di `text`, urut kemunculan, tanpa duplikat."""
    out: list[Quote] = []
    seen: set[str] = set()
    for match in _QUOTE.finditer(text):
        body = " ".join(match.group(1).split()).strip(" ,")
        if len(body.split()) < MIN_WORDS or body in seen:
            continue
        seen.add(body)
        speaker: str | None = None
        after = _AFTER.match(text[match.end() :])
        if after:
            speaker = _clean_name(after.group(1))
        else:
            before = _BEFORE.search(text[: match.start()])
            if before:
                speaker = _clean_name(before.group(1))
        out.append(Quote(text=body, speaker=speaker))
    return out
