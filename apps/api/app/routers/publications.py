"""Publikasi hasil riset (tahap 1 situs publikasi).

Dua router:

* `router`         bertenant, di belakang login: buat draf dari bahan
  `/laporan` (snapshot beku), sunting, ajukan tinjau, terbitkan, ralat.
* `public_router`  tanpa login, baca-saja, HANYA artikel berstatus
  `published`, lewat fungsi SECURITY DEFINER sempit (db/rls.sql). Situs
  publik tidak pernah membaca tabel proyek.

Tidak ada kalimat buatan model di sini: isi artikel ditulis manusia, angka
berasal dari snapshot. Narasi AI menunggu kunci Anthropic dan wajib lewat
`AIEnvelope` (R2). Rencana: `docs/rencana-situs-publikasi.md`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import CurrentUser, Role, TenantSession, require_role
from app.models.governance import AuditLog
from app.models.org import User
from app.models.project import Project
from app.models.publication import Publication
from app.routers.signals import conversation_report
from app.services import publications as pub

router = APIRouter(prefix="/projects/{project_id}/publications", tags=["publications"])
public_router = APIRouter(prefix="/public/publications", tags=["public"])

MIGRATION = "db/migrations/2026-11-13-publikasi.sql"
MAX_BODY = 200_000


# ------------------------------------------------------------- skema ----


class DraftIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    start: date
    end: date
    tz: Literal["WIB", "WITA", "WIT"] = "WIB"

    @field_validator("title")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Judul minimal 3 huruf.")
        return v


class EditIn(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    summary: str | None = Field(default=None, max_length=600)
    body: str | None = Field(default=None, max_length=MAX_BODY)
    tags: list[str] | None = Field(default=None, max_length=20)
    #: Wajib bila artikelnya sudah terbit: perubahan tercatat sebagai ralat.
    correction_note: str | None = Field(default=None, max_length=1000)


class StatusIn(BaseModel):
    status: Literal["draft", "review", "published"]


class PublicationRef(BaseModel):
    id: UUID
    slug: str
    title: str
    summary: str
    tags: list[str]
    author_name: str
    status: str
    version: int
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PublicationOut(PublicationRef):
    body: str
    snapshot: dict[str, Any]
    corrections: list[dict[str, Any]]


class PublicRef(BaseModel):
    slug: str
    title: str
    summary: str
    tags: list[str]
    author_name: str
    published_at: datetime
    version: int


class PublicList(BaseModel):
    total: int
    items: list[PublicRef]


class PublicCorrection(BaseModel):
    version: int
    at: str
    note: str


class PublicArticle(PublicRef):
    body: str
    updated_at: datetime
    snapshot: dict[str, Any]
    corrections: list[PublicCorrection]


# ------------------------------------------------------------ pembantu ----


@asynccontextmanager
async def _tables() -> AsyncIterator[None]:
    """Ubah "tabel/fungsi belum ada" menjadi 409 yang menyebut migrasinya."""
    try:
        yield
    except ProgrammingError as e:
        if "does not exist" in str(e.orig):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Tabel publikasi belum ada di basis data. Jalankan {MIGRATION}.",
            ) from e
        raise


async def _project(session: AsyncSession, project_id: UUID) -> Project:
    project = (
        await session.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyek tidak ditemukan.")
    return project


async def _get(session: AsyncSession, project_id: UUID, publication_id: UUID) -> Publication:
    async with _tables():
        row = (
            await session.execute(
                select(Publication).where(
                    Publication.id == publication_id, Publication.project_id == project_id
                )
            )
        ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Publikasi tidak ditemukan.")
    return row


def _ref(p: Publication) -> PublicationRef:
    return PublicationRef(
        id=p.id,
        slug=p.slug,
        title=p.title,
        summary=p.summary,
        tags=list(p.tags),
        author_name=p.author_name,
        status=p.status,
        version=p.version,
        published_at=p.published_at,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _out(p: Publication) -> PublicationOut:
    return PublicationOut(
        **_ref(p).model_dump(),
        body=p.body,
        snapshot=p.snapshot,
        corrections=list(p.corrections),
    )


def _audit(user: CurrentUser, action: str, p: Publication, **meta: object) -> AuditLog:
    return AuditLog(
        org_id=user.org_id,
        actor_id=user.user_id,
        action=action,
        entity="publication",
        entity_id=p.id,
        metadata_={"slug": p.slug, "version": p.version, **meta},
    )


# ------------------------------------------------- endpoint bertenant ----


@router.post(
    "",
    response_model=PublicationOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def create_draft(
    project_id: UUID, body: DraftIn, session: TenantSession, user: CurrentUser
) -> PublicationOut:
    """Buat draf dengan snapshot beku bahan `/laporan` untuk periode ini."""
    if body.end < body.start:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Tanggal akhir sebelum tanggal awal."
        )
    project = await _project(session, project_id)
    report = await conversation_report(
        project_id, session, user, days=30, start=body.start, end=body.end, tz=body.tz
    )
    now = datetime.now(UTC)
    snapshot = pub.build_snapshot(
        report=report.model_dump(mode="json"),
        project_name=project.name,
        frozen_at=now.isoformat(),
        timezone=body.tz,
    )
    if pub.snapshot_has_social_text(snapshot):  # pragma: no cover - penjaga
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Snapshot masih memuat teks konten warga."
        )
    author = (
        await session.execute(select(User.full_name).where(User.id == user.user_id))
    ).scalar_one_or_none()
    row = Publication(
        org_id=user.org_id,
        project_id=project_id,
        slug=pub.new_slug(body.title),
        title=body.title,
        author_name=author or "Tim riset",
        status="draft",
        snapshot=snapshot,
        tags=[],
        corrections=[],
        created_by=user.user_id,
    )
    async with _tables():
        session.add(row)
        await session.flush()
    session.add(_audit(user, "publication_create", row, period=[str(body.start), str(body.end)]))
    await session.flush()
    await session.refresh(row)
    return _out(row)


@router.get("", response_model=list[PublicationRef])
async def list_publications(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> list[PublicationRef]:
    await _project(session, project_id)
    async with _tables():
        rows = (
            (
                await session.execute(
                    select(Publication)
                    .where(Publication.project_id == project_id)
                    .order_by(Publication.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
    return [_ref(r) for r in rows]


@router.get("/{publication_id}", response_model=PublicationOut)
async def get_publication(
    project_id: UUID, publication_id: UUID, session: TenantSession, user: CurrentUser
) -> PublicationOut:
    return _out(await _get(session, project_id, publication_id))


@router.patch(
    "/{publication_id}",
    response_model=PublicationOut,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def edit_publication(
    project_id: UUID,
    publication_id: UUID,
    body: EditIn,
    session: TenantSession,
    user: CurrentUser,
) -> PublicationOut:
    """Sunting isi. Pada artikel terbit, ini RALAT: wajib catatan, versi naik."""
    row = await _get(session, project_id, publication_id)
    changes: dict[str, Any] = {}
    if body.title is not None and body.title.strip() != row.title:
        changes["title"] = body.title.strip()
    if body.summary is not None and body.summary.strip() != row.summary:
        changes["summary"] = body.summary.strip()
    if body.body is not None and body.body != row.body:
        changes["body"] = body.body
    if body.tags is not None and pub.normalize_tags(body.tags) != list(row.tags):
        changes["tags"] = pub.normalize_tags(body.tags)
    if not changes:
        return _out(row)

    if row.status == "published":
        if user.role.value not in pub.PUBLISHER_ROLES:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Ralat artikel terbit hanya oleh Research Director."
            )
        note = (body.correction_note or "").strip()
        if not note:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Artikel sudah terbit. Isi catatan ralat untuk mengubahnya.",
            )
        # Versi lama disimpan utuh supaya tetap bisa dibaca dan diaudit.
        row.corrections = [
            *row.corrections,
            {
                "version": row.version,
                "at": datetime.now(UTC).isoformat(),
                "note": note,
                "previous": {"title": row.title, "summary": row.summary, "body": row.body},
            },
        ]
        row.version += 1

    for key, value in changes.items():
        setattr(row, key, value)
    row.updated_at = datetime.now(UTC)
    session.add(
        _audit(
            user,
            "publication_correct" if row.status == "published" else "publication_edit",
            row,
            fields=sorted(changes),
        )
    )
    await session.flush()
    await session.refresh(row)
    return _out(row)


@router.post(
    "/{publication_id}/status",
    response_model=PublicationOut,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def set_status(
    project_id: UUID,
    publication_id: UUID,
    body: StatusIn,
    session: TenantSession,
    user: CurrentUser,
) -> PublicationOut:
    """draft -> review -> published. Menerbitkan hanya oleh Research Director."""
    row = await _get(session, project_id, publication_id)
    try:
        pub.check_transition(row.status, body.status, user.role.value)  # type: ignore[arg-type]
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e

    if body.status == "published":
        if not row.summary.strip() or not row.body.strip():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Ringkasan dan isi artikel harus terisi sebelum terbit.",
            )
        row.published_at = datetime.now(UTC)
        row.published_by = user.user_id
    previous = row.status
    row.status = body.status
    row.updated_at = datetime.now(UTC)
    session.add(_audit(user, f"publication_{body.status}", row, previous=previous))
    await session.flush()
    await session.refresh(row)
    return _out(row)


@router.delete(
    "/{publication_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def delete_draft(
    project_id: UUID, publication_id: UUID, session: TenantSession, user: CurrentUser
) -> None:
    """Hapus draf. Artikel terbit tidak bisa dihapus dari sini (hanya ralat)."""
    row = await _get(session, project_id, publication_id)
    if row.status == "published":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Artikel terbit tidak bisa dihapus; gunakan ralat."
        )
    session.add(_audit(user, "publication_delete", row))
    await session.delete(row)


# ---------------------------------------------------- endpoint publik ----


@public_router.get("", response_model=PublicList)
async def public_list(
    db: Annotated[AsyncSession, Depends(get_session)],
    tag: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PublicList:
    """Daftar artikel terbit, terbaru dulu. Tanpa login."""
    async with _tables():
        rows = (
            (
                await db.execute(
                    text("SELECT * FROM public_publications(:tag, :limit, :offset)"),
                    {"tag": tag, "limit": limit, "offset": offset},
                )
            )
            .mappings()
            .all()
        )
    return PublicList(
        total=rows[0]["total"] if rows else 0,
        items=[PublicRef(**{k: r[k] for k in PublicRef.model_fields}) for r in rows],
    )


@public_router.get("/{slug}", response_model=PublicArticle)
async def public_article(
    slug: str, db: Annotated[AsyncSession, Depends(get_session)]
) -> PublicArticle:
    """Satu artikel terbit beserta snapshot angkanya. Tanpa login."""
    async with _tables():
        row = (
            (await db.execute(text("SELECT * FROM public_publication(:slug)"), {"slug": slug}))
            .mappings()
            .first()
        )
    # Draf, artikel organisasi mana pun yang belum terbit, dan slug yang tidak
    # ada sengaja tidak dibedakan.
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artikel tidak ditemukan.")
    return PublicArticle(
        **{k: row[k] for k in PublicRef.model_fields},
        body=row["body"],
        updated_at=row["updated_at"],
        snapshot=row["snapshot"],
        # Isi versi lama tidak dibuka ke publik; yang tampil catatan ralatnya.
        corrections=[
            PublicCorrection(version=c["version"], at=c["at"], note=c["note"])
            for c in row["corrections"]
        ],
    )
