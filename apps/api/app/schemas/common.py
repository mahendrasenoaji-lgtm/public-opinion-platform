"""Skema bersama. Semua metrik yang keluar lewat HTTP memakai bentuk ini."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class SignalSource(StrEnum):
    SURVEY = "SURVEY"
    SOCIAL = "SOCIAL"
    MEDIA = "MEDIA"
    DIGITAL = "DIGITAL"


class Metric(BaseModel):
    """Aturan R1: tidak ada angka tanpa sumber dan metode."""

    key: str
    label: str
    value: float | None = Field(description="None bila sampel di bawah ambang publikasi")
    unit: str = "index"
    source: SignalSource
    method: str
    ci_low: float | None = None
    ci_high: float | None = None
    effective_n: int | None = None
    period_start: date | None = None
    period_end: date | None = None
    insufficient_data: bool = False
    note: str | None = None


class Change(BaseModel):
    delta: float
    direction: str
    intervals_separated: bool
    note: str


class Paginated(BaseModel):
    total: int
    limit: int
    offset: int
