"""Pengambilan konteks untuk AI Copilot — RAG di atas data AGREGAT.

## Kenapa retrieval-nya di atas agregat, bukan di atas mention individual

RAG yang lazim mencari potongan dokumen paling mirip dengan pertanyaan lalu
menyodorkannya ke model. Kalau itu diterapkan pada tabel `mentions`, yang
disodorkan ke model — dan berpotensi ikut dikutip di jawaban — adalah
tulisan orang per orang.

Itu dilarang di platform ini. `EvidenceRef` (app/ai/envelope.py) sengaja hanya
menerima rujukan agregat, dan komentarnya menyebutkan alasannya: kalau sebuah
klaim hanya bisa dibuktikan dengan menunjuk satu orang, klaim itu tidak boleh
dibuat. Maka yang diambil di sini adalah **kartu fakta** yang sudah berupa
agregat — index dan dimensinya, divergensi antar sumber, segmen, tema, volume
dan sentimen sinyal.

Konsekuensinya jujur dan perlu disebut: Copilot tidak bisa menjawab "apa yang
orang katakan persis" karena ia memang tidak pernah melihat kalimat siapa pun.
Ia menjawab dari angka yang sudah diringkas.

## Kenapa pencocokan kata kunci, bukan embedding

Sama seperti di services/topics.py: belum ada provider embedding yang
dikonfigurasi. Pencocokan kata kunci lebih lemah, tapi ia deterministik dan
bisa diaudit — pengguna yang bertanya kenapa suatu kartu dipakai bisa
ditunjukkan kata mana yang cocok. Metodenya dilaporkan apa adanya lewat
`METHOD`, bukan disebut "semantic search".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.ai.envelope import EvidenceRef
from app.services.ingestion import normalize_text, wordset

METHOD = "RAG atas kartu fakta agregat, pemilihan lewat pencocokan kata kunci"

#: Kata yang tidak membantu memilih kartu apa pun.
_QUESTION_STOPWORDS = wordset("""
    apa apakah siapa kapan mana bagaimana kenapa mengapa berapa yang dan di ke
    dari untuk dengan pada ini itu tidak akan sudah bisa ada saya kami kita
    mereka adalah karena kalau juga saja lebih banyak tolong coba jelaskan
    ceritakan sebutkan bagaimanakah gimana kah nya
""")

#: Skor minimum agar sebuah kartu dianggap relevan dengan pertanyaan.
RELEVANCE_THRESHOLD = 1


@dataclass(frozen=True, slots=True)
class FactCard:
    """Satu potong data agregat yang siap disodorkan ke model.

    `is_core` menandai kartu yang selalu layak dikirim untuk pertanyaan umum
    ("bagaimana kondisi opini publik sekarang?") yang tidak menyebut kata kunci
    spesifik apa pun.
    """

    key: str
    label: str
    payload: dict[str, Any]
    evidence: EvidenceRef
    keywords: frozenset[str] = field(default_factory=frozenset)
    is_core: bool = False

    def searchable(self) -> set[str]:
        return set(normalize_text(self.label).split()) | {
            w for k in self.keywords for w in normalize_text(k).split()
        }


@dataclass(frozen=True, slots=True)
class Retrieved:
    cards: list[FactCard]
    #: True bila tidak satu pun kartu cocok dan yang dikirim adalah kartu inti.
    fell_back_to_core: bool
    matched_terms: dict[str, list[str]]
    method: str = METHOD


def question_terms(question: str) -> set[str]:
    """Kata bermakna dari pertanyaan, setelah stopword dibuang."""
    return {
        w
        for w in normalize_text(question).split()
        if w not in _QUESTION_STOPWORDS and len(w) > 2
    }


def select_relevant(
    question: str, cards: Sequence[FactCard], *, limit: int = 8
) -> Retrieved:
    """Pilih kartu fakta yang relevan dengan pertanyaan.

    Kalau tidak ada yang cocok, yang dikembalikan adalah kartu inti — bukan
    daftar kosong. Alasannya: pertanyaan umum tanpa kata kunci spesifik adalah
    pertanyaan yang sah, dan menjawabnya "tidak ada data" padahal indexnya ada
    akan salah. `fell_back_to_core` menyatakan itu terjadi, supaya pemanggil
    bisa menurunkan keyakinan atau menyebutnya di batasan.
    """
    terms = question_terms(question)

    scored: list[tuple[int, list[str], FactCard]] = []
    for card in cards:
        matched = sorted(terms & card.searchable())
        if matched:
            scored.append((len(matched), matched, card))

    if not scored or max(s for s, _, _ in scored) < RELEVANCE_THRESHOLD:
        core = [c for c in cards if c.is_core][:limit]
        return Retrieved(cards=core, fell_back_to_core=True, matched_terms={})

    # Urutkan berdasarkan skor, lalu berdasarkan key supaya hasilnya stabil
    # untuk pertanyaan yang sama — jawaban yang berubah-ubah tanpa datanya
    # berubah akan menghancurkan kepercayaan pada seluruh fitur.
    scored.sort(key=lambda t: (-t[0], t[2].key))
    picked = scored[:limit]
    return Retrieved(
        cards=[c for _, _, c in picked],
        fell_back_to_core=False,
        matched_terms={c.key: m for _, m, c in picked},
    )
