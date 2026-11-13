"""Kinerja Komunikasi Pemerintah: katalog indikator, skor, ringkasan unggahan.

Kerangkanya ada di `docs/kerangka-kinerja-komunikasi-pemerintah.md`. Seluruh
bobot dan ambang di modul ini adalah RANCANGAN yang belum divalidasi dan bukan
standar resmi lembaga mana pun; `DISCLAIMER` wajib ikut tampil bersama skor.

Fungsi murni, tanpa I/O. Tiga aturan yang dijaga di sini:

1. Data yang tidak tersedia tidak pernah diisi. Indikator tanpa skor tidak
   ikut rata-rata; yang dilaporkan adalah cakupannya.
2. Skor dimensi tidak terbit bila cakupan di bawah `MIN_COVERAGE`; skor total
   tidak terbit bila ada dimensi yang tidak terbit.
3. Angka antarplatform tidak dijumlah. Ringkasan unggahan selalu per akun dan
   per platform, memakai median supaya satu konten viral tidak menentukan.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Final, Literal

MODEL_VERSION: Final = "gcp-rancangan-1"

DISCLAIMER: Final = (
    "Rancangan model yang belum divalidasi. Bobot, ambang, dan sebutan skor "
    "adalah usulan penyusun, bukan standar resmi pemerintah."
)

Dimension = Literal["INPUT", "PROCESS", "OUTPUT", "OUTCOME"]
Availability = Literal["PUBLIC", "ACCOUNT", "INTERNAL", "SURVEY"]
Platform = Literal["instagram", "tiktok", "x"]

DIMENSIONS: Final[tuple[Dimension, ...]] = ("INPUT", "PROCESS", "OUTPUT", "OUTCOME")
PLATFORMS: Final[tuple[Platform, ...]] = ("instagram", "tiktok", "x")

#: Bobot usulan (persen). Uji kepekaan dengan bobot rata selalu ikut dihitung.
DEFAULT_WEIGHTS: Final[dict[Dimension, float]] = {
    "INPUT": 15.0,
    "PROCESS": 30.0,
    "OUTPUT": 20.0,
    "OUTCOME": 35.0,
}

#: Cakupan minimal supaya skor satu dimensi terbit.
MIN_COVERAGE: Final = 0.6

#: Di bawah ini median per akun tidak ditampilkan ("data tidak cukup").
MIN_POSTS_FOR_MEDIAN: Final = 5

SCORE_MIN: Final = 1
SCORE_MAX: Final = 5


@dataclass(frozen=True)
class Indicator:
    code: str
    dimension: Dimension
    name: str
    #: Dari mana datanya bisa diperoleh; menentukan siapa yang bisa mengisi.
    availability: Availability
    definition: str
    #: Kriteria skor 1-5 (ringkas). Rubrik lengkap ada di dokumen kerangka.
    rubric: str


def _i(
    code: str,
    dimension: Dimension,
    name: str,
    availability: Availability,
    definition: str,
    rubric: str,
) -> Indicator:
    return Indicator(code, dimension, name, availability, definition, rubric)


INDICATORS: Final[tuple[Indicator, ...]] = (
    _i("I1", "INPUT", "Ketersediaan SDM komunikasi", "INTERNAL",
       "Jumlah orang yang tugas utamanya mengelola komunikasi publik dan media sosial.",
       "1 tidak ada petugas tetap; 3 ada tim tetapi merangkap; 5 tim khusus dengan peran tertulis"),
    _i("I2", "INPUT", "Kompetensi pengelola media sosial", "INTERNAL",
       "Pelatihan, sertifikasi, dan pengalaman yang relevan.",
       "1 tidak ada pelatihan; 3 sebagian terlatih; 5 semua peran inti terlatih"),
    _i("I3", "INPUT", "Anggaran komunikasi", "INTERNAL",
       "Kecukupan anggaran komunikasi digital terhadap rencana kerja sendiri.",
       "1 kegiatan inti tidak terbiayai; 5 seluruh rencana terbiayai"),
    _i("I4", "INPUT", "Infrastruktur digital", "INTERNAL",
       "Alat penjadwalan, pemantauan, arsip, dan analitik yang dipakai.",
       "1 hanya aplikasi bawaan; 3 ada alat tetapi tidak rutin; 5 dipakai rutin dan diarsipkan"),
    _i("I5", "INPUT", "SOP pengelolaan informasi", "INTERNAL",
       "Prosedur tertulis untuk pengumpulan, verifikasi, persetujuan, publikasi, komentar.",
       "1 tidak ada; 3 sebagian atau usang; 5 lengkap, mutakhir, diketahui pelaksana"),
    _i("I6", "INPUT", "Sistem koordinasi lintas kementerian", "INTERNAL",
       "Forum, kanal, dan narahubung tetap antarhumas.",
       "1 hubungan perorangan; 3 kanal tidak terjadwal; 5 forum terjadwal dengan notulen"),
    _i("P1", "PROCESS", "Mekanisme pengumpulan informasi", "INTERNAL",
       "Cara dan waktu memperoleh bahan dari kementerian teknis.",
       "1 tanpa jalur tetap; 3 jalur ada, waktu tidak tercatat; 5 jalur tetap dan terpantau"),
    _i("P2", "PROCESS", "Proses verifikasi informasi", "INTERNAL",
       "Langkah pengecekan fakta sebelum terbit dan siapa yang berwenang.",
       "1 tanpa verifikasi tertulis; 3 tidak terdokumentasi per konten; 5 tercatat per konten"),
    _i("P3", "PROCESS", "Koordinasi antarunit dan antarkementerian", "INTERNAL",
       "Apakah pesan dibicarakan dengan kementerian terkait sebelum terbit.",
       "1 tidak ada; 3 hanya pada isu besar; 5 rutin dan tercatat"),
    _i("P4", "PROCESS", "Proses editorial dan persetujuan konten", "INTERNAL",
       "Kejelasan jalur persetujuan dan waktu dari draf sampai disetujui.",
       "1 tidak jelas siapa menyetujui; 5 jalur jelas dan ada jalur cepat"),
    _i("P5", "PROCESS", "Strategi distribusi informasi", "INTERNAL",
       "Rencana konten per platform dan penyesuaian format.",
       "1 tanpa rencana; 3 format sama di semua platform; 5 rencana dan format per platform"),
    _i("P6", "PROCESS", "Monitoring dan respons isu", "INTERNAL",
       "Pemantauan percakapan publik dan pemicu tertulis untuk menanggapi.",
       "1 tidak dipantau; 3 dipantau tanpa ambang; 5 ada ambang dan penanggung jawab"),
    _i("P7", "PROCESS", "Pengelolaan umpan balik masyarakat", "INTERNAL",
       "Pertanyaan dan keluhan dicatat, digolongkan, dan diteruskan.",
       "1 tidak dicatat; 3 dicatat, tidak diteruskan; 5 diteruskan dan dilacak"),
    _i("O1", "OUTPUT", "Jumlah publikasi", "PUBLIC",
       "Keteraturan unggahan per platform terhadap rencana sendiri.",
       "1 jauh dari rencana; 5 sesuai rencana. Tanpa rencana: tidak tersedia"),
    _i("O2", "OUTPUT", "Reach", "ACCOUNT",
       "Akun unik yang melihat konten (insight pemilik akun).",
       "Kuintil terhadap kelompok pembanding"),
    _i("O3", "OUTPUT", "Impressions", "ACCOUNT",
       "Jumlah tayangan konten (insight pemilik akun).",
       "Kuintil terhadap kelompok pembanding"),
    _i("O4", "OUTPUT", "Views", "PUBLIC",
       "Median putar video per unggahan.",
       "Kuintil terhadap kelompok pembanding"),
    _i("O5", "OUTPUT", "Engagement rate", "PUBLIC",
       "Median (like + komentar + share) dibagi pengikut, per unggahan.",
       "Kuintil; selalu dibaca bersama pemahaman dan sentimen komentar"),
    _i("O6", "OUTPUT", "Shares", "PUBLIC",
       "Median bagikan atau repost per unggahan.",
       "Kuintil terhadap kelompok pembanding"),
    _i("O7", "OUTPUT", "Saves", "ACCOUNT",
       "Median simpan per unggahan (insight pemilik akun).",
       "Kuintil terhadap kelompok pembanding"),
    _i("O8", "OUTPUT", "Response rate", "PUBLIC",
       "Porsi komentar berisi pertanyaan yang dibalas akun resmi.",
       "1 di bawah 5%; 2 5-19%; 3 20-39%; 4 40-59%; 5 60% ke atas"),
    _i("O9", "OUTPUT", "Konsistensi pesan lintas platform", "PUBLIC",
       "Fakta kunci satu pengumuman sama di semua platform akun itu.",
       "1 sering berbeda; 3 sama tetapi tidak lengkap; 5 sama dan lengkap"),
    _i("C1", "OUTCOME", "Pemahaman masyarakat", "SURVEY",
       "Porsi responden yang menjawab benar soal fakta kebijakan.",
       "1 di bawah 20%; 2 20-39%; 3 40-59%; 4 60-79%; 5 80% ke atas"),
    _i("C2", "OUTCOME", "Kejelasan informasi kebijakan", "SURVEY",
       "Penilaian warga tentang jelas tidaknya isi (skala 1-5).",
       "Rata-rata skala kuesioner, dibulatkan"),
    _i("C3", "OUTCOME", "Keselarasan pesan antarkementerian", "PUBLIC",
       "Pernyataan Kemenko dan kementerian teknis memuat fakta dan sikap yang sama.",
       "1 bertentangan dan tidak diralat; 3 berbeda penekanan; 5 selaras"),
    _i("C4", "OUTCOME", "Kecepatan respons pemerintah", "PUBLIC",
       "Jam dari lonjakan percakapan sampai pernyataan resmi pertama.",
       "1 di atas 72 jam atau tidak ada; 2 48-72; 3 24-48; 4 6-24; 5 di bawah 6 jam"),
    _i("C5", "OUTCOME", "Kepercayaan terhadap informasi resmi", "SURVEY",
       "Tingkat percaya warga pada informasi akun resmi (skala 1-5).",
       "Rata-rata skala kuesioner. Sentimen komentar bukan ukuran kepercayaan"),
    _i("C6", "OUTCOME", "Tindak lanjut atas masukan masyarakat", "INTERNAL",
       "Porsi masukan yang diteruskan dan mendapat jawaban substantif.",
       "1 tidak ada bukti; 3 diteruskan tanpa kabar balik; 5 dijawab dan dikabarkan"),
)

INDICATOR_BY_CODE: Final[dict[str, Indicator]] = {i.code: i for i in INDICATORS}


# ------------------------------------------------------------------ skor ----


@dataclass(frozen=True)
class DimensionScore:
    dimension: Dimension
    #: None bila cakupan di bawah ambang.
    score: float | None
    coverage: float
    n_available: int
    n_total: int
    published: bool


@dataclass(frozen=True)
class Scorecard:
    dimensions: tuple[DimensionScore, ...]
    #: None bila ada dimensi yang tidak terbit.
    total: float | None
    #: Skor total dengan bobot rata; pembanding untuk uji kepekaan.
    total_equal_weights: float | None
    label: str | None
    weights: dict[Dimension, float]


def _validate_scores(scores: Mapping[str, int | None]) -> None:
    for code, value in scores.items():
        if code not in INDICATOR_BY_CODE:
            raise ValueError(f"Indikator tidak dikenal: {code}.")
        if value is not None and not SCORE_MIN <= value <= SCORE_MAX:
            raise ValueError(f"Skor {code} harus {SCORE_MIN} sampai {SCORE_MAX}.")


def score_dimension(dimension: Dimension, scores: Mapping[str, int | None]) -> DimensionScore:
    """Rata-rata indikator yang tersedia; tidak terbit bila cakupan kurang."""
    codes = [i.code for i in INDICATORS if i.dimension == dimension]
    available = [v for c in codes if (v := scores.get(c)) is not None]
    coverage = len(available) / len(codes)
    published = coverage >= MIN_COVERAGE
    return DimensionScore(
        dimension=dimension,
        score=round(sum(available) / len(available), 2) if published else None,
        coverage=round(coverage, 3),
        n_available=len(available),
        n_total=len(codes),
        published=published,
    )


def label_for(total: float) -> str:
    """Sebutan usulan; rentang dibagi sama lebar, tanpa dasar empiris."""
    if total < 1.85:
        return "Belum tertata"
    if total < 2.65:
        return "Dasar"
    if total < 3.45:
        return "Berkembang"
    if total < 4.25:
        return "Tertata"
    return "Terpadu"


def _weighted_total(
    dims: Iterable[DimensionScore], weights: Mapping[Dimension, float]
) -> float | None:
    acc = 0.0
    for d in dims:
        if d.score is None:
            return None
        acc += weights[d.dimension] * d.score
    return round(acc / sum(weights.values()), 2)


def build_scorecard(
    scores: Mapping[str, int | None],
    weights: Mapping[Dimension, float] | None = None,
) -> Scorecard:
    """Skor per dimensi, total (bila keempatnya terbit), dan pembanding bobot rata."""
    _validate_scores(scores)
    w = dict(weights) if weights is not None else dict(DEFAULT_WEIGHTS)
    if set(w) != set(DIMENSIONS) or any(v < 0 for v in w.values()) or sum(w.values()) <= 0:
        raise ValueError(
            "Bobot harus memuat keempat dimensi, tidak negatif, dan berjumlah positif."
        )
    dims = tuple(score_dimension(d, scores) for d in DIMENSIONS)
    total = _weighted_total(dims, w)
    equal = _weighted_total(dims, dict.fromkeys(DIMENSIONS, 1.0))
    return Scorecard(
        dimensions=dims,
        total=total,
        total_equal_weights=equal,
        label=label_for(total) if total is not None else None,
        weights=w,
    )


def score_response_rate(answered: int, questions: int) -> int | None:
    """O8. None bila tidak ada komentar berisi pertanyaan (tidak bisa dinilai)."""
    if questions <= 0:
        return None
    if answered < 0 or answered > questions:
        raise ValueError("Jumlah yang dibalas harus antara 0 dan jumlah pertanyaan.")
    pct = 100 * answered / questions
    for threshold, score in ((60, 5), (40, 4), (20, 3), (5, 2)):
        if pct >= threshold:
            return score
    return 1


def score_response_hours(hours: float | None) -> int:
    """C4. `None` berarti tidak ada pernyataan resmi sesudah lonjakan."""
    if hours is None:
        return 1
    if hours < 0:
        raise ValueError("Selang waktu tidak boleh negatif.")
    for limit, score in ((6, 5), (24, 4), (48, 3), (72, 2)):
        if hours < limit:
            return score
    return 1


# ------------------------------------------------------ ringkasan unggahan ----


@dataclass(frozen=True)
class PostRow:
    account: str
    platform: Platform
    posted_at: datetime
    kind: str | None
    likes: int | None
    comments: int | None
    shares: int | None
    views: int | None
    followers: int | None


@dataclass(frozen=True)
class AccountSummary:
    account: str
    platform: Platform
    n_posts: int
    first_post: datetime
    last_post: datetime
    by_kind: dict[str, int]
    posts_by_month: dict[str, int]
    median_likes: float | None
    median_comments: float | None
    median_shares: float | None
    median_views: float | None
    #: Persen; (like + komentar + share) / pengikut, median per unggahan.
    median_engagement_rate: float | None
    n_engagement_rate: int
    insufficient_data: bool


def _median_of(values: list[int]) -> float | None:
    """Median hanya bila cukup unggahan yang MEMUAT angka itu."""
    return float(median(values)) if len(values) >= MIN_POSTS_FOR_MEDIAN else None


def engagement_rate(row: PostRow) -> float | None:
    """Persen terhadap pengikut. None bila pengikut atau semua interaksi kosong.

    Share yang tidak tampil publik (Instagram) dihitung nol; itu sebabnya
    angka ini tidak boleh dibandingkan lintas platform.
    """
    if not row.followers or row.followers <= 0:
        return None
    if row.likes is None and row.comments is None and row.shares is None:
        return None
    total = (row.likes or 0) + (row.comments or 0) + (row.shares or 0)
    return 100 * total / row.followers


def summarize_posts(rows: Iterable[PostRow]) -> list[AccountSummary]:
    """Ringkasan per (akun, platform). Tidak ada penjumlahan lintas platform."""
    groups: dict[tuple[str, Platform], list[PostRow]] = {}
    for r in rows:
        groups.setdefault((r.account, r.platform), []).append(r)

    out: list[AccountSummary] = []
    for (account, platform), items in sorted(groups.items()):
        rates = [e for r in items if (e := engagement_rate(r)) is not None]
        out.append(
            AccountSummary(
                account=account,
                platform=platform,
                n_posts=len(items),
                first_post=min(r.posted_at for r in items),
                last_post=max(r.posted_at for r in items),
                by_kind=dict(Counter(r.kind or "tidak diketahui" for r in items)),
                posts_by_month=dict(
                    sorted(Counter(r.posted_at.strftime("%Y-%m") for r in items).items())
                ),
                median_likes=_median_of([r.likes for r in items if r.likes is not None]),
                median_comments=_median_of([r.comments for r in items if r.comments is not None]),
                median_shares=_median_of([r.shares for r in items if r.shares is not None]),
                median_views=_median_of([r.views for r in items if r.views is not None]),
                median_engagement_rate=(
                    round(float(median(rates)), 3)
                    if len(rates) >= MIN_POSTS_FOR_MEDIAN
                    else None
                ),
                n_engagement_rate=len(rates),
                insufficient_data=len(items) < MIN_POSTS_FOR_MEDIAN,
            )
        )
    return out
