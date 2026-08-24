"""Isolasi tenant ditegakkan Postgres RLS, bukan filter di aplikasi.

Tes ini butuh database nyata (docker compose up db). Ia sengaja memakai peran
pop_app, bukan superuser: superuser mengabaikan RLS dan akan membuat tes ini
lulus secara palsu.
"""

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.asyncio

DSN = os.getenv("TEST_DATABASE_URL_APP")


@pytest.fixture
async def sessionmaker_app():
    if not DSN:
        pytest.skip("TEST_DATABASE_URL_APP tidak diset")
    engine = create_async_engine(DSN)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _seed_two_orgs(sm) -> tuple[uuid.UUID, uuid.UUID]:
    a, b = uuid.uuid4(), uuid.uuid4()
    async with sm() as s, s.begin():
        await s.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(a)})
        await s.execute(
            text("INSERT INTO organizations (id, name, slug) VALUES (:i,'A',:s)"),
            {"i": str(a), "s": f"a-{a.hex[:6]}"},
        )
        await s.execute(
            text(
                "INSERT INTO projects (id, org_id, name) VALUES (gen_random_uuid(),:o,'Proyek A')"
            ),
            {"o": str(a)},
        )
    async with sm() as s, s.begin():
        await s.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(b)})
        await s.execute(
            text("INSERT INTO organizations (id, name, slug) VALUES (:i,'B',:s)"),
            {"i": str(b), "s": f"b-{b.hex[:6]}"},
        )
        await s.execute(
            text(
                "INSERT INTO projects (id, org_id, name) VALUES (gen_random_uuid(),:o,'Proyek B')"
            ),
            {"o": str(b)},
        )
    return a, b


async def test_tenant_hanya_melihat_proyeknya_sendiri(sessionmaker_app):
    a, b = await _seed_two_orgs(sessionmaker_app)
    async with sessionmaker_app() as s, s.begin():
        await s.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(a)})
        rows = (await s.execute(text("SELECT name FROM projects"))).scalars().all()
    assert rows == ["Proyek A"]


async def test_tanpa_konteks_org_tidak_ada_baris_yang_terbaca(sessionmaker_app):
    await _seed_two_orgs(sessionmaker_app)
    async with sessionmaker_app() as s, s.begin():
        rows = (await s.execute(text("SELECT id FROM projects"))).scalars().all()
    assert rows == []


async def test_insert_lintas_tenant_ditolak(sessionmaker_app):
    a, b = await _seed_two_orgs(sessionmaker_app)
    # Exception generik disengaja (bukan noqa demi kepatuhan linter semata):
    # driver Postgres yang sebenarnya melempar bisa beda kelas tergantung
    # versi asyncpg/SQLAlchemy (IntegrityError vs DBAPIError vs
    # InsufficientPrivilege) — yang ditegakkan tes ini adalah "pelanggaran
    # RLS ditolak", bukan tipe exception spesifiknya.
    with pytest.raises(Exception):  # noqa: B017
        async with sessionmaker_app() as s, s.begin():
            await s.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(a)})
            await s.execute(
                text("INSERT INTO projects (org_id, name) VALUES (:o,'Selundupan')"),
                {"o": str(b)},
            )


async def test_konteks_tidak_bocor_antar_transaksi(sessionmaker_app):
    a, _ = await _seed_two_orgs(sessionmaker_app)
    sm = sessionmaker_app
    async with sm() as s, s.begin():
        await s.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(a)})
        assert (await s.execute(text("SELECT count(*) FROM projects"))).scalar() == 1
    # transaksi baru pada koneksi yang mungkin sama, tanpa SET LOCAL
    async with sm() as s, s.begin():
        assert (await s.execute(text("SELECT count(*) FROM projects"))).scalar() == 0
