import pytest
from pydantic import ValidationError

from app.ai.envelope import AIEnvelope, Confidence, EvidenceRef


def ev(source="SURVEY", n=8940):
    return EvidenceRef(kind="metric_snapshot", label="POI W29 nasional", source=source, n=n)


def make(payload, **kw):
    base = dict(
        method="RAG atas data agregat",
        model_version="claude-sonnet-4-6",
        confidence=Confidence.MEDIUM,
        evidence=[ev()],
        limitations="Estimasi berdasarkan satu gelombang survei.",
    )
    base.update(kw)
    return AIEnvelope[dict](payload=payload, **base)


def test_bukti_wajib_ada():
    with pytest.raises(ValidationError):
        make({"text": "aman"}, evidence=[])


def test_batasan_wajib_diisi():
    with pytest.raises(ValidationError):
        make({"text": "aman"}, limitations="")


def test_klaim_kausal_ditolak_tanpa_desain_pembanding():
    with pytest.raises(ValidationError, match="kausal"):
        make({"text": "Penurunan indeks disebabkan oleh kenaikan harga."})


def test_klaim_kausal_diterima_bila_metodenya_mendukung():
    env = make(
        {"text": "Penurunan indeks disebabkan oleh kenaikan harga."},
        method="difference-in-differences dengan kelompok pembanding",
    )
    assert env.confidence is Confidence.MEDIUM


def test_klaim_berlebihan_ditolak():
    with pytest.raises(ValidationError, match="berlebihan"):
        make({"text": "Akun ini mengendalikan opini publik di Jawa."})


def test_simulasi_wajib_dinyatakan_pada_batasan():
    with pytest.raises(ValidationError, match="simulasi"):
        make({"text": "Indeks 70,5 pada H+30."}, is_simulation=True)


def test_confidence_tinggi_ditolak_bila_bukti_hanya_sosial():
    with pytest.raises(ValidationError, match="self-selected"):
        make({"text": "aman"}, evidence=[ev("SOCIAL", 200000)], confidence=Confidence.HIGH)


def test_agregat_terlalu_kecil_ditolak():
    with pytest.raises(ValidationError, match="re-identifikasi"):
        EvidenceRef(kind="segment", label="segmen kecil", source="SURVEY", n=3)
