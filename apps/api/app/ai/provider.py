"""Abstraksi provider LLM.

Aplikasi tidak pernah memanggil SDK vendor secara langsung. Semua lewat
`LLMProvider` supaya deployment on-premise pemerintah bisa menukar ke model
open-source tanpa menyentuh kode domain.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.config import get_settings


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    model_version: str
    prompt_hash: str
    usage: dict[str, int]


def prompt_hash(system: str, user: str) -> str:
    return hashlib.sha256(f"{system}\x00{user}".encode()).hexdigest()[:16]


class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2000,
    ) -> LLMResponse: ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        if schema:
            system = (
                f"{system}\n\nBalas HANYA dengan JSON valid sesuai skema berikut, "
                f"tanpa preamble dan tanpa pagar kode:\n{json.dumps(schema)}"
            )
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        return LLMResponse(
            text=text,
            model_version=msg.model,
            prompt_hash=prompt_hash(system, user),
            usage={"input": msg.usage.input_tokens, "output": msg.usage.output_tokens},
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("gunakan provider embedding terpisah")


class EchoProvider(LLMProvider):
    """Provider untuk tes dan mode demo offline. Deterministik, tanpa jaringan."""

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        return LLMResponse(
            text=json.dumps({"echo": user[:200]}),
            model_version="echo-1",
            prompt_hash=prompt_hash(system, user),
            usage={"input": 0, "output": 0},
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t) % 7)] * 1024 for t in texts]


def get_provider() -> LLMProvider:
    s = get_settings()
    if s.llm_provider == "anthropic" and s.anthropic_api_key:
        return AnthropicProvider(s.anthropic_api_key, s.llm_model)
    if s.llm_provider == "echo":
        return EchoProvider()
    raise RuntimeError(
        f"provider '{s.llm_provider}' belum dikonfigurasi. Setel LLM_PROVIDER dan "
        "kunci API yang sesuai."
    )
