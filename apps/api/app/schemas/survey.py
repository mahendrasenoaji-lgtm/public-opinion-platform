"""Survey, Question, Respondent, Response schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# --- Survey ---

class SurveyCreate(BaseModel):
    project_id: UUID
    title: str = Field(min_length=1, max_length=300)
    wave: int = Field(ge=1, default=1)
    sampling_method: str = "MULTISTAGE"
    target_n: int | None = None
    fielded_from: date | None = None
    fielded_to: date | None = None
    sampling_params: dict | None = None


class SurveyOut(BaseModel):
    id: UUID
    org_id: UUID
    project_id: UUID
    wave: int
    title: str
    sampling_method: str
    target_n: int | None
    fielded_from: date | None
    fielded_to: date | None
    sampling_params: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class SurveyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    sampling_method: str | None = None
    target_n: int | None = None
    fielded_from: date | None = None
    fielded_to: date | None = None


# --- Question (9 tipe: SINGLE, MULTI, LIKERT, SEMANTIC_DIFF, RANKING, MATRIX, OPEN, DEMOGRAPHIC, SCREENING) ---

class QuestionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    type: str  # SINGLE | MULTI | LIKERT | SEMANTIC_DIFF | RANKING | MATRIX | OPEN | DEMOGRAPHIC | SCREENING
    text: str = Field(min_length=1)
    position: int = Field(ge=0)
    options: list | None = None
    required: bool = True
    poi_dimension: str | None = None
    reverse_scored: bool = False


class QuestionOut(BaseModel):
    id: UUID
    survey_id: UUID
    position: int
    code: str
    type: str
    text: str
    options: list
    required: bool
    poi_dimension: str | None
    reverse_scored: bool

    model_config = {"from_attributes": True}


class QuestionReorder(BaseModel):
    """Reorder questions by passing question IDs in desired order."""
    question_ids: list[UUID]


# --- Respondent ---

class RespondentCreate(BaseModel):
    anon_code: str = Field(min_length=1)
    age_band: str | None = None
    gender: str | None = None
    education: str | None = None
    occupation: str | None = None
    province_code: str | None = None
    urbanicity: str | None = None
    duration_sec: int | None = None


class RespondentOut(BaseModel):
    id: UUID
    survey_id: UUID
    anon_code: str
    age_band: str | None
    gender: str | None
    education: str | None
    occupation: str | None
    province_code: str | None
    urbanicity: str | None
    weight: Decimal
    completed_at: datetime | None
    duration_sec: int | None
    quality_score: int | None
    quality_flags: list[str]

    model_config = {"from_attributes": True}


# --- Response ---

class ResponseCreate(BaseModel):
    question_id: UUID
    value_num: Decimal | None = None
    value_text: str | None = None
    value_json: dict | None = None


class ResponseBulk(BaseModel):
    """Ingest all responses for one respondent in one call."""
    respondent: RespondentCreate
    answers: list[ResponseCreate]


class ResponseOut(BaseModel):
    id: UUID
    respondent_id: UUID
    question_id: UUID
    value_num: Decimal | None
    value_text: str | None
    value_json: dict | None
    answered_at: datetime

    model_config = {"from_attributes": True}


# --- Post-stratification weighting (services/weighting.py) ---

class WeightingTargets(BaseModel):
    """Target populasi per variabel, dari sensus/BPS. Tiap variabel harus
    berjumlah mendekati 1.0. Variabel yang didukung: age_band, gender,
    education, occupation, province_code, urbanicity (lihat RAKEABLE_VARIABLES
    di services/weighting.py)."""

    targets: dict[str, dict[str, float]] = Field(
        description='Contoh: {"gender": {"L": 0.49, "P": 0.51}}',
    )
    max_iterations: int = Field(default=25, ge=1, le=100)
    trim_ratio: float = Field(default=3.0, ge=1.0, le=10.0)


class WeightingReport(BaseModel):
    survey_id: UUID
    respondent_count: int
    iterations: int
    converged: bool
    trimmed_count: int
    max_weight: float
    min_weight: float
    warnings: list[str]
