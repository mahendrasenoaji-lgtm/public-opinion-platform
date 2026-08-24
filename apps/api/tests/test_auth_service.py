"""Unit tests for auth service — password hashing and token logic.

Berjalan tanpa database; hanya menguji fungsi murni.
"""

import os

import pytest

# Auth service perlu JWT_SECRET dari environment
os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x@localhost/x")

from uuid import uuid4

from app.services.auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


def test_hash_dan_verify_cocok():
    hashed = hash_password("rahasia123")
    assert verify_password("rahasia123", hashed) is True


def test_verify_salah_password():
    hashed = hash_password("rahasia123")
    assert verify_password("salah", hashed) is False


def test_hash_berbeda_tiap_kali():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2  # argon2 pakai salt acak


def test_access_token_bisa_didecode():
    import jwt as pyjwt

    uid = uuid4()
    oid = uuid4()
    token = create_access_token(
        user_id=uid,
        org_id=oid,
        role="RESEARCHER",
        email="test@example.com",
    )
    claims = pyjwt.decode(token, "test-secret-for-unit-tests", algorithms=["HS256"])
    assert claims["sub"] == str(uid)
    assert claims["org"] == str(oid)
    assert claims["role"] == "RESEARCHER"
    assert claims["type"] == "access"


def test_refresh_token_bisa_didecode():
    uid = uuid4()
    oid = uuid4()
    token = create_refresh_token(user_id=uid, org_id=oid)
    claims = decode_refresh_token(token)
    assert claims["sub"] == str(uid)
    assert claims["type"] == "refresh"


def test_access_token_ditolak_sebagai_refresh():
    uid = uuid4()
    oid = uuid4()
    token = create_access_token(
        user_id=uid,
        org_id=oid,
        role="VIEWER",
        email="x@y.com",
    )
    with pytest.raises(ValueError, match="bukan refresh"):
        decode_refresh_token(token)
