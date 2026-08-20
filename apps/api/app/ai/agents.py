"""Orkestrasi multi-agent.

Setiap agen punya satu tanggung jawab dan satu kontrak keluaran. ReviewAgent
selalu berjalan terakhir dan berwenang menurunkan confidence atau menandai
keluaran sebagai NEEDS_REVIEW.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.ai.envelope import AIEnvelope, Confidence, EvidenceRef, ReviewStatus
from app.ai.provider import LLMProvider


@dataclass
class AgentContext:
    project_id: str
    period: str
    facts: dict[str, Any] = field(default_factory=dict)
    evidence: list[EvidenceRef] = field(default_factory=list)


class Agent(ABC):
    name: str
    method: str

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    @abstractmethod
    async def run(self, ctx: AgentContext) -> AIEnvelope[Any]: ...


class ReviewAgent:
    """Pemeriksa terakhir sebelum keluaran boleh menyentuh UI.

    Menurunkan keyakinan bila bukti tipis, dan menandai untuk tinjauan manusia
    bila keluaran menyentuh isu sensitif atau memuat rekomendasi tindakan.
    """

    SENSITIVE_HINTS = ("pemilu", "kandidat", "partai", "agama", "etnis", "suku")

    def review(self, env: AIEnvelope[Any]) -> AIEnvelope[Any]:
        updates: dict[str, Any] = {}

        survey_evidence = [e for e in env.evidence if e.source == "SURVEY"]
        if not survey_evidence and env.confidence is Confidence.HIGH:
            updates["confidence"] = Confidence.MEDIUM

        thin = [e for e in env.evidence if e.n is not None and e.n < 250]
        if thin and env.confidence is not Confidence.LOW:
            updates["confidence"] = Confidence.LOW
            updates["limitations"] = (
                env.limitations
                + " Sebagian bukti berasal dari agregat dengan sampel kecil."
            )

        text = " ".join(e.label for e in env.evidence).lower()
        if any(h in text for h in self.SENSITIVE_HINTS):
            updates["human_review"] = ReviewStatus.NEEDS_REVIEW

        return env.model_copy(update=updates) if updates else env


class Orchestrator:
    """Menjalankan agen secara berurutan lalu menyerahkan hasil ke ReviewAgent."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm
        self.reviewer = ReviewAgent()

    async def run(self, agents: list[Agent], ctx: AgentContext) -> list[AIEnvelope[Any]]:
        out: list[AIEnvelope[Any]] = []
        for agent in agents:
            env = await agent.run(ctx)
            out.append(self.reviewer.review(env))
        return out
