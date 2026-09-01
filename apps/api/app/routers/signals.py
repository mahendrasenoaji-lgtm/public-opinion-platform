"""Sinyal sosial dan media — konfigurasi sumber, ingest, dan agregasi (Phase 2).

Menggantikan kerangka 501 yang ada di sini sebelumnya.

## Aturan yang ditegakkan endpoint di file ini

**R1 — setiap angka membawa sumber dan metodenya.** Agregat sinyal dikembalikan
sebagai `Metric` dengan `source` SOCIAL atau MEDIA, tidak pernah dicampur ke
satu angka dengan hasil survei. Divergensi antar sumber adalah objek utama
platform ini; merata-ratakannya justru menghapus produknya.

**Sentimen media sosial bukan sentimen publik.** Ia sentimen dari orang yang
kebetulan menulis. Setiap respons agregat membawa `limitations` yang
menyatakan itu, dan `abstain_rate` yang menyatakan berapa banyak yang bahkan
tidak bisa dinilai.

**Tidak ada penilaian tentang akun.** Yang dilaporkan tentang penulis hanyalah
jumlah akun berbeda dan seberapa terpusat percakapannya — keduanya deskriptif.
Tidak ada endpoint di sini yang menyimpulkan koordinasi atau kecurangan
(CLAUDE.md §3).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Select, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.connectors import ConnectorError, CredentialMissing, available, get_connector
from app.deps import CurrentUser, Role, TenantSession, require_role
from app.models.governance import AuditLog
from app.models.measurement import SignalSource as ModelSignalSource
from app.models.signal import DataSource, Mention
from app.schemas.common import Metric, SignalSource
from app.services import sentiment as sentiment_svc
from app.services.ingestion import concentration_ratio
from app.services.pipeline import IncomingItem, prepare_batch
from app.services.sentiment_eval import LABELED

router = APIRouter(tags=["signals"])

#: Berapa hari ke belakang yang dianggap "periode berjalan" bila tidak disebut.
DEFAULT_WINDOW_DAYS = 30

#: Batas item per satu panggilan ingest. Bukan batas teknis — batas supaya satu
#: permintaan tidak menahan koneksi database terlalu lama.
MAX_INGEST_ITEMS = 1000

#: Di bawah ini, agregat sentimen tidak diterbitkan. Sama semangatnya dengan
#: ambang n<250 untuk skor provinsi (CLAUDE.md §3): angka dari 12 komentar
#: bukan pengukuran, itu anekdot dengan desimal.
MIN_MENTIONS_FOR_AGGREGATE = 30

_SOCIAL_LIMITATION = (
    "Percakapan media sosial bersifat self-selected: yang menulis bukan sampel "
    "dari populasi mana pun. Angka ini tidak bisa digeneralisasi ke penduduk "
    "Indonesia dan tidak sebanding langsung dengan hasil survei probabilistik."
)
_MEDIA_LIMITATION = (
    "Liputan media menunjukkan agenda redaksi, bukan opini pembaca. Volume "
    "liputan yang tinggi berarti isu itu diangkat, bukan bahwa publik "
    "menyetujuinya."
)
_SENTIMENT_METHOD = f"leksikon Indonesia berbobot ({sentiment_svc.MODEL_VERSION})"


# --------------------------------------------------------------- skema ----


class ConnectorOut(BaseModel):
    key: str
    label: str
    source: SignalSource
    requires_credential: str | None
    credential_configured: bool
    config_fields: list[str]
    notes: str


class SourceCreate(BaseModel):
    connector: str
    config: dict[str, str] = Field(default_factory=dict)


class SourceOut(BaseModel):
    id: UUID
    connector: str
    source: SignalSource
    config: dict
    is_active: bool
    last_sync_at: datetime | None


class IngestItem(BaseModel):
    """Satu item pada unggahan manual."""

    external_id: str = Field(min_length=1, max_length=512)
    text: str = Field(min_length=1)
    published_at: datetime
    author_handle: str | None = Field(
        default=None,
        description=(
            "Di-hash sebelum disimpan dan tidak pernah tersimpan apa adanya. "
            "Boleh dikosongkan."
        ),
    )
    engagement: int = Field(default=0, ge=0)
    reach_est: int | None = Field(default=None, ge=0)
    province_code: str | None = Field(
        default=None,
        description=(
            "Isi HANYA bila sumbernya memberi geotag resmi. Jangan menebaknya "
            "dari isi teks."
        ),
    )


class IngestRequest(BaseModel):
    connector: str = Field(default="manual")
    source: SignalSource = SignalSource.SOCIAL
    items: list[IngestItem] = Field(min_length=1, max_length=MAX_INGEST_ITEMS)
    accept_langs: list[str] | None = Field(
        default=None,
        description="Kosongkan untuk tidak menyaring bahasa. Contoh: [\"id\"].",
    )


class IngestResult(BaseModel):
    received: int
    stored: int
    already_present: int
    duplicates_dropped: int
    duplicate_rate: float
    language_rejected: int
    language_unknown: int
    sentiment_abstained: int
    sentiment_abstain_rate: float
    empty_dropped: int
    caveats: list[str]


class SignalSummary(BaseModel):
    volume: Metric
    sentiment: Metric
    distinct_authors: int
    concentration_top10: float
    source_mix: dict[str, int]
    period_start: date
    period_end: date
    limitations: list[str]


class SignalTrendPoint(BaseModel):
    day: date
    volume: int
    sentiment: float | None
    scored: int


class SentimentQuality(BaseModel):
    """Mutu leksikon terhadap set evaluasi berlabel (syarat roadmap Phase 2)."""

    model_version: str
    n: int
    accuracy: float
    accuracy_scored_only: float
    macro_f1: float
    abstain_rate: float
    abstain_by_class: dict[str, int]
    per_class: dict[str, dict[str, float]]
    caveat: str


# ------------------------------------------------------------- konektor ----


@router.get("/signals/connectors", response_model=list[ConnectorOut])
async def list_connectors(user: CurrentUser) -> list[ConnectorOut]:
    """Konektor yang tersedia beserta status kredensialnya di deployment ini.

    `credential_configured` dilaporkan supaya pengguna tahu konektor mana yang
    akan langsung gagal sebelum mereka menyusun sumbernya — bukan setelah.
    Nilai kuncinya sendiri tidak pernah ikut, cuma ada/tidaknya.
    """
    settings = get_settings()
    configured = {
        "YOUTUBE_API_KEY": bool(settings.youtube_api_key),
        "X_BEARER_TOKEN": bool(settings.x_bearer_token),
    }
    return [
        ConnectorOut(
            key=info.key,
            label=info.label,
            source=SignalSource(info.source.value),
            requires_credential=info.requires_credential,
            credential_configured=(
                True
                if info.requires_credential is None
                else configured.get(info.requires_credential, False)
            ),
            config_fields=list(info.config_fields),
            notes=info.notes,
        )
        for info in available()
    ]


@router.get("/projects/{project_id}/signals/sources", response_model=list[SourceOut])
async def list_sources(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> list[SourceOut]:
    rows = (
        (await session.execute(select(DataSource).where(DataSource.project_id == project_id)))
        .scalars()
        .all()
    )
    return [
        SourceOut(
            id=r.id,
            connector=r.connector,
            source=SignalSource(r.source.value),
            config=r.config,
            is_active=r.is_active,
            last_sync_at=r.last_sync_at,
        )
        for r in rows
    ]


@router.post(
    "/projects/{project_id}/signals/sources",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def create_source(
    project_id: UUID, body: SourceCreate, session: TenantSession, user: CurrentUser
) -> SourceOut:
    """Daftarkan satu sumber data untuk proyek ini.

    Konektor divalidasi di sini, bukan saat pengambilan pertama: salah ketik
    nama konektor harus gagal sekarang, bukan diam-diam menghasilkan sumber
    yang tidak pernah menarik apa pun.
    """
    try:
        connector = get_connector(body.connector)
    except ConnectorError as e:
        raise HTTPException(422, str(e)) from e

    missing = [f for f in connector.config_fields if not body.config.get(f, "").strip()]
    if missing:
        raise HTTPException(
            422,
            f"Konektor '{body.connector}' membutuhkan: {', '.join(missing)}.",
        )

    row = DataSource(
        org_id=user.org_id,
        project_id=project_id,
        source=ModelSignalSource(connector.source.value),
        connector=body.connector,
        config=dict(body.config),
    )
    session.add(row)
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="create",
            entity="data_source",
            metadata_={"connector": body.connector, "project_id": str(project_id)},
        )
    )
    await session.flush()
    return SourceOut(
        id=row.id,
        connector=row.connector,
        source=SignalSource(row.source.value),
        config=row.config,
        is_active=row.is_active,
        last_sync_at=row.last_sync_at,
    )


@router.delete(
    "/projects/{project_id}/signals/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def delete_source(
    project_id: UUID, source_id: UUID, session: TenantSession, user: CurrentUser
) -> None:
    """Hapus sumber. Mention yang sudah masuk TIDAK ikut terhapus.

    Disengaja: data yang sudah dipakai dalam analisis tidak boleh lenyap karena
    seseorang merapikan daftar sumber. Menghapus mention adalah tindakan
    terpisah yang harus disebut eksplisit.
    """
    result = await session.execute(
        delete(DataSource).where(DataSource.id == source_id, DataSource.project_id == project_id)
    )
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sumber tidak ditemukan.")
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="delete",
            entity="data_source",
            entity_id=source_id,
            metadata_={"project_id": str(project_id)},
        )
    )


# --------------------------------------------------------------- ingest ----


async def _store(
    session: TenantSession,
    *,
    org_id: UUID,
    project_id: UUID,
    connector: str,
    source: ModelSignalSource,
    items: list[IncomingItem],
    accept_langs: frozenset[str] | None,
) -> IngestResult:
    """Jalankan pipeline lalu simpan. Satu-satunya jalan masuk ke tabel mentions."""
    report = prepare_batch(
        items, author_salt=get_settings().author_salt(), accept_langs=accept_langs
    )

    stored = 0
    for p in report.prepared:
        # ON CONFLICT DO NOTHING pada (project_id, connector, external_id):
        # menarik ulang rentang waktu yang sama adalah operasi normal, dan
        # tidak boleh menggandakan volume. Deduplikasi di prepare_batch hanya
        # berlaku DALAM satu batch; ini yang menjaga antar-batch.
        result = await session.execute(
            pg_insert(Mention)
            .values(
                org_id=org_id,
                project_id=project_id,
                source=source,
                connector=connector,
                external_id=p.external_id,
                published_at=p.published_at,
                author_hash=p.author_hash,
                text=p.text,
                lang=p.lang,
                engagement=p.engagement,
                reach_est=p.reach_est,
                province_code=p.province_code,
                sentiment=None if p.sentiment is None else Decimal(str(p.sentiment)),
                emotion=p.emotion or None,
            )
            .on_conflict_do_nothing(index_elements=["project_id", "connector", "external_id"])
        )
        stored += result.rowcount or 0

    return IngestResult(
        received=report.received,
        stored=stored,
        already_present=report.kept - stored,
        duplicates_dropped=report.duplicates_dropped,
        duplicate_rate=report.duplicate_rate,
        language_rejected=report.language_rejected,
        language_unknown=report.language_unknown,
        sentiment_abstained=report.sentiment_abstained,
        sentiment_abstain_rate=report.sentiment_abstain_rate,
        empty_dropped=report.empty_dropped,
        caveats=report.caveats(),
    )


@router.post(
    "/projects/{project_id}/signals/ingest",
    response_model=IngestResult,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def ingest(
    project_id: UUID, body: IngestRequest, session: TenantSession, user: CurrentUser
) -> IngestResult:
    """Masukkan data yang sudah dimiliki organisasi (ekspor vendor, arsip sendiri).

    Melewati pipeline yang sama dengan konektor otomatis — dedup, deteksi
    bahasa, sentimen — supaya angkanya sebanding. Lisensi data yang diunggah
    adalah tanggung jawab pengunggah; platform tidak bisa memverifikasinya.
    """
    result = await _store(
        session,
        org_id=user.org_id,
        project_id=project_id,
        connector=body.connector,
        source=ModelSignalSource(body.source.value),
        items=[
            IncomingItem(
                external_id=i.external_id,
                text=i.text,
                published_at=i.published_at,
                author_handle=i.author_handle,
                engagement=i.engagement,
                reach_est=i.reach_est,
                province_code=i.province_code,
            )
            for i in body.items
        ],
        accept_langs=frozenset(body.accept_langs) if body.accept_langs else None,
    )
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="ingest",
            entity="mentions",
            metadata_={
                "project_id": str(project_id),
                "connector": body.connector,
                "stored": str(result.stored),
            },
        )
    )
    return result


@router.post(
    "/projects/{project_id}/signals/sources/{source_id}/collect",
    response_model=IngestResult,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def collect(
    project_id: UUID,
    source_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    since_days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=100, ge=1, le=MAX_INGEST_ITEMS),
) -> IngestResult:
    """Tarik data terbaru dari satu sumber yang sudah terdaftar.

    Dijalankan sinkron di dalam permintaan. Untuk pengumpulan terjadwal
    berskala besar ini harus pindah ke worker (Phase 2 lanjutan); bentuk
    sekarang cukup untuk menarik satu sumber atas permintaan pengguna, dan
    batas `limit` menjaganya tetap di bawah timeout permintaan.
    """
    source = (
        await session.execute(
            select(DataSource).where(
                DataSource.id == source_id, DataSource.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sumber tidak ditemukan.")
    if not source.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Sumber sedang dinonaktifkan.")

    try:
        connector = get_connector(source.connector)
        raw = await connector.fetch(
            dict(source.config),
            since=datetime.now(UTC) - timedelta(days=since_days),
            limit=limit,
        )
    except CredentialMissing as e:
        # 503, bukan 500: ini keadaan deployment yang bisa diperbaiki operator,
        # dan pesannya menyebut env var mana yang kurang.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e
    except ConnectorError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e

    result = await _store(
        session,
        org_id=user.org_id,
        project_id=project_id,
        connector=source.connector,
        source=source.source,
        items=[
            IncomingItem(
                external_id=r.external_id,
                text=r.text,
                published_at=r.published_at,
                author_handle=r.author_handle,
                engagement=r.engagement,
                reach_est=r.reach_est,
                province_code=r.province_code,
            )
            for r in raw
        ],
        accept_langs=None,
    )
    source.last_sync_at = datetime.now(UTC)
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="collect",
            entity="data_source",
            entity_id=source_id,
            metadata_={"stored": str(result.stored), "connector": source.connector},
        )
    )
    return result


# ------------------------------------------------------------- agregasi ----


def _window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(UTC)
    return end - timedelta(days=days), end


def _scoped(query: Select, project_id: UUID, since: datetime, until: datetime) -> Select:
    return query.where(
        Mention.project_id == project_id,
        Mention.published_at >= since,
        Mention.published_at <= until,
    )


@router.get("/projects/{project_id}/signals/summary", response_model=SignalSummary)
async def summary(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=1, le=365),
    source: SignalSource | None = None,
) -> SignalSummary:
    """Volume dan sentimen agregat untuk satu jendela waktu.

    Sentimen TIDAK diterbitkan di bawah MIN_MENTIONS_FOR_AGGREGATE — yang
    dikembalikan `value=None` dengan `insufficient_data=True`, pola yang sama
    dengan skor provinsi n<250 di opinion.py. Volume tetap ditampilkan: berapa
    banyak yang bicara adalah fakta perhitungan, bukan estimasi.
    """
    since, until = _window(days)

    base = _scoped(select(Mention), project_id, since, until)
    if source is not None:
        base = base.where(Mention.source == ModelSignalSource(source.value))

    rows = (await session.execute(base)).scalars().all()
    volume = len(rows)

    scored = [float(r.sentiment) for r in rows if r.sentiment is not None]
    distinct_authors = len({r.author_hash for r in rows if r.author_hash})
    concentration = concentration_ratio(r.author_hash for r in rows)

    mix: dict[str, int] = {}
    for r in rows:
        mix[r.source.value] = mix.get(r.source.value, 0) + 1

    enough = volume >= MIN_MENTIONS_FOR_AGGREGATE and len(scored) >= MIN_MENTIONS_FOR_AGGREGATE
    mean = round(sum(scored) / len(scored), 3) if scored else None

    dominant = (
        SignalSource.MEDIA
        if mix.get("MEDIA", 0) > mix.get("SOCIAL", 0)
        else SignalSource.SOCIAL
    )
    limitations = [_MEDIA_LIMITATION if dominant is SignalSource.MEDIA else _SOCIAL_LIMITATION]
    if volume and len(scored) / volume < 0.6:
        limitations.append(
            f"Hanya {len(scored)} dari {volume} konten bisa dinilai sentimennya "
            "oleh leksikon; rata-rata di atas mewakili sebagian itu saja."
        )
    if concentration >= 0.5 and distinct_authors:
        limitations.append(
            f"{concentration:.0%} percakapan datang dari 10 akun paling aktif. "
            "Ini deskripsi sebaran, bukan indikasi koordinasi."
        )

    return SignalSummary(
        volume=Metric(
            key="signal_volume",
            label="Volume percakapan",
            value=float(volume),
            unit="konten",
            source=dominant,
            method="hitungan konten unik setelah deduplikasi",
            effective_n=volume,
            period_start=since.date(),
            period_end=until.date(),
        ),
        sentiment=Metric(
            key="signal_sentiment",
            label="Sentimen rata-rata",
            value=mean if enough else None,
            unit="skala -1..1",
            source=dominant,
            method=_SENTIMENT_METHOD,
            effective_n=len(scored),
            period_start=since.date(),
            period_end=until.date(),
            insufficient_data=not enough,
            note=(
                None
                if enough
                else (
                    f"Perlu minimal {MIN_MENTIONS_FOR_AGGREGATE} konten bernilai "
                    f"sentimen; tersedia {len(scored)}."
                )
            ),
        ),
        distinct_authors=distinct_authors,
        concentration_top10=concentration,
        source_mix=mix,
        period_start=since.date(),
        period_end=until.date(),
        limitations=limitations,
    )


@router.get("/projects/{project_id}/signals/trend", response_model=list[SignalTrendPoint])
async def trend(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=2, le=365),
) -> list[SignalTrendPoint]:
    """Volume dan sentimen harian.

    Sentimen harian dikembalikan None untuk hari yang tidak punya satu pun
    konten bernilai — bukan 0.0, yang akan terbaca sebagai "netral hari itu"
    padahal artinya "tidak terukur hari itu".
    """
    since, until = _window(days)
    day = func.date_trunc("day", Mention.published_at).label("day")
    query = (
        _scoped(
            select(
                day,
                func.count().label("volume"),
                func.avg(Mention.sentiment).label("mean"),
                func.count(Mention.sentiment).label("scored"),
            ),
            project_id,
            since,
            until,
        )
        .group_by(day)
        .order_by(day)
    )
    return [
        SignalTrendPoint(
            day=row.day.date(),
            volume=int(row.volume),
            sentiment=round(float(row.mean), 3) if row.mean is not None else None,
            scored=int(row.scored),
        )
        for row in (await session.execute(query)).all()
    ]


@router.get(
    "/projects/{project_id}/signals/sentiment-quality", response_model=SentimentQuality
)
async def sentiment_quality(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> SentimentQuality:
    """Mutu leksikon terhadap set evaluasi berlabel manual.

    Ada karena docs/roadmap.md mensyaratkannya: "sediakan set evaluasi berlabel
    manual sebelum menyalakan fitur ini di proyek nyata, dan laporkan
    akurasinya di UI". Endpoint ini yang membuat syarat kedua bisa dipenuhi
    frontend.

    Perhatikan `caveat` yang ikut dikembalikan: angka ini diukur pada kalimat
    yang ditulis tim pengembang, bukan pada percakapan proyek Anda. Ia batas
    atas, bukan perkiraan lapangan.
    """
    report = sentiment_svc.evaluate(LABELED)
    return SentimentQuality(
        model_version=sentiment_svc.MODEL_VERSION,
        n=report.n,
        accuracy=report.accuracy,
        accuracy_scored_only=report.accuracy_scored_only,
        macro_f1=report.macro_f1,
        abstain_rate=report.abstain_rate,
        abstain_by_class=report.abstain_by_class,
        per_class=report.per_class,
        caveat=report.caveat,
    )
