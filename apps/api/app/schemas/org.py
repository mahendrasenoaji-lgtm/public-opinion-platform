"""Organization schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OrgCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9\-]+$")


class OrgOut(BaseModel):
    id: UUID
    name: str
    slug: str
    plan: str
    retention_days: int
    created_at: datetime

    model_config = {"from_attributes": True}


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
