"""Tes end-to-end untuk Executive Brief (/brief) dan jejak audit AI
(/governance/ai-outputs). Sama seperti test_auth_router.py /
test_dashboard_reads.py: httpx.AsyncClient asli, role pop_app, RLS aktif.

LLM_PROVIDER=echo (bawaan dev/CI, lihat .env.example) sengaja TIDAK bisa
menghasilkan JSON sesuai skema BriefPayload -- itu bukan kegagalan tes,
itu perilaku yang benar (lihat app/ai/brief.py:BriefGenerationError dan
docs/deployment-status.md). Tes generate() di sini memverifikasi endpoint
menolak dengan pesan jelas (502), bukan mencoba memverifikasi generate
sungguhan -- itu perlu ANTHROPIC_API_KEY asli, di luar cakupan CI.

Tes approve() di sini adalah regresi untuk bug dorman yang baru diperbaiki:
AIOutput.confidence/human_review sebelumnya dipetakan String biasa padahal
kolomnya confidence_band/review_status (enum Postgres native) -- baris ini
akan gagal ditulis/dibaca kalau bug itu belum benar-benar hilang.
"""

import os
import uuid

import pytest

DSN = os.getenv("TEST_DATABASE_URL_APP")

if DSN:
    os.environ["DATABASE_URL"] = DSN
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
async def client():
    if not DSN:
        pytest.skip("TEST_DATABASE_URL_APP tidak diset")

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _register_and_create_project(client) -> tuple[str, str, str]:
    slug = f"test-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Brief",
            "org_slug": slug,
            "full_name": "Penguji",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    proj = await client.post("/v1/projects", json={"name": "Proyek Tes"}, headers=headers)
    assert proj.status_code == 201, proj.text
    body = proj.json()
    return token, body["org_id"], body["id"]


async def _insert_as_org(org_id: str, sql: str, params: dict) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(DSN)
    try:
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s, s.begin():
            await s.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": org_id})
            await s.execute(text(sql), params)
    finally:
        await engine.dispose()


