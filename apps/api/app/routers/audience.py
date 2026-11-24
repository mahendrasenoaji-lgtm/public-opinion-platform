"""Profil audiens agregat (P11): estimasi gender, kelompok umur, dan minat.

Perhitungannya di `services/profiling.py`. Yang keluar dari endpoint ini HANYA
agregat: tidak ada hash akun, tidak ada daftar akun per segmen. Tidak ada yang
disimpan; estimasi dihitung dari komentar saat dibaca (CLAUDE.md §3,
pengecualian 2026-11-08).

Hanya sumber SOCIAL: liputan media ditulis redaksi, bukan akun pribadi.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentUser, TenantSession
from app.models.measurement import SignalSource as ModelSignalSource
from app.models.signal import Mention
from app.routers.network import cached_heavy
from app.routers.windowing import EndDate, StartDate, window
from app.services import profiling

router = APIRouter(prefix="/projects/{project_id}/audience", tags=["audience"])

DEFAULT_WINDOW_DAYS = 30
#: Sebaran (persen) dan rata-rata sentimen per segmen ditahan di bawah ini.
MIN_ACCOUNTS_FOR_SHARE = 30
MIN_SCORED_FOR_SENTIMENT = 30
#: ...dan dari minimal sekian akun, supaya satu akun yang rajin berkomentar
#: tidak menjadi "sentimen segmen".
MIN_ACCOUNTS_FOR_SENTIMENT = 10
#: Sel piramida umur x gender yang lebih kecil dari ini ditampilkan "< 5".
MIN_CELL = 5
_BATCH_ROWS = 5000
MAX_EXCLUDE = 30

LIMITATIONS = [
    "Ini ESTIMASI dari teks komentar, bukan data demografi. Hanya akun yang menyatakan "
    'dirinya sendiri ("saya ibu…", "gue anak SMA", "umur saya 52 tahun") yang '
    "mendapat estimasi gender atau umur; sebagian besar akun tidak menyatakannya dan "
    'tercatat "tidak diketahui".',
    "Akun yang menyebut dirinya cenderung berbeda dari yang tidak (mis. ibu rumah tangga "
    "lebih sering menyebut perannya daripada bapak). Sebaran di antara akun yang "
    "diketahui TIDAK mewakili seluruh komentator, apalagi populasi.",
    "Minat dibaca dari kosakata minimal dua komentar akun itu. Kata yang dekat dengan "
    "topik proyek ikut terhitung: proyek tentang BBM cenderung menaikkan minat otomotif.",
    "Skor keyakinan berbasis aturan, belum dievaluasi terhadap set uji berlabel manual. "
    "Presisi per atribut belum diketahui; jangan dipakai untuk penargetan sebelum "
    "evaluasi itu ada.",
    "Platform tidak menyimpan nama tampilan, jadi gender tidak ditebak dari nama. "
    "Agama, etnis, orientasi seksual, kesehatan, dan afiliasi politik tidak pernah "
    "diestimasi (CLAUDE.md §3).",
    "Tidak ada estimasi yang disimpan dan tidak ada daftar akun per segmen. Ekspor per "
    "akun (untuk peran berizin, dengan audit log) belum dibangun.",
]


class ValueCount(BaseModel):
    value: str
    accounts: int
    #: Persen di antara akun yang nilainya DIKETAHUI; None bila terlalu sedikit.
    share: float | None


class AttributeOut(BaseModel):
    known: int
    unknown: int
    values: list[ValueCount]
    insufficient_data: bool
    note: str | None = None


class PyramidCell(BaseModel):
    age: str
    gender: str
    #: None = di bawah MIN_CELL (ditampilkan "< 5").
    accounts: int | None


class InterestOut(BaseModel):
    value: str
    accounts: int
    #: Persen dari seluruh akun berbeda di jendela ini.
    share_of_accounts: float | None


class MarkerOut(BaseModel):
    marker: str
    accounts: int


class SegmentSentimentOut(BaseModel):
    segment: str
    accounts: int
    scored: int
    mean: float | None


class AudienceOut(BaseModel):
    period_start: date
    period_end: date
    source: str = "SOCIAL"
    method: str
    model_version: str
    min_confidence: float
    evaluated: bool = False
    n_accounts: int
    n_comments: int
    gender: AttributeOut
    age: AttributeOut
    pyramid: list[PyramidCell]
    interests: list[InterestOut]
    interests_by_gender: dict[str, list[InterestOut]]
    evidence: dict[str, list[MarkerOut]]
    sentiment: list[SegmentSentimentOut]
    computed_at: datetime
    insufficient_data: bool
    note: str | None = None
    #: Kata yang dikecualikan dari penanda minat atas permintaan analis.
    excluded: list[str] = []
    limitations: list[str]


def _attribute(counts: dict[str, int], n_accounts: int) -> AttributeOut:
    known = sum(counts.values())
    enough = known >= MIN_ACCOUNTS_FOR_SHARE
    return AttributeOut(
        known=known,
        unknown=n_accounts - known,
        values=[
            ValueCount(
                value=v,
                accounts=n,
                share=round(100 * n / known, 1) if enough and known else None,
            )
            for v, n in counts.items()
        ],
        insufficient_data=not enough,
        note=None
        if enough
        else f"Perlu minimal {MIN_ACCOUNTS_FOR_SHARE} akun yang diketahui; tersedia {known}.",
    )


def _interests(counts: dict[str, int], n_accounts: int) -> list[InterestOut]:
    enough = sum(counts.values()) >= MIN_ACCOUNTS_FOR_SHARE
    return [
        InterestOut(
            value=v,
            accounts=n,
            share_of_accounts=round(100 * n / n_accounts, 2) if enough and n_accounts else None,
        )
        for v, n in counts.items()
    ]


def to_out(stats: profiling.AudienceStats, since: datetime, until: datetime) -> AudienceOut:
    """Agregat murni -> respons, dengan ambang penahanan. Dipisah supaya bisa dites."""

    n = stats.n_accounts
    insufficient = n < MIN_ACCOUNTS_FOR_SHARE
    return AudienceOut(
        period_start=since.date(),
        period_end=until.date(),
        method=profiling.METHOD,
        model_version=profiling.MODEL_VERSION,
        min_confidence=profiling.MIN_CONFIDENCE,
        n_accounts=n,
        n_comments=stats.n_comments,
        gender=_attribute(stats.gender, n),
        age=_attribute(stats.age, n),
        pyramid=[
            PyramidCell(
                age=a,
                gender=g,
                accounts=(c if (c := stats.pyramid.get((a, g), 0)) == 0 or c >= MIN_CELL else None),
            )
            for a in profiling.AGE_BANDS
            for g in profiling.GENDERS
        ],
        interests=_interests(stats.interests, n),
        interests_by_gender={g: _interests(c, n) for g, c in stats.interests_by_gender.items()},
        evidence={
            k: [MarkerOut(marker=m, accounts=c) for m, c in v] for k, v in stats.evidence.items()
        },
        sentiment=[
            SegmentSentimentOut(
                segment=s.segment,
                accounts=s.accounts,
                scored=s.scored,
                mean=(
                    s.mean
                    if s.scored >= MIN_SCORED_FOR_SENTIMENT
                    and s.accounts >= MIN_ACCOUNTS_FOR_SENTIMENT
                    else None
                ),
            )
            for s in stats.sentiment
        ],
        computed_at=datetime.now(UTC),
        insufficient_data=insufficient,
        note=(
            f"Perlu minimal {MIN_ACCOUNTS_FOR_SHARE} akun berbeda; tersedia {n}."
            if insufficient
            else None
        ),
        limitations=LIMITATIONS,
    )


#: Hash akun per kueri `= ANY(...)` saat mengambil sentimen akun bertanda.
_AUTHOR_CHUNK = 2000


def parse_exclude(raw: str | None) -> tuple[str, ...]:
    """ "martabak, kuliah" -> ("kuliah", "martabak"): dinormalisasi, unik, terurut (kunci cache)."""
    if not raw:
        return ()
    words = {profiling.normalize(w) for w in raw.split(",")}
    return tuple(sorted(w for w in words if w))[:MAX_EXCLUDE]


async def _compute(
    session: AsyncSession,
    project_id: UUID,
    since: datetime,
    until: datetime,
    exclude: tuple[str, ...] = (),
) -> AudienceOut:
    scope = (
        Mention.project_id == project_id,
        Mention.source == ModelSignalSource.SOCIAL,
        Mention.published_at >= since,
        Mention.published_at <= until,
        Mention.author_hash.is_not(None),
        Mention.author_hash != "",
    )
    n_accounts = int(
        (
            await session.execute(
                select(func.count(func.distinct(Mention.author_hash))).where(*scope)
            )
        ).scalar_one()
    )

    # Lintasan 1: teks dibaca per potongan; profiler hanya menyimpan akun bertanda.
    profiler = profiling.Profiler(exclude=exclude)
    base = (
        select(Mention.author_hash, Mention.text, Mention.published_at, Mention.id)
        .where(*scope)
        .order_by(Mention.published_at.desc(), Mention.id.desc())
        .limit(_BATCH_ROWS)
    )
    last: tuple[datetime, UUID] | None = None
    while True:
        page = base
        if last is not None:
            page = base.where(
                or_(
                    Mention.published_at < last[0],
                    and_(Mention.published_at == last[0], Mention.id < last[1]),
                )
            )
        rows = (await session.execute(page)).all()
        if rows:
            batch = [(r.author_hash, r.text) for r in rows]
            # Regex per komentar murni Python: di thread supaya /health tetap
            # dijawab (pelajaran 17 Nov 2026, proyek Gibran).
            await asyncio.to_thread(profiler.add, batch)
        if len(rows) < _BATCH_ROWS:
            break
        last = (rows[-1].published_at, rows[-1].id)

    # Lintasan 2: sentimen hanya untuk akun bertanda, diagregasi di SQL.
    marked = profiler.marked_authors()
    sentiment: dict[str, tuple[float, int]] = {}
    for i in range(0, len(marked), _AUTHOR_CHUNK):
        chunk = marked[i : i + _AUTHOR_CHUNK]
        agg = await session.execute(
            select(
                Mention.author_hash,
                func.coalesce(func.sum(Mention.sentiment), 0),
                func.count(Mention.sentiment),
            )
            .where(*scope, Mention.author_hash.in_(chunk))
            .group_by(Mention.author_hash)
        )
        for author, total, n in agg.all():
            sentiment[author] = (float(total), int(n))

    stats = await asyncio.to_thread(
        lambda: profiler.result(n_accounts=n_accounts, sentiment=sentiment)
    )
    out = to_out(stats, since, until)
    out.excluded = list(exclude)
    return out


@router.get("", response_model=AudienceOut)
async def get_audience(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=1, le=365),
    start: date | None = StartDate,
    end: date | None = EndDate,
    exclude: str | None = Query(
        default=None,
        max_length=500,
        description="Kata topik proyek (dipisah koma) yang tidak dihitung sebagai minat",
    ),
) -> AudienceOut:
    """Profil audiens agregat percakapan SOSIAL. Baca `limitations` sebelum memakai angkanya."""
    since, until = window(days, start, end)
    words = parse_exclude(exclude)

    async def compute() -> AudienceOut:
        return await _compute(session, project_id, since, until, words)

    # Kunci memuat org_id: cache melewati RLS (lihat routers/network.py).
    result: AudienceOut = await cached_heavy(
        ("audience", user.org_id, project_id, days, start, end, words), compute
    )
    return result
