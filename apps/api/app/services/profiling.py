"""Estimasi gender, kelompok umur, dan minat akun dari komentarnya sendiri (P11).

Fungsi murni. Dipakai `routers/audience.py` saat dibaca; TIDAK ada profil per
akun yang disimpan di database. Itu keputusan desain tahap pertama:

- tanpa tabel baru berarti tanpa migrasi Supabase dan tanpa data pribadi
  turunan yang harus diberi retensi dan jalur koreksi/hapus (CLAUDE.md §3,
  pengecualian 2026-11-08). Menghapus komentar sumbernya otomatis menghapus
  estimasinya;
- yang keluar dari modul ini ke endpoint hanya AGREGAT. Daftar akun per
  segmen (untuk peran berizin, dengan audit log) belum dibangun.

## Sinyal yang dipakai

Platform tidak menyimpan nama tampilan (akun disimpan sebagai hash berkunci),
jadi kamus nama -> gender TIDAK mungkin dan tidak dipakai. Yang tersisa:

1. **Pernyataan diri sendiri** dalam komentar: kata ganti orang pertama diikuti
   peran ("saya ibu dua anak", "gue anak SMA", "aku mahasiswi", "umur saya 52
   tahun", "saya sudah pensiun"). Sapaan kepada orang lain ("bu", "mas",
   "bro") sengaja TIDAK dipakai: itu menyebut lawan bicara, bukan penulis.
   Pernyataan yang diawali negasi ("saya bukan ibu-ibu") dilewati.
2. **Kosakata komentar akun itu** untuk minat: kategori tetap (lihat
   `INTERESTS`), dihitung per komentar, butuh minimal dua komentar berbeda.

Kategori yang dilarang CLAUDE.md §3 (agama, etnis, orientasi seksual,
kesehatan, afiliasi politik) tidak ada di sini dan tidak boleh ditambahkan.

## Keyakinan

`confidence` adalah skor aturan, BUKAN probabilitas terkalibrasi: belum ada
set uji berlabel manual. Di bawah `MIN_CONFIDENCE` nilainya `None` ("tidak
diketahui"), bukan tebakan paksa. Pernyataan yang bertentangan (mis. "saya
ibu" dan "saya bapak" dari akun yang sama) juga menghasilkan `None`.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass

MODEL_VERSION = "profil-id-1"

METHOD = (
    "profil-id-1: pernyataan diri orang pertama dalam komentar akun itu sendiri "
    "(gender, kelompok umur) dan kosakata minimal dua komentarnya (minat); "
    "skor keyakinan berbasis aturan, belum dievaluasi terhadap label manusia"
)

MIN_CONFIDENCE = 0.6

GENDERS: tuple[str, ...] = ("L", "P")
AGE_BANDS: tuple[str, ...] = ("<=17", "18-24", "25-34", "35-44", "45+")

# --------------------------------------------------------------- normalisasi

_REPEAT_RE = re.compile(r"([a-z])\1{2,}")
_REDUP_RE = re.compile(r"\b([a-z]{2,})(?:2|-\1)\b")
_NONWORD_RE = re.compile(r"[^a-z0-9\s]+")
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Huruf kecil; huruf berulang 3+ jadi satu ("cowooook" -> "cowok");
    "ibu2"/"ibu-ibu" -> "ibu ibu"; tanda baca -> spasi."""
    t = text.lower()
    if "2" in t or "-" in t:
        t = _REDUP_RE.sub(r"\1 \1", t)
    t = _REPEAT_RE.sub(r"\1", t)
    t = _NONWORD_RE.sub(" ", t)
    return _WS_RE.sub(" ", t).strip()


# --------------------------------------------------------- pernyataan diri

#: "kita" sengaja tidak dipakai: di komentar publik ia hampir selalu berarti
#: "kita semua" ("kita bapak-bapak", "kita pensiun nanti"), bukan penulisnya.
_SINGULAR = r"(?:saya|sy|sya|aku|aq|ak|gue|gua|gw|gwe|ane)"
_PRONOUNS = r"(?:saya|sy|sya|aku|aq|ak|gue|gua|gw|gwe|ane|kami)"
#: Kata yang boleh berada di antara kata ganti dan peran. Sengaja pendek:
#: semakin panjang jaraknya, semakin besar kemungkinan peran itu milik orang lain.
_FILLERS = (
    r"(?:ini|juga|jg|sendiri|cuma|cm|cuman|hanya|sbg|sebagai|seorang|sorang|adalah|"
    r"masih|msh|yg|yang|sudah|udah|udh|dah|sdh|para|termasuk|salah satu|"
    r"bukan|bkn|tidak|gak|nggak|ngga|ga|tdk)"
)
_NEGATORS = frozenset({"bukan", "bkn", "tidak", "gak", "nggak", "ngga", "ga", "tdk"})

