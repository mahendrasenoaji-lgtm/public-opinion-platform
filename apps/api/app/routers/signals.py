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

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Select, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.connectors import (
    Connector,
    ConnectorError,
    CredentialMissing,
    RawItem,
    available,
    get_connector,
)
from app.deps import (
    RANK,
    ActorSession,
    CollectorPrincipal,
    CurrentActor,
    CurrentUser,
    Role,
    TenantSession,
    require_role,
)
from app.models.governance import AuditLog
from app.models.measurement import SignalSource as ModelSignalSource
from app.models.project import Project
from app.models.signal import DataSource, Mention
from app.schemas.common import Metric, SignalSource
from app.services import sentiment as sentiment_svc
from app.services.auth import MAX_COLLECTOR_TOKEN_DAYS, create_collector_token
from app.services.ingestion import concentration_ratio
from app.services.pipeline import IncomingItem, prepare_batch
from app.services.sentiment_eval import LABELED

router = APIRouter(tags=["signals"])
logger = logging.getLogger(__name__)

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
    optional_fields: list[str]
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
    url: str | None = Field(
        default=None,
        max_length=2048,
        description=(
            "URL ke halaman aslinya, untuk validasi manual -- BUKAN pengganti "
            "external_id (yang tetap wajib jadi identitas unik, sekalipun "
            "keduanya kebetulan sama untuk sumber yang guid-nya memang URL)."
        ),
    )
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
    reply_to_handle: str | None = Field(
        default=None,
        description=(
            "Akun yang DIBALAS item ini, kalau sumbernya menyatakannya secara "
            "eksplisit (mis. field referenced_tweets X). Di-hash sama seperti "
            "author_handle. Jangan menebak dari isi teks."
        ),
    )
    quote_of_handle: str | None = Field(
        default=None,
        description="Akun yang DIKUTIP item ini, dengan syarat yang sama seperti reply_to_handle.",
    )
    conversation_id: str | None = Field(default=None)


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


#: Dari mana URL di `source_url` berasal. Dibawa keluar bersama URL-nya,
#: bukan disembunyikan, karena keduanya TIDAK sama kuat: satu disimpan
#: sebagai URL, satunya dipulihkan dari identitas feed. Pembaca yang
#: memverifikasi angka berhak tahu yang mana.
UrlOrigin = Literal["kolom_url", "guid_feed"]


def _recover_source_url(url: str | None, external_id: str) -> tuple[str | None, UrlOrigin | None]:
    """URL terbaik yang tersedia untuk satu mention, beserta asal-usulnya.

    Sebagian besar feed RSS Indonesia (Antara, CNBC Indonesia, Republika,
    Sindonews — keempatnya diperiksa 2026-09-12) menulis `<guid>` yang PERSIS
    sama dengan `<link>`, yaitu URL artikelnya. `connectors/rss.py` menyimpan
    guid itu ke `external_id` sejak awal, sementara kolom `url` baru ada
    2026-09-11. Akibatnya ratusan item lama tampil "tidak ada URL sumber"
    padahal URL-nya ada di baris yang sama, di kolom sebelah.

    Ini PEMULIHAN, bukan tebakan — bedanya penting dan itu sebabnya fungsi
    ini tidak menyentuh apa pun selain URL absolut yang memang tersimpan:

    - guid yang bukan URL absolut (id numerik, `tag:` URI, handle akun dari
      konektor non-RSS) dikembalikan sebagai None. Tidak ada yang dirangkai,
      ditempel ke domain, atau dicarikan padanannya.
    - kolom `url` selalu menang kalau terisi. Yang dipulihkan hanya mengisi
      yang kosong, tidak pernah menimpa.

    Sengaja dihitung saat baca, bukan di-backfill ke tabel: menulis ulang
    kolom `url` pada data riset yang sudah ada adalah perubahan yang tidak
    bisa dibatalkan tanpa jejak, dan nilainya sama saja dengan menghitungnya
    di sini. Kalau nanti backfill memang diinginkan, fungsi ini yang jadi
    acuannya.
    """
    if url:
        return url, "kolom_url"
    if external_id.startswith(("http://", "https://")):
        return external_id, "guid_feed"
    return None, None


