"""Survey, Question, Respondent, RespondentIdentity, Response models."""

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
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


# noqa UP042 sengaja tidak diikuti di tiga enum ini (str+Enum vs
# enum.StrEnum) — lihat penjelasan lengkap di
# app/models/measurement.py:SignalSource.
class SamplingMethod(str, enum.Enum):  # noqa: UP042
    SRS = "SRS"
    STRATIFIED = "STRATIFIED"
    CLUSTER = "CLUSTER"
    MULTISTAGE = "MULTISTAGE"
    QUOTA = "QUOTA"
    PURPOSIVE = "PURPOSIVE"


class QuestionType(str, enum.Enum):  # noqa: UP042
    SINGLE = "SINGLE"
    MULTI = "MULTI"
    LIKERT = "LIKERT"
    SEMANTIC_DIFF = "SEMANTIC_DIFF"
    RANKING = "RANKING"
    MATRIX = "MATRIX"
    OPEN = "OPEN"
    DEMOGRAPHIC = "DEMOGRAPHIC"
    SCREENING = "SCREENING"


class QualityFlagEnum(str, enum.Enum):  # noqa: UP042
    SPEEDING = "SPEEDING"
    STRAIGHT_LINING = "STRAIGHT_LINING"
    INCONSISTENT = "INCONSISTENT"
    DUPLICATE_SUSPECT = "DUPLICATE_SUSPECT"
    OUT_OF_QUOTA = "OUT_OF_QUOTA"


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    wave: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    sampling_method: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SamplingMethod.MULTISTAGE.value
    )
    target_n: Mapped[int | None] = mapped_column(Integer)
    fielded_from: Mapped[date | None] = mapped_column(Date)
    fielded_to: Mapped[date | None] = mapped_column(Date)
    sampling_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="surveys")  # noqa: F821
    questions: Mapped[list[Question]] = relationship(
        back_populates="survey", cascade="all, delete-orphan"
    )
    respondents: Mapped[list[Respondent]] = relationship(
        back_populates="survey", cascade="all, delete-orphan"
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    survey_id: Mapped[UUID] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    poi_dimension: Mapped[str | None] = mapped_column(Text)
    reverse_scored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    survey: Mapped[Survey] = relationship(back_populates="questions")


class Respondent(Base):
    __tablename__ = "respondents"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    survey_id: Mapped[UUID] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False
    )
    anon_code: Mapped[str] = mapped_column(Text, nullable=False)
    age_band: Mapped[str | None] = mapped_column(Text)
    gender: Mapped[str | None] = mapped_column(Text)
    education: Mapped[str | None] = mapped_column(Text)
    occupation: Mapped[str | None] = mapped_column(Text)
    province_code: Mapped[str | None] = mapped_column(Text)
    urbanicity: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=Decimal("1.0"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    quality_score: Mapped[int | None] = mapped_column(Integer)
    quality_flags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    survey: Mapped[Survey] = relationship(back_populates="respondents")
    responses: Mapped[list[Response]] = relationship(
        back_populates="respondent", cascade="all, delete-orphan"
    )


class RespondentIdentity(Base):
    """PII terpisah, retensi sendiri. Lihat CLAUDE.md §3 dan data-model.md."""

    __tablename__ = "respondent_identities"

    respondent_id: Mapped[UUID] = mapped_column(
        ForeignKey("respondents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    contact_hash: Mapped[str] = mapped_column(Text, nullable=False)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consent_scope: Mapped[str] = mapped_column(Text, nullable=False)
    purge_after: Mapped[date] = mapped_column(Date, nullable=False)


class Response(Base):
    __tablename__ = "responses"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    respondent_id: Mapped[UUID] = mapped_column(
        ForeignKey("respondents.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    value_num: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    value_text: Mapped[str | None] = mapped_column(Text)
    value_json: Mapped[dict | None] = mapped_column(JSON)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    respondent: Mapped[Respondent] = relationship(back_populates="responses")
