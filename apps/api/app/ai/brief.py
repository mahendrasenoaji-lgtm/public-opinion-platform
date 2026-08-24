"""Executive Brief — agen AI generatif pertama di proyek ini.

Fakta yang dikirim ke LLM WAJIB cuma yang benar tersedia di database (lihat
_gather_facts di app/routers/brief.py). Prototipe (design-reference/) sempat
mengklaim delta index spesifik ("turun 4,2 poin dalam 4 minggu") — itu
fabrikasi, seed tidak punya deret waktu index komposit yang mendukungnya.
Jangan tergoda menambah klaim seperti itu di sini.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.ai.agents import Agent, AgentContext
from app.ai.envelope import AIEnvelope, Confidence
from app.ai.prompts import EXECUTIVE_BRIEF


class BriefPayload(BaseModel):
    """Enam bagian sesuai prompts.py:EXECUTIVE_BRIEF dan struktur prototipe."""

    apa_yang_terjadi: str = Field(min_length=1)
    mengapa: str = Field(min_length=1)
    siapa: str = Field(min_length=1)
    di_mana: str = Field(min_length=1)
    apa_berikutnya: str = Field(min_length=1)
    yang_perlu_diawasi: str = Field(min_length=1)


class BriefGenerationError(Exception):
    """LLM tidak menghasilkan JSON yang cocok dengan BriefPayload.

    Kemungkinan besar LLM_PROVIDER masih "echo" (gema offline, bukan model
    sungguhan) atau ANTHROPIC_API_KEY tidak valid. Router menerjemahkan ini
    ke 502 dengan pesan yang bisa ditindaklanjuti, bukan trace mentah.
    """


class ExecutiveBriefAgent(Agent):
    name = "executive_brief"
    method = "RAG atas data agregat proyek"

    async def run(self, ctx: AgentContext) -> AIEnvelope[BriefPayload]:
        user_prompt = (
            f"Periode: {ctx.period}\n\nFakta yang tersedia (JSON):\n"
            f"{json.dumps(ctx.facts, ensure_ascii=False, indent=2)}"
        )
        response = await self.llm.complete(
            system=EXECUTIVE_BRIEF,
            user=user_prompt,
            schema=BriefPayload.model_json_schema(),
        )

        try:
            raw: Any = json.loads(response.text)
            payload = BriefPayload.model_validate(raw)
        except (json.JSONDecodeError, ValueError) as e:
            raise BriefGenerationError(
                "LLM tidak menghasilkan JSON sesuai skema yang diharapkan. "
                "Cek LLM_PROVIDER=anthropic dan ANTHROPIC_API_KEY valid di server."
            ) from e

        # Confidence awal MEDIUM — ReviewAgent (app/ai/agents.py) yang
        # menurunkannya lebih lanjut kalau bukti tipis/non-survei, sesuai
        # pola yang sudah ada, bukan logika baru di sini.
        return AIEnvelope[BriefPayload](
            payload=payload,
            method=self.method,
            model_version=response.model_version,
            confidence=Confidence.MEDIUM,
            evidence=ctx.evidence,
            limitations=(
                "Ringkasan disusun dari data agregat proyek pada satu titik waktu; "
                "tidak ada deret waktu index historis untuk mengukur perubahan "
                "antar-periode. Ditinjau manusia sebelum dipublikasikan resmi."
            ),
            prompt_hash=response.prompt_hash,
        )
