"""Opinion Risk Score & Polarization Index — Phase 3 (docs/roadmap.md).

Polarization Index dihitung PENUH dari data nyata: sentimen per segmen
(services/risk.py mengharapkan posisi -100..100) dan size_pct sebagai bobot
massa — segments sudah ada sejak Phase 1 (routers/segments.py), jadi tidak
ada data yang direka.

Opinion Risk Score (9 komponen berbobot) sebelumnya SENGAJA ditahan di sini:
lima komponennya butuh sinyal yang belum ada, dan mengisinya dengan angka
reka-reka supaya skornya "lengkap" melanggar CLAUDE.md §3.

Sejak Phase 2 terpasang (konektor, mentions, topics, deret metrik), delapan
dari sembilan komponen bisa dihitung dari data nyata. Yang tersisa —
`geographic_spread` — butuh geotag resmi pada mention, dan sebagian besar
percakapan tidak punya itu; ia dilaporkan sebagai komponen yang hilang, bukan
ditebak dari isi teks (larangan yang sama seperti di services/ingestion.py).

Aturan penerbitannya tetap ketat: `partial_risk_score()` menolak memberi angka
kalau bobot yang punya data di bawah MIN_COVERAGE, dan selalu mengembalikan
`coverage` beserta daftar komponen yang hilang. Skor 62 dari 95% bobot dan
skor 62 dari 61% bobot adalah dua pernyataan berbeda.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentUser, TenantSession
from app.models.measurement import MetricSnapshot, Segment
from app.models.measurement import SignalSource as ModelSignalSource
from app.models.signal import Mention
from app.schemas.common import SignalSource
from app.services.ingestion import concentration_ratio
from app.services.risk import (
    DEFAULT_RISK_WEIGHTS,
    MIN_COVERAGE,
    decline_component,
    growth_component,
    partial_risk_score,
    polarization,
    share_negative,
    velocity_component,
)

router = APIRouter(prefix="/projects/{project_id}/risk", tags=["risk"])

#: Jendela pembanding untuk komponen yang mengukur perubahan.
WINDOW_DAYS = 14

#: Sejalan dengan ambang di routers/signals.py — komponen berbasis sinyal
#: tidak dihitung dari volume yang terlalu tipis.
MIN_MENTIONS = 30

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


class RiskComponentOut(BaseModel):
    key: str
    label: str
    value: float | None
    weight: float
    available: bool
    reason_missing: str | None = None


class RiskScoreOut(BaseModel):
    score: int | None = None
    band: str | None = None
    coverage: float
    components: list[RiskComponentOut]
    missing: list[str]
    top_contributors: list[str] = []
    method: str
    insufficient_data: bool = False
    note: str | None = None
    limitations: list[str] = []


#: Label yang dibaca manusia untuk tiap komponen, dan penjelasan kenapa sebuah
#: komponen bisa tidak tersedia. Dipakai apa adanya di UI.
_COMPONENT_LABELS: dict[str, str] = {
    "negative_sentiment": "Porsi percakapan bersentimen negatif",
    "sentiment_velocity": "Kecepatan sentimen memburuk",
    "issue_growth": "Pertumbuhan volume isu",
    "narrative_polarization": "Polarisasi antar-segmen",
    "influencer_amplification": "Pemusatan amplifikasi akun",
    "geographic_spread": "Sebaran geografis",
    "media_escalation": "Eskalasi liputan media",
    "trust_decline": "Penurunan kepercayaan",
    "approval_decline": "Penurunan persetujuan",
}

_MISSING_REASONS: dict[str, str] = {
    "negative_sentiment": f"Butuh minimal {MIN_MENTIONS} konten bernilai sentimen.",
    "sentiment_velocity": "Butuh sentimen terukur di dua periode pembanding.",
    "issue_growth": "Butuh volume percakapan di dua periode pembanding.",
    "narrative_polarization": "Butuh minimal dua segmen dengan sentimen terukur.",
    "influencer_amplification": "Butuh konten yang membawa identitas akun (ter-hash).",
    "geographic_spread": (
        "Butuh geotag resmi dari sumbernya. Provinsi TIDAK diinferensi dari isi "
        "teks — hasilnya akan dipakai sebagai georeferensi padahal bukan."
    ),
    "media_escalation": "Butuh konten bersumber MEDIA di dua periode pembanding.",
    "trust_decline": "Butuh minimal dua snapshot metrik 'trust'.",
    "approval_decline": "Butuh minimal dua snapshot metrik 'approval'.",
}


async def _metric_pair(
    session: TenantSession, project_id: UUID, metric: str
) -> tuple[float | None, float | None]:
    """Dua snapshot nasional terakhir sebuah metrik: (terbaru, sebelumnya)."""
    rows = (
        (
            await session.execute(
                select(MetricSnapshot)
                .where(
                    MetricSnapshot.project_id == project_id,
                    MetricSnapshot.metric == metric,
                    MetricSnapshot.province_code.is_(None),
                    MetricSnapshot.segment.is_(None),
                )
                .order_by(MetricSnapshot.period_end.desc())
                .limit(2)
            )
        )
        .scalars()
        .all()
    )
    if len(rows) < 2:
        return (float(rows[0].value) if rows else None, None)
    return float(rows[0].value), float(rows[1].value)


@router.get("/score", response_model=RiskScoreOut)
async def get_risk_score(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    days: int = Query(default=WINDOW_DAYS, ge=7, le=90),
) -> RiskScoreOut:
    """Opinion Risk Score dari komponen yang benar-benar punya data.

    Komponen yang datanya tidak ada dikeluarkan dari perhitungan dan disebut
    namanya — tidak diisi nol, tidak diisi rata-rata. `coverage` menyatakan
    berapa bagian bobot yang benar-benar terhitung, dan di bawah MIN_COVERAGE
    tidak ada skor yang diterbitkan sama sekali.
    """
    now = datetime.now(UTC)
    recent_start = now - timedelta(days=days)
    previous_start = now - timedelta(days=2 * days)

    mentions = (
        (
            await session.execute(
                select(Mention).where(
                    Mention.project_id == project_id,
                    Mention.published_at >= previous_start,
                )
            )
        )
        .scalars()
        .all()
    )
    recent = [m for m in mentions if m.published_at >= recent_start]
    previous = [m for m in mentions if m.published_at < recent_start]

    def _mean(rows: list[Mention]) -> float | None:
        scores = [float(m.sentiment) for m in rows if m.sentiment is not None]
        return sum(scores) / len(scores) if scores else None

    recent_scores = [float(m.sentiment) for m in recent if m.sentiment is not None]
    components: dict[str, float] = {}

    # 1. Porsi negatif — hanya kalau volumenya cukup untuk dibaca.
    if len(recent_scores) >= MIN_MENTIONS:
        value = share_negative(recent_scores)
        if value is not None:
            components["negative_sentiment"] = value

    # 2. Kecepatan memburuk.
    velocity = velocity_component(_mean(recent), _mean(previous))
    if velocity is not None:
        components["sentiment_velocity"] = velocity

    # 3 & 7. Pertumbuhan volume, dipisah sosial dan media: keduanya tumbuh
    # dengan alasan berbeda dan tidak boleh disatukan jadi satu angka (R1).
    def _growth(source: ModelSignalSource | None) -> float | None:
        a = [m for m in recent if source is None or m.source is source]
        b = [m for m in previous if source is None or m.source is source]
        if not b:
            return None
        return growth_component(100 * (len(a) - len(b)) / len(b))

    issue_growth = _growth(None)
    if issue_growth is not None:
        components["issue_growth"] = issue_growth

    media_growth = _growth(ModelSignalSource.MEDIA)
    if media_growth is not None:
        components["media_escalation"] = media_growth

    # 4. Polarisasi antar-segmen — memakai jalur yang sama dengan endpoint
    # /polarization supaya kedua angka tidak pernah berbeda.
    segments = (
        (await session.execute(select(Segment).where(Segment.project_id == project_id)))
        .scalars()
        .all()
    )
    usable = [
        (s.name, float(s.sentiment), float(s.size_pct) / 100)
        for s in segments
        if s.sentiment is not None
    ]
    if len(usable) >= MIN_SEGMENTS_FOR_POLARIZATION:
        components["narrative_polarization"] = float(
            polarization(usable)["polarization_score"]  # type: ignore[arg-type]
        )

    # 5. Pemusatan amplifikasi. Deskriptif — lihat catatan di signals.py.
    hashed = [m.author_hash for m in recent if m.author_hash]
    if len(hashed) >= MIN_MENTIONS:
        components["influencer_amplification"] = round(
            100 * concentration_ratio(hashed), 2
        )

    # 6. Sebaran geografis — hanya dari geotag resmi.
    geotagged = [m for m in recent if m.province_code]
    if len(geotagged) >= MIN_MENTIONS:
        provinces = len({m.province_code for m in geotagged})
        components["geographic_spread"] = round(min(100.0, 100 * provinces / 38), 2)

    # 8 & 9. Penurunan kepercayaan dan persetujuan dari deret snapshot.
    for metric, key in (("trust", "trust_decline"), ("approval", "approval_decline")):
        latest, earlier = await _metric_pair(session, project_id, metric)
        value = decline_component(latest, earlier)
        if value is not None:
            components[key] = value

    result = partial_risk_score(components)

    return RiskScoreOut(
        score=result.score,
        band=result.band,
        coverage=result.coverage,
        components=[
            RiskComponentOut(
                key=key,
                label=_COMPONENT_LABELS[key],
                value=components.get(key),
                weight=weight,
                available=key in components,
                reason_missing=None if key in components else _MISSING_REASONS[key],
            )
            for key, weight in DEFAULT_RISK_WEIGHTS.items()
        ],
        missing=result.missing,
        top_contributors=[_COMPONENT_LABELS[k] for k, _ in result.top_contributors],
        method=(
            "rata-rata berbobot komponen yang tersedia, bobot dinormalisasi "
            f"ulang atas cakupan {result.coverage:.0%}"
        ),
        insufficient_data=result.insufficient_data,
        note=result.note,
        limitations=[
            "Skala tiap komponen adalah penilaian tim, belum dikalibrasi "
            "terhadap kejadian krisis nyata. Skor ini berguna untuk "
            "membandingkan periode atau proyek dengan skala yang sama, bukan "
            "sebagai ambang absolut.",
            "Komponen berbasis percakapan berasal dari data self-selected dan "
            "tidak bisa digeneralisasi ke populasi.",
            f"Skor tidak diterbitkan bila cakupan bobot di bawah {MIN_COVERAGE:.0%}.",
        ],
    )