class MentionOut(BaseModel):
    """Satu item mentah, untuk validasi manual lewat GET .../mentions."""

    id: UUID
    external_id: str
    url: str | None
    #: URL terbaik yang tersedia + asalnya. `url` di atas sengaja dibiarkan
    #: apa adanya (NULL tetap NULL) supaya keadaan tabel tetap terbaca dari
    #: respons ini; yang dipakai UI untuk menaut adalah dua field ini.
    source_url: str | None
    source_url_origin: UrlOrigin | None
    text: str
    published_at: datetime
    source: SignalSource
    connector: str
    engagement: int
    sentiment: float | None


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
            optional_fields=list(info.optional_fields),
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
    try:
        connector.validate_config(body.config)
    except ConnectorError as e:
        raise HTTPException(422, str(e)) from e

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
                url=p.url,
                lang=p.lang,
                engagement=p.engagement,
                reach_est=p.reach_est,
                province_code=p.province_code,
                sentiment=None if p.sentiment is None else Decimal(str(p.sentiment)),
                emotion=p.emotion or None,
                reply_to_hash=p.reply_to_hash,
                quote_of_hash=p.quote_of_hash,
                conversation_id=p.conversation_id,
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
                url=i.url,
                province_code=i.province_code,
                reply_to_handle=i.reply_to_handle,
                quote_of_handle=i.quote_of_handle,
                conversation_id=i.conversation_id,
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

    fetched = await _fetch_source(source, since_days=since_days, limit=limit)
    if isinstance(fetched.error, CredentialMissing):
        # 503, bukan 500: ini keadaan deployment yang bisa diperbaiki operator,
        # dan pesannya menyebut env var mana yang kurang.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(fetched.error))
    if fetched.error is not None:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(fetched.error))

    return await _store_fetched(
        session, source=source, fetched=fetched, actor_id=user.user_id, via="user"
    )


@dataclass(slots=True)
class _Fetched:
    """Hasil pengambilan satu sumber, sebelum menyentuh database."""

    connector: Connector | None
    items: list[RawItem]
    error: ConnectorError | None


async def _fetch_source(source: DataSource, *, since_days: int, limit: int) -> _Fetched:
    """Ambil dari jaringan saja — tidak ada query database di sini.

    Dipisah dari penyimpanan supaya `collect-all` bisa mengambil semua feed
    bersamaan (menunggu jaringan) lalu menyimpannya berurutan di satu sesi
    (satu sesi SQLAlchemy tidak boleh dipakai bersamaan).
    """
    try:
        connector = get_connector(source.connector)
    except ConnectorError as e:
        return _Fetched(None, [], e)
    try:
        items = await connector.fetch(
            dict(source.config),
            since=datetime.now(UTC) - timedelta(days=since_days),
            limit=limit,
        )
    except ConnectorError as e:
        return _Fetched(connector, [], e)
    except Exception as e:  # noqa: BLE001
        # Satu konektor yang melempar sesuatu di luar kontraknya (mis.
        # httpx.InvalidURL, yang bukan turunan HTTPError) tidak boleh
        # menjatuhkan pengambilan sumber-sumber lain di collect-all. Tetap
        # dicatat lengkap di log, dan dilaporkan ke pemanggil sebagai gagal.
        logger.exception("konektor %s melempar di luar kontrak", source.connector)
        return _Fetched(
            connector, [], ConnectorError(f"kesalahan tak terduga ({type(e).__name__}): {e}")
        )
    return _Fetched(connector, items, None)


async def _store_fetched(
    session: TenantSession,
    *,
    source: DataSource,
    fetched: _Fetched,
    actor_id: UUID,
    via: Literal["user", "collector_token"],
    token_id: UUID | None = None,
    write_audit: bool = True,
) -> IngestResult:
    """`write_audit=False` dipakai oleh `collect_all` — lihat komentar di sana.

    Bukan berarti panggilan itu tidak diaudit: `collect_all` menulis SATU
    baris ringkasan untuk semua sumber setelah loop-nya selesai, bukan satu
    baris per sumber di sini.
    """
    result = await _store(
        session,
        org_id=source.org_id,
        project_id=source.project_id,
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
                url=r.url,
                province_code=r.province_code,
                reply_to_handle=r.reply_to_handle,
                quote_of_handle=r.quote_of_handle,
                conversation_id=r.conversation_id,
            )
            for r in fetched.items
        ],
        accept_langs=None,
    )
    source.last_sync_at = datetime.now(UTC)
    if write_audit:
        metadata = {"stored": str(result.stored), "connector": source.connector, "via": via}
        if token_id is not None:
            metadata["token_id"] = str(token_id)
        session.add(
            AuditLog(
                org_id=source.org_id,
                actor_id=actor_id,
                action="collect",
                entity="data_source",
                entity_id=source.id,
                metadata_=metadata,
            )
        )
    return result


