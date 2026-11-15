"""Kinerja Komunikasi: keaktifan situs web resmi lembaga.

Menjawab satu pertanyaan sempit: apa saja yang terbit untuk publik di situs
resmi sebuah lembaga, seberapa sering, dan kapan terakhir. Butir masuk lewat
tiga jalur: (1) feed RSS/Atom atau sitemap bertanggal milik situs itu, (2)
halaman daftar berita yang alamatnya didaftarkan pengguna, bila (1) tidak ada
(pengecualian tertulis di `connectors/base.py`), (3) unggahan manual.

Yang disimpan hanya judul, alamat, tanggal, dan kategori. Isi artikel tidak
diambil. Halaman ini tidak menilai mutu informasi dan tidak menyimpulkan
sebab sebuah situs sepi.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import ProgrammingError

from app.connectors import official_site as osite
from app.connectors.base import ConnectorError
from app.deps import CurrentUser, Role, TenantSession, require_role
from app.models.comm import OfficialSite, OfficialSiteItem
from app.models.governance import AuditLog
from app.routers.comm_performance import _require_project
from app.services import site_activity as sa

router = APIRouter(prefix="/projects/{project_id}/comm-performance", tags=["comm-performance"])

MIGRATION = "db/migrations/2026-11-15b-kinerja-situs-resmi.sql"
#: Tanggal terbit dibaca sebagai hari WIB.
LOCAL_OFFSET = timedelta(hours=7)
MAX_MANUAL_ITEMS = 500
MAX_SITES = 30
LATEST_ITEMS = 8
#: Jarak minimal antar-pembacaan satu situs, supaya situs lembaga tidak dibebani.
READ_COOLDOWN = timedelta(hours=1)

LIMITATIONS = [
    "Yang dihitung hanya butir yang TERCATAT di proyek ini. Halaman daftar berita biasanya "
    "hanya menampilkan 10-20 butir terbaru, jadi hitungan 30 dan 90 hari baru lengkap setelah "
    "situs dibaca berkala; sebelum itu angkanya batas bawah, bukan jumlah sebenarnya.",
    "Butir dari halaman daftar dipasangkan dengan tanggal terdekat di halaman itu. Pada tata "
    "letak yang tidak biasa pasangan bisa keliru; cek contoh butir terbaru terhadap situsnya.",
    "\"Sepi\" berarti tidak ada terbitan tercatat selama "
    f"{sa.QUIET_DAYS} hari sampai pengambilan data terakhir. Itu belum tentu berarti lembaganya "
    "tidak berkomunikasi: bisa lewat kanal lain, atau datanya belum diambil.",
    "Kategori ditebak dari alamat butir (mis. /siaran-pers/), bukan dari isinya, kecuali "
    "diisi saat unggah.",
    "Jumlah terbitan bukan ukuran mutu. Halaman ini tidak menilai isi dan tidak memeringkat "
    "lembaga.",
]


@asynccontextmanager
async def _tables() -> AsyncIterator[None]:
    try:
        yield
    except ProgrammingError as e:
        if "does not exist" in str(e.orig) or "UndefinedTable" in type(e.orig).__name__:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Tabel situs resmi belum ada di basis data. Jalankan {MIGRATION}.",
            ) from e
        raise


def _clean(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("tidak boleh kosong")
    return v


class SiteIn(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=4, max_length=300)
    #: Halaman daftar berita/siaran pers; dibaca bila situs tanpa feed.
    list_urls: list[str] = Field(default_factory=list, max_length=osite.MAX_LIST_PAGES)

    _strip = field_validator("subject", "url")(_clean)


class ListUrlsIn(BaseModel):
    list_urls: list[str] = Field(max_length=osite.MAX_LIST_PAGES)


class ManualItem(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    title: str | None = Field(default=None, max_length=500)
    published_at: datetime
    category: str | None = None

    @field_validator("url")
    @classmethod
    def _http(cls, v: str) -> str:
        v = v.strip()
        if not v.lower().startswith(("http://", "https://")):
            raise ValueError("Alamat butir harus diawali http:// atau https://.")
        return v

    @field_validator("published_at")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        # Tanpa zona dianggap WIB, seperti yang tertulis di situs lembaga.
        return v if v.tzinfo else v.replace(tzinfo=UTC) - LOCAL_OFFSET

    @field_validator("category")
    @classmethod
    def _known(cls, v: str | None) -> str | None:
        v = (v or "").strip().lower().replace(" ", "_") or None
        if v is not None and v not in sa.CATEGORY_KEYS:
            known = ", ".join(sorted(sa.CATEGORY_KEYS))
            raise ValueError(f"Kategori tidak dikenal. Pilihan: {known}.")
        return v


class ManualItemsIn(BaseModel):
    items: list[ManualItem] = Field(min_length=1, max_length=MAX_MANUAL_ITEMS)


class WeekOut(BaseModel):
    start: date
    n: int


class ItemOut(BaseModel):
    url: str
    title: str | None
    published_at: datetime
    category: str
    origin: str


class SiteOut(BaseModel):
    id: UUID
    subject: str
    base_url: str
    feed_kind: str
    source_url: str | None
    list_urls: list[str]
    check_notes: list[str]
    checked_at: datetime | None
    #: Kapan butir terakhir kali ditambahkan (otomatis atau manual).
    last_captured_at: datetime | None
    n_total: int
    n_window: int
    n_30: int
    last_published: date | None
    days_since_last: int | None
    longest_gap_days: int | None
    median_gap_days: float | None
    active_days: int
    weeks_without: int
    quiet: bool
    status: str
    weeks: list[WeekOut]
    categories: list[tuple[str, str, int]]
    origins: dict[str, int]
    latest: list[ItemOut]


class SitesOut(BaseModel):
    source: str = "OFFICIAL_SITE"
    method: str
    window_days: int
    quiet_days: int
    today: date
    sites: list[SiteOut]
    limitations: list[str]


class StoreResult(BaseModel):
    received: int
    stored: int
    updated: int


class ReadResult(BaseModel):
    site_id: UUID
    feed_kind: str
    source_url: str | None
    notes: list[str]
    n_requests: int
    result: StoreResult


async def _store(
    session: TenantSession, site: OfficialSite, rows: list[dict[str, Any]]
) -> StoreResult:
    """Upsert butir; kembalikan berapa yang baru dan berapa yang diperbarui."""
    by_url = {r["url"]: r for r in rows}
    if not by_url:
        return StoreResult(received=len(rows), stored=0, updated=0)
    existing = set(
        (
            await session.execute(
                select(OfficialSiteItem.url).where(
                    OfficialSiteItem.site_id == site.id, OfficialSiteItem.url.in_(list(by_url))
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    values = [
        {
            "org_id": site.org_id,
            "project_id": site.project_id,
            "site_id": site.id,
            "captured_at": now,
            **r,
        }
        for r in by_url.values()
    ]
    stmt = pg_insert(OfficialSiteItem).values(values)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["site_id", "url"],
            set_={
                k: stmt.excluded[k]
                for k in ("title", "published_at", "category", "origin", "captured_at")
            },
        )
    )
    return StoreResult(
        received=len(rows), stored=len(by_url) - len(existing), updated=len(existing)
    )


async def _read_and_store(session: TenantSession, site: OfficialSite) -> ReadResult:
    try:
        reading = await osite.read_site(site.base_url, list_urls=list(site.list_urls or []))
    except ConnectorError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    notes = list(reading.notes)
    kind = reading.kind
    items = reading.items
    if kind == "sitemap" and sa.dates_look_generated([i.published_at for i in items]):
        notes.append(
            f"Tanggal di sitemap hampir semuanya sama ({len(items)} alamat), jadi itu cap waktu "
            "pembuatan berkas, bukan tanggal terbit. Tidak dipakai."
        )
        kind, items = "none", []
    if kind == "none":
        notes.append(
            "Situs ini belum terbaca otomatis. Daftarkan alamat halaman daftar beritanya, atau "
            "masukkan butirnya lewat unggahan manual."
        )
    site.feed_kind = kind
    site.source_url = reading.source_url if kind != "none" else None
    site.check_notes = notes
    site.checked_at = datetime.now(UTC)
    result = await _store(
        session,
        site,
        [
            {
                "url": i.url,
                "title": i.title,
                "published_at": i.published_at,
                "category": sa.guess_category(i.url),
                "origin": kind,
            }
            for i in items
        ],
    )
    return ReadResult(
        site_id=site.id,
        feed_kind=kind,
        source_url=site.source_url,
        notes=notes,
        n_requests=reading.n_requests,
        result=result,
    )


async def _site(session: TenantSession, project_id: UUID, site_id: UUID) -> OfficialSite:
    row = (
        await session.execute(
            select(OfficialSite).where(
                OfficialSite.id == site_id, OfficialSite.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Situs tidak ditemukan.")
    return row


def _cooldown(site: OfficialSite) -> None:
    if site.checked_at and datetime.now(UTC) - site.checked_at < READ_COOLDOWN:
        minutes = int(READ_COOLDOWN.total_seconds() // 60)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Situs ini baru saja dibaca. Tunggu {minutes} menit antar-pembacaan.",
        )


@router.get("/sites", response_model=SitesOut)
async def list_sites(project_id: UUID, session: TenantSession, user: CurrentUser) -> SitesOut:
    """Keaktifan tiap situs resmi yang terdaftar di proyek ini."""
    await _require_project(session, project_id)
    async with _tables():
        sites = (
            (
                await session.execute(
                    select(OfficialSite)
                    .where(OfficialSite.project_id == project_id)
                    .order_by(OfficialSite.subject)
                )
            )
            .scalars()
            .all()
        )
        items = (
            (
                await session.execute(
                    select(OfficialSiteItem)
                    .where(OfficialSiteItem.project_id == project_id)
                    .order_by(OfficialSiteItem.published_at.desc())
                )
            )
            .scalars()
            .all()
        )
    today = (datetime.now(UTC) + LOCAL_OFFSET).date()
    labels = dict(sa.CATEGORIES)
    out: list[SiteOut] = []
    for s in sites:
        mine = [i for i in items if i.site_id == s.id]
        act = sa.summarize(
            (((i.published_at + LOCAL_OFFSET).date(), i.category) for i in mine), today=today
        )
        origins: dict[str, int] = {}
        for i in mine:
            origins[i.origin] = origins.get(i.origin, 0) + 1
        out.append(
            SiteOut(
                id=s.id,
                subject=s.subject,
                base_url=s.base_url,
                feed_kind=s.feed_kind,
                source_url=s.source_url,
                list_urls=list(s.list_urls or []),
                check_notes=list(s.check_notes or []),
                checked_at=s.checked_at,
                last_captured_at=max((i.captured_at for i in mine), default=None),
                n_total=act.n_total,
                n_window=act.n_window,
                n_30=act.n_30,
                last_published=act.last_published,
                days_since_last=act.days_since_last,
                longest_gap_days=act.longest_gap_days,
                median_gap_days=act.median_gap_days,
                active_days=act.active_days,
                weeks_without=act.weeks_without,
                quiet=act.quiet,
                status=sa.status_label(act),
                weeks=[WeekOut(start=w.start, n=w.n) for w in act.weeks],
                categories=[(k, labels[k], n) for k, n in act.categories],
                origins=origins,
                latest=[
                    ItemOut(
                        url=i.url,
                        title=i.title,
                        published_at=i.published_at,
                        category=i.category,
                        origin=i.origin,
                    )
                    for i in mine[:LATEST_ITEMS]
                ],
            )
        )
    return SitesOut(
        method=(
            f"hitungan butir bertanggal per situs dalam {sa.WINDOW_DAYS} hari terakhir (hari "
            "WIB): jumlah per minggu, hari sejak terbitan terakhir, jeda terpanjang, median jeda"
        ),
        window_days=sa.WINDOW_DAYS,
        quiet_days=sa.QUIET_DAYS,
        today=today,
        sites=out,
        limitations=LIMITATIONS,
    )


@router.post(
    "/sites",
    response_model=ReadResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def add_site(
    project_id: UUID, body: SiteIn, session: TenantSession, user: CurrentUser
) -> ReadResult:
    """Daftarkan situs resmi sebuah lembaga, lalu langsung coba baca."""
    await _require_project(session, project_id)
    try:
        base_url = osite.normalize_base(body.url)
        list_urls = osite.normalize_list_urls(body.list_urls, base_url)
    except ConnectorError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    async with _tables():
        count, duplicate = (
            await session.execute(
                select(
                    func.count(),
                    func.count().filter(OfficialSite.base_url == base_url),
                ).where(OfficialSite.project_id == project_id)
            )
        ).one()
        if duplicate:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Situs itu sudah terdaftar di proyek ini."
            )
        if count >= MAX_SITES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"Paling banyak {MAX_SITES} situs per proyek."
            )
        site = OfficialSite(
            org_id=user.org_id,
            project_id=project_id,
            subject=body.subject,
            base_url=base_url,
            list_urls=list_urls,
            created_by=user.user_id,
        )
        session.add(site)
        await session.flush()
        result = await _read_and_store(session, site)
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="comm_site_add",
            entity="official_site",
            entity_id=site.id,
            metadata_={"base_url": base_url, "feed_kind": result.feed_kind,
                       "stored": result.result.stored},
        )
    )
    return result


@router.post(
    "/sites/{site_id}/refresh",
    response_model=ReadResult,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def refresh_site(
    project_id: UUID, site_id: UUID, session: TenantSession, user: CurrentUser
) -> ReadResult:
    """Baca ulang situs. Butir lama tetap; yang baru ditambahkan."""
    async with _tables():
        site = await _site(session, project_id, site_id)
        _cooldown(site)
        result = await _read_and_store(session, site)
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="comm_site_refresh",
            entity="official_site",
            entity_id=site_id,
            metadata_={"feed_kind": result.feed_kind, "stored": result.result.stored},
        )
    )
    return result


@router.put(
    "/sites/{site_id}/list-urls",
    response_model=ReadResult,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def set_list_urls(
    project_id: UUID, site_id: UUID, body: ListUrlsIn, session: TenantSession, user: CurrentUser
) -> ReadResult:
    """Setel halaman daftar berita sebuah situs, lalu langsung baca."""
    async with _tables():
        site = await _site(session, project_id, site_id)
        try:
            site.list_urls = osite.normalize_list_urls(body.list_urls, site.base_url)
        except ConnectorError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
        result = await _read_and_store(session, site)
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="comm_site_list_urls",
            entity="official_site",
            entity_id=site_id,
            metadata_={"list_urls": site.list_urls, "stored": result.result.stored},
        )
    )
    return result


@router.post(
    "/sites/{site_id}/items",
    response_model=StoreResult,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def upload_items(
    project_id: UUID, site_id: UUID, body: ManualItemsIn, session: TenantSession, user: CurrentUser
) -> StoreResult:
    """Unggah butir manual untuk situs yang tidak bisa dibaca otomatis."""
    async with _tables():
        site = await _site(session, project_id, site_id)
        foreign = [i.url for i in body.items if not osite.same_site(i.url, site.base_url)]
        if foreign:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"{len(foreign)} alamat bukan dari {site.base_url} (contoh: {foreign[0][:120]}).",
            )
        future = datetime.now(UTC) + timedelta(days=1)
        if any(i.published_at > future for i in body.items):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Ada tanggal terbit di masa depan."
            )
        result = await _store(
            session,
            site,
            [
                {
                    "url": i.url,
                    "title": (i.title or "").strip() or None,
                    "published_at": i.published_at,
                    "category": i.category or sa.guess_category(i.url),
                    "origin": "manual",
                }
                for i in body.items
            ],
        )
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="comm_site_items_upload",
            entity="official_site",
            entity_id=site_id,
            metadata_=result.model_dump(),
        )
    )
    return result


@router.delete(
    "/sites/{site_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def delete_site(
    project_id: UUID, site_id: UUID, session: TenantSession, user: CurrentUser
) -> None:
    """Hapus situs beserta semua butirnya dari proyek ini."""
    async with _tables():
        site = await _site(session, project_id, site_id)
        session.add(
            AuditLog(
                org_id=user.org_id,
                actor_id=user.user_id,
                action="comm_site_delete",
                entity="official_site",
                entity_id=site_id,
                metadata_={"base_url": site.base_url, "subject": site.subject},
            )
        )
        await session.execute(delete(OfficialSiteItem).where(OfficialSiteItem.site_id == site_id))
        await session.delete(site)