#: peran -> (gender, kelompok umur, keyakinan umur). `None` = tidak menyatakan.
_ROLES: dict[str, tuple[str | None, str | None, float]] = {
    # perempuan
    "ibu": ("P", None, 0.0),
    "ibu rumah tangga": ("P", None, 0.0),
    "irt": ("P", None, 0.0),
    "emak": ("P", None, 0.0),
    "mamah": ("P", None, 0.0),
    "mama": ("P", None, 0.0),
    "bunda": ("P", None, 0.0),
    "istri": ("P", None, 0.0),
    "isteri": ("P", None, 0.0),
    "perempuan": ("P", None, 0.0),
    "wanita": ("P", None, 0.0),
    "cewek": ("P", None, 0.0),
    "cewe": ("P", None, 0.0),
    "janda": ("P", None, 0.0),
    "nenek": ("P", "45+", 0.75),
    "mahasiswi": ("P", "18-24", 0.65),
    "siswi": ("P", "<=17", 0.7),
    # laki-laki
    "bapak": ("L", None, 0.0),
    "bpk": ("L", None, 0.0),
    "ayah": ("L", None, 0.0),
    "suami": ("L", None, 0.0),
    "pria": ("L", None, 0.0),
    "laki laki": ("L", None, 0.0),
    "laki": ("L", None, 0.0),
    "lelaki": ("L", None, 0.0),
    "cowok": ("L", None, 0.0),
    "cowo": ("L", None, 0.0),
    "duda": ("L", None, 0.0),
    "kakek": ("L", "45+", 0.75),
    # umur saja
    "mahasiswa": (None, "18-24", 0.65),
    "maba": (None, "18-24", 0.75),
    "anak kuliahan": (None, "18-24", 0.7),
    "anak kuliah": (None, "18-24", 0.7),
    "anak sma": (None, "<=17", 0.8),
    "anak smk": (None, "<=17", 0.8),
    "anak smp": (None, "<=17", 0.85),
    "anak sd": (None, "<=17", 0.85),
    "siswa sma": (None, "<=17", 0.8),
    "siswa smk": (None, "<=17", 0.8),
    "siswa smp": (None, "<=17", 0.85),
    "sma": (None, "<=17", 0.7),
    "smk": (None, "<=17", 0.7),
    "smp": (None, "<=17", 0.8),
    "pensiunan": (None, "45+", 0.8),
    "pensiun": (None, "45+", 0.75),
    "lansia": (None, "45+", 0.8),
}

#: Peran disusun dari yang terpanjang supaya "ibu rumah tangga" menang atas "ibu".
_ROLE_ALT = "|".join(sorted((re.escape(r) for r in _ROLES), key=len, reverse=True))
_SELF_RE = re.compile(
    rf"\b(?P<pron>{_PRONOUNS})(?P<fill>(?:\s+{_FILLERS})*)\s+(?P<role>{_ROLE_ALT})\b"
)
#: "umur saya 52", "usia sy 30 thn", "umurku 19", "saya 23 tahun".
#: Kata ganti WAJIB: "umur 39" tanpa kata ganti hampir selalu umur orang yang
#: dibicarakan (proyek Gibran: 48 akun "35-44" dari umur Gibran sendiri).
#: "saya 20 tahun kerja di sini" adalah lama waktu, bukan umur: angka yang
#: diikuti kata kerja/keterangan di `_DURATION_NEXT` dilewati.
_DURATION_NEXT = (
    r"lagi|kerja|bekerja|jadi|menjadi|di|tinggal|hidup|mengabdi|ngajar|mengajar|nunggu|"
    r"menunggu|berjuang|ikut|pakai|pake|memilih|milih|dukung|mendukung|merantau|nikah|"
    r"menikah|kuliah|sekolah|usaha|dagang|jualan|bertani|lihat|melihat|ikuti|mengikuti|"
    r"nonton|menonton|belajar|yang|yg|lalu|silam|kemarin|terakhir|ke|dan|bersama|sama|"
    r"setia|jd|dlm|dalam|sebagai|sbg|berkarir|mengalami|merasakan|antri|ngantri|mengantri|"
    r"antre|mengantre"
)
_AGE_NUM_RE = re.compile(
    rf"\b(?:(?:umur|usia)(?:\s*{_SINGULAR}|ku)\s+(?P<a>\d{{2}})\b"
    rf"|{_SINGULAR}(?:\s+(?:ini|sudah|udah|udh|dah|sdh|masih|msh|baru))?\s+(?P<b>\d{{2}})"
    rf"\s+(?:tahun|thn|th|thun|taun)\b(?!\s+(?:{_DURATION_NEXT})\b))"
)

