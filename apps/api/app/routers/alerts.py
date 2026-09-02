"""Peringatan aktif — anomali statistik pada deret sinyal & metrik proyek.

Menjawab kartu "Peringatan aktif" yang sengaja belum dirender di Command
Center sejak Phase 1 (lihat CLAUDE.md §8 dan catatan yang sekarang dihapus
dari halaman Command Center) — waktu itu belum ada topic modeling maupun
anomaly detection nyata untuk mengisinya. Modul ini yang mengisi bagian
anomaly detection-nya; `services/alerts.py` yang menghitung, murni tanpa I/O.

Tiga deret yang diperiksa:

1. **Volume percakapan harian** (30 hari terakhir) — lonjakan/penurunan
   mendadak dibanding pola 29 hari sebelumnya.
2. **Sentimen percakapan harian** — pergeseran sentimen mendadak, dari hari
   yang punya cukup konten bernilai.
3. **Tiap metrik `metric_snapshots` nasional** (poi, trust, approval, dst.) —
   titik terbaru dibanding riwayat gelombang sebelumnya.

Tidak ada satu pun di sini yang menyimpulkan PENYEBAB. Label yang dipakai
selalu "menyimpang dari pola historis", bukan "krisis" atau "disebabkan
oleh". Peristiwa dari `timeline_events` pada periode yang sama disertakan
sebagai KONTEKS WAKTU, bukan sebab — kata yang dipakai "berdekatan waktu
dengan".
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.deps import CurrentUser, TenantSession
from app.models.measurement import MetricSnapshot, TimelineEvent
from app.models.signal import Mention
from app.services.alerts import AnomalyPoint, build_report, detect

router = APIRouter(prefix="/projects/{project_id}/alerts", tags=["alerts"])

#: Jendela deret harian sinyal yang diperiksa.
SIGNAL_WINDOW_DAYS = 30

#: Sejalan dengan MIN_MENTIONS_FOR_AGGREGATE di routers/signals.py — hari
#: dengan konten bernilai sentimen di bawah ini tidak ikut deret sentimen,
#: supaya "sentimen hari itu" bukan dihitung dari segelintir komentar.
MIN_SCORED_PER_DAY = 5

#: Berapa hari ke belakang mencari peristiwa timeline sebagai konteks waktu.
CONTEXT_WINDOW_DAYS = 3


class NearbyEvent(BaseModel):
    label: str
    kind: str
    occurred_at: datetime


class AlertOut(BaseModel):
    key: str
    label: str
    direction: str | None
    latest_value: float
    latest_period: str
    baseline_mean: float
    baseline_sd: float | None
    z_score: float | None
    n_baseline: int
    method: str
    limitations: str
    #: Peristiwa timeline dalam CONTEXT_WINDOW_DAYS dari titik yang menyimpang.
    #: Konteks waktu, BUKAN sebab — lihat docstring modul.
    nearby_events: list[NearbyEvent] = []


class AlertsOut(BaseModel):
    alerts: list[AlertOut]
    checked: list[str]
    insufficient: list[str]
    method: str
    limitations: list[str]


_LIMITATIONS = (
    "Ini deteksi penyimpangan statistik terhadap pola historis deret itu "
    "sendiri, bukan penilaian krisis dan bukan prediksi. Penyimpangan yang "
    "terdeteksi belum tentu berarti buruk — bisa juga perbaikan mendadak. "
    "Peristiwa timeline yang disertakan hanya menunjukkan kedekatan waktu, "
    "bukan hubungan sebab-akibat."
)


async def _signal_daily_series(
    session: TenantSession, project_id: UUID, *, days: int
) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    """(deret_volume, deret_sentimen) harian, terurut naik.

    Deret sentimen hanya memuat hari dengan >= MIN_SCORED_PER_DAY konten
    bernilai — hari dengan sedikit konten dilewati dari deret, bukan diisi
    nilai yang tidak berdasar cukup data.
    """
    since = datetime.now(UTC) - timedelta(days=days)
    day = func.date_trunc("day", Mention.published_at).label("day")
    rows = (
        await session.execute(
            select(
                day,
                func.count().label("volume"),
                func.avg(Mention.sentiment).label("mean_sentiment"),
                func.count(Mention.sentiment).label("scored"),
            )
            .where(Mention.project_id == project_id, Mention.published_at >= since)
            .group_by(day)
            .order_by(day)
        )
    ).all()

    volume = [(row.day.date().isoformat(), float(row.volume)) for row in rows]
    sentiment = [
        (row.day.date().isoformat(), float(row.mean_sentiment))
        for row in rows
        if row.mean_sentiment is not None and row.scored >= MIN_SCORED_PER_DAY
    ]
    return volume, sentiment


async def _metric_series(
    session: TenantSession, project_id: UUID
) -> dict[str, list[tuple[str, float]]]:
    """Deret nasional tiap metrik di metric_snapshots, per nama metrik."""
    rows = (
        await session.execute(
            select(MetricSnapshot)
            .where(
                MetricSnapshot.project_id == project_id,
                MetricSnapshot.province_code.is_(None),
                MetricSnapshot.segment.is_(None),
            )
            .order_by(MetricSnapshot.period_end)
        )
    ).scalars().all()

    by_metric: dict[str, list[tuple[str, float]]] = {}
    for row in rows:
        by_metric.setdefault(row.metric, []).append(
            (row.period_end.isoformat(), float(row.value))
        )
    return by_metric


async def _nearby_events(
    session: TenantSession, project_id: UUID, around: datetime
) -> list[NearbyEvent]:
    lo = around - timedelta(days=CONTEXT_WINDOW_DAYS)
    hi = around + timedelta(days=CONTEXT_WINDOW_DAYS)
    rows = (
        await session.execute(
            select(TimelineEvent)
            .where(
                TimelineEvent.project_id == project_id,
                TimelineEvent.occurred_at >= lo,
                TimelineEvent.occurred_at <= hi,
            )
            .order_by(TimelineEvent.occurred_at)
            .limit(5)
        )
    ).scalars().all()
    return [NearbyEvent(label=r.label, kind=r.kind, occurred_at=r.occurred_at) for r in rows]


def _to_out(point: AnomalyPoint) -> AlertOut:
    return AlertOut(
        key=point.key,
        label=point.label,
        direction=point.direction,
        latest_value=point.latest_value,
        latest_period=point.latest_period,
        baseline_mean=point.baseline_mean,
        baseline_sd=point.baseline_sd,
        z_score=point.z_score,
        n_baseline=point.n_baseline,
        method=point.method,
        limitations=_LIMITATIONS,
    )


@router.get("", response_model=AlertsOut)
async def get_alerts(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    days: int = Query(default=SIGNAL_WINDOW_DAYS, ge=7, le=365),
) -> AlertsOut:
    """Deret mana pun yang titik terbarunya menyimpang dari pola historisnya.

    Daftar `alerts` kosong adalah kabar baik yang sah — bukan sinyal endpoint
    ini gagal. `checked` dan `insufficient` menyatakan deret mana yang
    benar-benar bisa diperiksa, supaya "tidak ada alert" tidak disalahartikan
    sebagai "semuanya baik-baik saja" padahal sebagian besar deret belum
    punya cukup riwayat untuk diperiksa sama sekali.
    """
    volume_series, sentiment_series = await _signal_daily_series(session, project_id, days=days)
    metric_series = await _metric_series(session, project_id)

    results: dict[str, AnomalyPoint | None] = {
        "signal_volume": detect(
            volume_series, key="signal_volume", label="Volume percakapan harian"
        ),
        "signal_sentiment": detect(
            sentiment_series, key="signal_sentiment", label="Sentimen percakapan harian"
        ),
    }
    for metric_key, series in metric_series.items():
        results[f"metric:{metric_key}"] = detect(
            series, key=f"metric:{metric_key}", label=f"Metrik {metric_key}"
        )

    report = build_report(results)

    out: list[AlertOut] = []
    for point in report.alerts:
        item = _to_out(point)
        try:
            when = datetime.fromisoformat(point.latest_period).replace(tzinfo=UTC)
        except ValueError:
            when = datetime.now(UTC)
        item.nearby_events = await _nearby_events(session, project_id, when)
        out.append(item)

    return AlertsOut(
        alerts=out,
        checked=report.checked,
        insufficient=report.insufficient,
        method="z-score terhadap baseline historis deret sendiri, per deret",
        limitations=[_LIMITATIONS],
    )
