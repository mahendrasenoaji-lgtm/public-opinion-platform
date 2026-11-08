"""Tes pola frasa (informal-4) dan peta aktor — fungsi murni."""

from __future__ import annotations

import pytest

from app.services import actors, phrases
from app.services.sentiment import INFORMAL_MODEL_VERSION, score


def test_versi() -> None:
    assert INFORMAL_MODEL_VERSION == "lexicon-id-1+informal-4"


def test_komentar_contoh_pengguna_negatif() -> None:
    r = score(
        "Bahlil tu lo.ganti aja kok.gk bisa mengatasi bbm. "
        "Kalau ngomong mulutnya kok kaya ular berbisa",
        register="informal",
    )
    assert r.label == "negatif"
    assert [w for w, _ in r.matched] == [
        "ganti aja",
        "tidak bisa bekerja/mengatasi",
        "ular berbisa",
    ]


@pytest.mark.parametrize(
    "teks",
    [
        "Koster nggak mampu ngurus bali",
        "pejabat gak punya malu",  # dulu terbaca positif: negasi membalik "malu"
        "Gubenur ga tau diri",
        "Gk pantas jadi pemimpin",
        "Gubernur cari muka",
        "biang keroknya bahlil",
        "Pilkada berikutnya jangan dipilih lagi",
        "Alasan gk masuk akal",
    ],
)
def test_frasa_kritik_terbaca_negatif(teks: str) -> None:
    assert score(teks, register="informal").label == "negatif", teks


@pytest.mark.parametrize(
    "teks",
    ["rakyat tidak mampu beli pertamax", "antrean kayak ular", "ganti oli dulu", "diam kamu"],
)
def test_frasa_yang_sengaja_tidak_ada(teks: str) -> None:
    assert score(teks, register="informal").abstained, teks


def test_frasa_tidak_berlaku_di_ragam_baku() -> None:
    assert score("tidak bisa mengatasi masalah").matched == []


def test_tidak_di_dalam_frasa_tidak_membalik_kata_lain() -> None:
    toks, hits = phrases.match(["tidak", "punya", "malu", "bagus"])
    assert toks == [phrases.PLACEHOLDER, "bagus"] and len(hits) == 1
    assert (
        score("gak punya malu tapi bagus", register="informal").matched[0][0]
        == "tidak punya hati/otak/empati"
    )


def test_aktor_dan_tingkat() -> None:
    t = "Bahlil dan gubernurnya sama aja, pertamina juga"
    assert actors.detect(t) == ["bahlil", "pertamina"]
    assert actors.levels(t) == ["Pemerintah pusat", "Pemerintah daerah", "BUMN energi"]


def test_jabatan_umum_bukan_orang() -> None:
    assert actors.detect("gubernur kok gitu") == []
    assert actors.levels("gubernur kok gitu") == ["Pemerintah daerah"]


def test_aktor_julukan_dan_klitik() -> None:
    assert actors.detect("kosternya arogan") == ["koster"]
    assert actors.detect("pak yan diam aja") == ["koster"]
