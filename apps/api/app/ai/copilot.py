"""Agen AI Copilot — menjawab pertanyaan dari kartu fakta agregat.

Keluarannya AIEnvelope, sama seperti Executive Brief (R2). Yang membedakan:
buktinya ditentukan oleh pertanyaan pengguna lewat `app/ai/retrieval.py`,
bukan ditetapkan di kode.

Satu perilaku yang sengaja dibuat mudah: menjawab "tidak tahu". Payload punya
field `data_tidak_tersedia`, dan prompt COPILOT sudah memerintahkan model
mengatakannya. Kalau field itu true, keyakinan diturunkan ke LOW di sini
sebelum ReviewAgent bahkan melihatnya.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.ai.agents import Agent, AgentContext
from app.ai.envelope import AIEnvelope, Confidence
from app.ai.prompts import COPILOT
from app.ai.retrieval import METHOD


class CopilotAnswer(BaseModel):
    """Jawaban Copilot. Setiap klaim harus bisa ditelusuri ke kartu bukti."""

    jawaban: str = Field(min_length=1)
    #: Kunci kartu fakta yang benar-benar dipakai, diisi model sendiri.
    bukti_dipakai: list[str] = Field(default_factory=list)
    #: True bila pertanyaan menyangkut hal yang datanya tidak ada.
    data_tidak_tersedia: bool = False


class CopilotError(Exception):
    """LLM tidak menghasilkan JSON yang cocok dengan CopilotAnswer.

    Paling sering karena LLM_PROVIDER masih "echo" (gema offline) atau kunci
    API tidak valid. Router menerjemahkannya ke 502 yang bisa ditindaklanjuti.
    """


class CopilotAgent(Agent):
    name = "copilot"
    method = METHOD

    async def run(self, ctx: AgentContext) -> AIEnvelope[CopilotAnswer]:
        question = str(ctx.facts.get("pertanyaan", "")).strip()
        cards = ctx.facts.get("kartu_fakta", {})

        user_prompt = (
            f"Pertanyaan pengguna:\n{question}\n\n"
            f"Periode data: {ctx.period}\n\n"
            "Kartu fakta agregat yang tersedia (JSON). Anda HANYA boleh memakai "
            "ini; tidak ada data lain yang bisa Anda akses, dan Anda tidak "
            "pernah melihat tulisan individual siapa pun:\n"
            f"{json.dumps(cards, ensure_ascii=False, indent=2)}\n\n"
            "Isi 'bukti_dipakai' dengan kunci kartu yang benar-benar Anda pakai. "
            "Kalau kartu yang ada tidak menjawab pertanyaan, setel "
            "'data_tidak_tersedia' true dan sebutkan data apa yang tersedia."
        )

        response = await self.llm.complete(
            system=COPILOT,
            user=user_prompt,
            schema=CopilotAnswer.model_json_schema(),
        )

        try:
            payload = CopilotAnswer.model_validate(json.loads(response.text))
        except (json.JSONDecodeError, ValueError) as e:
            raise CopilotError(
                "LLM tidak menghasilkan JSON sesuai skema yang diharapkan. "
                "Cek LLM_PROVIDER=anthropic dan ANTHROPIC_API_KEY valid di server."
            ) from e

        limitations = (
            "Jawaban disusun dari data agregat proyek, bukan dari tulisan "
            "individual — Copilot tidak pernah membaca komentar siapa pun, "
            "sehingga tidak bisa mengutip apa yang orang katakan persis. "
            "Pemilihan bukti memakai pencocokan kata kunci, bukan pemahaman "
            "makna, sehingga bukti yang relevan bisa terlewat."
        )
        if ctx.facts.get("bukti_umum"):
            limitations += (
                " Pertanyaan tidak mengandung kata kunci yang cocok dengan data "
                "mana pun, jadi yang dipakai adalah ringkasan umum proyek."
            )

        confidence = Confidence.MEDIUM
        if payload.data_tidak_tersedia or ctx.facts.get("bukti_umum"):
            confidence = Confidence.LOW

        return AIEnvelope[CopilotAnswer](
            payload=payload,
            method=self.method,
            model_version=response.model_version,
            confidence=confidence,
            evidence=ctx.evidence,
            limitations=limitations,
            prompt_hash=response.prompt_hash,
        )


def as_facts(question: str, cards: dict[str, Any], *, general: bool) -> dict[str, Any]:
    """Bentuk `AgentContext.facts` untuk agen ini."""
    return {"pertanyaan": question, "kartu_fakta": cards, "bukti_umum": general}