GENDER_CONFIDENCE_ONE = 0.8
GENDER_CONFIDENCE_MANY = 0.9
AGE_NUMBER_CONFIDENCE = 0.85
MIN_STATED_YEARS = 15


def age_band(years: int) -> str | None:
    if years < 10 or years > 95:
        return None
    if years <= 17:
        return "<=17"
    if years <= 24:
        return "18-24"
    if years <= 34:
        return "25-34"
    if years <= 44:
        return "35-44"
    return "45+"


@dataclass(frozen=True)
class SelfStatement:
    gender: str | None
    age: str | None
    age_confidence: float
    marker: str


#: Kata sebelum kata ganti yang membuat "saya bapak X" menjadi sapaan/opini
#: ("menurut saya bpk prabowo…", "salam hormat saya bapak gibran") atau
#: kepunyaan ("bapak gw yg pensiunan").
_REJECT_BEFORE = frozenset(
    [
        "menurut",
        "mnurut",
        "buat",
        "bagi",
        "mata",
        "harapan",
        "keluhan",
        "hormat",
        "salam",
        "idola",
        "untuk",
        "utk",
        "dgn",
        "dengan",
        "bapak",
        "bpk",
        "ibu",
        "ayah",
        "emak",
        "anak",
        "istri",
        "suami",
        "adik",
        "kakak",
        "teman",
        "tmn",
        "temen",
        "kawan",
        "om",
        "tante",
        "paman",
        "mertua",
        "ortu",
    ]
)
#: Kata sesudah peran yang menunjukkan peran itu milik orang lain ("wanita itu",
#: "ayah saya", "ayah nya").
_REJECT_AFTER = frozenset(
    [
        "itu",
        "tersebut",
        "ini",
        "nya",
        "saya",
        "sy",
        "aku",
        "gue",
        "gw",
        "mu",
        "kamu",
        "kalian",
        "anda",
    ]
)
#: Peran yang sering dipakai sebagai sapaan atau gelar di depan nama ("saya
#: bapak jokowi", "kami bapak prabowo"). Diterima hanya bila ada penegas
#: ("saya SEORANG ibu", "saya SEBAGAI bapak") atau kata sesudahnya menerangkan
#: penulis ("saya ibu rumah tangga", "saya bapak dua anak", "saya ibu tua").
_HONORIFIC = frozenset(["ibu", "bapak", "bpk", "ayah", "bunda", "mama", "mamah", "emak"])
_AFFIRM_FILLERS = frozenset(["seorang", "sorang", "sebagai", "sbg"])
_HONORIFIC_NEXT = frozenset(
    [
        "rumah",
        "yg",
        "yang",
        "dua",
        "tiga",
        "empat",
        "lima",
        "enam",
        "satu",
        "anak",
        "tua",
        "biasa",
        "tunggal",
        "muda",
        "beranak",
        "lansia",
        "pensiunan",
        "juga",
        "jg",
        "aja",
        "saja",
        "sih",
        "kok",
        "nih",
        "awam",
    ]
)
#: "sma"/"smp"/"smk" tanpa "anak"/"siswa" hanya diterima dengan "masih": tanpa
#: itu "sy sma" lebih sering berarti "sama", dan "gw smp" berarti "sampai".
_BARE_SCHOOL = frozenset({"sma", "smp", "smk"})


def _accept(t: str, start: int, end: int, role: str, fillers: set[str]) -> bool:
    before = t[:start].split()[-1:]
    after = t[end:].split()[:1]
    if before and before[0] in _REJECT_BEFORE:
        return False
    if after and after[0] in _REJECT_AFTER:
        return False
    if role in _BARE_SCHOOL:
        return bool(fillers & {"masih", "msh"})
    if role in _HONORIFIC and not fillers & _AFFIRM_FILLERS:
        # "kami ibu-ibu" (bentuk ulang = kelompok penulis) juga diterima.
        return not after or after[0] in _HONORIFIC_NEXT or after[0] == role or after[0].isdigit()
    return True


