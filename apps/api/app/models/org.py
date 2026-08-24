"""Organization and User models."""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


# noqa UP042 sengaja tidak diikuti (str+Enum vs enum.StrEnum) — lihat
# penjelasan lengkap di app/models/measurement.py:SignalSource.
class UserRole(str, enum.Enum):  # noqa: UP042
    SUPER_ADMIN = "SUPER_ADMIN"
    RESEARCH_DIRECTOR = "RESEARCH_DIRECTOR"
    RESEARCHER = "RESEARCHER"
    DATA_ANALYST = "DATA_ANALYST"
    COMM_STRATEGIST = "COMM_STRATEGIST"
    EXECUTIVE = "EXECUTIVE"
    CLIENT = "CLIENT"
    VIEWER = "VIEWER"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(Text, nullable=False, default="starter")
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=730)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list[User]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    projects: Mapped[list] = relationship(
        "Project", back_populates="organization", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default=UserRole.VIEWER.value)
    mfa_secret: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization] = relationship(back_populates="users")
