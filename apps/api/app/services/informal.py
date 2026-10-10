"""Normalisasi ragam informal Bahasa Indonesia (komentar media sosial).

Leksikon di `services/sentiment.py` ditulis dalam ejaan baku. Komentar publik
tidak: "gk", "sdh", "betuuuul", "anak2", "mksh". Diukur pada 440 komentar
YouTube nyata (`sentiment_eval_field.py`), leksikon baku abstain pada ~73%
di antaranya — bukan karena komentarnya tak bermuatan, tapi karena kata
bermuatannya dieja dengan cara yang tidak dikenali.

Modul ini HANYA mengembalikan ejaan ke bentuk yang dikenali. Ia tidak menilai
apa pun dan tidak tahu leksikon mana yang memakainya; kosakata sasaran
dioper sebagai argumen ke `canonical()`.

## Yang sengaja tidak dilakukan

- **Tidak ada stemming umum.** Hanya klitik di ekor (-nya, -lah, -kah, -mu,
  -ku) yang dilepas, dan hanya kalau sisanya memang ada di kosakata. Stemmer
  penuh akan menyamakan "membantu" dengan "pembantu".
- **Tidak ada koreksi salah ketik bebas** (jarak sunting). "Maaataaap" tidak
  ditebak jadi "mantap". Setiap pemetaan di `SLANG` ditulis tangan supaya
  setiap skor tetap bisa ditelusuri ke aturan yang memicunya.
- **Bahasa daerah tidak diterjemahkan.** Komentar berbahasa Jawa atau Sunda
  tetap tidak terbaca, dan akan abstain.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection

from app.services.ingestion import _URL_RE, normalize_text

#: Ejaan informal -> bentuk yang dipakai leksikon. Ditulis per kelompok fungsi
#: supaya mudah disunting. Hanya kata yang memengaruhi skor (negator, penguat,
#: penghubung klausa, kata bermuatan) — bukan kamus singkatan umum.
_SLANG_GROUPS: dict[str, str] = {
    # negator
    "tidak": "gk ga gak g ngga nggak ngak kagak kgk ndak ndk nda tdk tida engga enga engak gax",
    "belum": "blm blom belom",
    "jangan": "jgn jngn jgan jagan",
    "bukan": "bkn",
    "tanpa": "tnpa",
    "kurang": "krg",
    # penguat / pelemah
    "banget": "bgt bngt bgtt bangat bingit",
    "sangat": "sgt sngt sanggat",
    "sekali": "skali skli",
    # penghubung klausa
    "tapi": "tp tpi",
    "padahal": "pdhl pdhal padhal",
    # kata bermuatan
    "mantap": "mantab mantaf mntap mantul",
    "bagus": "bgs",
    "terimakasih": "mksh makasih makasi trims tks trimakasih",
    "setuju": "stuju setujuh",
    "betul": "betol btul btl",
    "kecewa": "kcw",
    "susah": "ssh",
    "percuma": "percumah",
    "peduli": "perduli",
    "korupsi": "kurup korup koropsi keropsi korupsii",
    "koruptor": "koroptor",
    "amburadul": "amboradol amburadol",
    "biadab": "biadad biadap",
    "bodoh": "bdoh bodo",
    "goblok": "goblog gblk",
    "zalim": "dzalim dzolim zolim zholim dholim",
    "mubazir": "mubadir mubajir mubazzir",
    "kasihan": "kasian kesian ksian",
    "khianat": "hianat",
    "pengkhianat": "penghianat",
    "seram": "serem",
    "menyesal": "nyesel",
    "utang": "hutang",
}

SLANG: dict[str, str] = {
    variant: canon for canon, variants in _SLANG_GROUPS.items() for variant in variants.split()
}

#: Frasa dua kata yang di leksikon ditulis serangkai. Tanpa ini entri seperti
#: "omongkosong" tidak pernah cocok dengan teks mana pun.
PHRASES: dict[tuple[str, str], str] = {
    ("terima", "kasih"): "terimakasih",
    ("trima", "kasih"): "terimakasih",
    ("omong", "kosong"): "omongkosong",
    ("putus", "asa"): "putusasa",
    ("tepat", "sasaran"): "tepatsasaran",
    ("tanggung", "jawab"): "tanggungjawab",
    ("bertanggung", "jawab"): "tanggungjawab",
}

#: Klitik yang boleh dilepas dari ekor kata. Urutannya penting: "-nya" dicoba
#: sebelum "-a" yang tidak ada di sini (dan memang tidak boleh ada).
_CLITICS = ("nya", "lah", "kah", "mu", "ku")

_RUN3_RE = re.compile(r"(.)\1{2,}")
_RUN2_RE = re.compile(r"(.)\1")
#: "anak2", "gara2", "anak2nya" — angka 2 sebagai tanda ulang. NFKC di
#: normalize_text() sudah mengubah "²" jadi "2".
_REDUP_RE = re.compile(r"^([a-z]{3,})2(nya)?$")

#: Penanda batas klausa yang disisipkan `canonical_tokens()` di tempat tanda
#: baca pemisah. normalize_text() membuang tanda baca, sehingga tanpa ini
#: negasi di "gk becus, bubarkan aja" ikut membalik "bubarkan". Bukan huruf,
#: jadi tidak mungkin bertabrakan dengan token sungguhan.
CLAUSE_BOUNDARY = "|"
_CLAUSE_SPLIT_RE = re.compile(r"[,.;:!?\n]+")

#: Emoji dibaca dari teks MENTAH: normalize_text() membuang semua yang bukan
#: huruf/angka, jadi sesudahnya ia sudah hilang.
_VARIATION_SELECTOR = "️"


def split_informal(raw: str) -> list[str]:
    """Token ternormalisasi, dengan tanda ulang dan huruf berulang dirapikan.

    Huruf yang diulang tiga kali atau lebih dipangkas jadi DUA, bukan satu:
    "maaaf" harus tetap bisa jadi "maaf". Pemangkasan ke satu huruf dicoba
    belakangan di `canonical()`, dan hanya dipakai kalau hasilnya dikenali.
    """
    tokens: list[str] = []
    for tok in normalize_text(raw).split():
        tok = _RUN3_RE.sub(r"\1\1", tok)
        redup = _REDUP_RE.match(tok)
        if redup:
            tok = redup.group(1)
        tokens.append(tok)
    return tokens


def _known(tok: str, vocab: Collection[str]) -> str | None:
    if tok in vocab:
        return tok
    mapped = SLANG.get(tok)
    if mapped is not None:
        return mapped
    return None


def canonical(tok: str, vocab: Collection[str]) -> str:
    """Bentuk `tok` yang dikenali `vocab`, atau `tok` apa adanya.

    Dicoba berurutan, berhenti di yang pertama berhasil: apa adanya atau lewat
    `SLANG`; huruf ganda dipangkas ("mantapp" -> "mantap"); klitik ekor
    dilepas ("parahnya" -> "parah"). Kalau tidak ada yang dikenali, token
    dikembalikan TANPA diubah — modul ini tidak menebak.
    """
    hit = _known(tok, vocab)
    if hit is not None:
        return hit

    squeezed = _RUN2_RE.sub(r"\1", tok)
    if squeezed != tok:
        hit = _known(squeezed, vocab)
        if hit is not None:
            return hit

    for base in (tok, squeezed):
        for clitic in _CLITICS:
            if base.endswith(clitic) and len(base) - len(clitic) >= 3:
                hit = _known(base[: -len(clitic)], vocab)
                if hit is not None:
                    return hit
    return tok


def canonical_tokens(raw: str, vocab: Collection[str]) -> list[str]:
    """`split_informal` + `canonical` per token + penggabungan frasa.

    Tanda baca pemisah klausa diganti `CLAUSE_BOUNDARY`. URL dibuang lebih
    dulu supaya titik di dalamnya tidak dianggap batas klausa.
    """
    tokens: list[str] = []
    for clause in _CLAUSE_SPLIT_RE.split(_URL_RE.sub(" ", raw)):
        words = [canonical(t, vocab) for t in split_informal(clause)]
        if not words:
            continue
        if tokens:
            tokens.append(CLAUSE_BOUNDARY)
        tokens.extend(words)
    merged: list[str] = []
    i = 0
    while i < len(tokens):
        phrase = PHRASES.get((tokens[i], tokens[i + 1])) if i + 1 < len(tokens) else None
        if phrase is not None:
            merged.append(phrase)
            i += 2
        else:
            merged.append(tokens[i])
            i += 1
    return merged


def emoji_marks(raw: str, known: Collection[str]) -> list[str]:
    """Emoji dari `known` yang muncul di teks mentah, masing-masing SEKALI.

    Sekali per jenis, berapa pun diulang: "😡😡😡😡" adalah satu penanda yang
    ditekankan, bukan empat bukti terpisah. Menghitungnya empat kali akan
    membuat satu komentar beremoji menenggelamkan kata-katanya sendiri.
    """
    seen: list[str] = []
    for ch in unicodedata.normalize("NFKC", raw):
        if ch != _VARIATION_SELECTOR and ch in known and ch not in seen:
            seen.append(ch)
    return seen