_PRONOUN_SET = frozenset(_PRONOUNS[3:-1].split("|"))


def self_statements(text: str) -> list[SelfStatement]:
    """Pernyataan diri dalam satu komentar. Negasi di antara kata ganti dan peran -> dilewati."""
    return _self_statements(normalize(text))


def _self_statements(t: str) -> list[SelfStatement]:
    """Seperti `self_statements`, untuk teks yang sudah dinormalisasi."""
    out: list[SelfStatement] = []
    has_pronoun = not _PRONOUN_SET.isdisjoint(t.split())
    if has_pronoun:
        for m in _SELF_RE.finditer(t):
            fillers = set(m.group("fill").split())
            role = m.group("role")
            if fillers & _NEGATORS or not _accept(t, m.start(), m.end(), role, fillers):
                continue
            gender, age, age_conf = _ROLES[role]
            out.append(SelfStatement(gender, age, age_conf, f"{m.group('pron')} … {role}"))
    if has_pronoun or "umur" in t or "usia" in t:
        for m in _AGE_NUM_RE.finditer(t):
            years = int(m.group("a") or m.group("b"))
            # "saya 12 tahun loyalis…", "saya sudah 11 tahun mengantri": angka kecil
            # dalam bentuk "saya N tahun" hampir selalu lama waktu, bukan umur.
            if m.group("b") and years < MIN_STATED_YEARS:
                continue
            band = age_band(years)
            if band:
                out.append(SelfStatement(None, band, AGE_NUMBER_CONFIDENCE, "umur dalam angka"))
    return out


# ------------------------------------------------------------------- minat


#: Kategori tetap. Kosakata yang menjadi inti topik pemantauan umum (harga BBM,
#: bensin, sembako, sekolah/guru untuk MBG, balita/bayi) sengaja tidak dipakai
#: sebagai penanda. Kata kendaraan ("motor", "mobil") tetap dipakai, jadi pada
#: proyek BBM minat otomotif cenderung lebih tinggi: itu disebut di batasan.
def _words(prose: str) -> frozenset[str]:
    return frozenset(prose.split())


INTERESTS: dict[str, frozenset[str]] = {
    "otomotif": _words(
        "mobil motor montor matic nmax vario beat avanza bengkel servis oli knalpot "
        "modif touring moge velg turbo"
    ),
    "kuliner": _words(
        "kuliner resep masak memasak masakan bakso mieayam ngopi kopi jajan jajanan "
        "cemilan camilan rendang sate kue seblak martabak"
    ),
    "olahraga": _words(
        "bola sepakbola timnas futsal badminton bulutangkis voli gym fitness maraton "
        "liga persib persija arema motogp gol jogging"
    ),
    "gim": _words(
        "game gim mabar gamer playstation ps5 pubg valorant genshin roblox minecraft "
        "pushrank esport esports"
    ),
    "keluarga": _words("anakku istriku suamiku cucuku keluargaku parenting mertua"),
    "keuangan": _words(
        "saham investasi reksadana kripto crypto bitcoin trading trader tabungan nabung "
        "cicilan kpr dividen deposito asuransi"
    ),
    "wisata": _words(
        "wisata liburan traveling travel pantai hotel villa backpacker turis pelesir piknik"
    ),
    "teknologi": _words(
        "android iphone laptop gadget aplikasi coding programmer software hardware "
        "smartphone chatgpt"
    ),
    "pendidikan": _words("kuliah kampus dosen beasiswa skripsi ujian ukt wisuda"),
    "hiburan": _words(
        "musik lagu konser film drakor kpop anime netflix sinetron nonton band podcast"
    ),
}
_INTEREST_OF: dict[str, str] = {w: cat for cat, words in INTERESTS.items() for w in words}
MIN_INTEREST_COMMENTS = 2


def interest_markers(text: str, exclude: Collection[str] = ()) -> dict[str, str]:
    """Kategori minat -> satu kata penanda yang ditemukan di komentar ini.

    `exclude`: kata topik proyek yang tidak boleh dihitung sebagai minat
    (mis. "martabak" pada proyek tentang Gibran, yang keluarganya berbisnis
    martabak). Dipilih analis setelah melihat kata penanda di hasil.
    """
    return _interest_markers(normalize(text), exclude)


