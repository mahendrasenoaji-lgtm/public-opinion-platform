"""Topic discovery dan momentum narasi.

## Metode dan kenapa ia dilabeli apa adanya

`docs/roadmap.md` Phase 2 menuliskan "embedding → HDBSCAN → label LLM". Yang
dijalankan modul ini adalah **TF-IDF → LSA (SVD) → HDBSCAN → label kata kunci**,
dan `method` mengembalikan persis kalimat itu, bukan kalimat roadmap.

Alasannya bukan bahwa TF-IDF lebih baik — ia lebih buruk untuk parafrase, dan
tidak paham bahwa "harga naik" dan "makin mahal" adalah keluhan yang sama.
Alasannya: belum ada provider embedding yang dikonfigurasi di deployment ini,
dan mengklaim "embedding" pada vektor TF-IDF melanggar R1 di tempat yang paling
mahal — metadata metode adalah satu-satunya cara pembaca laporan tahu seberapa
jauh angka ini bisa dipercaya.

Ketika provider embedding tersedia, yang perlu diganti hanya `_vectorize()`.
Label metode dan `limitations` HARUS ikut berubah di commit yang sama.

## Kenapa klaster yang tidak masuk dilaporkan, bukan disembunyikan

HDBSCAN menyisakan titik yang tidak masuk klaster mana pun sebagai derau.
Itu fitur, bukan kegagalan: percakapan publik memang sebagian besar tidak rapi.
`unclustered_pct` dikembalikan dan wajib ditampilkan — peta narasi yang
menyembunyikan bahwa 40% percakapan tidak terpetakan sedang berbohong tentang
cakupannya sendiri. Kolom `narratives.unclustered_pct` di schema.sql ada untuk
ini sejak awal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import HDBSCAN
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from app.services.ingestion import normalize_text, wordset

#: Di bawah ini, klaster apa pun yang muncul lebih mungkin derau daripada tema.
#: Bukan batas teknis HDBSCAN — batas kelayakan pelaporan.
MIN_DOCUMENTS = 20

#: Ukuran klaster minimum. Lima orang membicarakan hal yang sama belum tema
#: publik; ia bisa satu utas percakapan.
DEFAULT_MIN_CLUSTER_SIZE = 5

#: Batas atas dimensi LSA, untuk korpus besar.
SVD_COMPONENTS = 50

#: Berapa dokumen yang dibutuhkan per dimensi LSA.
#:
#: Ini bukan angka yang bisa dibiarkan tetap. HDBSCAN bekerja dari kepadatan,
#: dan kepadatan menguap begitu dimensi naik mendekati jumlah titik: 24
#: dokumen yang diproyeksikan ke 23 dimensi menghasilkan NOL klaster — setiap
#: titik terlihat sama jauhnya dari semua titik lain, jadi semuanya dilaporkan
#: sebagai derau. Korpus yang sama pada 3 dimensi memisahkan temanya dengan
#: bersih.
#:
#: Konsekuensinya disengaja: korpus kecil hanya boleh menghasilkan tema kasar.
#: Struktur yang lebih halus baru boleh dicari setelah datanya cukup untuk
#: menopangnya, bukan dipaksa keluar dari data yang tipis.
DOCUMENTS_PER_COMPONENT = 8

METHOD = "TF-IDF + LSA(SVD) + HDBSCAN, label dari kata kunci teratas"

#: Stopword Bahasa Indonesia untuk vektorisasi. Lebih panjang daripada daftar
#: di ingestion.py (yang tugasnya membedakan bahasa, bukan membuang kata umum).
STOPWORDS_ID = wordset("""
    yang dan di ke dari untuk dengan pada ini itu tidak akan sudah bisa ada
    saya kami kita mereka dia adalah karena kalau juga saja lebih banyak
    orang tahun bagi oleh dalam atau agar sangat masih belum bukan para
    kan nya se ya nih sih dong deh aja gitu gini kok toh pun lah
    apa siapa kapan mana bagaimana kenapa mengapa berapa
    ada adanya menjadi jadi dapat harus perlu boleh mau ingin
    satu dua tiga empat lima enam tujuh delapan sembilan sepuluh
    dia nya anda kamu aku beliau tersebut demikian tapi tetapi namun
    kalau jika bila ketika saat setelah sebelum sampai hingga selama
    tentang terhadap seperti sebagai antara serta hanya sudah belum pernah
