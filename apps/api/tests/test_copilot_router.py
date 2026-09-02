"""Tes end-to-end AI Copilot.

Berbeda dari test_brief.py yang hanya memverifikasi penolakan bersih saat
provider belum siap, di sini jalur SUKSES juga diuji — lewat provider tiruan
yang mengembalikan JSON sesuai skema. Tanpa itu, tidak ada yang membuktikan
envelope tersusun benar dan barisnya benar-benar tertulis ke ai_outputs, dan
dua hal itu adalah inti R2.

Provider tiruan bukan mock LLM yang berpura-pura pintar: ia mengembalikan
jawaban tetap. Yang diuji adalah pipa di sekelilingnya, bukan mutu model.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

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


@pytest.fixture
def provider_tiruan(monkeypatch):
    """Provider yang mengembalikan CopilotAnswer valid, tanpa jaringan."""
    from app.ai.provider import LLMProvider, LLMResponse

    class StubProvider(LLMProvider):
        def __init__(self) -> None:
            self.last_user_prompt = ""

        async def complete(
            self,
            *,
            system: str,
            user: str,
            schema: dict[str, Any] | None = None,
            max_tokens: int = 2000,
        ) -> LLMResponse:
            self.last_user_prompt = user
            return LLMResponse(
                text=json.dumps(
                    {
                        "jawaban": (
                            "Berdasarkan data agregat, sentimen berkaitan dengan "
                            "kenaikan harga pangan."
                        ),
                        "bukti_dipakai": ["signal:summary"],
                        "data_tidak_tersedia": False,
                    }
                ),
                model_version="stub-1",
                prompt_hash="abc123",
                usage={"input": 10, "output": 20},
            )

        async def embed(self, texts: list[str]) -> list[list[float]]:
            raise NotImplementedError

    stub = StubProvider()
    monkeypatch.setattr("app.routers.copilot.get_provider", lambda: stub)
    return stub


async def _new_project(client) -> tuple[dict[str, str], str]:
    slug = f"cop-org-{uuid.uuid4().hex[:10]}"
    reg = await client.post(
        "/v1/auth/register",
        json={
            "org_name": "Org Tes Copilot",
            "org_slug": slug,
            "full_name": "Penguji Copilot",
            "email": f"{slug}@example.com",
            "password": "PasswordAsli123",
        },
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    proj = await client.post("/v1/projects", json={"name": "Proyek Copilot"}, headers=headers)
    return headers, proj.json()["id"]


async def _isi_sinyal(client, headers, pid, n: int = 35) -> None:
    items = [
        {
            "external_id": f"c-{uuid.uuid4().hex[:8]}-{i}",
            "text": f"harga beras di pasar naik lagi dan warga mengeluh nomor {i}",
            "published_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "engagement": i,
        }
        for i in range(n)
    ]
    r = await client.post(
        f"/v1/projects/{pid}/signals/ingest", json={"items": items}, headers=headers
    )
    assert r.status_code == 200, r.text


class TestPenolakanYangBenar:
    async def test_proyek_tanpa_data_menolak_bukan_mengarang(self, client) -> None:
        """AIEnvelope memang menolak bukti kosong; 409 menjelaskannya ke pengguna."""
        headers, pid = await _new_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/copilot/ask",
            json={"question": "Bagaimana kondisi opini publik?"},
            headers=headers,
        )
        assert r.status_code == 409, r.text
        assert "belum punya data" in r.json()["detail"]

    async def test_provider_belum_siap_ditolak_jelas(self, client) -> None:
        """LLM_PROVIDER=echo di CI tidak bisa menghasilkan JSON sesuai skema."""
        headers, pid = await _new_project(client)
        await _isi_sinyal(client, headers, pid)
        r = await client.post(
            f"/v1/projects/{pid}/copilot/ask",
            json={"question": "Bagaimana sentimen media sosial?"},
            headers=headers,
        )
        assert r.status_code in (502, 503), r.text
        detail = r.json()["detail"].lower()
        assert "skema" in detail or "dikonfigurasi" in detail

    async def test_pertanyaan_terlalu_pendek_ditolak_validasi(self, client) -> None:
        headers, pid = await _new_project(client)
        r = await client.post(
            f"/v1/projects/{pid}/copilot/ask", json={"question": "a"}, headers=headers
        )
        assert r.status_code == 422


class TestJalurSukses:
    async def test_jawaban_dibungkus_envelope_lengkap(self, client, provider_tiruan) -> None:
        headers, pid = await _new_project(client)
        await _isi_sinyal(client, headers, pid)

        r = await client.post(
            f"/v1/projects/{pid}/copilot/ask",
            json={"question": "Bagaimana sentimen percakapan media sosial?"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # R2: enam field wajib envelope harus ada dan terisi
        assert body["method"]
        assert body["model_version"] == "stub-1"
        assert body["confidence"] in {"LOW", "MEDIUM", "HIGH"}
        assert body["evidence"], "envelope tanpa bukti tidak boleh lolos"
        assert len(body["limitations"]) > 10
        assert body["human_review"] == "PENDING"

    async def test_bukti_hanya_agregat_tidak_pernah_mention_individual(
        self, client, provider_tiruan
    ) -> None:
        """Inti aturan: Copilot tidak boleh jadi pintu belakang ke tulisan orang."""
        headers, pid = await _new_project(client)
        await _isi_sinyal(client, headers, pid)
        r = await client.post(
            f"/v1/projects/{pid}/copilot/ask",
            json={"question": "Bagaimana sentimen media sosial?"},
            headers=headers,
        )
        kinds = {e["kind"] for e in r.json()["evidence"]}
        assert kinds <= {"metric_snapshot", "mention_aggregate", "narrative", "segment", "forecast"}

        # dan teks mention mentah tidak pernah dikirim ke model
        assert "warga mengeluh nomor" not in provider_tiruan.last_user_prompt

    async def test_jawaban_tercatat_di_ai_outputs(self, client, provider_tiruan) -> None:
        """R2: setiap keluaran AI harus punya jejak yang bisa ditinjau."""
        headers, pid = await _new_project(client)
        await _isi_sinyal(client, headers, pid)
        await client.post(
            f"/v1/projects/{pid}/copilot/ask",
            json={"question": "Bagaimana sentimen media sosial?"},
            headers=headers,
        )
        hist = await client.get(f"/v1/projects/{pid}/copilot/history", headers=headers)
        assert hist.status_code == 200
        assert len(hist.json()) == 1
        assert hist.json()[0]["payload"]["jawaban"]

        # jejaknya satu, dibaca halaman governance dari tabel yang sama
        gov = await client.get(f"/v1/projects/{pid}/governance/ai-outputs", headers=headers)
        if gov.status_code == 200:
            assert any(o["kind"] == "copilot_answer" for o in gov.json())

    async def test_kata_yang_cocok_dilaporkan_untuk_audit(
        self, client, provider_tiruan
    ) -> None:
        headers, pid = await _new_project(client)
        await _isi_sinyal(client, headers, pid)
        r = await client.post(
            f"/v1/projects/{pid}/copilot/ask",
            json={"question": "Bagaimana sentimen percakapan sosial?"},
            headers=headers,
        )
        body = r.json()
        assert body["cards_considered"] >= 1
        assert body["cards_used"] >= 1

    async def test_pertanyaan_umum_menurunkan_keyakinan(
        self, client, provider_tiruan
    ) -> None:
        """Bukti yang dipilih karena tak ada yang cocok tidak boleh berkeyakinan tinggi."""
        headers, pid = await _new_project(client)
        await _isi_sinyal(client, headers, pid)
        r = await client.post(
            f"/v1/projects/{pid}/copilot/ask",
            json={"question": "Ceritakan keadaannya sekarang bagaimana"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["confidence"] == "LOW"

    async def test_batasan_menyebut_copilot_tidak_membaca_tulisan_individual(
        self, client, provider_tiruan
    ) -> None:
        headers, pid = await _new_project(client)
        await _isi_sinyal(client, headers, pid)
        r = await client.post(
            f"/v1/projects/{pid}/copilot/ask",
            json={"question": "Bagaimana sentimen media sosial?"},
            headers=headers,
        )
        assert "individual" in r.json()["limitations"]


class TestIsolasiTenant:
    async def test_riwayat_org_lain_tidak_terlihat(self, client, provider_tiruan) -> None:
        headers_a, pid_a = await _new_project(client)
        headers_b, _ = await _new_project(client)
        await _isi_sinyal(client, headers_a, pid_a)
        await client.post(
            f"/v1/projects/{pid_a}/copilot/ask",
            json={"question": "Bagaimana sentimen media sosial?"},
            headers=headers_a,
        )
        r = await client.get(f"/v1/projects/{pid_a}/copilot/history", headers=headers_b)
        assert r.json() == []

    async def test_org_lain_tidak_bisa_bertanya_atas_data_proyek_asing(
        self, client, provider_tiruan
    ) -> None:
        headers_a, pid_a = await _new_project(client)
        headers_b, _ = await _new_project(client)
        await _isi_sinyal(client, headers_a, pid_a)
        r = await client.post(
            f"/v1/projects/{pid_a}/copilot/ask",
            json={"question": "Bagaimana sentimen media sosial?"},
            headers=headers_b,
        )
        # RLS mengosongkan kartu fakta -> tidak ada bukti -> menolak, bukan menjawab
        assert r.status_code == 409, r.text