# ------------------------------------------------ pengumpulan terjadwal ----
#
# Kenapa ini ada (2026-09-15): akumulasi harian proyek riset MBG dijalankan
# dari routine cloud yang mengambil feed dari sandbox-nya sendiri. Empat hari
# berturut-turut SEMUA feed membalas 403 dari jaringan sandbox itu — dan
# routine-nya tetap berstatus "berhasil", karena yang dinilai hanya apakah
# agennya selesai. Pengambilan dipindah ke sini, ke API yang memang memiliki
# konektornya, dan dipicu penjadwal di luar (GitHub Actions — Render free
# tidur saat sepi, jadi penjadwal di dalam proses tidak akan pernah bangun).
#
# Penjadwal itu butuh kredensial. Menaruh token sesi pengguna di secret CI
# berarti mesin memegang SEMUA kewenangan pengguna selama 30 hari; menaruh
# password-nya lebih buruk. Token pengumpul hanya bisa satu hal: menarik
# sumber yang SUDAH didaftarkan peneliti, untuk satu proyek.


class CollectorTokenCreate(BaseModel):
    days: int = Field(default=180, ge=1, le=MAX_COLLECTOR_TOKEN_DAYS)


class CollectorTokenOut(BaseModel):
    token: str
    token_id: UUID
    project_id: UUID
    expires_at: datetime
    scope: str


class CollectorTokenStatus(BaseModel):
    active: bool
    token_id: UUID | None
    issued_at: datetime | None
    expires_at: datetime | None
    issued_by: UUID | None


class SourceCollectOut(BaseModel):
    source_id: UUID
    connector: str
    label: str | None
    ok: bool
    error: str | None
    #: Berapa item yang ditawarkan sumber dan berapa yang lolos penyaring
    #: tanggal + kata kunci. None kalau konektornya tidak melaporkan.
    offered: int | None
    matched: int | None
    oldest_offered: datetime | None
    previous_sync_at: datetime | None
    #: True bila item tertua yang masih ditawarkan sumber lebih baru dari
    #: pengambilan sukses sebelumnya: ada berita di antaranya yang sudah jatuh
    #: dari feed dan TIDAK tersimpan. Jadwal perlu dirapatkan untuk sumber ini.
    coverage_gap: bool
    result: IngestResult | None


class CollectAllOut(BaseModel):
    project_id: UUID
    via: Literal["user", "collector_token"]
    sources_total: int
    sources_ok: int
    sources_failed: int
    sources_inactive: int
    coverage_gaps: int
    stored_total: int
    results: list[SourceCollectOut]


async def _current_collector_token(
    session: TenantSession, project_id: UUID
) -> AuditLog | None:
    """Penerbitan token pengumpul yang masih berlaku untuk proyek ini, kalau ada.

    Tidak ada tabel token: yang berlaku adalah entri `issue` TERAKHIR di audit
    log, selama tidak disusul `revoke`. Menerbitkan token baru otomatis
    mematikan yang lama. Dipilih supaya fitur ini tidak butuh migrasi
    Supabase — dan audit log memang tempat keputusan "siapa memberi mesin
    akses apa, kapan" seharusnya tercatat.
    """
    row = (
        await session.execute(
            select(AuditLog)
            .where(
                AuditLog.entity == "collector_token",
                AuditLog.entity_id == project_id,
                AuditLog.action.in_(("issue", "revoke")),
            )
            .order_by(AuditLog.at.desc(), AuditLog.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None or row.action != "issue":
        return None
    expires = datetime.fromisoformat(str(row.metadata_.get("expires_at")))
    if expires <= datetime.now(UTC):
        return None
    return row


@router.post(
    "/projects/{project_id}/signals/collector-token",
    response_model=CollectorTokenOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.RESEARCH_DIRECTOR))],
)
async def issue_collector_token(
    project_id: UUID, body: CollectorTokenCreate, session: TenantSession, user: CurrentUser
) -> CollectorTokenOut:
    """Terbitkan token untuk penjadwal pengumpulan. Token lama langsung tidak berlaku.

    Token hanya ditampilkan SEKALI, di respons ini. Yang tersimpan hanya
    identitasnya dan masa berlakunya.
    """
    project = (
        await session.execute(select(Project.id).where(Project.id == project_id))
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyek tidak ditemukan.")

    token_id = uuid4()
    expires_at = datetime.now(UTC) + timedelta(days=body.days)
    token = create_collector_token(
        user_id=user.user_id,
        org_id=user.org_id,
        project_id=project_id,
        token_id=token_id,
        expires_at=expires_at,
    )
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="issue",
            entity="collector_token",
            entity_id=project_id,
            metadata_={"token_id": str(token_id), "expires_at": expires_at.isoformat()},
        )
    )
    return CollectorTokenOut(
        token=token,
        token_id=token_id,
        project_id=project_id,
        expires_at=expires_at,
        scope=(
            "Hanya POST /projects/{id}/signals/collect-all untuk proyek ini. "
            "Tidak bisa membaca data, mengubah sumber, atau dipakai sebagai sesi."
        ),
    )


