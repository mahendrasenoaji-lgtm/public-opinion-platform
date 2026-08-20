"""Project schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    objective: str | None = None
    poi_weights: dict[str, float] | None = None


class ProjectOut(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    objective: str | None
    poi_weights: dict[str, float]
    is_demo: bool
    created_by: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    objective: str | None = None
    poi_weights: dict[str, float] | None = None