""")


@dataclass(frozen=True, slots=True)
class TopicCluster:
    """Satu tema hasil klasterisasi."""

    keywords: list[str]
    size: int
    member_indexes: list[int]
    #: Rata-rata kemiripan kosinus antar anggota. Klaster dengan koherensi
    #: rendah adalah tema yang longgar — dilaporkan supaya pembaca tahu mana
    #: tema yang tajam dan mana yang sekadar berdekatan.
    coherence: float

    @property
    def label(self) -> str:
        """Label sementara dari kata kunci.

        Sengaja bukan kalimat: label yang enak dibaca ("Kekhawatiran soal harga
        pangan") adalah interpretasi, dan interpretasi butuh verifikasi manusia
        atau AIEnvelope. Gabungan kata kunci tidak mengklaim apa pun selain
        kata apa yang sering muncul bersama.
        """
        return " / ".join(self.keywords[:3]) if self.keywords else "(tanpa kata kunci)"


@dataclass(frozen=True, slots=True)
class TopicResult:
    clusters: list[TopicCluster]
    unclustered_indexes: list[int]
    unclustered_pct: float
    n: int
    method: str = METHOD
    insufficient_data: bool = False
    note: str | None = None
    limitations: list[str] = field(default_factory=list)


def limitations_for(unclustered_pct: float) -> list[str]:
    """Batasan yang wajib menyertai setiap hasil klasterisasi.

    Publik (bukan helper privat) karena isinya aturan pelaporan, bukan detail
    implementasi: peta tema yang tidak menyebut berapa banyak percakapan di
    luar petanya sedang berbohong soal cakupannya sendiri.
    """
    out = [
        "Klasterisasi memakai kemiripan kata (TF-IDF), bukan makna. Dua "
        "keluhan yang sama tapi berbeda pilihan kata bisa jatuh ke tema "
        "berbeda.",
        "Label tema adalah gabungan kata kunci, bukan interpretasi yang sudah "
        "diverifikasi manusia.",
    ]
    if unclustered_pct >= 30:
        out.append(
            f"{unclustered_pct:.0f}% percakapan tidak masuk tema mana pun. "
            "Peta tema ini tidak menggambarkan sebagian besar percakapan."
        )
    return out


def _vectorize(texts: Sequence[str]) -> tuple[np.ndarray, list[str], np.ndarray]:
    """Teks -> (matriks LSA ternormalisasi, kosakata, matriks TF-IDF padat).

    Titik pengganti ketika provider embedding tersedia. Lihat catatan modul.
    """
    vectorizer = TfidfVectorizer(
        preprocessor=normalize_text,
        stop_words=sorted(STOPWORDS_ID),
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.6,
        sublinear_tf=True,
    )
    tfidf = vectorizer.fit_transform(texts)
    vocabulary = list(vectorizer.get_feature_names_out())

    n_samples, n_features = tfidf.shape
    components = min(
        SVD_COMPONENTS,
        n_features - 1,
        n_samples - 1,
        max(2, n_samples // DOCUMENTS_PER_COMPONENT),
    )
    if components < 2:
        # Korpus terlalu seragam untuk direduksi; pakai TF-IDF apa adanya.
        dense = np.asarray(tfidf.todense())
        return normalize(dense), vocabulary, dense

    # random_state tetap: dua panggilan atas data yang sama harus menghasilkan
    # tema yang sama, kalau tidak laporan minggu ini tidak bisa dibandingkan
    # dengan laporan minggu lalu.
    svd = TruncatedSVD(n_components=components, random_state=0)
    reduced = svd.fit_transform(tfidf)
    return normalize(reduced), vocabulary, np.asarray(tfidf.todense())


def _keywords_for(
    members: np.ndarray, tfidf: np.ndarray, vocabulary: list[str], k: int
) -> list[str]:
    """Kata dengan bobot TF-IDF rata-rata tertinggi di dalam klaster."""
    if members.size == 0 or not vocabulary:
        return []
    mean_weights = tfidf[members].mean(axis=0)
    top = np.argsort(mean_weights)[::-1][:k]
    return [vocabulary[i] for i in top if mean_weights[i] > 0]


def _coherence(members: np.ndarray, reduced: np.ndarray) -> float:
    """Rata-rata kemiripan kosinus antar anggota klaster."""
    if members.size < 2:
        return 0.0
    vectors = reduced[members]
    similarity = vectors @ vectors.T
    n = len(members)
    # Buang diagonal (kemiripan dengan diri sendiri selalu 1).
    off_diagonal = (similarity.sum() - np.trace(similarity)) / (n * (n - 1))
    return round(float(off_diagonal), 3)


def discover(
    texts: Sequence[str],
    *,
    min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
    keywords_per_topic: int = 6,
) -> TopicResult:
    """Temukan tema dari sekumpulan teks.

    Menolak bekerja di bawah MIN_DOCUMENTS: dari 12 komentar, HDBSCAN akan
    tetap menghasilkan sesuatu, dan sesuatu itu akan dipresentasikan sebagai
    "tema publik". Lebih baik mengatakan datanya belum cukup (CLAUDE.md §8).
    """
    n = len(texts)
    if n < MIN_DOCUMENTS:
        return TopicResult(
            clusters=[],
            unclustered_indexes=list(range(n)),
            unclustered_pct=100.0 if n else 0.0,
            n=n,
            insufficient_data=True,
            note=(
                f"Perlu minimal {MIN_DOCUMENTS} percakapan untuk menemukan tema; "
                f"tersedia {n}."
            ),
        )

    non_empty = [i for i, t in enumerate(texts) if normalize_text(t)]
    if len(non_empty) < MIN_DOCUMENTS:
        return TopicResult(
            clusters=[],
            unclustered_indexes=list(range(n)),
            unclustered_pct=100.0,
            n=n,
            insufficient_data=True,
            note="Sebagian besar teks kosong setelah normalisasi.",
        )

    corpus = [texts[i] for i in non_empty]
    try:
        reduced, vocabulary, tfidf = _vectorize(corpus)
    except ValueError:
        # TfidfVectorizer melempar kalau seluruh kosakata tersaring habis
        # (mis. semua teks hanya berisi stopword).
        return TopicResult(
            clusters=[],
            unclustered_indexes=list(range(n)),
            unclustered_pct=100.0,
            n=n,
            insufficient_data=True,
            note="Tidak ada kata yang cukup membedakan setelah penyaringan.",
        )

    labels = HDBSCAN(
        min_cluster_size=max(2, min_cluster_size),
        metric="euclidean",
        cluster_selection_method="eom",
        # Eksplisit: default `copy` berubah di sklearn 1.10, dan kita tidak mau
        # perilaku diam-diam bergeser saat dependensi dinaikkan.
        copy=True,
    ).fit_predict(reduced)

    clusters: list[TopicCluster] = []
    for label in sorted({int(x) for x in labels if x >= 0}):
        members = np.flatnonzero(labels == label)
        clusters.append(
            TopicCluster(
                keywords=_keywords_for(members, tfidf, vocabulary, keywords_per_topic),
                size=int(members.size),
                member_indexes=[non_empty[i] for i in members.tolist()],
                coherence=_coherence(members, reduced),
            )
        )
    clusters.sort(key=lambda c: c.size, reverse=True)

    noise = [non_empty[i] for i in np.flatnonzero(labels == -1).tolist()]
    # Teks yang dibuang karena kosong ikut dihitung tidak terpetakan: dari sudut
    # pandang pembaca laporan ia memang percakapan yang tidak masuk tema.
    unclustered = sorted(noise + [i for i in range(n) if i not in set(non_empty)])
    unclustered_pct = round(100 * len(unclustered) / n, 1)

    return TopicResult(
        clusters=clusters,
        unclustered_indexes=unclustered,
        unclustered_pct=unclustered_pct,
        n=n,
        limitations=limitations_for(unclustered_pct),
    )


def momentum(current: int, previous: int) -> float | None:
    """Perubahan volume antar dua periode setara, dalam persen.

    None kalau periode sebelumnya nol: pertumbuhan dari nol tidak punya
    persentase yang bermakna, dan menampilkan "+∞%" atau "+100%" sama-sama
    menyesatkan. Yang benar adalah mengatakan tema ini baru muncul.
    """
    if previous < 0 or current < 0:
        raise ValueError("volume tidak boleh negatif")
    if previous == 0:
        return None
    return round(100 * (current - previous) / previous, 1)


def share_of_voice(volumes: dict[str, int]) -> dict[str, float]:
    """Porsi tiap tema dari total, dalam persen.

    Penyebutnya adalah total percakapan yang MASUK tema — bukan seluruh
    percakapan. Pemanggil wajib menyajikan `unclustered_pct` di sebelahnya,
    kalau tidak pembaca akan mengira ketiga tema ini mencakup semuanya.
    """
    total = sum(volumes.values())
    if total <= 0:
        return {}
    return {k: round(100 * v / total, 1) for k, v in volumes.items()}
