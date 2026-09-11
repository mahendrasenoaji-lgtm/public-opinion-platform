"""Pengumpulan deret waktu dari sumber publik ke `metric_snapshots`.

Sejajar dengan `routers/signals.py`, bukan bagian darinya: yang masuk lewat
sini adalah DERET (satu angka per periode), bukan KONTEN (teks yang dinilai
sentimennya). Alasan pemisahan lengkapnya ada di docstring
`app/connectors/metrics.py`.

Deret yang tersimpan di sini langsung terbaca oleh `/forecast/baseline`,
`/forecast/what-if`, dan `/opinion/trend` — ketiganya sudah metrik-agnostik,
jadi tidak ada satu pun yang perlu diubah untuk mendukung sumber baru.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.connectors import (
    ConnectorError,
    CredentialMissing,
    available_metrics,
    get_metric_connector,
)
from app.deps import CurrentUser, Role, TenantSession, require_role
from app.models.governance import AuditLog
from app.models.measurement import MetricSnapshot

router = APIRouter(tags=["metrics"])

#: Batas rentang satu permintaan. Sama alasannya dengan `limit` di
#: signals/collect: pengumpulan jalan sinkron di dalam permintaan HTTP, jadi
#: rentangnya harus tetap di bawah timeout. 365 hari sudah jauh lebih dari
#: cukup untuk mem-fit model state-space.
MAX_RANGE_DAYS = 365


class MetricConnectorOut(BaseModel):
    key: str
    label: str
    source: str
    requires_credential: str | None
    config_fields: list[str]
    notes: str


class CollectSeriesRequest(BaseModel):
    connector: str = Field(description="Kunci konektor, mis. 'wikipedia_pageviews'.")
    config: dict[str, str] = Field(
        default_factory=dict,
        description="Konfigurasi konektor, mis. {'project': 'id.wikipedia', 'article': '...'}.",
    )
    days: int = Field(
        default=90,
        ge=2,
        le=MAX_RANGE_DAYS,
        description=(
            "Jumlah hari ke belakang yang diambil. Minimal 2 — satu titik "
            "bukan deret, dan model tidak bisa di-fit dari situ."
        ),
    )


class CollectSeriesResult(BaseModel):
    metric: str
    fetched: int
    stored: int
    replaced: int
    period_start: date | None
    period_end: date | None
    source: str
    method: str
    #: Kode provinsi yang terisi dari deret ini. Kosong berarti deret nasional
    #: — dan hanya deret nasional yang dibaca /forecast/baseline.
    provinces: list[str]
    limitations: list[str]


class SeriesSummaryOut(BaseModel):
    metric: str
    source: str
    method: str
    n_observations: int
    period_start: date
    period_end: date
    #: Nilai terakhir deret — hanya untuk deret NASIONAL.
    #:
    #: null untuk deret per-provinsi, dan itu disengaja. Baris di tabel ini
    #: diurutkan per tanggal saja, jadi "baris terakhir" dari deret 20
    #: provinsi adalah provinsi yang kebetulan terurut paling belakang di
    #: tanggal terakhir — angka satu provinsi yang akan terbaca sebagai
    #: angka seluruh deret. Merata-ratakannya juga bukan jawaban: itu
    #: menciptakan angka yang tidak pernah diukur di mana pun.
    latest_value: float | None
    #: True kalau seluruh deret ini nasional (province_code NULL). Hanya deret
    #: nasional yang bisa dibaca /forecast/baseline — deret per-provinsi
    #: sengaja tidak, supaya potongan populasi berbeda tidak tercampur jadi
    #: satu riwayat (lihat routers/forecast.py:_history).
    is_national: bool
    provinces: list[str]


@router.get("/projects/{project_id}/metrics", response_model=list[SeriesSummaryOut])
async def list_series(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
) -> list[SeriesSummaryOut]:
    """Deret yang sudah tersimpan di proyek ini, terbanyak pengamatan dulu.

    Termasuk deret survei bawaan (`poi`, `trust`, `approval`) — halaman ini
    memang untuk melihat riwayat APA SAJA yang bisa dijadikan baseline
    forecast, bukan cuma yang ditarik dari sumber publik.
    """
    rows = (
        (
            await session.execute(
                select(MetricSnapshot)
                .where(
                    MetricSnapshot.project_id == project_id,
                    MetricSnapshot.segment.is_(None),
                )
                .order_by(MetricSnapshot.period_end)
            )
        )
        .scalars()
        .all()
    )

    grouped: dict[str, list[MetricSnapshot]] = {}
    for row in rows:
        grouped.setdefault(row.metric, []).append(row)

    summaries = []
    for metric, items in grouped.items():
        national = all(i.province_code is None for i in items)
        summaries.append(
            SeriesSummaryOut(
                metric=metric,
                source=items[-1].source.value,
                method=items[-1].method,
                n_observations=len(items),
                period_start=items[0].period_end,
                period_end=items[-1].period_end,
                latest_value=float(items[-1].value) if national else None,
                is_national=national,
                provinces=sorted({i.province_code for i in items if i.province_code}),
            )
        )
    summaries.sort(key=lambda s: (-s.n_observations, s.metric))
    return summaries


@router.get("/metrics/connectors", response_model=list[MetricConnectorOut])
async def list_metric_connectors(user: CurrentUser) -> list[MetricConnectorOut]:
    """Konektor deret waktu yang tersedia di deployment ini."""
    return [
        MetricConnectorOut(
            key=c.key,
            label=c.label,
            source=c.source.value,
            requires_credential=c.requires_credential,
            config_fields=list(c.config_fields),
            notes=c.notes,
        )
        for c in available_metrics()
    ]


@router.post(
    "/projects/{project_id}/metrics/collect",
    response_model=CollectSeriesResult,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def collect_series(
    project_id: UUID,
    body: CollectSeriesRequest,
    session: TenantSession,
    user: CurrentUser,
    until: date | None = Query(
        default=None,
        description="Hari terakhir yang diambil. Default: kemarin.",
    ),
) -> CollectSeriesResult:
    """Tarik satu deret waktu dari sumber publik dan simpan ke metric_snapshots.

    Hari yang sudah pernah tersimpan untuk metrik yang sama DIGANTI, bukan
    ditambahkan lagi. Tanpa itu, menjalankan endpoint ini dua kali akan
    menggandakan setiap hari dalam rentang yang bertindih, dan
    `timeseries.fit()` akan melihat dua pengamatan di tanggal yang sama —
    yang membuat estimasi lebar intervalnya mengecil palsu karena "variasi"
    antar duplikat selalu nol.
    """
    # Default "kemarin", bukan "hari ini": hari berjalan belum lengkap di
    # sumber mana pun, dan menyimpannya membuat titik terakhir deret selalu
    # terlihat anjlok. Itu akan terbaca sebagai tren turun yang tidak ada.
    last_day = until or (datetime.now(UTC).date() - timedelta(days=1))
    first_day = last_day - timedelta(days=body.days - 1)

    try:
        connector = get_metric_connector(body.connector)
        observations = await connector.fetch_series(
            dict(body.config), start=first_day, end=last_day
        )
    except CredentialMissing as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e
    except ConnectorError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e

    if not observations:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Sumber tidak mengembalikan satu pun pengamatan untuk rentang itu. "
            "Deret kosong tidak disimpan — tidak ada yang bisa dianalisis darinya.",
        )

    metric = observations[0].metric
    days = {o.period_end for o in observations}

    # Kunci identitas sebuah pengamatan adalah (tanggal, provinsi), bukan
    # tanggal saja. Deret nasional (`province_code=None`) dan deret provinsi
    # hidup berdampingan di tabel yang sama untuk metrik berbeda, dan
    # routers/forecast.py:_history memisahkannya lewat `province_code IS NULL`.
    # Kalau kunci di sini cuma tanggal, satu tarikan 20 provinsi akan saling
    # menimpa dan menyisakan satu provinsi terakhir saja.
    existing = {
        (row.period_end, row.province_code): row
        for row in (
            (
                await session.execute(
                    select(MetricSnapshot).where(
                        MetricSnapshot.project_id == project_id,
                        MetricSnapshot.metric == metric,
                        MetricSnapshot.segment.is_(None),
                        MetricSnapshot.period_end >= min(days),
                        MetricSnapshot.period_end <= max(days),
                    )
                )
            )
            .scalars()
            .all()
        )
    }

    stored = replaced = 0
    for obs in observations:
        row = existing.get((obs.period_end, obs.province_code))
        if row is not None:
            row.value = Decimal(str(obs.value))
            row.method = obs.method
            row.source = obs.source
            row.breakdown = dict(obs.breakdown)
            replaced += 1
            continue
        session.add(
            MetricSnapshot(
                org_id=user.org_id,
                project_id=project_id,
                metric=metric,
                source=obs.source,
                method=obs.method,
                period_start=obs.period_start,
                period_end=obs.period_end,
                value=Decimal(str(obs.value)),
                province_code=obs.province_code,
                breakdown=dict(obs.breakdown),
            )
        )
        stored += 1

    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="collect_series",
            entity="metric_snapshot",
            entity_id=project_id,
            metadata_={
                "connector": body.connector,
                "metric": metric,
                "stored": str(stored),
                "replaced": str(replaced),
            },
        )
    )

    return CollectSeriesResult(
        metric=metric,
        fetched=len(observations),
        stored=stored,
        replaced=replaced,
        period_start=min(days),
        period_end=max(days),
        source=observations[0].source.value,
        method=observations[0].method,
        provinces=sorted({o.province_code for o in observations if o.province_code}),
        limitations=[connector.notes] if connector.notes else [],
    )
