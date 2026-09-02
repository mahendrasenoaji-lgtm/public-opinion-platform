"""Estimasi jaringan interaksi antar-akun dari relasi balasan/kutipan (Phase 3).

## Kata yang dipakai, dan kenapa

Sama seperti services/influence.py: modul ini TIDAK menyimpulkan bahwa sebuah
akun "mengendalikan" percakapan (CLAUDE.md §3), dan TIDAK menyimpulkan
koordinasi antar-akun. Yang bisa diukur dari relasi balasan/kutipan adalah
**posisi struktural** — seberapa sering sebuah akun dibalas atau dikutip oleh
akun lain yang IKUT muncul dalam data yang sama. Itu bukan pengaruh kausal,
dan bukan bukti kendali; ia deskripsi dari graf percakapan yang teramati.

## Batasan struktural yang tidak bisa dihindari

**Hanya edge di antara akun yang muncul di kedua sisi.** Kalau akun A membalas
tweet dari akun B, tapi tweet B itu sendiri tidak IKUT terambil konektor (di
luar kueri pencarian, di luar jendela waktu 7 hari, dsb — lihat
connectors/x.py), maka B tidak muncul sebagai node di graf ini. Bukan karena B
tidak pernah dibalas, tapi karena data tentang siapa B tidak ada dalam
himpunan ini. Graf ini SELALU sebagian, tidak pernah lengkap — dan itu
disebutkan di setiap hasil, bukan disembunyikan di balik angka yang terlihat
utuh.

**Bukan deteksi buzzer atau koordinasi.** Akun yang banyak dibalas bisa karena
opininya memang memicu perdebatan sehat, atau karena memancing kemarahan lewat
cara lain — relasi balasan saja tidak bisa membedakan itu. Sistem ini tidak
menandai fraud (CLAUDE.md §3); ia hanya menghitung.

**Bukan identifikasi akun.** Sama seperti influence.py: yang masuk dan keluar
dari sini adalah `author_hash`, bukan handle.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

#: Di bawah ini, peringkat "paling banyak dibalas/dikutip" tidak diterbitkan —
#: sama semangatnya dengan MIN_AUTHORS di services/influence.py.
MIN_ACCOUNTS = 10

#: Minimal relasi (edge) supaya graf bukan sekadar dua-tiga interaksi acak
#: yang kebetulan tertangkap konektor.
MIN_EDGES = 15

METHOD = (
    "graf terarah dari relasi balasan dan kutipan yang tertangkap konektor -- "
    "in-degree berbobot per akun, bukan ukuran pengaruh kausal"
)

LIMITATIONS = (
    "Graf ini hanya memuat relasi antar akun yang KEDUANYA muncul sebagai "
    "penulis dalam data yang berhasil diambil -- kalau akun yang dibalas atau "
    "dikutip tidak ikut terambil, relasinya tidak tercatat sama sekali, "
    "bukan tercatat sebagai nol. 'Paling banyak dibalas/dikutip' adalah "
    "deskripsi struktural dari graf yang teramati, bukan bukti pengaruh "
    "kausal, kendali atas opini, atau koordinasi antar-akun."
)

EdgeKind = Literal["reply", "quote"]


@dataclass(frozen=True, slots=True)
class InteractionEdge:
    """Satu relasi balasan atau kutipan antar dua akun, sudah di-hash.

    `source_hash` adalah akun yang membalas/mengutip; `target_hash` adalah
    akun yang dibalas/dikutip.
    """

    source_hash: str
    target_hash: str
    kind: EdgeKind


@dataclass(frozen=True, slots=True)
class AccountPosition:
    """Posisi satu akun dalam graf — seberapa sering ia jadi TUJUAN relasi."""

    author_hash: str
    replies_received: int
    quotes_received: int
    #: replies_received + quotes_received. Cuma untuk mengurutkan, bukan
    #: satuan apa pun (sama semangatnya dengan influence_estimate).
    in_degree: int
    #: Berapa akun BERBEDA yang membalas/mengutip akun ini — membedakan satu
    #: akun yang membalas 20 kali dari 20 akun yang masing-masing sekali.
    distinct_sources: int


@dataclass(frozen=True, slots=True)
class NetworkReport:
    top: list[AccountPosition]
    total_accounts: int
    total_edges: int
    method: str = METHOD
    insufficient_data: bool = False
    note: str | None = None
    limitations: list[str] = field(default_factory=lambda: [LIMITATIONS])


def build(edges: Sequence[InteractionEdge], *, limit: int = 10) -> NetworkReport:
    """Peringkat akun berdasarkan seberapa sering dibalas/dikutip akun lain.

    Self-loop (akun membalas dirinya sendiri, mis. thread panjang satu orang)
    dibuang — itu bukan interaksi ANTAR akun.
    """
    filtered = [e for e in edges if e.source_hash != e.target_hash]
    accounts = {a for e in filtered for a in (e.source_hash, e.target_hash)}
    total_accounts = len(accounts)
    total_edges = len(filtered)

    if total_accounts < MIN_ACCOUNTS:
        return NetworkReport(
            top=[],
            total_accounts=total_accounts,
            total_edges=total_edges,
            insufficient_data=True,
            note=(
                f"Perlu minimal {MIN_ACCOUNTS} akun berbeda yang terhubung lewat "
                f"balasan/kutipan; baru ada {total_accounts}."
            ),
        )
    if total_edges < MIN_EDGES:
        return NetworkReport(
            top=[],
            total_accounts=total_accounts,
            total_edges=total_edges,
            insufficient_data=True,
            note=(
                f"Perlu minimal {MIN_EDGES} relasi balasan/kutipan untuk "
                f"menggambar graf; baru ada {total_edges}."
            ),
        )

    replies: dict[str, int] = {}
    quotes: dict[str, int] = {}
    sources: dict[str, set[str]] = {}
    for e in filtered:
        if e.kind == "reply":
            replies[e.target_hash] = replies.get(e.target_hash, 0) + 1
        else:
            quotes[e.target_hash] = quotes.get(e.target_hash, 0) + 1
        sources.setdefault(e.target_hash, set()).add(e.source_hash)

    positions: list[AccountPosition] = []
    for acc in accounts:
        r = replies.get(acc, 0)
        q = quotes.get(acc, 0)
        if r == 0 and q == 0:
            continue  # akun ini cuma pernah jadi SUMBER, tidak pernah dituju
        positions.append(
            AccountPosition(
                author_hash=acc,
                replies_received=r,
                quotes_received=q,
                in_degree=r + q,
                distinct_sources=len(sources.get(acc, set())),
            )
        )
    # Urutan kedua/ketiga berdasarkan hash supaya hasilnya stabil saat seri.
    positions.sort(key=lambda p: (-p.in_degree, -p.distinct_sources, p.author_hash))

    return NetworkReport(
        top=positions[:limit],
        total_accounts=total_accounts,
        total_edges=total_edges,
    )