@router.get(
    "/projects/{project_id}/signals/collector-token",
    response_model=CollectorTokenStatus,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def collector_token_status(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> CollectorTokenStatus:
    row = await _current_collector_token(session, project_id)
    if row is None:
        return CollectorTokenStatus(
            active=False, token_id=None, issued_at=None, expires_at=None, issued_by=None
        )
    return CollectorTokenStatus(
        active=True,
        token_id=UUID(str(row.metadata_["token_id"])),
        issued_at=row.at,
        expires_at=datetime.fromisoformat(str(row.metadata_["expires_at"])),
        issued_by=row.actor_id,
    )


@router.delete(
    "/projects/{project_id}/signals/collector-token",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.RESEARCH_DIRECTOR))],
)
async def revoke_collector_token(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> None:
    """Cabut token pengumpul proyek ini. Penjadwal akan mulai menerima 401."""
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="revoke",
            entity="collector_token",
            entity_id=project_id,
            metadata_={},
        )
    )


@router.post("/projects/{project_id}/signals/collect-all", response_model=CollectAllOut)
async def collect_all(
    project_id: UUID,
    session: ActorSession,
    actor: CurrentActor,
    since_days: int = Query(default=2, ge=1, le=90),
    limit: int = Query(default=100, ge=1, le=MAX_INGEST_ITEMS),
) -> CollectAllOut:
    """Tarik SEMUA sumber aktif proyek ini dalam satu panggilan.

    Diterima dari pengguna (RESEARCHER ke atas) atau token pengumpul milik
    proyek ini. Kegagalan satu sumber tidak menggagalkan yang lain — ia
    dilaporkan per sumber, lengkap dengan pesannya, dan `sources_failed` di
    ringkasan. Penjadwal yang memanggil ini WAJIB membaca angka itu: status
    200 berarti permintaan diproses, bukan bahwa semua feed berhasil.
    """
    if isinstance(actor, CollectorPrincipal):
        if actor.project_id != project_id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Token pengumpul ini untuk proyek lain."
            )
        current = await _current_collector_token(session, project_id)
        if current is None or current.metadata_.get("token_id") != str(actor.token_id):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Token pengumpul sudah dicabut, diganti, atau kedaluwarsa.",
            )
        actor_id, via, token_id = actor.issuer_id, "collector_token", actor.token_id
    else:
        if RANK[actor.role] < RANK[Role.RESEARCHER]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Tindakan ini memerlukan peran {Role.RESEARCHER.value} atau lebih tinggi.",
            )
        actor_id, via, token_id = actor.user_id, "user", None

    sources = (
        (await session.execute(select(DataSource).where(DataSource.project_id == project_id)))
        .scalars()
        .all()
    )
    active = [s for s in sources if s.is_active]
    fetched_all = await asyncio.gather(
        *(_fetch_source(s, since_days=since_days, limit=limit) for s in active)
    )

    results: list[SourceCollectOut] = []
    for source, fetched in zip(active, fetched_all, strict=True):
        previous = source.last_sync_at
        stats = fetched.connector.last_fetch if fetched.connector is not None else None
        label = source.config.get("label") or source.config.get("feed_url")
        if fetched.error is not None:
            results.append(
                SourceCollectOut(
                    source_id=source.id,
                    connector=source.connector,
                    label=label,
                    ok=False,
                    error=str(fetched.error),
                    offered=None,
                    matched=None,
                    oldest_offered=None,
                    previous_sync_at=previous,
                    coverage_gap=False,
                    result=None,
                )
            )
            continue
        stored = await _store_fetched(
            session,
            source=source,
            fetched=fetched,
            actor_id=actor_id,
            via=via,
            token_id=token_id,
            write_audit=False,
        )
        oldest = stats.oldest_offered if stats is not None else None
        results.append(
            SourceCollectOut(
                source_id=source.id,
                connector=source.connector,
                label=label,
                ok=True,
                error=None,
                offered=stats.offered if stats is not None else None,
                matched=stats.matched if stats is not None else None,
                oldest_offered=oldest,
                previous_sync_at=previous,
                coverage_gap=coverage_gap(oldest_offered=oldest, previous_sync_at=previous),
                result=stored,
            )
        )

    # Satu baris audit untuk seluruh panggilan, bukan satu per sumber (K5,
    # 2026-09-16): pada jadwal 30 menit x 14 sumber ini dulu ~670 baris/hari
    # (~245rb/tahun) — cukup untuk mendekati batas 500 MB Supabase free tier
    # dalam hitungan tahun tanpa pernah dipangkas. Ringkasan per sumber tetap
    # lengkap di `metadata_`, jadi tidak ada informasi yang hilang, cuma
    # digabung jadi satu baris per run.
    session.add(
        AuditLog(
            org_id=actor.org_id,
            actor_id=actor_id,
            action="collect_all",
            entity="project",
            entity_id=project_id,
            metadata_={
                "via": via,
                "token_id": str(token_id) if token_id is not None else None,
                "sources_total": len(sources),
                "sources_ok": sum(1 for r in results if r.ok),
                "sources_failed": sum(1 for r in results if not r.ok),
                "sources": [
                    {
                        "source_id": str(r.source_id),
                        "connector": r.connector,
                        "ok": r.ok,
                        "error": r.error,
                        "stored": r.result.stored if r.result is not None else None,
                        "coverage_gap": r.coverage_gap,
                    }
                    for r in results
                ],
            },
        )
    )

    return CollectAllOut(
        project_id=project_id,
        via=via,
        sources_total=len(sources),
        sources_ok=sum(1 for r in results if r.ok),
        sources_failed=sum(1 for r in results if not r.ok),
        sources_inactive=len(sources) - len(active),
        coverage_gaps=sum(1 for r in results if r.coverage_gap),
        stored_total=sum(r.result.stored for r in results if r.result is not None),
        results=results,
    )


