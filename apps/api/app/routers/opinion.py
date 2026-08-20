"""Public Opinion Index, divergensi sinyal, dan snapshot command center.

Repository layer sekarang membaca dari metric_snapshots dan menghubungkannya
ke services/poi.py dan services/divergence.py. Tidak ada filter org_id manual —
RLS via TenantSession yang menegakkannya.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentUser, Role, TenantSession, require_capability
from app.models.governance import AuditLog
from app.models.measurement import MetricSnapshot
from app.models.project import Project
from app.schemas.common import Metric, SignalSource
from app.services import divergence, poi

router = APIRouter(prefix="/projects/{project_id}/opinion", tags=["opinion"])


class WeightUpdate(BaseModel):
    weights: dict[str, float] = Field(description="Bobot mentah; dinormalisasi di server")


class IndexResponse(BaseModel):
    index: Metric
    dimensions: list[Metric]
    source_mix: dict[str, float]
    generalisable_share: float
    limitations: list[str]


@router.get("/index", response_model=IndexResponse)
async def get_index(project_id: UUID, session: TenantSession, user: CurrentUser) -> IndexResponse:
    """Hitung POI dari snapshot dimensi terbaru proyek."""
    dims = await _load_dimensions(session, project_id)
    if not dims:
        raise HTTPException(404, "Belum ada data dimensi untuk proyek ini.")

    result = poi.compute_index(dims)
    publish = poi.publishable(result)

    return IndexResponse(
        index=Metric(
            key="poi",
            label="Public Opinion Index",
            value=result.value if publish else None,
            source=SignalSource.SURVEY,
            method=result.method,
            ci_low=result.ci_low,
            ci_high=result.ci_high,
            effective_n=result.effective_n,
            insufficient_data=not publish,
            note=None if publish else "Sampel efektif di bawah ambang publikasi.",
        ),
        dimensions=[
            Metric(
                key=d.key,
                label=d.label,
                value=d.score,
                source=SignalSource(d.source.value),
                method="agregasi item terverifikasi",
                effective_n=d.effective_n,
            )
            for d in dims
        ],
        source_mix=result.source_mix,
        generalisable_share=round(result.generalisable_share, 3),
        limitations=result.limitations,
    )


@router.put("/weights", dependencies=[Depends(require_capability("poi_weights:write"))])
async def set_weights(
    project_id: UUID,
    body: WeightUpdate,
    session: TenantSession,
    user: CurrentUser,
) -> dict:
    """Ubah bobot dimensi POI proyek.

    Perubahan bobot mengubah seluruh deret historis indeks. Simpan versinya dan
    catat di audit log supaya laporan lama tetap bisa direproduksi.
    """
    if sum(body.weights.values()) <= 0:
        raise HTTPException(422, "Total bobot harus lebih besar dari nol.")

    result = await session.execute(select(Project).where(Project.id == project_id))
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(404, "Proyek tidak ditemukan.")

    old_weights = dict(proj.poi_weights)
    proj.poi_weights = body.weights

    # Audit log entry
    log = AuditLog(
        org_id=user.org_id,
        actor_id=user.user_id,
        action="poi_weights:update",
        entity="projects",
        entity_id=project_id,
        metadata_={"old": old_weights, "new": body.weights},
    )
    session.add(log)
    await session.flush()

    return {"status": "updated", "old_weights": old_weights, "new_weights": body.weights}


@router.get("/divergence")
async def get_divergence(project_id: UUID, session: TenantSession, user: CurrentUser) -> dict:
    """Bandingkan survei, sosial, dan media pada pertanyaan yang setara."""
    readings = await _load_signal_readings(session, project_id)
    if len(readings) < 2:
        raise HTTPException(404, "Perlu minimal dua sumber sinyal untuk perbandingan.")

    result = divergence.analyse(readings)
    return {
        "gap": result.gap,
        "is_notable": result.is_notable,
        "readings": [
            {
                "source": r.source.value,
                "value": r.value,
                "n": r.n,
                "method": r.method,
                "known_bias": r.known_bias,
            }
            for r in result.readings
        ],
        "explanations": result.explanations,
        "limitations": result.limitations,
    }


# --- repository (Phase 1 — implemented) --------------------------------------

#: Dimensi POI yang dikenali. Harus cocok dengan poi_weights default di schema.sql.
_POI_DIMS = {
    "sentiment": "Sentimen",
    "approval": "Persetujuan",
    "trust": "Kepercayaan",
    "satisfaction": "Kepuasan",
    "issue_perception": "Persepsi Isu",
    "confidence": "Keyakinan",
}

#: Mapping source string ke enum dan bias deskripsi.
_SOURCE_META = {
    "SURVEY": ("SURVEY", "data probabilistik; bisa digeneralisasi ke populasi"),
    "SOCIAL": ("SOCIAL", "data self-selected; tidak representatif populasi"),
    "MEDIA": ("MEDIA", "agenda redaksi; bukan opini pembaca"),
    "DIGITAL": ("DIGITAL", "sinyal digital agregat"),
}


async def _load_dimensions(session: AsyncSession, project_id: UUID) -> list[poi.Dimension]:
    """Baca metric_snapshots terbaru per dimensi POI.

    Mengambil satu snapshot terakhir per (metric, source) di mana metric
    termasuk dalam _POI_DIMS, province_code IS NULL (nasional), dan segment
    IS NULL (seluruh sampel).
    """
    # Ambil bobot dari proyek
    proj_result = await session.execute(select(Project).where(Project.id == project_id))
    proj = proj_result.scalar_one_or_none()
    if not proj:
        return []

    weights = proj.poi_weights or {}
    dims: list[poi.Dimension] = []

    for dim_key, dim_label in _POI_DIMS.items():
        weight = weights.get(dim_key, 0)
        if weight <= 0:
            continue

        # Snapshot terbaru untuk dimensi ini, nasional, seluruh sampel
        snap_q = (
            select(MetricSnapshot)
            .where(
                MetricSnapshot.project_id == project_id,
                MetricSnapshot.metric == dim_key,
                MetricSnapshot.province_code.is_(None),
                MetricSnapshot.segment.is_(None),
            )
            .order_by(MetricSnapshot.period_end.desc())
            .limit(1)
        )
        snap_result = await session.execute(snap_q)
        snap = snap_result.scalar_one_or_none()
        if not snap:
            continue

        dims.append(
            poi.Dimension(
                key=dim_key,
                label=dim_label,
                score=float(snap.value),
                weight=weight,
                source=poi.SignalSource(snap.source),
                effective_n=snap.effective_n,
            )
        )

    return dims


async def _load_signal_readings(
    session: AsyncSession, project_id: UUID,
) -> list[divergence.SignalReading]:
    """Baca satu nilai POI terbaru per SignalSource."""
    readings: list[divergence.SignalReading] = []

    for source_str, (_, bias) in _SOURCE_META.items():
        snap_q = (
            select(MetricSnapshot)
            .where(
                MetricSnapshot.project_id == project_id,
                MetricSnapshot.metric == "poi",
                MetricSnapshot.source == source_str,
                MetricSnapshot.province_code.is_(None),
                MetricSnapshot.segment.is_(None),
            )
            .order_by(MetricSnapshot.period_end.desc())
            .limit(1)
        )
        result = await session.execute(snap_q)
        snap = result.scalar_one_or_none()
        if snap:
            readings.append(
                divergence.SignalReading(
                    source=poi.SignalSource(snap.source),
                    value=float(snap.value),
                    n=snap.effective_n or 0,
                    method=snap.method,
                    known_bias=bias,
                )
            )

    return readings
