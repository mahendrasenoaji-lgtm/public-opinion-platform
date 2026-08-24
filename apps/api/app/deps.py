"""Dependency FastAPI: identitas, konteks tenant, dan otorisasi peran.

Isolasi tenant dijalankan dengan menyetel `app.current_org` di dalam transaksi
Postgres. Kebijakan RLS (db/rls.sql) yang menegakkan batasnya. Aplikasi tidak
menambahkan filter org_id manual — kalau RLS gagal, kita ingin query gagal,
bukan diam-diam mengembalikan data tenant lain.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import SessionLocal

settings = get_settings()
bearer = HTTPBearer(auto_error=True)


class Role(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    RESEARCH_DIRECTOR = "RESEARCH_DIRECTOR"
    RESEARCHER = "RESEARCHER"
    DATA_ANALYST = "DATA_ANALYST"
    COMM_STRATEGIST = "COMM_STRATEGIST"
    EXECUTIVE = "EXECUTIVE"
    CLIENT = "CLIENT"
    VIEWER = "VIEWER"


#: Urutan kewenangan untuk pemeriksaan "minimal peran".
RANK = {
    Role.VIEWER: 0,
    Role.CLIENT: 1,
    Role.EXECUTIVE: 2,
    Role.COMM_STRATEGIST: 3,
    Role.DATA_ANALYST: 4,
    Role.RESEARCHER: 5,
    Role.RESEARCH_DIRECTOR: 6,
    Role.SUPER_ADMIN: 7,
}

#: Kemampuan yang tidak mengikuti hierarki dan harus disebut eksplisit.
CAPABILITIES: dict[str, set[Role]] = {
    # Membaca PII responden. Sengaja sempit.
    "respondent_pii:read": {Role.SUPER_ADMIN, Role.RESEARCH_DIRECTOR},
    # Menyetujui keluaran AI agar boleh tampil di laporan resmi.
    "ai_output:approve": {Role.SUPER_ADMIN, Role.RESEARCH_DIRECTOR, Role.RESEARCHER},
    # Mengubah bobot POI sebuah proyek.
    "poi_weights:write": {Role.SUPER_ADMIN, Role.RESEARCH_DIRECTOR, Role.RESEARCHER},
    # Mengekspor data mentah.
    "raw_data:export": {Role.SUPER_ADMIN, Role.RESEARCH_DIRECTOR, Role.DATA_ANALYST},
}


class Principal(BaseModel):
    user_id: UUID
    org_id: UUID
    role: Role
    email: str


def decode_token(token: str) -> Principal:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesi berakhir. Masuk kembali.") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token tidak valid.") from e

    try:
        return Principal(
            user_id=UUID(claims["sub"]),
            org_id=UUID(claims["org"]),
            role=Role(claims["role"]),
            email=claims["email"],
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token tidak lengkap.") from e


async def current_principal(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
) -> Principal:
    return decode_token(creds.credentials)


async def tenant_session(
    principal: Annotated[Principal, Depends(current_principal)],
) -> AsyncIterator[AsyncSession]:
    """Session yang sudah terikat pada satu organisasi.

    `SET LOCAL` berlaku sampai akhir transaksi, sehingga koneksi yang kembali ke
    pool tidak membawa konteks tenant sebelumnya.
    """
    async with SessionLocal() as session, session.begin():
        # SET/SET LOCAL tidak menerima bind parameter di Postgres — itu
        # batasan protokolnya, bukan SQLAlchemy atau asyncpg. set_config()
        # adalah fungsi biasa, jadi bisa dipanggil dengan parameter seperti
        # query lain; is_local=true membuatnya berlaku sampai commit,
        # setara SET LOCAL. Lihat db/rls.sql: current_org() membaca
        # setting yang sama lewat current_setting().
        await session.execute(
            text("SELECT set_config('app.current_org', :org, true)"),
            {"org": str(principal.org_id)},
        )
        yield session


def require_role(minimum: Role):
    """Guard berbasis hierarki peran."""

    async def _guard(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
        if RANK[principal.role] < RANK[minimum]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Tindakan ini memerlukan peran {minimum.value} atau lebih tinggi.",
            )
        return principal

    return _guard


def require_capability(capability: str):
    """Guard berbasis kemampuan eksplisit — dipakai untuk PII dan persetujuan AI."""

    allowed = CAPABILITIES.get(capability)
    if allowed is None:
        raise KeyError(f"kemampuan tidak dikenal: {capability}")

    async def _guard(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Peran {principal.role.value} tidak memiliki akses untuk {capability}.",
            )
        return principal

    return _guard


TenantSession = Annotated[AsyncSession, Depends(tenant_session)]
CurrentUser = Annotated[Principal, Depends(current_principal)]
