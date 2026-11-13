"""Kinerja Komunikasi Pemerintah (rancangan model, belum divalidasi).

Tiga hal yang dilayani router ini:

* `GET  .../framework`      katalog indikator, bobot usulan, aturan cakupan;
* `POST .../posts` dan `GET .../posts/summary`  unggahan akun resmi lembaga
  (diunggah peneliti, bukan diambil otomatis) dan ringkasannya per akun per
  platform;
* `GET/PUT .../scores`      skor indikator 1-5 per lembaga per bulan, beserta
  kartu skor yang hanya terbit bila cakupannya cukup.

Bukan `AIEnvelope`: tidak ada keluaran model bahasa di sini. Setiap skor
diisi manusia dengan bukti tertulis; yang tidak punya data dicatat "tidak
tersedia" dengan alasannya dan tidak ikut rata-rata.

Kerangka: `docs/kerangka-kinerja-komunikasi-pemerintah.md`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentUser, Role, TenantSession, require_role
from app.models.comm import CommIndicatorScore, OfficialPost
from app.models.governance import AuditLog
from app.models.project import Project
from app.services import comm_performance as cp

router = APIRouter(prefix="/projects/{project_id}/comm-performance", tags=["comm-performance"])

MIGRATION = "db/migrations/2026-11-12-kinerja-komunikasi.sql"
MAX_POSTS_PER_CALL = 1000
SCORE_MUTABLE = ("score", "unavailable_reason", "evidence", "assessed_by", "assessed_at")

PlatformIn = Literal["instagram", "tiktok", "x"]

POST_LIMITATIONS = [
    "Angka diunggah peneliti dari data yang tampil publik atau dari ekspor pemilik akun; "
    "platform ini tidak mengambilnya sendiri dan tidak bisa memverifikasinya.",
    "Median dihitung per akun per platform. Angka antarplatform tidak dijumlah dan tidak "
    "sebanding (yang tampil publik berbeda di tiap platform).",
    "Engagement rate di sini dibagi jumlah pengikut, bukan reach. Angka tinggi menandakan "
    "interaksi, bukan pemahaman atau persetujuan.",
    "Reach, impressions, dan saves hanya ada bila pemilik akun memberikannya.",
]


# ------------------------------------------------------------- skema ----


class IndicatorOut(BaseModel):
    code: str
    dimension: str
    name: str
    availability: str
    definition: str
    rubric: str


class FrameworkOut(BaseModel):
    model_version: str
    disclaimer: str
    dimensions: list[str]
    weights: dict[str, float]
    min_coverage: float
    min_posts_for_median: int
    indicators: list[IndicatorOut]
    document: str


class PostIn(BaseModel):
    platform: PlatformIn
    account: str = Field(min_length=1, max_length=120)
    external_id: str = Field(min_length=1, max_length=200)
    posted_at: datetime
    url: str | None = Field(default=None, max_length=2000)
    kind: str | None = Field(default=None, max_length=40)
    caption: str | None = Field(default=None, max_length=10000)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    views: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)
    reach: int | None = Field(default=None, ge=0)
    impressions: int | None = Field(default=None, ge=0)
    followers: int | None = Field(default=None, ge=0)
    captured_at: datetime | None = None

    @field_validator("account", "external_id")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("tidak boleh kosong")
        return v

    @field_validator("posted_at", "captured_at")
    @classmethod
    def _aware(cls, v: datetime | None) -> datetime | None:
        # Cap waktu tanpa zona dianggap UTC supaya tidak bergantung zona server.
        return v.replace(tzinfo=UTC) if v is not None and v.tzinfo is None else v


class PostsIn(BaseModel):
    items: list[PostIn] = Field(min_length=1, max_length=MAX_POSTS_PER_CALL)


class PostsResult(BaseModel):
    received: int
    stored: int
    updated: int
    duplicates_dropped: int


class AccountSummaryOut(BaseModel):
    account: str
    platform: str
    n_posts: int
    first_post: datetime
    last_post: datetime
    by_kind: dict[str, int]
    posts_by_month: dict[str, int]
    median_likes: float | None
    median_comments: float | None
    median_shares: float | None
    median_views: float | None
    median_engagement_rate: float | None
    n_engagement_rate: int
    insufficient_data: bool


class PostsSummaryOut(BaseModel):
    source: str = "OFFICIAL_ACCOUNT"
    method: str
    n_posts: int
    accounts: list[AccountSummaryOut]
    limitations: list[str]


class ScoreIn(BaseModel):
    indicator: str
    score: int | None = Field(default=None, ge=cp.SCORE_MIN, le=cp.SCORE_MAX)
    unavailable_reason: str | None = Field(default=None, max_length=500)
    evidence: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def _exactly_one(self) -> ScoreIn:
        self.evidence = self.evidence.strip()
        reason = (self.unavailable_reason or "").strip() or None
        self.unavailable_reason = reason
        if self.indicator not in cp.INDICATOR_BY_CODE:
            raise ValueError(f"Indikator tidak dikenal: {self.indicator}.")
        if (self.score is None) == (reason is None):
            raise ValueError(
                f"{self.indicator}: isi skor ATAU alasan tidak tersedia, tepat salah satu."
            )
        if self.score is not None and not self.evidence:
            # Skor tanpa bukti tidak diterima; itu sama dengan menebak.
            raise ValueError(f"{self.indicator}: skor harus disertai bukti.")
        return self


class ScoresIn(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    period: str = Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")
    items: list[ScoreIn] = Field(min_length=1, max_length=len(cp.INDICATORS))

    @field_validator("subject")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("tidak boleh kosong")
        return v


class ScoreOut(BaseModel):
    indicator: str
    score: int | None
    unavailable_reason: str | None
    evidence: str
    assessed_at: datetime | None


class DimensionOut(BaseModel):
    dimension: str
    score: float | None
    coverage: float
    n_available: int
    n_total: int
    published: bool
    weight: float


class ScorecardOut(BaseModel):
    subject: str
    period: str
    method: str
    model_version: str
    disclaimer: str
    dimensions: list[DimensionOut]
    total: float | None
    total_equal_weights: float | None
    label: str | None
    n_scored: int
    n_unavailable: int
    n_empty: int
    items: list[ScoreOut]
    limitations: list[str]


class AssessmentRef(BaseModel):
    subject: str
    period: str
    n_scored: int
    n_unavailable: int


# ------------------------------------------------------------ pembantu ----


@asynccontextmanager
async def _tables() -> AsyncIterator[None]:
    """Ubah "tabel belum ada" menjadi 409 yang menyebut migrasinya.

    Kode ini bisa sampai di production sebelum migrasinya dijalankan di
    Supabase. Tanpa ini pengguna melihat 500 polos.
    """
    try:
        yield
    except ProgrammingError as e:
        if "does not exist" in str(e.orig) or "UndefinedTable" in type(e.orig).__name__:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Tabel modul Kinerja Komunikasi belum ada di basis data. Jalankan {MIGRATION}.",
            ) from e
        raise


async def _require_project(session: AsyncSession, project_id: UUID) -> None:
    found = (
        await session.execute(select(Project.id).where(Project.id == project_id))
    ).scalar_one_or_none()
    # Proyek organisasi lain disaring RLS menjadi nol baris: sengaja tidak
    # dibedakan dari proyek yang tidak ada.
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyek tidak ditemukan.")


def _score_limitations(card: cp.Scorecard) -> list[str]:
    out = [
        cp.DISCLAIMER,
        "Skor ordinal dirata-rata seolah berjarak sama; itu penyederhanaan.",
        "Skor diisi penilai berdasarkan bukti yang dilampirkan; penilai lain bisa menilai berbeda.",
        "Skor Outcome tidak membuktikan komunikasi sebagai penyebab perubahan pada publik.",
    ]
    unpublished = [d.dimension for d in card.dimensions if not d.published]
    if unpublished:
        out.append(
            "Skor total tidak terbit karena cakupan data kurang dari "
            f"{round(cp.MIN_COVERAGE * 100)}% pada dimensi: {', '.join(unpublished)}."
        )
    return out


# ------------------------------------------------------------ endpoint ----


@router.get("/framework", response_model=FrameworkOut)
async def get_framework(project_id: UUID, user: CurrentUser) -> FrameworkOut:
    """Katalog indikator dan aturan skor. Tidak membaca basis data."""
    return FrameworkOut(
        model_version=cp.MODEL_VERSION,
        disclaimer=cp.DISCLAIMER,
        dimensions=list(cp.DIMENSIONS),
        weights={k: v for k, v in cp.DEFAULT_WEIGHTS.items()},
        min_coverage=cp.MIN_COVERAGE,
        min_posts_for_median=cp.MIN_POSTS_FOR_MEDIAN,
        indicators=[IndicatorOut(**asdict(i)) for i in cp.INDICATORS],
        document="docs/kerangka-kinerja-komunikasi-pemerintah.md",
    )


@router.post(
    "/posts",
    response_model=PostsResult,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def upload_posts(
    project_id: UUID, body: PostsIn, session: TenantSession, user: CurrentUser
) -> PostsResult:
    """Unggah unggahan akun resmi. Mengunggah ulang memperbarui angkanya.

    Hak memakai data yang diunggah adalah tanggung jawab pengunggah. Platform
    ini tidak mengambil data Instagram, TikTok, atau X secara otomatis.
    """
    await _require_project(session, project_id)

    # Dalam satu berkas, baris terakhir untuk unggahan yang sama yang dipakai.
    unique: dict[tuple[str, str], PostIn] = {}
    for item in body.items:
        unique[(item.platform, item.external_id)] = item

    async with _tables():
        existing = set(
            (
                await session.execute(
                    select(OfficialPost.platform, OfficialPost.external_id).where(
                        OfficialPost.project_id == project_id,
                        OfficialPost.external_id.in_([k[1] for k in unique]),
                    )
                )
            )
            .tuples()
            .all()
        )
        rows = [
            {"org_id": user.org_id, "project_id": project_id, **item.model_dump()}
            for item in unique.values()
        ]
        stmt = pg_insert(OfficialPost).values(rows)
        mutable = [
            "account", "url", "posted_at", "kind", "caption", "likes", "comments", "shares",
            "views", "saves", "reach", "impressions", "followers", "captured_at",
        ]
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["project_id", "platform", "external_id"],
                set_={c: stmt.excluded[c] for c in mutable},
            )
        )

    updated = sum(1 for k in unique if k in existing)
    result = PostsResult(
        received=len(body.items),
        stored=len(unique) - updated,
        updated=updated,
        duplicates_dropped=len(body.items) - len(unique),
    )
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="comm_posts_upload",
            entity="project",
            entity_id=project_id,
            metadata_=result.model_dump(),
        )
    )
    return result


@router.get("/posts/summary", response_model=PostsSummaryOut)
async def posts_summary(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> PostsSummaryOut:
    """Ringkasan unggahan per akun per platform (median, tidak dijumlah)."""
    await _require_project(session, project_id)
    q = select(OfficialPost).where(OfficialPost.project_id == project_id)
    if start is not None:
        q = q.where(OfficialPost.posted_at >= start)
    if end is not None:
        q = q.where(OfficialPost.posted_at < end)
    async with _tables():
        posts = (await session.execute(q)).scalars().all()

    summaries = cp.summarize_posts(
        cp.PostRow(
            account=p.account,
            platform=p.platform,  # type: ignore[arg-type]  # dijaga CHECK di basis data
            posted_at=p.posted_at,
            kind=p.kind,
            likes=p.likes,
            comments=p.comments,
            shares=p.shares,
            views=p.views,
            followers=p.followers,
        )
        for p in posts
    )
    return PostsSummaryOut(
        method=(
            "Median per unggahan, per akun dan platform; median ditahan bila kurang dari "
            f"{cp.MIN_POSTS_FOR_MEDIAN} unggahan memuat angkanya. Engagement rate = "
            "(like + komentar + share) / pengikut."
        ),
        n_posts=len(posts),
        accounts=[AccountSummaryOut(**asdict(s)) for s in summaries],
        limitations=POST_LIMITATIONS,
    )


@router.get("/assessments", response_model=list[AssessmentRef])
async def list_assessments(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> list[AssessmentRef]:
    """Daftar (lembaga, periode) yang sudah punya isian."""
    await _require_project(session, project_id)
    async with _tables():
        rows = (
            await session.execute(
                select(
                    CommIndicatorScore.subject,
                    CommIndicatorScore.period,
                    CommIndicatorScore.score,
                ).where(CommIndicatorScore.project_id == project_id)
            )
        ).all()
    acc: dict[tuple[str, str], list[int]] = {}
    for subject, period, score in rows:
        pair = acc.setdefault((subject, period), [0, 0])
        pair[0 if score is not None else 1] += 1
    return [
        AssessmentRef(subject=s, period=p, n_scored=v[0], n_unavailable=v[1])
        for (s, p), v in sorted(acc.items(), key=lambda kv: (kv[0][1], kv[0][0]), reverse=True)
    ]


async def _scorecard(
    session: AsyncSession, project_id: UUID, subject: str, period: str
) -> ScorecardOut:
    async with _tables():
        rows = (
            (
                await session.execute(
                    select(CommIndicatorScore).where(
                        CommIndicatorScore.project_id == project_id,
                        CommIndicatorScore.subject == subject,
                        CommIndicatorScore.period == period,
                    )
                )
            )
            .scalars()
            .all()
        )
    by_code = {r.indicator: r for r in rows if r.indicator in cp.INDICATOR_BY_CODE}
    card = cp.build_scorecard({c: r.score for c, r in by_code.items()})
    n_scored = sum(1 for r in by_code.values() if r.score is not None)
    return ScorecardOut(
        subject=subject,
        period=period,
        method=(
            "Skor 1-5 per indikator dari penilai dengan bukti; rata-rata indikator yang "
            f"tersedia per dimensi; dimensi terbit bila cakupan minimal "
            f"{round(cp.MIN_COVERAGE * 100)}%; total = rata-rata tertimbang keempat dimensi."
        ),
        model_version=cp.MODEL_VERSION,
        disclaimer=cp.DISCLAIMER,
        dimensions=[
            DimensionOut(**asdict(d), weight=card.weights[d.dimension]) for d in card.dimensions
        ],
        total=card.total,
        total_equal_weights=card.total_equal_weights,
        label=card.label,
        n_scored=n_scored,
        n_unavailable=len(by_code) - n_scored,
        n_empty=len(cp.INDICATORS) - len(by_code),
        items=[
            ScoreOut(
                indicator=i.code,
                score=by_code[i.code].score if i.code in by_code else None,
                unavailable_reason=(
                    by_code[i.code].unavailable_reason if i.code in by_code else None
                ),
                evidence=by_code[i.code].evidence if i.code in by_code else "",
                assessed_at=by_code[i.code].assessed_at if i.code in by_code else None,
            )
            for i in cp.INDICATORS
        ],
        limitations=_score_limitations(card),
    )


@router.get("/scores", response_model=ScorecardOut)
async def get_scores(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    subject: Annotated[str, Query(min_length=1, max_length=120)],
    period: Annotated[str, Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")],
) -> ScorecardOut:
    """Isian dan kartu skor satu lembaga untuk satu bulan."""
    await _require_project(session, project_id)
    return await _scorecard(session, project_id, subject.strip(), period)


@router.put(
    "/scores",
    response_model=ScorecardOut,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def put_scores(
    project_id: UUID, body: ScoresIn, session: TenantSession, user: CurrentUser
) -> ScorecardOut:
    """Simpan isian indikator. Indikator yang tidak dikirim tidak diubah."""
    await _require_project(session, project_id)
    unique = {item.indicator: item for item in body.items}
    now = datetime.now(UTC)
    rows = [
        {
            "org_id": user.org_id,
            "project_id": project_id,
            "subject": body.subject,
            "period": body.period,
            "indicator": item.indicator,
            "score": item.score,
            "unavailable_reason": item.unavailable_reason,
            "evidence": item.evidence,
            "assessed_by": user.user_id,
            "assessed_at": now,
        }
        for item in unique.values()
    ]
    stmt = pg_insert(CommIndicatorScore).values(rows)
    async with _tables():
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["project_id", "subject", "period", "indicator"],
                set_={c: stmt.excluded[c] for c in SCORE_MUTABLE},
            )
        )
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="comm_scores_save",
            entity="project",
            entity_id=project_id,
            metadata_={
                "subject": body.subject,
                "period": body.period,
                "indicators": sorted(unique),
                "model_version": cp.MODEL_VERSION,
            },
        )
    )
    await session.flush()
    return await _scorecard(session, project_id, body.subject, body.period)
