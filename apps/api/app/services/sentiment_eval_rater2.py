"""Penilai KEDUA untuk set lapangan, dan angka kesepakatan antarpenilai.

`sentiment_eval_field.py` dilabeli satu penilai. Modul ini menambahkan label
kedua atas 440 komentar yang sama supaya kesepakatan antarpenilai bisa
DIHITUNG, bukan diasumsikan.

## Cara pelabelan

- Dibuat 2026-10-12 dari teksnya saja: label, belahan, dan penanda penilai
  pertama tidak dibuka sebelum seluruh 440 label ini selesai ditulis, dan
  tidak ada label yang diubah sesudah keduanya dibandingkan.
- Pedomannya sama dengan penilai pertama: yang dilabeli NADA teks; sarkasme
  menurut maksudnya; campuran mengikuti yang dominan.

## Batasnya — baca sebelum mengutip kappa-nya

Penilai kedua ini juga agen AI, dari keluarga model yang sama dengan penilai
pertama. Ia independen dalam arti tidak melihat label pertama, TIDAK dalam
arti berasal dari latar yang berbeda: dua penilai yang berbagi kecenderungan
akan sepakat lebih sering daripada dua manusia. Kappa di sini adalah batas
atas yang wajar, bukan pengganti penilai manusia. Yang benar-benar berguna
darinya adalah daftar komentar yang TIDAK disepakati: di situlah pedoman
pelabelannya sendiri tidak cukup tegas.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.sentiment import EvaluationReport, evaluate
from app.services.sentiment_eval_field import FIELD

LABELS = ("negatif", "netral", "positif")
_CODE = {"n": "negatif", "t": "netral", "p": "positif"}

#: Satu huruf per komentar, urutannya sama dengan `FIELD`. Sepuluh per baris.
_RATER2 = (
    "nnnnnnnttn"  # 0
    "nntnnnptnn"  # 10
    "pnnnnnntnp"  # 20
    "nnnnnnnnnn"  # 30
    "nnnnnpnnnn"  # 40
    "pnnnnnnpnt"  # 50
    "ntntnnnnnn"  # 60
    "nntnppntnn"  # 70
    "nnnnpnnnnn"  # 80
    "nnnnptnnnn"  # 90
    "tnnnnnnnnn"  # 100
    "nttnpnpnnn"  # 110
    "pnnnntnntn"  # 120
    "nnpnnnnnnp"  # 130
    "tnpnntnpnn"  # 140
    "ntpnnpnnnn"  # 150
    "nnnnnnnnnn"  # 160
    "nnpntnpnpt"  # 170
    "nppnnnnpnn"  # 180
    "nnnnnnnnnt"  # 190
    "nnnntpnnpn"  # 200
    "nnntnnpntn"  # 210
    "npnnnpnnnn"  # 220
    "tnntnnnnnp"  # 230
    "nnnnnnnnnn"  # 240
    "npnnpnnppn"  # 250
    "nnnnntnntn"  # 260
    "nnnnnptnnn"  # 270
    "npnnntnnnn"  # 280
    "nnnnnnnpnn"  # 290
    "nnnnpnnnnn"  # 300
    "nnnntnptnn"  # 310
    "nnnnnnntnn"  # 320
    "nnnnnnnnpt"  # 330
    "nnpnnnnnnn"  # 340
    "nnnnnpntpt"  # 350
    "nntnntttnn"  # 360
    "ntnnnnnpnp"  # 370
    "tpnppnnnnn"  # 380
    "nnnptnnnnp"  # 390
    "tnnnnpnnpn"  # 400
    "nnnnnnnnnn"  # 410
    "nnntnnnnnn"  # 420
    "tpnttnnnnt"  # 430
)

RATER2: tuple[str, ...] = tuple(_CODE[c] for c in _RATER2)

if len(RATER2) != len(FIELD):  # pragma: no cover — penjaga saat set diubah
    raise RuntimeError(
        f"label penilai kedua ({len(RATER2)}) tidak sepanjang set lapangan ({len(FIELD)})"
    )


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Kappa Cohen untuk dua penilai atas item yang sama. Fungsi murni.

    Kesepakatan yang dikoreksi peluang: 0 berarti tidak lebih baik dari
    kebetulan menurut sebaran label masing-masing penilai, 1 berarti selalu
    sama. Mengembalikan 1.0 bila keduanya hanya memakai satu label yang sama
    (tidak ada yang bisa dikoreksi).
    """
    if len(a) != len(b):
        raise ValueError("dua penilai harus menilai item yang sama")
    if not a:
        raise ValueError("tidak ada item yang dinilai")
    n = len(a)
    observed = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    expected = sum((a.count(label) / n) * (b.count(label) / n) for label in set(a) | set(b))
    if expected >= 1.0:
        return 1.0
    return (observed - expected) / (1.0 - expected)


@dataclass(frozen=True, slots=True)
class AgreementReport:
    n: int
    #: Bagian item yang kedua penilai beri label sama.
    observed_agreement: float
    kappa: float
    #: confusion[label_penilai_1][label_penilai_2] = jumlah item.
    confusion: dict[str, dict[str, int]]
    #: Sebaran label tiap penilai.
    rater1_distribution: dict[str, int]
    rater2_distribution: dict[str, int]
    #: Mutu ragam informal terhadap label penilai KEDUA, belahan uji.
    informal_vs_rater2: EvaluationReport
    #: Mutu ragam informal hanya pada item uji yang DISEPAKATI kedua penilai.
    informal_on_agreed: EvaluationReport
    agreed_test_n: int
    caveat: str


AGREEMENT_CAVEAT = (
    "Penilai kedua juga agen AI dari keluarga model yang sama dengan penilai "
    "pertama; ia tidak melihat label pertama, tapi bukan penilai manusia yang "
    "independen. Kappa ini batas atas yang wajar, bukan ukuran final."
)


def evaluate_agreement() -> AgreementReport:
    first = [item.label for item in FIELD]
    second = list(RATER2)
    confusion = {a: {b: 0 for b in LABELS} for a in LABELS}
    for a, b in zip(first, second, strict=True):
        confusion[a][b] += 1

    test = [(item, r2) for item, r2 in zip(FIELD, second, strict=True) if item.split == "uji"]
    agreed = [(item.text, r2) for item, r2 in test if item.label == r2]
    return AgreementReport(
        n=len(first),
        observed_agreement=round(
            sum(1 for a, b in zip(first, second, strict=True) if a == b) / len(first), 3
        ),
        kappa=round(cohen_kappa(first, second), 3),
        confusion=confusion,
        rater1_distribution={label: first.count(label) for label in LABELS},
        rater2_distribution={label: second.count(label) for label in LABELS},
        informal_vs_rater2=evaluate([(item.text, r2) for item, r2 in test], register="informal"),
        informal_on_agreed=evaluate(agreed, register="informal"),
        agreed_test_n=len(agreed),
        caveat=AGREEMENT_CAVEAT,
    )
