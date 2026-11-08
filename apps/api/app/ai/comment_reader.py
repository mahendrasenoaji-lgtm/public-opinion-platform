"""Pembaca komentar berbasis LLM: nada, sasaran, dan alat bahasa per komentar.

Penilai leksikon (`services/sentiment.py`) abstain pada komentar yang tidak
memuat kata kamus, termasuk kritik lewat kiasan, sindiran, atau pertanyaan
retoris. Pembaca ini membaca kalimat utuh dan, dengan daftar aktor dari
`services/actors.py`, juga menyebut KEPADA SIAPA nada itu diarahkan.

Ia BUKAN pengganti penilai leksikon di deret sentimen. Keluarannya:
- dibungkus `AIEnvelope` (R2), dengan confidence paling tinggi MEDIUM karena
  buktinya data sosial yang self-selected;
- wajib menyertakan `bukti` yang benar-benar ada di teks komentar; bacaan yang
  buktinya tidak ditemukan di teks dibuang, bukan dipercaya;
- harus diukur dulu terhadap sampel berlabel (lihat
  proyek/bbm-bali-youtube/skrip/pilot_pembaca_ai.py) sebelum dipakai.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.ai.envelope import AIEnvelope, Confidence, EvidenceRef
from app.ai.prompts import COMMENT_READING
from app.ai.provider import LLMProvider
from app.services import actors

Tone = Literal["negatif", "positif", "netral", "tidak jelas"]
Device = Literal[
    "kata_penilai",
    "tuntutan",
    "kiasan",
    "sindiran",
    "pertanyaan_retoris",
    "tuduhan",
    "bahasa_daerah",
    "lainnya",
]

#: Komentar per panggilan. Cukup kecil supaya jawaban JSON tidak terpotong.
BATCH = 25

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "bacaan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "nada": {"enum": ["negatif", "positif", "netral", "tidak jelas"]},
                    "sasaran": {"type": "array", "items": {"type": "string"}},
                    "alat": {"type": "array", "items": {"type": "string"}},
                    "bukti": {"type": "string"},
                    "alasan": {"type": "string"},
                },
                "required": ["id", "nada", "sasaran", "alat", "bukti", "alasan"],
            },
        }
    },
    "required": ["bacaan"],
}


class CommentReading(BaseModel):
    id: str
    nada: Tone
    sasaran: list[str] = Field(default_factory=list)
    alat: list[Device] = Field(default_factory=list)
    bukti: str
    alasan: str = Field(max_length=300)


def actor_context() -> str:
    """Daftar aktor dan jabatannya, untuk prompt."""
    lines = [f"- {a.key}: {a.name} — {a.role} ({a.level})" for a in actors.ACTORS]
    return "Daftar aktor (jabatan per Oktober 2026):\n" + "\n".join(lines)


def build_user_message(comments: Sequence[tuple[str, str]], topic: str) -> str:
    """Pesan pengguna: konteks isu, daftar aktor, lalu komentar bernomor."""
    body = "\n".join(
        json.dumps({"id": cid, "teks": text}, ensure_ascii=False) for cid, text in comments
    )
    return f"Isu: {topic}\n\n{actor_context()}\n\nKomentar (satu JSON per baris):\n{body}"


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def parse_readings(
    raw: str, comments: Sequence[tuple[str, str]]
) -> tuple[list[CommentReading], list[str]]:
    """Bacaan yang valid, plus id yang ditolak.

    Ditolak: JSON rusak, id asing, atau bukti yang tidak ada di teks komentar.
    """
    texts = {cid: text for cid, text in comments}
    try:
        items = json.loads(raw.strip().removeprefix("```json").removesuffix("```")).get(
            "bacaan", []
        )
    except (json.JSONDecodeError, AttributeError):
        return [], list(texts)
    ok: list[CommentReading] = []
    seen: set[str] = set()
    for item in items:
        try:
            r = CommentReading.model_validate(item)
        except ValidationError:
            continue
        if r.id not in texts or r.id in seen:
            continue
        if r.bukti and _norm(r.bukti) not in _norm(texts[r.id]):
            continue  # bukti karangan: bacaan dibuang
        seen.add(r.id)
        ok.append(r)
    return ok, [cid for cid in texts if cid not in seen]


async def read_comments(
    llm: LLMProvider, comments: Sequence[tuple[str, str]], *, topic: str
) -> AIEnvelope[list[CommentReading]]:
    """Baca komentar per kelompok BATCH dan bungkus hasilnya dalam AIEnvelope."""
    readings: list[CommentReading] = []
    rejected: list[str] = []
    model = "?"
    for i in range(0, len(comments), BATCH):
        chunk = comments[i : i + BATCH]
        resp = await llm.complete(
            system=COMMENT_READING,
            user=build_user_message(chunk, topic),
            schema=SCHEMA,
            max_tokens=6000,
        )
        model = resp.model_version
        got, bad = parse_readings(resp.text, chunk)
        readings.extend(got)
        rejected.extend(bad)
    n = len(comments)
    return AIEnvelope[list[CommentReading]](
        payload=readings,
        method=(
            "pembacaan LLM per komentar dengan daftar aktor; "
            "bukti wajib kutipan persis dari teks"
        ),
        model_version=model,
        confidence=Confidence.LOW if n < 100 else Confidence.MEDIUM,
        evidence=[
            EvidenceRef(
                kind="mention_aggregate",
                label=f"{n} komentar dibaca untuk isu: {topic}",
                n=n if n >= 5 else None,
                source="SOCIAL",
            )
        ],
        limitations=(
            "Nada teks, bukan sikap publik; komentar self-selected. "
            f"{len(rejected)} dari {n} komentar tidak punya bacaan valid "
            "(JSON rusak atau bukti tidak ada di teks). "
            "Belum diukur terhadap label manusia kecuali disebut lain."
        ),
    )
