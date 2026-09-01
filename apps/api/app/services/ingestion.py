"""Pipeline ingestion sinyal: normalisasi, deduplikasi, deteksi bahasa.

Fungsi murni tanpa I/O (CLAUDE.md §4) supaya bisa dites tanpa database dan
tanpa memanggil jaringan.

Tiga keputusan yang perlu dijelaskan karena mudah salah dipahami:

**Deduplikasi bukan deteksi kecurangan.** Konten yang sama persis muncul
berkali-kali di media sosial karena orang me-retweet, mengutip, dan menyalin —
itu perilaku normal. Modul ini membuang duplikat dari *hitungan volume* supaya
satu pesan yang disalin seribu kali tidak terbaca sebagai seribu orang. Ia
TIDAK menyimpulkan bahwa penyalinnya terkoordinasi (CLAUDE.md §3: sistem tidak
menandai fraud).

**Deteksi bahasa di sini adalah heuristik, bukan model.** Rasio stopword tidak
bisa membedakan bahasa Indonesia dari bahasa Melayu, dan menyerah pada teks
pendek. Karena itu ia mengembalikan `confidence` dan boleh mengembalikan
`None`, bukan menebak. Konsumennya wajib menampilkan itu apa adanya.

**Tidak ada inferensi provinsi dari teks.** Tergoda menebak asal penutur dari
kata daerah atau nama kota di dalam kalimat — itu dilarang: hasilnya akan
dipakai sebagai georeferensi padahal bukan. `province_code` hanya diisi kalau
konektornya memang menyediakan geotag resmi (CLAUDE.md §6 soal peta).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

#: Ukuran shingle (n-gram kata) untuk perbandingan kemiripan.
SHINGLE_K = 5

#: Ambang Jaccard di atasnya dua teks dianggap salinan satu sama lain.
#: 0.82 dipilih supaya kutipan dengan tambahan komentar pendek tetap terhitung
#: sebagai duplikat, tapi dua kalimat berbeda tentang topik sama tidak.
NEAR_DUPLICATE_THRESHOLD = 0.82

_NUM_PERM = 64
_BANDS = 16
_ROWS = _NUM_PERM // _BANDS

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_HANDLE_RE = re.compile(r"[@][A-Za-z0-9_.]{2,}")
_HASHTAG_RE = re.compile(r"#(\w+)")
_NONWORD_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_WS_RE = re.compile(r"\s+")

def wordset(prose: str) -> frozenset[str]:
    """Daftar kata dari teks berspasi.

    Ada supaya daftar kata (stopword, negator, penanda emosi) bisa ditulis
    sebagai prosa yang enak dibaca dan disunting, bukan sebagai puluhan string
    berkutip. Dipakai juga oleh services/sentiment.py.
    """
    return frozenset(prose.split())


#: Stopword frekuensi tinggi. Daftar sengaja pendek dan umum: yang dibutuhkan
#: cuma sinyal pembeda antar bahasa, bukan analisis linguistik.
_ID_STOPWORDS = wordset("""
    yang dan di ke dari untuk dengan pada ini itu tidak akan sudah bisa ada
    saya kami kita mereka dia adalah karena kalau juga saja lebih banyak
    orang tahun bagi oleh dalam atau agar sangat masih belum bukan para
""")
_EN_STOPWORDS = wordset("""
    the and of to in for with on this that is are was were be been will
    would can could not have has had they we you it as at by from but or
