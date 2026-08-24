"""CRUD projects — scoped to tenant via RLS (deps.TenantSession)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.deps import CurrentUser, Role, TenantSession, require_role
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(session: TenantSession, user: CurrentUser):
    """Daftar proyek dalam organisasi user (RLS otomatis)."""
    result = await session.execute(select(Project).order_by(Project.created_at.desc()))
    return [ProjectOut.model_validate(p) for p in result.scalars()]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: UUID, session: TenantSession, user: CurrentUser):
    result = await session.execute(select(Project).where(Project.id == project_id))
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyek tidak ditemukan.")
    return ProjectOut.model_validate(proj)


@router.post(
    "",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def create_project(body: ProjectCreate, session: TenantSession, user: CurrentUser):
    """Buat proyek baru. Minimal peran RESEARCHER."""
    proj = Project(
        org_id=user.org_id,
        name=body.name,
        objective=body.objective,
        created_by=user.user_id,
    )
    if body.poi_weights:
        if sum(body.poi_weights.values()) <= 0:
            raise HTTPException(422, "Total bobot POI harus > 0.")
        proj.poi_weights = body.poi_weights

    session.add(proj)
    await session.flush()
    await session.refresh(proj)
    return ProjectOut.model_validate(proj)


@router.patch(
    "/{project_id}",
    response_model=ProjectOut,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    session: TenantSession,
    user: CurrentUser,
):
    result = await session.execute(select(Project).where(Project.id == project_id))
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyek tidak ditemukan.")

    if body.name is not None:
        proj.name = body.name
    if body.objective is not None:
        proj.objective = body.objective
    if body.poi_weights is not None:
        if sum(body.poi_weights.values()) <= 0:
            raise HTTPException(422, "Total bobot POI harus > 0.")
        proj.poi_weights = body.poi_weights

    await session.flush()
    await session.refresh(proj)
    return ProjectOut.model_validate(proj)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.RESEARCH_DIRECTOR))],
)
async def delete_project(project_id: UUID, session: TenantSession):
    """Hapus proyek. Minimal peran RESEARCH_DIRECTOR."""
    result = await session.execute(select(Project).where(Project.id == project_id))
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyek tidak ditemukan.")
    await session.delete(proj)
