"""Report generator — ekspor PDF (Phase 4, item pertama, docs/roadmap.md).

Bukan `AIEnvelope`: laporan ini murni agregasi statistik dari layer yang
sudah ada (Segments Phase 1, Polarization Index Phase 3), sama seperti
`routers/segments.py` dan `routers/risk.py` sendiri tidak memakai envelope.

**Cakupan v1 sengaja terbatas** ke dua bagian yang datanya paling stabil:
Segments dan Polarization Index. Signals summary, Risk Score 9-komponen,
dan Forecast SENGAJA belum diikutkan — nambah tiga bagian sekaligus di
laporan pertama menaikkan risiko field tersembunyi salah tanpa
verifikasi yang setara untuk masing-masing (CLAUDE.md §8). Menyusul di
sesi berikutnya begitu ada permintaan konkret soal formatnya.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.deps import CurrentUser, TenantSession
from app.models.measurement import Segment
from app.models.project import Project
from app.services.reports import ReportMetric, ReportSection, build_summary_pdf
from app.services.risk import polarization

router = APIRouter(prefix="/projects/{project_id}/reports", tags=["reports"])

#: Sinkron dengan MIN_SEGMENTS_FOR_POLARIZATION di routers/risk.py — dua
#: titik valid secara matematis tapi belum cukup bermakna untuk dilaporkan.
MIN_SEGMENTS_FOR_POLARIZATION = 2


@router.get("/summary", response_class=Response)
async def get_summary_report(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> Response:
    """Laporan ringkasan proyek (Segments + Polarization Index) sebagai PDF."""
    project = (
        await session.execute(select(Project).where(Project.id == project_id))
    ).scalar_one()

    segments = (
        (await session.execute(select(Segment).where(Segment.project_id == project_id)))
        .scalars()
        .all()
    )

    segment_section = ReportSection(
        title="Public Segments",
        metrics=[
            ReportMetric(
                label=s.name,
                source="SURVEY",
                method=s.method,
                value=(
                    f"{s.size_pct}% populasi"
                    + (f" · sentimen {s.sentiment}" if s.sentiment is not None else "")
                    + (f" · trust {s.trust}" if s.trust is not None else "")
                ),
            )
            for s in segments
        ],
    )
    if not segments:
        segment_section.limitations.append(
            "Belum ada segmen tersurvei untuk proyek ini."
        )

    positions = [
        (s.name, float(s.sentiment), float(s.size_pct)) for s in segments if s.sentiment is not None
    ]
    pol = (
        polarization(positions)
        if len(positions) >= MIN_SEGMENTS_FOR_POLARIZATION
        else None
    )
    polarization_section = ReportSection(
        title="Polarization Index",
        metrics=[
            ReportMetric(
                label="Skor polarisasi",
                source="SURVEY",
                method="bimodalitas berbobot ukuran segmen",
                value=(
                    f"{pol['polarization_score']} — {pol['state']}"
                    if pol is not None
                    else None
                ),
                insufficient_data=pol is None,
            )
        ],
        limitations=(
            []
            if pol is not None
            else [
                f"Butuh minimal {MIN_SEGMENTS_FOR_POLARIZATION} segmen bersentimen "
                f"terukur; tersedia {len(positions)}."
            ]
        ),
    )

    pdf_bytes = build_summary_pdf(
        project_name=project.name,
        is_demo=project.is_demo,
        generated_at=datetime.now(UTC),
        sections=[segment_section, polarization_section],
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="ringkasan-{project_id}.pdf"'
        },
    )