def _interest_markers(t: str, exclude: Collection[str] = ()) -> dict[str, str]:
    found: dict[str, str] = {}
    t = t.replace("mie ayam", "mieayam").replace("push rank", "pushrank")
    for tok in t.split():
        cat = _INTEREST_OF.get(tok)
        if cat and cat not in found and tok not in exclude:
            found[cat] = tok
    return found


def interest_confidence(n_comments: int) -> float:
    """1 komentar -> 0,5 (di bawah ambang); 2 -> 0,7; naik 0,05 per komentar, maks. 0,9."""
    if n_comments <= 0:
        return 0.0
    if n_comments == 1:
        return 0.5
    return min(0.9, 0.7 + 0.05 * (n_comments - 2))


# ------------------------------------------------------------- per akun


@dataclass(frozen=True)
class Estimate:
    value: str | None
    confidence: float
    evidence: tuple[str, ...] = ()


class _Acc:
    """Penanda satu akun dalam SATU Counter (kunci bertipe) supaya ringan:
    ("g", gender), ("a", kelompok umur), ("i", minat), ("w", minat, kata),
    ("e", atribut, penanda). `age_conf` hanya dibuat bila ada penanda umur."""

    __slots__ = ("age_conf", "marks")

    def __init__(self) -> None:
        self.marks: Counter[tuple[str, ...]] = Counter()
        self.age_conf: dict[str, float] | None = None

    def of(self, kind: str) -> dict[str, int]:
        return {k[1]: n for k, n in self.marks.items() if k[0] == kind}


@dataclass(frozen=True)
class Profile:
    gender: Estimate
    age: Estimate
    interests: tuple[Estimate, ...]


def _gender(acc: _Acc) -> Estimate:
    genders = acc.of("g")
    if len(genders) != 1:  # tidak ada, atau bertentangan
        return Estimate(None, 0.0)
    ((value, n),) = genders.items()
    conf = GENDER_CONFIDENCE_MANY if n >= 2 else GENDER_CONFIDENCE_ONE
    return Estimate(value if conf >= MIN_CONFIDENCE else None, conf)


def _age(acc: _Acc) -> Estimate:
    votes = acc.of("a")
    if not votes or acc.age_conf is None:
        return Estimate(None, 0.0)
    value, n = max(votes.items(), key=lambda kv: (kv[1], kv[0]))
    if n / sum(votes.values()) < 2 / 3:  # tidak cukup sepakat
        return Estimate(None, 0.0)
    conf = acc.age_conf[value]
    return Estimate(value if conf >= MIN_CONFIDENCE else None, conf)


def _words_for(acc: _Acc, cat: str) -> tuple[str, ...]:
    words = [(k[2], n) for k, n in acc.marks.items() if k[0] == "w" and k[1] == cat]
    return tuple(w for w, _ in sorted(words, key=lambda kv: (-kv[1], kv[0]))[:3])


def _profile(acc: _Acc) -> Profile:
    interests = tuple(
        Estimate(
            cat,
            interest_confidence(n),
            _words_for(acc, cat),
        )
        for cat, n in sorted(acc.of("i").items(), key=lambda kv: (-kv[1], kv[0]))
        if interest_confidence(n) >= MIN_CONFIDENCE
    )
    return Profile(gender=_gender(acc), age=_age(acc), interests=interests)


# ------------------------------------------------------------- agregat


@dataclass(slots=True)
class _SentAcc:
    total: float = 0.0
    n: int = 0


@dataclass(frozen=True)
class SegmentSentiment:
    segment: str
    accounts: int
    scored: int
    mean: float | None


@dataclass(frozen=True)
class AudienceStats:
    n_accounts: int
    n_comments: int
    gender: dict[str, int]
    age: dict[str, int]
    #: (kelompok umur, gender) -> jumlah akun; hanya akun yang keduanya diketahui.
    pyramid: dict[tuple[str, str], int]
    interests: dict[str, int]
    interests_by_gender: dict[str, dict[str, int]]
    #: kata penanda -> jumlah akun, per atribut ("gender:P", "age:18-24", "minat:gim").
    evidence: dict[str, list[tuple[str, int]]]
    sentiment: list[SegmentSentiment]


def _evidence(evidence: dict[str, Counter[str]], acc: _Acc, attr: str) -> None:
    """Satu hitungan per akun per penanda (bukan per kemunculan)."""
    for key in acc.marks:
        if key[0] == "e" and key[1] == attr:
            evidence.setdefault(attr, Counter())[key[2]] += 1


