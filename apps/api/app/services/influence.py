"""Estimasi pengaruh akun dalam percakapan (Phase 3).

## Kata yang dipakai, dan kenapa

CLAUDE.md §3: "Jangan pernah menyatakan akun tertentu 'mengendalikan' opini.
Istilah yang dipakai: *influence estimate*, selalu dengan metodenya."

Itu bukan kehalusan bahasa. Yang bisa diukur dari data ini adalah **seberapa
besar porsi percakapan dan keterlibatan yang melekat pada sebuah akun**. Yang
TIDAK bisa diukur adalah apakah orang berubah pikiran karenanya. Sebuah akun
bisa mendominasi lini masa dan tidak mengubah satu pun sikap; sebuah akun kecil
bisa memicu perubahan besar lewat jalur yang tidak terlihat di data ini.

Karena itu modul ini mengembalikan `influence_estimate` — ukuran keterpaparan,
bukan ukuran pengaruh kausal — dan kalimat batasannya ikut di setiap hasil.

## Yang tidak dilakukan

**Tidak menyimpulkan koordinasi.** Beberapa akun yang memposting hal serupa
pada waktu berdekatan adalah pola yang sama persis untuk kampanye
terkoordinasi DAN untuk orang-orang yang membaca berita yang sama pagi itu.
Data ini tidak bisa memisahkan keduanya, jadi modul ini tidak mencoba.

**Tidak mengidentifikasi akun.** Yang masuk ke sini `author_hash`, bukan
handle. Keluarannya juga hash. Menerjemahkannya kembali ke nama akun adalah
keputusan produk yang belum diambil, dan tidak boleh diam-diam terjadi lewat
modul ini.

**Tidak memeringkat dari satu unggahan.** Satu unggahan viral bukan pengaruh,
itu satu unggahan viral. `MIN_POSTS_FOR_RANKING` menjaga itu.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from statistics import median

#: Akun dengan unggahan lebih sedikit dari ini tidak diperingkat. Ia tetap
#: ikut dalam penyebut (porsi percakapan), cuma tidak muncul sebagai "akun
#: berpengaruh" — sekali viral bukan pengaruh.
MIN_POSTS_FOR_RANKING = 3

#: Di bawah jumlah akun ini, pemeringkatan tidak diterbitkan: dari 4 akun,
#: yang teratas otomatis terlihat dominan tanpa itu berarti apa-apa.
MIN_AUTHORS = 10

METHOD = (
    "estimasi keterpaparan: porsi unggahan dan keterlibatan per akun, "
    "dinormalisasi terhadap total periode"
)

LIMITATIONS = (
    "Angka ini mengukur porsi percakapan dan keterlibatan yang melekat pada "
    "sebuah akun — keterpaparan, bukan pengaruh kausal. Ia tidak mengukur "
    "apakah ada orang yang berubah pikiran. Keterlibatan juga dimediasi "
    "algoritma platform yang tidak transparan, sehingga sebagian perbedaan "
    "antar-akun berasal dari distribusi, bukan dari isi pesannya."
)


@dataclass(frozen=True, slots=True)
class AuthorActivity:
    """Rekap satu akun pada periode yang dianalisis."""

    author_hash: str
    posts: int
    engagement: int


@dataclass(frozen=True, slots=True)
class InfluenceEstimate:
    author_hash: str
    posts: int
    engagement: int
    #: Porsi unggahan akun ini dari seluruh unggahan periode, persen.
    post_share_pct: float
    #: Porsi keterlibatan akun ini dari seluruh keterlibatan periode, persen.
    engagement_share_pct: float
    #: Keterlibatan per unggahan dibanding median akun lain. 1.0 = biasa saja.
    amplification: float
    #: Skor gabungan 0-100, hanya untuk mengurutkan — bukan satuan apa pun.
    influence_estimate: float


@dataclass(frozen=True, slots=True)
class InfluenceReport:
    top: list[InfluenceEstimate]
    total_authors: int
    ranked_authors: int
    total_posts: int
    total_engagement: int
    #: Porsi percakapan dari 10 akun teratas. Deskriptif, bukan tuduhan.
    concentration_top10_pct: float
    method: str = METHOD
    insufficient_data: bool = False
    note: str | None = None
    limitations: list[str] = field(default_factory=lambda: [LIMITATIONS])


def estimate(
    activity: Sequence[AuthorActivity], *, limit: int = 10
) -> InfluenceReport:
    """Estimasi keterpaparan per akun dari rekap aktivitas periode.

    Skor gabungan memberi bobot lebih besar pada porsi keterlibatan daripada
    porsi unggahan (0.6 : 0.4): memposting banyak tanpa ada yang menanggapi
    bukan keterpaparan, itu kebisingan. Pembobotan ini penilaian, bukan hasil
    kalibrasi — sama seperti skala di services/risk.py — dan itu sebabnya
    keduanya tetap dikembalikan terpisah supaya pembaca bisa menilai sendiri.
    """
    if not activity:
        return InfluenceReport(
            top=[],
            total_authors=0,
            ranked_authors=0,
            total_posts=0,
            total_engagement=0,
            concentration_top10_pct=0.0,
            insufficient_data=True,
            note="Belum ada percakapan yang membawa identitas akun.",
        )

    total_posts = sum(a.posts for a in activity)
    total_engagement = sum(a.engagement for a in activity)
    total_authors = len(activity)

    if total_authors < MIN_AUTHORS:
        return InfluenceReport(
            top=[],
            total_authors=total_authors,
            ranked_authors=0,
            total_posts=total_posts,
            total_engagement=total_engagement,
            concentration_top10_pct=0.0,
            insufficient_data=True,
            note=(
                f"Perlu minimal {MIN_AUTHORS} akun berbeda untuk memeringkat "
                f"keterpaparan; periode ini baru punya {total_authors}."
            ),
        )

    per_post = [a.engagement / a.posts for a in activity if a.posts > 0]
    baseline = median(per_post) if per_post else 0.0

    rankable = [a for a in activity if a.posts >= MIN_POSTS_FOR_RANKING]
    estimates: list[InfluenceEstimate] = []
    for a in rankable:
        post_share = 100 * a.posts / total_posts if total_posts else 0.0
        engagement_share = (
            100 * a.engagement / total_engagement if total_engagement else 0.0
        )
        amplification = (a.engagement / a.posts) / baseline if baseline > 0 else 0.0
        estimates.append(
            InfluenceEstimate(
                author_hash=a.author_hash,
                posts=a.posts,
                engagement=a.engagement,
                post_share_pct=round(post_share, 2),
                engagement_share_pct=round(engagement_share, 2),
                amplification=round(amplification, 2),
                influence_estimate=round(
                    min(100.0, 0.4 * post_share + 0.6 * engagement_share), 2
                ),
            )
        )

    # Urutan kedua berdasarkan hash supaya hasilnya stabil saat skornya seri.
    estimates.sort(key=lambda e: (-e.influence_estimate, e.author_hash))

    top10_posts = sum(
        a.posts for a in sorted(activity, key=lambda x: -x.posts)[:10]
    )
    concentration = 100 * top10_posts / total_posts if total_posts else 0.0

    note = None
    if not estimates:
        note = (
            f"Tidak ada akun dengan minimal {MIN_POSTS_FOR_RANKING} unggahan "
            "pada periode ini. Satu unggahan viral bukan keterpaparan yang "
            "bisa diperingkat."
        )

    return InfluenceReport(
        top=estimates[:limit],
        total_authors=total_authors,
        ranked_authors=len(estimates),
        total_posts=total_posts,
        total_engagement=total_engagement,
        concentration_top10_pct=round(concentration, 2),
        insufficient_data=not estimates,
        note=note,
    )
