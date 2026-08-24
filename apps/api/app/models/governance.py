"""AIOutput, AuditLog, DataQualityScore models."""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import INET, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ConfidenceBand(str, enum.Enum):  # noqa: UP042 — lihat catatan di
    # app/models/measurement.py:SignalSource. Sama alasannya: cocok dengan
    # tipe enum Postgres native `confidence_band` (db/schema.sql), bukan
    # String biasa. Enum lokal di sini (bukan impor app.ai.envelope.Confidence)
    # supaya app/models tidak bergantung ke app/ai.
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ReviewStatus(str, enum.Enum):  # noqa: UP042
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class AIOutput(Base):
    """Satu baris per keluaran AI (CLAUDE.md R2). Ditulis pertama kali oleh
    ExecutiveBriefAgent (app/ai/brief.py) — sebelum itu tabel ini memang
    kosong, bukan bug."""

    __tablename__ = "ai_outputs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False)
    confidence: Mapped[ConfidenceBand] = mapped_column(
        SAEnum(
            ConfidenceBand,
            name="confidence_band",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    limitations: Mapped[str] = mapped_column(Text, nullable=False)
    human_review: Mapped[ReviewStatus] = mapped_column(
        SAEnum(
            ReviewStatus,
            name="review_status",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=ReviewStatus.PENDING,
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    ip: Mapped[str | None] = mapped_column(INET)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataQualityScore(Base):
    __tablename__ = "data_quality_scores"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    dataset: Mapped[str] = mapped_column(Text, nullable=False)
    completeness: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicate: Mapped[int] = mapped_column(Integer, nullable=False)
    response_qual: Mapped[int] = mapped_column(Integer, nullable=False)
    consistency: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_score: Mapped[int] = mapped_column(Integer, nullable=False)
    overall: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
