"""MetricSnapshot, Segment, TimelineEvent, Forecast models."""

from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SignalSource(str, enum.Enum):  # noqa: UP042 — lihat catatan di bawah
    """Cocok dengan tipe enum Postgres `signal_source` di schema.sql. Jangan
    dipetakan sebagai String biasa — perbandingan (`WHERE source = ...`) akan
    gagal dengan "operator does not exist: signal_source = character varying"
    karena Postgres tidak melakukan cast implisit enum↔varchar pada operator
    kesetaraan.

    Sengaja TIDAK diganti ke enum.StrEnum (saran ruff UP042): area persis ini
    sudah ada bug dorman yang dicatat di docs/deployment-status.md soal
    pemetaan enum Postgres native vs String biasa — bukan tempat yang tepat
    untuk modernisasi sintaks tanpa verifikasi eksplisit terhadap perilaku
    SQLAlchemy sesungguhnya."""

    SURVEY = "SURVEY"
    SOCIAL = "SOCIAL"
    MEDIA = "MEDIA"
    DIGITAL = "DIGITAL"


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[SignalSource] = mapped_column(
        SAEnum(
            SignalSource,
            name="signal_source",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    method: Mapped[str] = mapped_column(Text, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    ci_low: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    ci_high: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    effective_n: Mapped[int | None] = mapped_column(Integer)
    province_code: Mapped[str | None] = mapped_column(Text)
    segment: Mapped[str | None] = mapped_column(Text)
    breakdown: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    size_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    sentiment: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    trust: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    profile: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    method: Mapped[str] = mapped_column(Text, nullable=False, default="latent_class")
    entropy: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    value_note: Mapped[str | None] = mapped_column(Text)
    associated_metric: Mapped[str | None] = mapped_column(Text)


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    expected: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    pi_low: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    pi_high: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    pi_level: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, default=Decimal("0.80")
    )
    model: Mapped[str] = mapped_column(Text, nullable=False)
    drivers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_simulation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scenario: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
