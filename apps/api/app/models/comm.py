"""Tabel modul Kinerja Komunikasi Pemerintah.

`official_posts` sengaja BUKAN bagian dari `mentions`: unggahan akun resmi
lembaga adalah pernyataan lembaga, bukan percakapan warga (SOCIAL) dan bukan
liputan redaksi (MEDIA). Menyimpannya terpisah menjamin ia tidak pernah ikut
terhitung dalam sentimen publik (CLAUDE.md R1). Kolom `account` berisi nama
akun LEMBAGA yang dinilai, bukan akun warga.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OfficialPost(Base):
    __tablename__ = "official_posts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    account: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kind: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    likes: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)
    views: Mapped[int | None] = mapped_column(Integer)
    saves: Mapped[int | None] = mapped_column(Integer)
    reach: Mapped[int | None] = mapped_column(Integer)
    impressions: Mapped[int | None] = mapped_column(Integer)
    followers: Mapped[int | None] = mapped_column(Integer)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommIndicatorScore(Base):
    __tablename__ = "comm_indicator_scores"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    period: Mapped[str] = mapped_column(Text, nullable=False)
    indicator: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int | None] = mapped_column(SmallInteger)
    unavailable_reason: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="")
    assessed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OfficialPostCoding(Base):
    """Kode isi satu unggahan oleh satu lembar pengode (1 atau 2)."""

    __tablename__ = "official_post_codings"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    post_id: Mapped[UUID] = mapped_column(
        ForeignKey("official_posts.id", ondelete="CASCADE"), nullable=False
    )
    coder: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    coder_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    codes: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    coded_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    coded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommFlowRecord(Base):
    """Cap waktu arus informasi satu konten yang ditelusuri auditor (T1-T4)."""

    __tablename__ = "comm_flow_records"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    drafted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bottleneck_stage: Mapped[int | None] = mapped_column(SmallInteger)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommAlignmentPair(Base):
    """Kode keselarasan satu pasangan pernyataan dua lembaga (indikator C3)."""

    __tablename__ = "comm_alignment_pairs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    issue: Mapped[str] = mapped_column(Text, nullable=False)
    subject_a: Mapped[str] = mapped_column(Text, nullable=False)
    url_a: Mapped[str | None] = mapped_column(Text)
    subject_b: Mapped[str] = mapped_column(Text, nullable=False)
    url_b: Mapped[str | None] = mapped_column(Text)
    coder: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    coded_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    coded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OfficialSite(Base):
    """Situs web resmi lembaga yang dipantau keaktifannya."""

    __tablename__ = "official_sites"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    feed_kind: Mapped[str] = mapped_column(Text, nullable=False, default="none")
    source_url: Mapped[str | None] = mapped_column(Text)
    check_notes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    list_urls: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OfficialSiteItem(Base):
    """Satu butir yang terbit di situs resmi: judul, alamat, tanggal, kategori."""

    __tablename__ = "official_site_items"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[UUID] = mapped_column(
        ForeignKey("official_sites.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False, default="lainnya")
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