class Profiler:
    """Dikumpulkan sepotong demi sepotong: `add` per potongan baris database.

    Memori: keadaan disimpan HANYA untuk akun yang punya penanda. Jumlah akun
    berbeda dan sentimen per akun tidak dihitung di sini: pemanggil mengambilnya
    dengan agregat SQL (`marked_authors()` memberi daftar akun yang perlu) lalu
    mengopernya ke `result`. Begitu proyek sebesar Gibran (±164 ribu akun) tidak
    perlu satu entri per akun di memori.
    """

    def __init__(self, *, exclude: Collection[str] = ()) -> None:
        self._acc: dict[str, _Acc] = {}
        self._exclude = frozenset(normalize(w) for w in exclude if w.strip())
        self.n_comments = 0

    def add(self, rows: Iterable[tuple[str | None, str]]) -> None:
        for author, text in rows:
            if not author:
                continue
            self.n_comments += 1
            norm = normalize(text)
            statements = _self_statements(norm)
            markers = _interest_markers(norm, self._exclude)
            if not statements and not markers:
                continue
            acc = self._acc.get(author)
            if acc is None:
                acc = self._acc[author] = _Acc()
            marks = acc.marks
            for st in statements:
                if st.gender:
                    marks["g", st.gender] += 1
                    marks["e", f"gender:{st.gender}", st.marker] += 1
                if st.age:
                    marks["a", st.age] += 1
                    marks["e", f"age:{st.age}", st.marker] += 1
                    conf = acc.age_conf if acc.age_conf is not None else {}
                    conf[st.age] = max(conf.get(st.age, 0.0), st.age_confidence)
                    acc.age_conf = conf
            for cat, word in markers.items():
                marks["i", cat] += 1
                marks["w", cat, word] += 1

    def marked_authors(self) -> list[str]:
        return list(self._acc)

    def profiles(self) -> dict[str, Profile]:
        return {a: _profile(acc) for a, acc in self._acc.items()}

    def result(
        self,
        *,
        n_accounts: int,
        sentiment: Mapping[str, tuple[float, int]] | None = None,
    ) -> AudienceStats:
        """`sentiment`: akun -> (jumlah skor, banyak konten bernilai), cukup untuk
        akun di `marked_authors()`. Akun yang tidak ada dianggap tanpa skor."""
        sent = sentiment or {}
        gender: Counter[str] = Counter()
        age: Counter[str] = Counter()
        pyramid: Counter[tuple[str, str]] = Counter()
        interests: Counter[str] = Counter()
        by_gender: dict[str, Counter[str]] = {g: Counter() for g in GENDERS}
        evidence: dict[str, Counter[str]] = {}
        seg_sent: dict[str, _SentAcc] = {}
        seg_accounts: Counter[str] = Counter()

        def _seg(name: str, author: str) -> None:
            seg_accounts[name] += 1
            total, n = sent.get(author, (0.0, 0))
            agg = seg_sent.setdefault(name, _SentAcc())
            agg.total += total
            agg.n += n

        for author, acc in self._acc.items():
            p = _profile(acc)
            if p.gender.value:
                gender[p.gender.value] += 1
                _seg(f"gender:{p.gender.value}", author)
                _evidence(evidence, acc, f"gender:{p.gender.value}")
            if p.age.value:
                age[p.age.value] += 1
                _seg(f"age:{p.age.value}", author)
                _evidence(evidence, acc, f"age:{p.age.value}")
            if p.gender.value and p.age.value:
                pyramid[(p.age.value, p.gender.value)] += 1
            for est in p.interests:
                assert est.value is not None
                interests[est.value] += 1
                _seg(f"minat:{est.value}", author)
                if p.gender.value:
                    by_gender[p.gender.value][est.value] += 1
                for word in est.evidence:
                    evidence.setdefault(f"minat:{est.value}", Counter())[word] += 1

        segments = [
            SegmentSentiment(
                segment=name,
                accounts=seg_accounts[name],
                scored=agg.n,
                mean=round(agg.total / agg.n, 3) if agg.n else None,
            )
            for name, agg in sorted(seg_sent.items())
        ]
        return AudienceStats(
            n_accounts=n_accounts,
            n_comments=self.n_comments,
            gender={g: gender.get(g, 0) for g in GENDERS},
            age={b: age.get(b, 0) for b in AGE_BANDS},
            pyramid=dict(pyramid),
            interests=dict(interests.most_common()),
            interests_by_gender={g: dict(c.most_common()) for g, c in by_gender.items()},
            evidence={k: c.most_common(5) for k, c in sorted(evidence.items())},
            sentiment=segments,
        )
