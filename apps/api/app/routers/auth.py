"""Auth: register, login, refresh, me.

Register membuat organisasi baru sekaligus user pertamanya (SUPER_ADMIN).
Login mengembalikan access + refresh token.
"""

from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import CurrentUser
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

    Slug organisasi harus unik. Lewat auth_register() (SECURITY DEFINER),
    bukan INSERT ORM langsung: org_id belum ada sampai baris organizations
    dibuat, jadi get_session() tanpa app.current_org bikin INSERT melanggar
    WITH CHECK RLS dan gagal total. Lihat db/rls.sql.
    """
    register_sql = text(
        "SELECT * FROM auth_register(:org_name, :org_slug, :full_name, :email, :password_hash)"
    )
    try:
        result = await db.execute(
            register_sql,
            {
                "org_name": body.org_name,
                "org_slug": body.org_slug,
                "full_name": body.full_name,
                "email": body.email,
                "password_hash": hash_password(body.password),
            },
        )
        row = result.mappings().one()
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug organisasi sudah dipakai.") from e

    return TokenPair(
        access_token=create_access_token(
            user_id=row["user_id"], org_id=row["org_id"], role=row["role"], email=body.email,
        ),
        refresh_token=create_refresh_token(user_id=row["user_id"], org_id=row["org_id"]),
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

    if row is None or row["password_hash"] is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email atau password salah.")
    if not verify_password(body.password, row["password_hash"]):
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
    """Tukar refresh token dengan access + refresh token baru.

    Lewat auth_lookup_user_by_id() (SECURITY DEFINER) dengan alasan yang
    sama seperti /auth/login: get_session() tidak men-set app.current_org,
    jadi select(User) biasa kena RLS dan selalu kosong. Lihat db/rls.sql.
    """
    try:
        claims = decode_refresh_token(body.refresh_token)
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token tidak valid.")

    user_id = UUID(claims["sub"])
    lookup_sql = text("SELECT * FROM auth_lookup_user_by_id(:user_id)")
    result = await db.execute(lookup_sql, {"user_id": str(user_id)})
    row = result.mappings().first()

    if not row or not row["is_active"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User tidak ditemukan atau tidak aktif.")

    return TokenPair(
        access_token=create_access_token(
            user_id=row["id"], org_id=row["org_id"], role=row["role"], email=row["email"],
        ),
        refresh_token=create_refresh_token(user_id=row["id"], org_id=row["org_id"]),
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
