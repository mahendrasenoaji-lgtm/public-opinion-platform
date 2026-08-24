"""Auth: register, login, refresh, me.

Register membuat organisasi baru sekaligus user pertamanya (SUPER_ADMIN).
Login mengembalikan access + refresh token.
"""

from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import CurrentUser
from app.models.org import Organization, User, UserRole
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.services.auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_session)):
    """Buat organisasi baru + user pertama (SUPER_ADMIN).

    Slug organisasi harus unik.
    """
    existing = await db.execute(select(Organization).where(Organization.slug == body.org_slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug organisasi sudah dipakai.")

    org = Organization(name=body.org_name, slug=body.org_slug)
    db.add(org)
    await db.flush()

    user = User(
        org_id=org.id,
        email=body.email,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        role=UserRole.SUPER_ADMIN.value,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenPair(
        access_token=create_access_token(
            user_id=user.id, org_id=org.id, role=user.role, email=user.email,
        ),
        refresh_token=create_refresh_token(user_id=user.id, org_id=org.id),
    )


@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_session)):
    """Login dengan email + password. Mengembalikan access + refresh token.

    Lookup lewat auth_lookup_user() (SECURITY DEFINER), bukan select(User)
    langsung: org_id user belum diketahui di titik ini (ayam-telur — org_id
    baru ketahuan SETELAH user ditemukan), dan get_session() tidak men-set
    app.current_org, jadi query ORM biasa kena FORCE ROW LEVEL SECURITY dan
    selalu kosong. Lihat db/rls.sql untuk penjelasan lengkap & kenapa bukan
    melonggarkan policy tenant-nya.
    """
    result = await db.execute(text("SELECT * FROM auth_lookup_user(:email)"), {"email": body.email})
    row = result.mappings().first()

    password_hash = row["password_hash"] if row else None
    if not password_hash or not verify_password(body.password, password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email atau password salah.")

    if not row["is_active"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Akun dinonaktifkan.")

    # last_login_at sengaja tidak diupdate di sini: UPDATE lewat sesi tanpa
    # app.current_org akan kena RLS yang sama (0 baris terpengaruh, senyap).
    # Bukan bug baru — field ini memang belum pernah tertulis. Perbaiki
    # bersamaan kalau auth_lookup_user() suatu saat diperluas.

    return TokenPair(
        access_token=create_access_token(
            user_id=row["id"], org_id=row["org_id"], role=row["role"], email=row["email"],
        ),
        refresh_token=create_refresh_token(user_id=row["id"], org_id=row["org_id"]),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_session)):
    """Tukar refresh token dengan access + refresh token baru."""
    try:
        claims = decode_refresh_token(body.refresh_token)
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token tidak valid.")

    user_id = UUID(claims["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User tidak ditemukan atau tidak aktif.")

    return TokenPair(
        access_token=create_access_token(
            user_id=user.id, org_id=user.org_id, role=user.role, email=user.email,
        ),
        refresh_token=create_refresh_token(user_id=user.id, org_id=user.org_id),
    )


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    """Profil user dari token."""
    return UserOut(
        id=user.user_id,
        org_id=user.org_id,
        email=user.email,
        full_name="",  # full_name tidak ada di token, baca dari DB kalau perlu
        role=user.role.value,
        is_active=True,
    )