def coverage_gap(*, oldest_offered: datetime | None, previous_sync_at: datetime | None) -> bool:
    """Apakah ada rentang waktu yang pasti tidak terlihat sejak pengambilan terakhir.

    Tidak bisa dinilai (False) kalau sumber belum pernah ditarik atau tidak
    melaporkan apa yang ditawarkannya. False di sini berarti "tidak ada bukti
    celah", bukan jaminan lengkap: feed bisa saja menghapus item di tengah.
    """
    if oldest_offered is None or previous_sync_at is None:
        return False
    return oldest_offered > previous_sync_at


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


@router.get("/projects/{project_id}/mentions", response_model=list[MentionOut])
async def list_mentions(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=1, le=365),
    source: SignalSource | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[MentionOut]:
    """Daftar item mentah, satu per satu, untuk validasi manual.

    Ini SATU-SATUNYA endpoint di paket ini yang mengembalikan konten mentah
    alih-alih agregat -- ditambahkan atas kebutuhan akuntabilitas riset:
    setiap angka di dashboard bisa ditelusuri balik ke sumbernya lewat `url`
    (kalau ada -- lihat catatan kolom `url` di `models/signal.py`), bukan
    cuma dipercaya begitu saja. Bukan pengganti Signal Monitor/Topic
    Discovery, yang tetap sumber kebenaran untuk agregat.

    `url` bisa `None` untuk mention yang diingest sebelum kolom ini ada
    (2026-09-11) atau dari sumber yang memang tidak punya URL publik. Yang
    dipakai untuk menaut adalah `source_url` + `source_url_origin`, bukan
    `url` mentah -- lihat `_recover_source_url`: untuk item RSS lama, URL
    aslinya masih tersimpan di `external_id` (guid feed = permalink artikel)
    dan itu dipulihkan di sini. Kalau keduanya kosong, tetap tampilkan
    "tidak ada URL sumber"; jangan ditebak dari field lain.
    """
    since, until = _window(days)
    query = _scoped(select(Mention), project_id, since, until)
    if source is not None:
        query = query.where(Mention.source == ModelSignalSource(source.value))
    query = query.order_by(Mention.published_at.desc()).limit(limit).offset(offset)
    out: list[MentionOut] = []
    for m in (await session.execute(query)).scalars():
        source_url, origin = _recover_source_url(m.url, m.external_id)
        out.append(
            MentionOut(
                id=m.id,
                external_id=m.external_id,
                url=m.url,
                source_url=source_url,
                source_url_origin=origin,
                text=m.text,
                published_at=m.published_at,
                source=SignalSource(m.source.value),
                connector=m.connector,
                engagement=m.engagement,
                sentiment=float(m.sentiment) if m.sentiment is not None else None,
            )
        )
    return out


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
