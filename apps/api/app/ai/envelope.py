"""Kontrak keluaran AI.

Aturan R2 di CLAUDE.md: tidak ada hasil LLM yang boleh keluar dari API ini tanpa
bukti, metode, tingkat keyakinan, batasan, versi model, dan status tinjauan.

Kontrak ini ditegakkan oleh validator Pydantic, bukan oleh disiplin penulis kode.
Kalau sebuah fitur tidak bisa menyebutkan buktinya, fitur itu memang tidak boleh
ditampilkan.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

T = TypeVar("T")


class Confidence(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ReviewStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class EvidenceRef(BaseModel):
    """Penunjuk ke data agregat yang mendasari sebuah klaim.

    Tidak pernah menunjuk ke responden individual. Kalau sebuah klaim hanya bisa
    dibuktikan dengan menunjuk satu orang, klaim itu tidak boleh dibuat.
    """

    kind: Literal["metric_snapshot", "mention_aggregate", "narrative", "segment", "forecast"]
    ref_id: UUID | None = None
    label: str = Field(min_length=1, description="Deskripsi bukti yang bisa dibaca manusia")
    period: str | None = None
    n: int | None = Field(default=None, ge=0)
    source: Literal["SURVEY", "SOCIAL", "MEDIA", "DIGITAL"]

    @field_validator("n")
    @classmethod
    def _aggregate_only(cls, v: int | None) -> int | None:
        if v is not None and 0 < v < 5:
            raise ValueError(
                "agregat dengan n < 5 tidak boleh dijadikan bukti — risiko "
                "re-identifikasi responden"
            )
        return v


#: Kata-kata yang menyiratkan kausalitas dari data observasional.
#: Lihat CLAUDE.md §3. Daftar ini dicek pada teks yang dihasilkan model.
CAUSAL_TERMS = (
    "menyebabkan",
    "disebabkan oleh",
    "mengakibatkan",
    "akibat langsung",
    "terbukti membuat",
    "caused by",
    "causes",
)

#: Klaim determinasi yang dilarang pada modul forecast dan influencer.
OVERCLAIM_TERMS = ("dipastikan", "pasti akan", "mengendalikan opini", "menjamin")


# noqa: UP046 sengaja tidak diterapkan di sini — sintaks generic class PEP 695
# belum diverifikasi stabil dengan model_validator generik Pydantic v2 untuk
# file R2 CLAUDE.md ini (kontrak wajib tiap keluaran AI); tidak ikut
# modernisasi otomatis tanpa pengujian eksplisit.
class AIEnvelope(BaseModel, Generic[T]):  # noqa: UP046
    """Pembungkus wajib untuk setiap keluaran AI."""

    payload: T
    method: str = Field(min_length=3)
    model_version: str = Field(min_length=1)
    confidence: Confidence
    evidence: list[EvidenceRef] = Field(min_length=1)
    limitations: str = Field(min_length=10)
    human_review: ReviewStatus = ReviewStatus.PENDING
    is_simulation: bool = False
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    prompt_hash: str | None = None

    model_config = {"protected_namespaces": ()}

    @model_validator(mode="after")
    def _guard(self) -> AIEnvelope[T]:
        text = _flatten(self.payload).lower()

        found = [t for t in CAUSAL_TERMS if t in text]
        if found and not self._has_causal_design():
            raise ValueError(
                "keluaran memuat klaim kausal "
                f"({', '.join(found)}) tanpa desain pembanding. Gunakan "
                "'berkaitan dengan' atau 'kemungkinan terkait', atau jalankan "
                "modul Communication Impact."
            )

        over = [t for t in OVERCLAIM_TERMS if t in text]
        if over:
            raise ValueError(f"keluaran memuat klaim berlebihan: {', '.join(over)}")

        if self.is_simulation and "simulasi" not in self.limitations.lower():
            raise ValueError(
                "keluaran simulasi wajib menyatakan pada bagian limitations bahwa "
                "angka tersebut hasil simulasi, bukan prediksi terjamin"
            )

        sources = {e.source for e in self.evidence}
        if sources == {"SOCIAL"} and self.confidence is Confidence.HIGH:
            raise ValueError(
                "confidence HIGH tidak diperbolehkan bila seluruh bukti berasal "
                "dari data media sosial yang self-selected"
            )
        return self

    def _has_causal_design(self) -> bool:
        return any(
            k in self.method.lower()
            for k in ("difference-in-differences", "did", "rct", "synthetic control", "eksperimen")
        )

    def approve(self, reviewer: UUID) -> AIEnvelope[T]:
        return self.model_copy(update={"human_review": ReviewStatus.APPROVED})


def _flatten(value: object, depth: int = 0) -> str:
    """Ratakan payload menjadi teks agar bisa dicek oleh guard."""
    if depth > 6:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, BaseModel):
        return _flatten(value.model_dump(), depth + 1)
    if isinstance(value, dict):
        return " ".join(_flatten(v, depth + 1) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten(v, depth + 1) for v in value)
    return ""