""")


@dataclass(frozen=True, slots=True)
class LanguageGuess:
    """Tebakan bahasa beserta kejujuran soal seberapa tipis dasarnya."""

    #: None kalau bukti tidak cukup — bukan ditebak ke 'id' sebagai default.
    lang: str | None
    confidence: float
    method: str = "rasio stopword (heuristik, bukan model bahasa)"


@dataclass(frozen=True, slots=True)
class DedupeResult:
    """Hasil deduplikasi satu batch.

    `kept_indexes` menunjuk ke posisi di input, bukan ke objek baru, supaya
    pemanggil bisa memutuskan sendiri apa yang dilakukan pada yang dibuang
    (dibuang total, atau disimpan dengan penanda).
    """

    kept_indexes: list[int]
    #: index duplikat -> index wakil yang dipertahankan
    duplicate_of: dict[int, int]
    exact_duplicates: int
    near_duplicates: int

    @property
    def duplicate_rate(self) -> float:
        total = len(self.kept_indexes) + len(self.duplicate_of)
        return round(len(self.duplicate_of) / total, 4) if total else 0.0


def normalize_text(raw: str) -> str:
    """Bentuk kanonik untuk perbandingan — bukan untuk ditampilkan.

    URL dan handle dibuang sebelum perbandingan: dua salinan pesan yang sama
    sering hanya berbeda pada tautan pelacak di ekornya.
    """
    text = unicodedata.normalize("NFKC", raw).casefold()
    text = _URL_RE.sub(" ", text)
    text = _HANDLE_RE.sub(" ", text)
    text = _HASHTAG_RE.sub(r"\1", text)
    text = _NONWORD_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def content_fingerprint(raw: str) -> str:
    """Sidik jari teks ternormalisasi — dipakai untuk duplikat persis."""
    return hashlib.sha256(normalize_text(raw).encode()).hexdigest()


def hash_author(handle: str, *, salt: str) -> str:
    """Hash akun berkunci.

    HMAC, bukan sha256 polos: tanpa kunci, hash dari daftar handle yang bisa
    ditebak (akun publik jumlahnya terbatas) bisa dibalik lewat pencocokan
    kamus. `salt` harus per-deployment dan tidak ikut di-commit.

    Konsekuensi yang disengaja: mengganti salt memutus kesinambungan
    author_hash lama. Itu memang harganya — hash yang stabil selamanya adalah
    identitas permanen dengan nama lain.
    """
    if not handle.strip():
        raise ValueError("handle kosong tidak bisa di-hash")
    normalized = handle.strip().casefold().lstrip("@")
    return hmac.new(salt.encode(), normalized.encode(), hashlib.sha256).hexdigest()[:32]


def shingles(text: str, k: int = SHINGLE_K) -> frozenset[str]:
    """Himpunan n-gram kata dari teks ternormalisasi.

    Teks yang lebih pendek dari k kata memakai seluruh teks sebagai satu
    shingle — kalimat pendek tidak punya cukup struktur untuk dibandingkan
    per-potongan, dan memaksakannya menghasilkan kemiripan palsu yang tinggi.
    """
    words = normalize_text(text).split()
    if not words:
        return frozenset()
    if len(words) < k:
        return frozenset([" ".join(words)])
    return frozenset(" ".join(words[i : i + k]) for i in range(len(words) - k + 1))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def _minhash(shingle_set: frozenset[str]) -> tuple[int, ...]:
    """Signature MinHash deterministik lintas proses.

    blake2b dengan salt per-permutasi, bukan `hash()` bawaan Python: `hash()`
    di-randomisasi per proses (PYTHONHASHSEED), jadi dua worker akan
    menghasilkan signature berbeda untuk teks yang sama.
    """
    encoded = [s.encode() for s in shingle_set]
    signature: list[int] = []
    for i in range(_NUM_PERM):
        salt = i.to_bytes(2, "big")
        signature.append(
            min(
                int.from_bytes(hashlib.blake2b(e, digest_size=8, salt=salt).digest(), "big")
                for e in encoded
            )
        )
    return tuple(signature)


def _candidate_pairs(signatures: Sequence[tuple[int, ...]]) -> set[tuple[int, int]]:
    """LSH banding — hindari perbandingan O(n²) pada batch besar."""
    pairs: set[tuple[int, int]] = set()
    for band in range(_BANDS):
        buckets: dict[tuple[int, ...], list[int]] = {}
        lo, hi = band * _ROWS, (band + 1) * _ROWS
        for idx, sig in enumerate(signatures):
            buckets.setdefault(sig[lo:hi], []).append(idx)
        for members in buckets.values():
            if len(members) < 2:
                continue
            for i, a in enumerate(members):
                for b in members[i + 1 :]:
                    pairs.add((a, b))
    return pairs


def dedupe(
    texts: Sequence[str], *, threshold: float = NEAR_DUPLICATE_THRESHOLD
) -> DedupeResult:
    """Buang salinan persis dan salinan nyaris-persis dari satu batch.

    Yang dipertahankan adalah kemunculan PERTAMA. Untuk feed yang terurut dari
    terbaru ke terlama itu berarti yang tersimpan adalah salinan termuda —
    pemanggil yang peduli pada yang asli harus mengurutkan naik dulu.
    """
    if not 0.0 < threshold <= 1.0:
        raise ValueError("threshold harus di antara 0 dan 1")

    kept: list[int] = []
    duplicate_of: dict[int, int] = {}
    exact = 0

    seen_fingerprint: dict[str, int] = {}
    survivor_shingles: list[frozenset[str]] = []
    survivor_index: list[int] = []

    for idx, raw in enumerate(texts):
        fp = content_fingerprint(raw)
        first = seen_fingerprint.get(fp)
        if first is not None:
            duplicate_of[idx] = first
            exact += 1
            continue
        seen_fingerprint[fp] = idx
        kept.append(idx)
        survivor_shingles.append(shingles(raw))
        survivor_index.append(idx)

    # Tahap dua: yang lolos duplikat-persis dibandingkan secara nyaris-sama.
    signatures = [_minhash(s) if s else tuple([0] * _NUM_PERM) for s in survivor_shingles]
    near = 0
    absorbed: set[int] = set()
    for a, b in sorted(_candidate_pairs(signatures)):
        if a in absorbed or b in absorbed:
            continue
        if jaccard(survivor_shingles[a], survivor_shingles[b]) >= threshold:
            duplicate_of[survivor_index[b]] = survivor_index[a]
            absorbed.add(b)
            near += 1

    kept = [i for i in kept if i not in {survivor_index[p] for p in absorbed}]
    return DedupeResult(
        kept_indexes=kept,
        duplicate_of=duplicate_of,
        exact_duplicates=exact,
        near_duplicates=near,
    )


def detect_language(raw: str, *, min_words: int = 6) -> LanguageGuess:
    """Tebak bahasa dari rasio stopword.

    Menyerah (`lang=None`) pada teks pendek dan pada teks tanpa satu pun
    stopword yang dikenal. Itu jawaban yang benar untuk metode ini — memaksa
    keluaran 'id' pada teks tiga kata akan membuat filter bahasa di hilir
    terlihat bekerja padahal tidak.

    Bahasa Melayu akan terbaca sebagai 'id'. Batasan itu nyata dan wajib
    disebut di UI, bukan diperbaiki dengan menambah kata ke daftar.
    """
    words = normalize_text(raw).split()
    if len(words) < min_words:
        return LanguageGuess(lang=None, confidence=0.0)

    unique = set(words)
    id_hits = len(unique & _ID_STOPWORDS)
    en_hits = len(unique & _EN_STOPWORDS)
    total_hits = id_hits + en_hits
    if total_hits == 0:
        return LanguageGuess(lang=None, confidence=0.0)

    if id_hits == en_hits:
        return LanguageGuess(lang=None, confidence=0.0)

    lang = "id" if id_hits > en_hits else "en"
    dominant = max(id_hits, en_hits)
    # Keyakinan naik bersama selisih DAN bersama banyaknya bukti: 3 banding 0
    # lebih meyakinkan daripada 1 banding 0.
    margin = (dominant - min(id_hits, en_hits)) / total_hits
    evidence = min(1.0, dominant / 4)
    return LanguageGuess(lang=lang, confidence=round(margin * evidence, 3))


def concentration_ratio(author_hashes: Iterable[str | None], *, top: int = 10) -> float:
    """Berapa bagian percakapan yang datang dari `top` akun paling aktif.

    Angka deskriptif, bukan tuduhan. Percakapan yang terpusat bisa berarti
    beberapa akun besar ikut membicarakan, bukan bahwa mereka mengoordinasikan
    apa pun — dan modul ini tidak pernah menyimpulkan yang kedua.
    """
    counts: dict[str, int] = {}
    total = 0
    for h in author_hashes:
        if h is None:
            continue
        counts[h] = counts.get(h, 0) + 1
        total += 1
    if total == 0:
        return 0.0
    top_n = sorted(counts.values(), reverse=True)[:top]
    return round(sum(top_n) / total, 4)