async def test_latest_404_saat_belum_ada_brief(client):
    token, _org_id, project_id = await _register_and_create_project(client)
    res = await client.get(
        f"/v1/projects/{project_id}/brief/latest", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 404


async def test_generate_menolak_jelas_saat_provider_belum_siap(client):
    """Tanpa LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY valid (default di
    dev/CI -- lihat app/ai/provider.py:get_provider), endpoint ini HARUS
    menolak dengan pesan jelas (503/502), bukan 500 mentah. Ini perilaku
    BENAR (lihat docstring modul), bukan endpoint yang gagal senyap. Perlu
    data agregat dulu (index dkk) supaya sampai ke tahap memanggil provider,
    bukan berhenti di 404 "belum ada data"."""
    token, org_id, project_id = await _register_and_create_project(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _insert_as_org(
        org_id,
        """INSERT INTO metric_snapshots
           (id, org_id, project_id, metric, source, method, period_start,
            period_end, value, effective_n)
           VALUES (gen_random_uuid(), :org, :proj, 'sentiment', 'SURVEY',
                   'agregasi item terverifikasi', '2026-01-01', '2026-01-08', 65, 8940)""",
        {"org": org_id, "proj": project_id},
    )

    res = await client.post(f"/v1/projects/{project_id}/brief/generate", headers=headers)
    assert res.status_code in (502, 503), res.text
    detail = res.json()["detail"].lower()
    assert "skema" in detail or "provider" in detail or "dikonfigurasi" in detail


async def test_approve_mengubah_human_review(client):
    """Regresi bug dorman: AIOutput.confidence/human_review sebelumnya
    String biasa padahal kolomnya enum Postgres native -- baris ini gagal
    ditulis/dibaca kalau bug itu kembali."""
    token, org_id, project_id = await _register_and_create_project(client)
    headers = {"Authorization": f"Bearer {token}"}

    output_id = str(uuid.uuid4())
    await _insert_as_org(
        org_id,
        """INSERT INTO ai_outputs
           (id, org_id, project_id, kind, model_version, method, prompt_hash,
            payload, evidence, confidence, limitations, human_review)
           VALUES (:id, :org, :proj, 'executive_brief', 'test-model', 'tes',
                   'hash123', CAST(:payload AS jsonb), CAST(:evidence AS jsonb),
                   'MEDIUM', 'Batasan tes.', 'PENDING')""",
        {
            "id": output_id,
            "org": org_id,
            "proj": project_id,
            "payload": (
                '{"apa_yang_terjadi": "tes", "mengapa": "tes", "siapa": "tes", '
                '"di_mana": "tes", "apa_berikutnya": "tes", "yang_perlu_diawasi": "tes"}'
            ),
            "evidence": (
                '[{"kind": "metric_snapshot", "label": "tes", "source": "SURVEY", "n": 100}]'
            ),
        },
    )

    latest = await client.get(f"/v1/projects/{project_id}/brief/latest", headers=headers)
    assert latest.status_code == 200, latest.text
    assert latest.json()["human_review"] == "PENDING"
    assert latest.json()["confidence"] == "MEDIUM"

    approved = await client.post(
        f"/v1/projects/{project_id}/brief/{output_id}/approve", headers=headers
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["human_review"] == "APPROVED"
    assert approved.json()["reviewed_by"] is not None


async def test_ai_outputs_kosong_lalu_terisi(client):
    token, org_id, project_id = await _register_and_create_project(client)
    headers = {"Authorization": f"Bearer {token}"}

    empty = await client.get(f"/v1/projects/{project_id}/governance/ai-outputs", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == []

    await _insert_as_org(
        org_id,
        """INSERT INTO ai_outputs
           (id, org_id, project_id, kind, model_version, method, prompt_hash,
            payload, evidence, confidence, limitations, human_review)
           VALUES (gen_random_uuid(), :org, :proj, 'executive_brief', 'test-model',
                   'tes', 'hash123', CAST(:payload AS jsonb), CAST(:evidence AS jsonb),
                   'HIGH', 'Batasan tes.', 'PENDING')""",
        {
            "org": org_id,
            "proj": project_id,
            "payload": '{"a": "b"}',
            "evidence": (
                '[{"kind": "metric_snapshot", "label": "tes", "source": "SURVEY", "n": 100}]'
            ),
        },
    )

    filled = await client.get(f"/v1/projects/{project_id}/governance/ai-outputs", headers=headers)
    assert filled.status_code == 200
    assert len(filled.json()) == 1
    assert filled.json()[0]["confidence"] == "HIGH"


async def test_ai_outputs_terisolasi_antar_tenant(client):
    """RLS: baris ai_outputs org lain tidak boleh terlihat."""
    token_a, org_a, project_a = await _register_and_create_project(client)
    _token_b, org_b, _project_b = await _register_and_create_project(client)

    await _insert_as_org(
        org_a,
        """INSERT INTO ai_outputs
           (id, org_id, project_id, kind, model_version, method, prompt_hash,
            payload, evidence, confidence, limitations, human_review)
           VALUES (gen_random_uuid(), :org, :proj, 'executive_brief', 'test-model',
                   'tes', 'hash123', CAST(:payload AS jsonb), CAST(:evidence AS jsonb),
                   'MEDIUM', 'Batasan tes.', 'PENDING')""",
        {
            "org": org_a,
            "proj": project_a,
            "payload": '{"a": "b"}',
            "evidence": (
                '[{"kind": "metric_snapshot", "label": "tes", "source": "SURVEY", "n": 100}]'
            ),
        },
    )
    assert org_a != org_b

    res = await client.get(
        f"/v1/projects/{project_a}/governance/ai-outputs",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 200
    assert len(res.json()) == 1
