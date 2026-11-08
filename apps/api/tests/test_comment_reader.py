"""Tes pembaca komentar LLM dengan provider palsu — tanpa jaringan."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.ai.comment_reader import build_user_message, parse_readings, read_comments
from app.ai.envelope import Confidence
from app.ai.provider import LLMProvider, LLMResponse

COMMENTS = [
    (
        "1",
        "Bahlil tu lo. ganti aja kok. gk bisa mengatasi bbm. "
        "Kalau ngomong mulutnya kok kaya ular berbisa",
    ),
    ("2", "antrean kayak ular dari jam 5 pagi"),
]


def _answer(bukti1: str = "mulutnya kok kaya ular berbisa") -> str:
    return json.dumps(
        {
            "bacaan": [
                {
                    "id": "1",
                    "nada": "negatif",
                    "sasaran": ["bahlil"],
                    "alat": ["tuntutan", "kiasan"],
                    "bukti": bukti1,
                    "alasan": "menuntut menteri diganti",
                },
                {
                    "id": "2",
                    "nada": "netral",
                    "sasaran": [],
                    "alat": ["lainnya"],
                    "bukti": "antrean kayak ular",
                    "alasan": "gambaran antrean",
                },
            ]
        }
    )


class FakeLLM(LLMProvider):
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[str] = []

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        self.calls.append(user)
        return LLMResponse(text=self.text, model_version="fake-1", prompt_hash="x", usage={})

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return []


def test_pesan_memuat_daftar_aktor_dan_komentar() -> None:
    msg = build_user_message(COMMENTS, "Kelangkaan BBM Bali")
    assert "Menteri ESDM" in msg and "Gubernur Bali" in msg
    assert '"id": "1"' in msg


def test_bacaan_valid_diterima() -> None:
    ok, bad = parse_readings(_answer(), COMMENTS)
    assert [r.id for r in ok] == ["1", "2"] and bad == []
    assert ok[0].nada == "negatif" and "kiasan" in ok[0].alat


def test_bukti_karangan_ditolak() -> None:
    ok, bad = parse_readings(_answer(bukti1="menteri korup dan bodoh"), COMMENTS)
    assert [r.id for r in ok] == ["2"] and bad == ["1"]


def test_json_rusak_semua_ditolak() -> None:
    ok, bad = parse_readings("bukan json", COMMENTS)
    assert ok == [] and bad == ["1", "2"]


def test_dibungkus_envelope_dengan_batas() -> None:
    env = asyncio.run(read_comments(FakeLLM(_answer()), COMMENTS, topic="BBM Bali"))
    assert len(env.payload) == 2
    assert env.confidence is Confidence.LOW
    assert env.evidence[0].source == "SOCIAL"
    assert "self-selected" in env.limitations
