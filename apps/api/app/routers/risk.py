"""Opinion Risk Score & Polarization Index — Phase 3 (docs/roadmap.md).

Polarization Index dihitung PENUH dari data nyata: sentimen per segmen
(services/risk.py mengharapkan posisi -100..100) dan size_pct sebagai bobot
massa — segments sudah ada sejak Phase 1 (routers/segments.py), jadi tidak
ada data yang direka.

Opinion Risk Score (9 komponen berbobot, lihat services/risk.py) SENGAJA
belum diekspos di sini. 5 dari 9 komponennya — issue_growth,
influencer_amplification, media_escalation, trust_decline, approval_decline —
butuh sinyal yang belum ada: konektor media sosial, jaringan influencer, dan
deret waktu tren (semua Phase 2/3, lihat docs/roadmap.md). Mengisi komponen
itu dengan angka reka-reka supaya skornya "lengkap" melanggar CLAUDE.md §3
("platform ini lebih baik mengatakan 'kami tidak tahu'"). Endpoint risk-score
menyusul begitu komponennya nyata, bukan diisi placeholder sekarang.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentUser, TenantSession
from app.models.measurement import Segment
from app.schemas.common import SignalSource
from app.services.risk import polarization

router = APIRouter(prefix="/projects/{project_id}/risk", tags=["risk"])

#: Dua titik valid secara matematis (services/risk.py), tapi hasilnya baru
#: cukup bermakna untuk dilaporkan ke pengguna dengan >=2 segmen bersentimen
#: terukur. Sama semangatnya dengan ambang n<250 di opinion.py — jangan
#: tampilkan angka dari input yang terlalu tipis.
MIN_SEGMENTS_FOR_POLARIZATION = 2


class PolarizationOut(BaseModel):
    polarization_score: int | None = None
    state: str | None = None
    pole_mass: float | None = None
    middle_mass: float | None = None
    spread: float | None = None
    method: str
    source: SignalSource = SignalSource.SURVEY
    segments_used: int
    insufficient_data: bool = False
    note: str | None = None
    limitations: str | None = None


@router.get("/polarization", response_model=PolarizationOut)
async def get_polarization(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> PolarizationOut:
    """Jarak antar-segmen pada sumbu sentimen (services/risk.py:polarization()).

    Posisi tiap segmen dipakai dari `sentiment`-nya (skala -100..100, hasil
    survei via latent class analysis) — itu bukan sumbu ideologi umum,
    melainkan sentimen segmen terhadap isu yang diukur. Batasan itu
    dilaporkan lewat field `limitations`, bukan disembunyikan.
    """
    q = select(Segment).where(Segment.project_id == project_id)
    result = await session.execute(q)
    rows = result.scalars().all()

    usable = [
        (s.name, float(s.sentiment), float(s.size_pct) / 100)
        for s in rows
        if s.sentiment is not None
    ]

    if len(usable) < MIN_SEGMENTS_FOR_POLARIZATION:
        return PolarizationOut(
            method="bimodalitas berbobot ukuran segmen",
            segments_used=len(usable),
            insufficient_data=True,
            note=(
                "Perlu minimal dua segmen dengan sentimen terukur untuk "
                f"menghitung polarisasi; proyek ini baru punya {len(usable)}."
            ),
        )

    r = polarization(usable)
    return PolarizationOut(
        polarization_score=r["polarization_score"],
        state=r["state"],
        pole_mass=r["pole_mass"],
        middle_mass=r["middle_mass"],
        spread=r["spread"],
        method=r["method"],
        segments_used=len(usable),
        limitations=(
            f"{r['limitations']} Posisi memakai skor sentimen segmen "
            "terhadap isu yang diukur, bukan sumbu ideologi umum."
        ),
    )
