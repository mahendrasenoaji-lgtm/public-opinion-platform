"""Auth service — pure logic, no router concerns.

Password hashing: argon2 (as specified in CLAUDE.md §5).
Token: JWT HS256, access + refresh pair — plus a narrow collector token for
scheduled collection (see `create_collector_token`).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import get_settings

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def create_access_token(
    *,
    user_id: UUID,
    org_id: UUID,
    role: str,
    email: str,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "org": str(org_id),
        "role": role,
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(*, user_id: UUID, org_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "org": str(org_id),
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_days),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Decode a refresh token; raises on expiry or invalid."""
    settings = get_settings()
    claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if claims.get("type") != "refresh":
        raise ValueError("bukan refresh token")
    return claims


#: `type` claim of the scheduled-collection token. Deliberately NOT "access":
#: `deps.decode_token` only accepts "access", so this token can never be used
#: as a user session, whatever endpoint it is sent to.
COLLECTOR_TOKEN_TYPE = "collector"

#: Upper bound on collector token lifetime. A machine credential that lives in
#: a CI secret should be rotated; a year is long enough to cover a research
#: period without anyone having to remember a monthly renewal.
MAX_COLLECTOR_TOKEN_DAYS = 365


def create_collector_token(
    *,
    user_id: UUID,
    org_id: UUID,
    project_id: UUID,
    token_id: UUID,
    expires_at: datetime,
) -> str:
    """Token that can do exactly one thing: collect a project's registered sources.

    It carries no `role` and no `email`, so even a decoder that forgot to check
    `type` could not turn it into a user principal. `sub` is the user who
    issued it — collection runs are audited under that person, because a
    machine acting on nobody's authority is exactly what an audit log must
    not contain. `jti` lets the issuer revoke it (see routers/signals.py).
    """
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "org": str(org_id),
        "prj": str(project_id),
        "jti": str(token_id),
        "iat": datetime.now(UTC),
        "exp": expires_at,
        "type": COLLECTOR_TOKEN_TYPE,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
