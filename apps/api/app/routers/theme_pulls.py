"""Tarik tema (YouTube, TikTok, Instagram): satu tombol, server mengerjakan sendiri sampai selesai.

Alur dan batasnya dijelaskan di ``app/services/theme_pull.py``. File ini berisi
endpoint dan pekerja latar belakang.

## Kenapa pekerja di dalam proses, dan apa akibatnya

Render free tidak punya worker terpisah dan tidur sesudah ±15 menit tanpa
permintaan masuk. Karena itu:

- pekerjaan dikerjakan ``asyncio`` task di proses API, SATU pekerjaan sekali
  jalan untuk seluruh server (menjaga memori 512 MB dan kuota bersama);
- setiap langkah kecil (satu halaman API) di-commit sendiri, jadi server yang
  mati di tengah tidak membuang apa pun selain langkah yang sedang berjalan;
- selama ada pekerjaan, pekerja memanggil ``/health`` miliknya sendiri lewat
  URL publik (``RENDER_EXTERNAL_URL``) tiap 4 menit supaya server tidak tidur;
- sesudah deploy ulang atau restart, pekerjaan yang belum selesai dilanjutkan
  saat daftar pekerjaan dibuka lagi (halaman Sinyal memintanya otomatis).
  Server tidak bisa melanjutkannya sendiri saat start: tanpa sesi pengguna ia
  tidak tahu organisasi mana yang harus diikat untuk RLS (R3), dan itu disengaja.

Kuota harian YouTube habis → status ``waiting_quota`` sampai kuota pulih
(sekitar 15.05 WIB), lalu lanjut sendiri bila server masih hidup, atau saat
halaman Sinyal dibuka.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import os
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.connectors import instagram_theme as ig
from app.connectors import tiktok_theme as tt
from app.connectors import youtube_theme as yt
from app.connectors.base import ConnectorError, CredentialMissing
from app.connectors.theme_common import PullRejected
from app.db import SessionLocal
from app.deps import CurrentUser, Role, TenantSession, bind_org, require_role
from app.models.governance import AuditLog
from app.models.measurement import SignalSource as ModelSignalSource
from app.models.signal import DataSource
from app.services import theme_pull as tp
from app.services.pipeline import IncomingItem

router = APIRouter(tags=["signals"])
logger = logging.getLogger(__name__)

#: Dimatikan tes yang tidak ingin pekerja jalan di latar belakang.
AUTOSTART = True
#: Jeda antarlangkah normal — sopan terhadap API dan database.
STEP_PAUSE = 0.3
#: Jeda sesudah galat jaringan sementara, dan berapa kali boleh berturut-turut.
RETRY_PAUSE = 30.0
MAX_RETRIES = 6
#: Pekerjaan aktif per proyek.
MAX_ACTIVE_PER_PROJECT = 3
KEEPALIVE_SECONDS = 240

_tasks: dict[UUID, asyncio.Task[None]] = {}
_one_at_a_time = asyncio.Semaphore(1)


# ------------------------------------------------------------- skema ----


Platform = Literal["youtube", "tiktok", "instagram"]


def platform_configured(key: str) -> bool:
    if key == tp.TIKTOK:
        return tt.configured()
    if key == tp.INSTAGRAM:
        return ig.configured()
    return bool(get_settings().youtube_api_key)


class ThemeCreate(BaseModel):
    platform: Platform = "youtube"
    queries: str = Field(min_length=1, max_length=700)
    start: date
    end: date
    max_videos: int = Field(default=tp.DEFAULT_MAX_VIDEOS, ge=1, le=tp.MAX_MAX_VIDEOS)
    include_replies: bool = True
    comments_until_now: bool = False
    keyword_filter: bool = True
    label: str | None = Field(default=None, max_length=120)


class ThemeVideoOut(BaseModel):
    id: str
    title: str
    channel: str
    comment_count: int
    got: int
    state: str
    note: str | None
    url: str | None = None


class ThemePullOut(BaseModel):
    id: UUID
    platform: str
    label: str
    queries: list[str]
    start: date
    end: date
    max_videos: int
    include_replies: bool
    comments_until_now: bool
    keyword_filter: bool
    status: str
    running: bool
    videos_total: int
    videos_done: int
    videos_skipped: int
    comments_expected: int
    received: int
    stored: int
    outside_window: int
    dropped_by_filter: int
    units: int
    units_remaining_est: int
    current_video: str | None
    error: str | None
    notes: list[str]
    created_at: datetime | None
    updated_at: datetime | None
    finished_at: datetime | None
    resume_at: datetime | None
    videos: list[ThemeVideoOut]
    method: str = tp.METHOD
    limitations: list[str] = Field(default_factory=lambda: list(tp.LIMITATIONS))


class ThemePlatformOut(BaseModel):
    key: str
    label: str
    configured: bool
    env_vars: list[str]
    collects_comments: bool
    max_days_back: int | None
    access_note: str
    method: str
    limitations: list[str]


def _dt(raw: object) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


def _out(source: DataSource) -> ThemePullOut:
    s: dict[str, Any] = source.config or {}
    p = tp.progress(s)
    plat = tp.info(s)
    return ThemePullOut(
        id=source.id,
        platform=plat.key,
        method=plat.method,
        limitations=list(plat.limitations),
        label=str(s.get("label") or ", ".join(s.get("queries") or [])),
        queries=list(s.get("queries") or []),
        start=date.fromisoformat(s["start"]),
        end=date.fromisoformat(s["end"]),
        max_videos=int(s.get("max_videos") or 0),
        include_replies=bool(s.get("include_replies")),
        comments_until_now=bool(s.get("comments_until_now")),
        keyword_filter=bool(s.get("keyword_filter", True)),
        status=p.status,
        running=source.id in _tasks and not _tasks[source.id].done(),
        videos_total=p.videos_total,
        videos_done=p.videos_done,
        videos_skipped=p.videos_skipped,
        comments_expected=p.comments_expected,
        received=p.received,
        stored=p.stored,
        outside_window=int(s.get("outside_window") or 0),
        dropped_by_filter=int(s.get("dropped_by_filter") or 0),
        units=p.units,
        units_remaining_est=tp.estimate_units(s),
        current_video=p.current_video,
        error=s.get("error"),
        notes=list(s.get("notes") or []),
        created_at=_dt(s.get("created_at")),
        updated_at=_dt(s.get("updated_at")),
        finished_at=_dt(s.get("finished_at")),
        resume_at=_dt(s.get("resume_at")),
        videos=[
            ThemeVideoOut(
                id=v["id"],
                title=v["title"],
                channel=v.get("channel", ""),
                comment_count=int(v["comment_count"]),
                got=int(v["got"]),
                state=v["state"],
                note=v.get("note"),
                url=v.get("url"),
            )
            for v in s.get("videos") or []
        ],
    )


# ----------------------------------------------------------- pekerja ----


def ensure_running(job_id: UUID, org_id: UUID) -> None:
    """Jalankan pekerja untuk pekerjaan ini bila belum jalan di proses ini."""
    if not AUTOSTART:
        return
    task = _tasks.get(job_id)
    if task is not None and not task.done():
        return
    _tasks[job_id] = asyncio.create_task(_run(job_id, org_id))


async def _keepalive() -> None:
    base = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not base:
        return
    async with httpx.AsyncClient(timeout=10) as http:
        while True:
            await asyncio.sleep(KEEPALIVE_SECONDS)
            try:
                await http.get(f"{base}/health")
            except httpx.HTTPError:
                logger.warning("keepalive tarik tema gagal")


async def _run(job_id: UUID, org_id: UUID) -> None:
    try:
        async with _one_at_a_time:
            keepalive = asyncio.create_task(_keepalive())
            try:
                async with httpx.AsyncClient(timeout=30.0) as http:
                    while True:
                        delay = await run_step(job_id, org_id, http)
                        if delay is None:
                            return
                        await asyncio.sleep(delay)
            finally:
                keepalive.cancel()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("pekerja tarik tema %s berhenti karena galat", job_id)
    finally:
        _tasks.pop(job_id, None)


async def run_step(job_id: UUID, org_id: UUID, http: httpx.AsyncClient) -> float | None:
    """Kerjakan satu langkah dan commit. None = pekerjaan selesai/tidak ada lagi."""
    async with SessionLocal() as session:
        await bind_org(session, org_id)
        source = (
            await session.execute(
                select(DataSource)
                .where(DataSource.id == job_id, DataSource.connector == tp.KEY)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if source is None:
            return None
        state = copy.deepcopy(source.config or {})
        if state.get("status") not in tp.ACTIVE:
            return None
        now = datetime.now(UTC)
        if not tp.quota_ready(state, now):
            resume = datetime.fromisoformat(state["resume_at"])
            return max(5.0, min(600.0, (resume - now).total_seconds()))
        tp.leave_quota_wait(state)

        delay: float = STEP_PAUSE
        try:
            await _advance(session, source, state, http)
            state["retries"] = 0
        except yt.QuotaExceeded:
            tp.wait_for_quota(state, now)
            state["notes"] = _note(state, f"Kuota habis {now:%d %b %H.%M} UTC; lanjut otomatis.")
        except (CredentialMissing, PullRejected) as e:
            state["stage"] = state["status"]
            state["status"], state["error"] = tp.STATUS_FAILED, str(e)
        except ConnectorError as e:
            state["retries"] = int(state.get("retries") or 0) + 1
            if state["retries"] >= MAX_RETRIES:
                state["stage"] = state["status"]
                state["status"] = tp.STATUS_FAILED
                state["error"] = f"{e} (gagal {MAX_RETRIES}x berturut-turut)"
            else:
                delay = RETRY_PAUSE

        state["updated_at"] = datetime.now(UTC).isoformat()
        if state["status"] in tp.FINAL:
            state["finished_at"] = state["updated_at"]
            source.is_active = False
            session.add(
                AuditLog(
                    org_id=source.org_id,
                    actor_id=None,
                    action="theme_pull_finish",
                    entity="data_source",
                    entity_id=source.id,
                    metadata_={
                        "project_id": str(source.project_id),
                        "status": state["status"],
                        "stored": state.get("stored"),
                        "units": state.get("units"),
                        "videos": len(state.get("videos") or []),
                    },
                )
            )
        source.config = state
        source.last_sync_at = datetime.now(UTC)
        await session.commit()
        return None if state["status"] in tp.FINAL else delay


def _note(state: dict[str, Any], text: str) -> list[str]:
    notes = list(state.get("notes") or [])
    notes.append(text)
    return notes[-10:]


async def _advance(
    session: AsyncSession,
    source: DataSource,
    state: dict[str, Any],
    http: httpx.AsyncClient,
) -> None:
    st = state["status"]
    platform = tp.platform_of(state)
    if st == tp.STATUS_SEARCHING and platform != tp.YOUTUBE:
        await _search_other(session, source, state, http, platform)
        return
    if st == tp.STATUS_SEARCHING:
        lo, hi = tp.window_utc(date.fromisoformat(state["start"]), date.fromisoformat(state["end"]))
        query = state["queries"][state["query_index"]]
        ids, token = await yt.search_page(
            http,
            query=query,
            published_after=tp.rfc3339(lo),
            published_before=tp.rfc3339(hi),
            page_token=state.get("search_token"),
            max_results=tp.search_page_size(state),
        )
        state["units"] += tp.SEARCH_UNITS
        tp.add_candidates(state, ids)
        tp.advance_search(state, next_token=token)
        return

    if st == tp.STATUS_DETAILS:
        batch = tp.next_detail_batch(state)
        if platform != tp.YOUTUBE:
            details = tp.prefetched_details(state, batch)
        else:
            details = await yt.video_details(http, batch) if batch else []
            if batch:
                state["units"] += 1
        tp.accept_details(state, details, len(batch))
        return

    if st == tp.STATUS_COLLECTING:
        tp.settle_video_index(state)
        if state["status"] != tp.STATUS_COLLECTING:
            return
        video = state["videos"][state["video_index"]]
        try:
            if platform == tp.TIKTOK:
                page = await tt.comment_page(
                    http,
                    video_id=video["id"],
                    video_url_=video.get("url") or tt.video_url(None, video["id"]),
                    page_token=state.get("comment_token"),
                    include_replies=bool(state.get("include_replies")),
                )
            else:
                page = await yt.comment_page(
                    http,
                    video_id=video["id"],
                    page_token=state.get("comment_token"),
                    include_replies=bool(state.get("include_replies")),
                )
        except yt.VideoUnavailable as e:
            tp.finish_video(state, skipped_note=str(e))
            return
        state["units"] += page.units
        lo, hi = tp.comment_window(state)
        kept = [i for i in page.items if tp.in_window(i.published_at, lo, hi)]
        video["got"] = int(video["got"]) + len(page.items)
        state["outside_window"] += len(page.items) - len(kept)
        state["received"] += len(kept)
        if kept:
            stored = await _save(session, source, kept)
            state["stored"] += stored
        if page.next_token:
            state["comment_token"] = page.next_token
        else:
            tp.finish_video(state)
        return


async def _search_other(
    session: AsyncSession,
    source: DataSource,
    state: dict[str, Any],
    http: httpx.AsyncClient,
    platform: str,
) -> None:
    """Satu halaman pencarian TikTok/Instagram; detail ikut, jadi langsung disimpan."""
    start, end = date.fromisoformat(state["start"]), date.fromisoformat(state["end"])
    lo, hi = tp.window_utc(start, end)
    query = state["queries"][state["query_index"]]
    if platform == tp.TIKTOK:
        page = await tt.search_page(
            http, query=query, start=start, end=end, lo=lo, hi=hi,
            page_token=state.get("search_token"),
            max_results=tp.search_page_size(state),
        )
    else:
        page = await ig.search_page(
            http, query=query, lo=lo, hi=hi,
            page_token=state.get("search_token"),
            max_results=tp.search_page_size(state),
        )
    state["units"] += page.units
    room = max(0, int(state["max_videos"]) - len(state["candidates"]))
    details = page.details[:room] if not tp.info(state).collects_comments else page.details
    tp.add_prefetched(state, details)
    if page.items:
        keep = {str(d["id"]) for d in details}
        items = [i for i in page.items if i.external_id in keep]
        state["received"] += len(items)
        if items:
            state["stored"] += await _save(session, source, items)
    tp.advance_search(state, next_token=page.next_token)


async def _save(session: AsyncSession, source: DataSource, items: list[Any]) -> int:
    # Impor di sini: signals.py besar dan mengimpor banyak modul; menariknya di
    # tingkat modul membuat urutan impor router rapuh.
    from app.routers.signals import _store

    result = await _store(
        session,
        org_id=source.org_id,
        project_id=source.project_id,
        connector=tp.info(source.config or {}).store_connector,
        source=ModelSignalSource.SOCIAL,
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
            for r in items
        ],
        accept_langs=None,
    )
    return int(result.stored)


# ---------------------------------------------------------- endpoint ----


async def _jobs(session: AsyncSession, project_id: UUID) -> list[DataSource]:
    rows = (
        (
            await session.execute(
                select(DataSource).where(
                    DataSource.project_id == project_id, DataSource.connector == tp.KEY
                )
            )
        )
        .scalars()
        .all()
    )
    return sorted(rows, key=lambda r: str((r.config or {}).get("created_at") or ""), reverse=True)


async def _job(session: AsyncSession, project_id: UUID, job_id: UUID) -> DataSource:
    row = (
        await session.execute(
            select(DataSource).where(
                DataSource.id == job_id,
                DataSource.project_id == project_id,
                DataSource.connector == tp.KEY,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Penarikan tidak ditemukan.")
    return row


def _start_after_commit(job_id: UUID, org_id: UUID) -> None:
    """Pekerja mulai SESUDAH transaksi permintaan ini di-commit.

    `tenant_session` meng-commit saat dependensi ditutup, sesudah respons
    dibentuk; pekerja yang mulai lebih cepat tidak akan menemukan barisnya.
    Jeda singkat cukup — langkah pertama mengunci baris lalu membaca ulang.
    """
    if not AUTOSTART:
        return

    async def later() -> None:
        await asyncio.sleep(1.0)
        ensure_running(job_id, org_id)

    asyncio.get_running_loop().create_task(later())


@router.get("/signals/theme-platforms", response_model=list[ThemePlatformOut])
async def list_theme_platforms(user: CurrentUser) -> list[ThemePlatformOut]:
    """Platform tarik tema dan apakah kuncinya sudah diisi di deployment ini.

    Nilai kunci tidak pernah ikut, hanya ada/tidaknya.
    """
    return [
        ThemePlatformOut(
            key=p.key,
            label=p.label,
            configured=platform_configured(p.key),
            env_vars=list(p.env_vars),
            collects_comments=p.collects_comments,
            max_days_back=p.max_days_back,
            access_note=p.access_note,
            method=p.method,
            limitations=list(p.limitations),
        )
        for p in tp.PLATFORMS.values()
    ]


@router.get("/projects/{project_id}/signals/theme-pulls", response_model=list[ThemePullOut])
async def list_theme_pulls(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> list[ThemePullOut]:
    """Daftar penarikan tema proyek ini, terbaru dulu.

    Membuka daftar ini juga melanjutkan pekerjaan yang belum selesai tetapi
    tidak sedang dikerjakan (sesudah server restart atau tidur).
    """
    rows = await _jobs(session, project_id)
    for r in rows:
        if (r.config or {}).get("status") in tp.ACTIVE:
            ensure_running(r.id, r.org_id)
    return [_out(r) for r in rows]


@router.post(
    "/projects/{project_id}/signals/theme-pulls",
    response_model=ThemePullOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def create_theme_pull(
    project_id: UUID, body: ThemeCreate, session: TenantSession, user: CurrentUser
) -> ThemePullOut:
    plat = tp.PLATFORMS[body.platform]
    if not platform_configured(plat.key):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{' dan '.join(plat.env_vars)} belum diset di backend; "
            f"tarik tema {plat.label} belum bisa jalan.",
        )
    now = datetime.now(UTC)
    today = (now + timedelta(hours=tp.WIB_HOURS)).date()
    try:
        req = tp.parse_request(
            queries=body.queries,
            start=body.start,
            end=body.end,
            max_videos=body.max_videos,
            include_replies=body.include_replies,
            comments_until_now=body.comments_until_now,
            keyword_filter=body.keyword_filter,
            today=today,
            platform=body.platform,
        )
    except tp.ThemeError as e:
        raise HTTPException(422, str(e)) from e

    jobs = await _jobs(session, project_id)
    active = [r for r in jobs if (r.config or {}).get("status") in tp.ACTIVE]
    if len(active) >= MAX_ACTIVE_PER_PROJECT:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Sudah ada {len(active)} penarikan berjalan di proyek ini. "
            "Tunggu salah satu selesai atau hentikan dulu.",
        )

    label = (body.label or "").strip() or ", ".join(req.queries)
    row = DataSource(
        org_id=user.org_id,
        project_id=project_id,
        source=ModelSignalSource.SOCIAL,
        connector=tp.KEY,
        config=tp.initial_state(req, label=label, now=now),
        is_active=True,
    )
    session.add(row)
    await session.flush()
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="theme_pull_create",
            entity="data_source",
            entity_id=row.id,
            metadata_={
                "project_id": str(project_id),
                "platform": req.platform,
                "queries": list(req.queries),
                "start": req.start.isoformat(),
                "end": req.end.isoformat(),
                "max_videos": req.max_videos,
            },
        )
    )
    await session.flush()
    _start_after_commit(row.id, user.org_id)
    return _out(row)


@router.post(
    "/projects/{project_id}/signals/theme-pulls/{job_id}/stop",
    response_model=ThemePullOut,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def stop_theme_pull(
    project_id: UUID, job_id: UUID, session: TenantSession, user: CurrentUser
) -> ThemePullOut:
    """Hentikan. Komentar yang sudah tersimpan tetap ada."""
    row = await _job(session, project_id, job_id)
    # Kunci baris: pekerja yang sedang di tengah langkah menyelesaikan
    # langkahnya dulu, lalu membaca status "stopped" di langkah berikutnya.
    await session.execute(
        select(DataSource.id).where(DataSource.id == row.id).with_for_update()
    )
    await session.refresh(row)
    state = copy.deepcopy(row.config or {})
    if state.get("status") in tp.ACTIVE:
        state["stage"] = (
            state.get("status_before_wait") or tp.STATUS_COLLECTING
            if state["status"] == tp.STATUS_WAITING_QUOTA
            else state["status"]
        )
        state["status_before_wait"] = None
        state["resume_at"] = None
        state["status"] = tp.STATUS_STOPPED
        state["finished_at"] = state["updated_at"] = datetime.now(UTC).isoformat()
        row.config = state
        row.is_active = False
        session.add(
            AuditLog(
                org_id=user.org_id,
                actor_id=user.user_id,
                action="theme_pull_stop",
                entity="data_source",
                entity_id=row.id,
                metadata_={"project_id": str(project_id), "stored": state.get("stored")},
            )
        )
    await session.flush()
    return _out(row)


@router.post(
    "/projects/{project_id}/signals/theme-pulls/{job_id}/resume",
    response_model=ThemePullOut,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def resume_theme_pull(
    project_id: UUID, job_id: UUID, session: TenantSession, user: CurrentUser
) -> ThemePullOut:
    """Lanjutkan penarikan yang dihentikan atau gagal, dari langkah terakhirnya."""
    row = await _job(session, project_id, job_id)
    await session.execute(
        select(DataSource.id).where(DataSource.id == row.id).with_for_update()
    )
    await session.refresh(row)
    state = copy.deepcopy(row.config or {})
    if state.get("status") in (tp.STATUS_STOPPED, tp.STATUS_FAILED):
        stage = state.get("stage")
        state["status"] = (
            stage
            if stage in (tp.STATUS_SEARCHING, tp.STATUS_DETAILS, tp.STATUS_COLLECTING)
            else tp.STATUS_COLLECTING
        )
        state["error"] = None
        state["retries"] = 0
        state["finished_at"] = None
        state["updated_at"] = datetime.now(UTC).isoformat()
        row.config = state
        row.is_active = True
        await session.flush()
        _start_after_commit(row.id, user.org_id)
    return _out(row)
