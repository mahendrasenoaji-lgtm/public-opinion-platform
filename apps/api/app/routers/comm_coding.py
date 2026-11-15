"""Kinerja Komunikasi: pengodean isi, arus informasi, keselarasan, C4, dan O8.

Lanjutan `routers/comm_performance.py` dengan prefix yang sama:

* `GET/PUT .../coding`            kode isi per unggahan (Lampiran A), dua lembar
  pengode, dan `GET .../coding/reliability` (Krippendorff alpha per variabel);
* `GET/POST/DELETE .../flow`      penelusuran T1-T4 per konten dan ringkasannya
  pada 11 tahap model acuan;
* `GET/PUT/DELETE .../alignment`  pasangan pernyataan antarlembaga (C3);
* `GET  .../response-time`        C4 dari lonjakan percakapan SOCIAL dan
  unggahan akun resmi;
* `POST .../youtube-response-rate` O8 dari komentar publik di video kanal
  resmi. Komentar hanya dihitung di memori; teks dan penulisnya tidak disimpan.

Tidak ada keluaran model bahasa di sini. C4, C3, dan O8 keluar sebagai SARAN
skor beserta batasnya; skor resmi tetap diisi penilai lewat `PUT .../scores`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import ProgrammingError

from app.connectors import youtube_channel as ytc
from app.connectors.base import ConnectorError, CredentialMissing
from app.deps import CurrentUser, Role, TenantSession, require_role
from app.models.comm import CommAlignmentPair, CommFlowRecord, OfficialPost, OfficialPostCoding
from app.models.governance import AuditLog
from app.models.signal import Mention
from app.routers.comm_performance import _require_project
from app.routers.windowing import EndDate, StartDate, window
from app.schemas.common import SignalSource
from app.services import comm_flow as cf
from app.services import comm_performance as cp
from app.services import content_coding as cc
from app.services.signal_stats import TIMEZONES


def _id(x: float) -> str:
    """Angka dengan koma desimal untuk kalimat berbahasa Indonesia."""
    return str(x).replace(".", ",")

router = APIRouter(prefix="/projects/{project_id}/comm-performance", tags=["comm-performance"])

MIGRATION = "db/migrations/2026-11-15-kinerja-pengodean-arus.sql"

CoderSlot = Literal[1, 2]

CODING_LIMITATIONS = [
    "Kode diisi manusia menurut lembar coding (Lampiran A kerangka); sistem tidak mengode.",
    "Dua lembar pengode boleh diisi dari satu login. Sistem tidak bisa memeriksa bahwa "
    "keduanya bekerja terpisah; itu tanggung jawab peneliti.",
    "Sebaran kode memakai lembar pengode 1 (lembar 2 bila lembar 1 kosong). Lembar kedua "
    "dipakai untuk menguji kesepakatan, bukan untuk menggandakan hitungan.",
    f"Alpha ditahan bila unggahan yang dikode ganda kurang dari {cc.MIN_DOUBLE_CODED}. "
    f"Di bawah {_id(cc.ALPHA_TENTATIVE)} kategori diperbaiki dulu dan sebarannya ditahan.",
]

FLOW_LIMITATIONS = [
    "Cap waktu diisi auditor dari log, surat, atau wawancara. Platform hanya menampilkan apa "
    "yang diisi dan tidak bisa memverifikasinya.",
    "Sebelas tahap adalah model acuan untuk diaudit, bukan gambaran keadaan lembaga mana pun.",
    f"Median sebuah selang ditahan bila konten yang kedua ujungnya tercatat kurang dari "
    f"{cf.MIN_RECORDS}.",
    "Konten yang ditelusuri dipilih auditor (10-20 unggahan), bukan sampel acak.",
]

ALIGNMENT_LIMITATIONS = [
    "Pasangan pernyataan dipilih dan dikode manusia. Isu yang tidak diperiksa tidak terwakili.",
    "Saran skor mengikuti rubrik kerangka (1, 3, atau 5) dari lembar pengode 1, dan baru "
    f"keluar pada {cf.MIN_PAIRS} pasangan atau lebih.",
    "Berbeda penekanan tidak sama dengan bertentangan; bacalah catatan pengodenya.",
]

RESPONSE_TIME_LIMITATIONS = [
    "Selang waktu, bukan sebab: unggahan resmi sesudah lonjakan belum tentu menanggapi "
    "lonjakan itu. Isi unggahannya harus dicek manusia.",
    "Lonjakan didefinisikan per hari, jadi titik awalnya pukul 00.00 hari itu. Selang yang "
    "tampil bisa lebih panjang sampai 24 jam daripada selang sebenarnya.",
    f"Unggahan dicari sampai {cf.RESPONSE_HORIZON_HOURS} jam sesudah awal hari lonjakan; lebih "
    "dari itu dianggap tidak ada tanggapan.",
    "Lonjakan dihitung dari percakapan SOSIAL yang terkumpul di proyek ini saja, dan unggahan "
    "resmi dari yang sudah diunggah atau diambil. Data yang belum masuk tidak terlihat.",
]

RESPONSE_RATE_LIMITATIONS = [
    "Pertanyaan dikenali dari bentuknya (tanda tanya atau kata tanya di awal). Pertanyaan "
    "retoris ikut terhitung dan sebagian pertanyaan terlewat.",
    "Dibalas berarti ada balasan dari kanal itu sendiri pada utas komentar. Mutu jawabannya "
    "tidak dinilai.",
    "Hanya 100 utas terbaru per video yang dibaca, dan YouTube menyertakan paling banyak 5 "
    "balasan per utas; balasan resmi di luar itu tidak terlihat.",
    "Teks komentar hanya dipakai untuk menghitung dan tidak disimpan; penulisnya tidak dibaca.",
    f"Angka ditahan bila komentar berisi pertanyaan kurang dari {cf.MIN_QUESTIONS}.",
]


@asynccontextmanager
async def _tables() -> AsyncIterator[None]:
    """Ubah "tabel belum ada" menjadi 409 yang menyebut migrasinya."""
    try:
        yield
    except ProgrammingError as e:
        if "does not exist" in str(e.orig) or "UndefinedTable" in type(e.orig).__name__:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Tabel pengodean dan arus informasi belum ada di basis data. "
                f"Jalankan {MIGRATION}.",
            ) from e
        raise


def _aware(v: datetime | None) -> datetime | None:
    return v.replace(tzinfo=UTC) if v is not None and v.tzinfo is None else v


def _clean(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("tidak boleh kosong")
    return v


# =============================================================== pengodean ====


class VariableOut(BaseModel):
    code: str
    name: str
    level: str
    values: list[tuple[int, str]]


class CodingRow(BaseModel):
    post_id: UUID
    platform: str
    account: str
    posted_at: datetime
    url: str | None
    kind: str | None
    caption: str | None
    #: Kode lembar yang diminta; kosong bila belum dikode.
    codes: dict[str, int]
    note: str
    coded: bool
    #: Lembar pengode lain sudah mengisi? Nilainya sengaja tidak dikirim
    #: supaya pengode tidak saling melihat.
    coded_by_other: bool


class CodingListOut(BaseModel):
    coder: int
    total: int
    n_coded: int
    variables: list[VariableOut]
    accounts: list[str]
    items: list[CodingRow]


class CodingIn(BaseModel):
    coder: CoderSlot
    coder_name: str = Field(default="", max_length=120)
    codes: dict[str, int | None]
    note: str = Field(default="", max_length=2000)


class VariableReliabilityOut(BaseModel):
    code: str
    name: str
    level: str
    n_double_coded: int
    alpha: float | None
    label: str
    percent_agreement: float | None


class DistributionOut(BaseModel):
    code: str
    name: str
    n: int
    #: False bila alpha di bawah ambang: sebarannya ditahan.
    published: bool
    #: True bila alpha sudah dihitung; False = belum diuji kesepakatannya.
    tested: bool
    counts: list[tuple[int, str, int]]


class ReliabilityOut(BaseModel):
    source: str = "OFFICIAL_ACCOUNT"
    method: str
    n_posts: int
    n_coded: int
    n_double_coded: int
    n_coders: int
    double_share: float
    target_double_share: float
    meets_target: bool
    variables: list[VariableReliabilityOut]
    distributions: list[DistributionOut]
    limitations: list[str]


def _publishable(alpha: float | None) -> bool:
    """Sebaran tampil bila alpha belum diuji atau lolos ambang sementara."""
    return alpha is None or alpha >= cc.ALPHA_TENTATIVE


def _variables() -> list[VariableOut]:
    return [
        VariableOut(code=v.code, name=v.name, level=v.level, values=list(v.values))
        for v in cc.VARIABLES
    ]


@router.get("/coding", response_model=CodingListOut)
async def list_coding(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    coder: Annotated[int, Query(ge=1, le=2)] = 1,
    account: Annotated[str | None, Query(max_length=120)] = None,
    only_uncoded: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CodingListOut:
    """Unggahan akun resmi beserta kode lembar pengode yang diminta."""
    await _require_project(session, project_id)
    async with _tables():
        accounts = sorted(
            (
                await session.execute(
                    select(OfficialPost.account)
                    .where(OfficialPost.project_id == project_id)
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        mine = (
            select(OfficialPostCoding.post_id)
            .where(OfficialPostCoding.project_id == project_id, OfficialPostCoding.coder == coder)
            .scalar_subquery()
        )
        base = select(OfficialPost).where(OfficialPost.project_id == project_id)
        if account:
            base = base.where(OfficialPost.account == account)
        total = (
            await session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        n_coded = (
            await session.execute(
                select(func.count()).select_from(base.where(OfficialPost.id.in_(mine)).subquery())
            )
        ).scalar_one()
        if only_uncoded:
            base = base.where(OfficialPost.id.not_in(mine))
        posts = (
            (
                await session.execute(
                    base.order_by(OfficialPost.posted_at.desc(), OfficialPost.id)
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        codings = (
            (
                await session.execute(
                    select(OfficialPostCoding).where(
                        OfficialPostCoding.post_id.in_([p.id for p in posts])
                    )
                )
            )
            .scalars()
            .all()
        )
    own = {c.post_id: c for c in codings if c.coder == coder}
    other = {c.post_id for c in codings if c.coder != coder}
    return CodingListOut(
        coder=coder,
        total=total,
        n_coded=n_coded,
        variables=_variables(),
        accounts=accounts,
        items=[
            CodingRow(
                post_id=p.id,
                platform=p.platform,
                account=p.account,
                posted_at=p.posted_at,
                url=p.url,
                kind=p.kind,
                caption=p.caption,
                codes=dict(own[p.id].codes) if p.id in own else {},
                note=own[p.id].note if p.id in own else "",
                coded=p.id in own,
                coded_by_other=p.id in other,
            )
            for p in posts
        ],
    )


@router.put(
    "/coding/{post_id}",
    response_model=CodingRow,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def put_coding(
    project_id: UUID, post_id: UUID, body: CodingIn, session: TenantSession, user: CurrentUser
) -> CodingRow:
    """Simpan kode satu unggahan untuk satu lembar pengode (menimpa yang lama)."""
    await _require_project(session, project_id)
    try:
        codes = cc.validate_codes(body.codes)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    async with _tables():
        post = (
            await session.execute(
                select(OfficialPost).where(
                    OfficialPost.id == post_id, OfficialPost.project_id == project_id
                )
            )
        ).scalar_one_or_none()
        if post is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unggahan tidak ditemukan.")
        values = {
            "org_id": user.org_id,
            "project_id": project_id,
            "post_id": post_id,
            "coder": body.coder,
            "coder_name": body.coder_name.strip(),
            "codes": codes,
            "note": body.note.strip(),
            "coded_by": user.user_id,
            "coded_at": datetime.now(UTC),
        }
        stmt = pg_insert(OfficialPostCoding).values(values)
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["post_id", "coder"],
                set_={
                    k: stmt.excluded[k]
                    for k in ("coder_name", "codes", "note", "coded_by", "coded_at")
                },
            )
        )
        other = (
            await session.execute(
                select(func.count())
                .select_from(OfficialPostCoding)
                .where(
                    OfficialPostCoding.post_id == post_id,
                    OfficialPostCoding.coder != body.coder,
                )
            )
        ).scalar_one()
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="comm_coding_put",
            entity="official_post",
            entity_id=post_id,
            metadata_={"coder": body.coder, "variables": sorted(codes)},
        )
    )
    return CodingRow(
        post_id=post.id,
        platform=post.platform,
        account=post.account,
        posted_at=post.posted_at,
        url=post.url,
        kind=post.kind,
        caption=post.caption,
        codes=codes,
        note=body.note.strip(),
        coded=True,
        coded_by_other=other > 0,
    )


@router.get("/coding/reliability", response_model=ReliabilityOut)
async def coding_reliability(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    account: Annotated[str | None, Query(max_length=120)] = None,
) -> ReliabilityOut:
    """Krippendorff alpha per variabel dan sebaran kode yang lolos uji."""
    await _require_project(session, project_id)
    async with _tables():
        posts = select(OfficialPost.id).where(OfficialPost.project_id == project_id)
        if account:
            posts = posts.where(OfficialPost.account == account)
        n_posts = (
            await session.execute(select(func.count()).select_from(posts.subquery()))
        ).scalar_one()
        rows = (
            (
                await session.execute(
                    select(OfficialPostCoding)
                    .where(
                        OfficialPostCoding.project_id == project_id,
                        OfficialPostCoding.post_id.in_(posts.scalar_subquery()),
                    )
                    .order_by(OfficialPostCoding.coder)
                )
            )
            .scalars()
            .all()
        )
    by_post: dict[UUID, dict[int, dict[str, int]]] = {}
    for r in rows:
        by_post.setdefault(r.post_id, {})[r.coder] = dict(r.codes)
    rel = cc.reliability(by_post, n_posts=n_posts)
    alpha = {v.code: v for v in rel.variables}
    # Lembar 1 mewakili; lembar 2 hanya bila lembar 1 kosong (baris terurut coder).
    firsts = [next(iter(per.values())) for per in by_post.values()]
    return ReliabilityOut(
        method=(
            "Krippendorff alpha per variabel pada unggahan yang diisi kedua lembar pengode "
            "(nominal atau ordinal sesuai variabel); sebaran dari satu kode per unggahan"
        ),
        n_posts=rel.n_posts,
        n_coded=rel.n_coded,
        n_double_coded=rel.n_double_coded,
        n_coders=rel.n_coders,
        double_share=rel.double_share,
        target_double_share=cc.TARGET_DOUBLE_SHARE,
        meets_target=rel.meets_target,
        variables=[
            VariableReliabilityOut(
                code=v.code,
                name=v.name,
                level=v.level,
                n_double_coded=v.n_double_coded,
                alpha=v.alpha,
                label=v.label,
                percent_agreement=v.percent_agreement,
            )
            for v in rel.variables
        ],
        distributions=[
            DistributionOut(
                code=d.code,
                name=d.name,
                n=d.n,
                tested=alpha[d.code].alpha is not None,
                published=_publishable(alpha[d.code].alpha),
                counts=list(d.counts) if _publishable(alpha[d.code].alpha) else [],
            )
            for d in cc.distributions(firsts)
        ],
        limitations=CODING_LIMITATIONS,
    )


# ========================================================= arus informasi ====


class FlowIn(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=300)
    kind: Literal["rutin", "klarifikasi"]
    requested_at: datetime | None = None
    received_at: datetime | None = None
    verified_at: datetime | None = None
    drafted_at: datetime | None = None
    approved_at: datetime | None = None
    published_at: datetime | None = None
    bottleneck_stage: int | None = Field(default=None, ge=1, le=11)
    note: str = Field(default="", max_length=2000)

    _strip = field_validator("subject", "label")(_clean)
    _utc = field_validator(*cf.TIMESTAMPS)(_aware)


class FlowRow(FlowIn):
    id: UUID
    hours: dict[str, float | None]


class IntervalOut(BaseModel):
    code: str
    meaning: str
    stages: list[int]
    n: int
    median_hours: float | None
    max_hours: float | None


class StageOut(BaseModel):
    stage: int
    name: str
    n_bottleneck: int


class FlowOut(BaseModel):
    source: str = "INTERNAL_AUDIT"
    method: str
    subjects: list[str]
    n_records: int
    min_records: int
    intervals: list[IntervalOut]
    slowest: str | None
    stages: list[StageOut]
    records: list[FlowRow]
    limitations: list[str]


def _flow_record(r: CommFlowRecord | FlowIn) -> cf.FlowRecord:
    return cf.FlowRecord(
        **{name: getattr(r, name) for name in cf.TIMESTAMPS},
        bottleneck_stage=r.bottleneck_stage,
    )


@router.get("/flow", response_model=FlowOut)
async def get_flow(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    subject: Annotated[str | None, Query(max_length=120)] = None,
) -> FlowOut:
    """Penelusuran T1-T4 dan ringkasannya pada 11 tahap model acuan."""
    await _require_project(session, project_id)
    async with _tables():
        all_rows = (
            (
                await session.execute(
                    select(CommFlowRecord)
                    .where(CommFlowRecord.project_id == project_id)
                    .order_by(CommFlowRecord.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
    rows = [r for r in all_rows if subject is None or r.subject == subject]
    summary = cf.summarize_flow([_flow_record(r) for r in rows])
    return FlowOut(
        method=(
            "selang jam antara cap waktu yang dicatat auditor; median per selang; hitungan "
            "konten per tahap yang ditandai sebagai hambatan"
        ),
        subjects=sorted({r.subject for r in all_rows}),
        n_records=summary.n_records,
        min_records=cf.MIN_RECORDS,
        intervals=[
            IntervalOut(
                code=i.code,
                meaning=i.meaning,
                stages=list(i.stages),
                n=i.n,
                median_hours=i.median_hours,
                max_hours=i.max_hours,
            )
            for i in summary.intervals
        ],
        slowest=summary.slowest,
        stages=[StageOut(stage=s, name=n, n_bottleneck=c) for s, n, c in summary.bottlenecks],
        records=[
            FlowRow(
                id=r.id,
                subject=r.subject,
                label=r.label,
                kind=r.kind,  # type: ignore[arg-type]
                **{name: getattr(r, name) for name in cf.TIMESTAMPS},
                bottleneck_stage=r.bottleneck_stage,
                note=r.note,
                hours=dict(cf.interval_hours(_flow_record(r))),
            )
            for r in rows
        ],
        limitations=FLOW_LIMITATIONS,
    )


@router.post(
    "/flow",
    response_model=FlowRow,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def add_flow(
    project_id: UUID, body: FlowIn, session: TenantSession, user: CurrentUser
) -> FlowRow:
    """Catat penelusuran satu konten. Cap waktu yang mundur ditolak."""
    await _require_project(session, project_id)
    record = _flow_record(body)
    try:
        cf.check_order(record)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    row = CommFlowRecord(
        org_id=user.org_id,
        project_id=project_id,
        created_by=user.user_id,
        **body.model_dump(),
    )
    async with _tables():
        session.add(row)
        await session.flush()
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="comm_flow_add",
            entity="comm_flow_record",
            entity_id=row.id,
            metadata_={"subject": body.subject, "kind": body.kind},
        )
    )
    return FlowRow(id=row.id, **body.model_dump(), hours=dict(cf.interval_hours(record)))


@router.delete(
    "/flow/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def delete_flow(
    project_id: UUID, record_id: UUID, session: TenantSession, user: CurrentUser
) -> None:
    async with _tables():
        row = (
            await session.execute(
                select(CommFlowRecord).where(
                    CommFlowRecord.id == record_id, CommFlowRecord.project_id == project_id
                )
            )
        ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Catatan tidak ditemukan.")
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="comm_flow_delete",
            entity="comm_flow_record",
            entity_id=record_id,
            metadata_={"subject": row.subject, "label": row.label},
        )
    )
    await session.delete(row)


# ====================================================== keselarasan (C3) ====


class AlignmentIn(BaseModel):
    issue: str = Field(min_length=1, max_length=200)
    subject_a: str = Field(min_length=1, max_length=120)
    url_a: str | None = Field(default=None, max_length=2000)
    subject_b: str = Field(min_length=1, max_length=120)
    url_b: str | None = Field(default=None, max_length=2000)
    coder: CoderSlot
    code: cf.Alignment
    corrected: bool = False
    note: str = Field(default="", max_length=2000)

    _strip = field_validator("issue", "subject_a", "subject_b")(_clean)

    @field_validator("url_a", "url_b")
    @classmethod
    def _http_only(cls, v: str | None) -> str | None:
        v = (v or "").strip() or None
        if v is not None and not v.lower().startswith(("http://", "https://")):
            raise ValueError("Tautan harus diawali http:// atau https://.")
        return v


class AlignmentRow(AlignmentIn):
    id: UUID


class AlignmentOut(BaseModel):
    source: str = "OFFICIAL_ACCOUNT"
    method: str
    n_pairs: int
    counts: dict[str, int]
    n_contradiction_open: int
    suggested_score: int | None
    min_pairs: int
    n_double_coded: int
    alpha: float | None
    alpha_label: str
    items: list[AlignmentRow]
    limitations: list[str]


@router.get("/alignment", response_model=AlignmentOut)
async def get_alignment(
    project_id: UUID, session: TenantSession, user: CurrentUser
) -> AlignmentOut:
    """Pasangan pernyataan antarlembaga dan saran skor C3."""
    await _require_project(session, project_id)
    async with _tables():
        rows = (
            (
                await session.execute(
                    select(CommAlignmentPair)
                    .where(CommAlignmentPair.project_id == project_id)
                    .order_by(
                        CommAlignmentPair.issue,
                        CommAlignmentPair.subject_a,
                        CommAlignmentPair.subject_b,
                        CommAlignmentPair.coder,
                    )
                )
            )
            .scalars()
            .all()
        )
    by_pair: dict[tuple[str, str, str], dict[int, CommAlignmentPair]] = {}
    for r in rows:
        by_pair.setdefault((r.issue, r.subject_a, r.subject_b), {})[r.coder] = r
    firsts = [next(iter(per.values())) for per in by_pair.values()]
    summary = cf.summarize_alignment(
        (f.code, f.corrected) for f in firsts  # type: ignore[misc]
    )
    double = [
        [cf.ALIGNMENT_RANK[c.code] for c in per.values()]  # type: ignore[index]
        for per in by_pair.values()
        if len(per) >= 2
    ]
    enough = len(double) >= cc.MIN_DOUBLE_CODED
    alpha = cc.krippendorff_alpha(double, level="ordinal") if enough else None
    return AlignmentOut(
        method=(
            "pasangan pernyataan resmi per isu, dikode selaras / berbeda penekanan / "
            "bertentangan; saran skor menurut rubrik C3; alpha ordinal antar dua lembar pengode"
        ),
        n_pairs=summary.n_pairs,
        counts=dict(summary.counts),
        n_contradiction_open=summary.n_contradiction_open,
        suggested_score=summary.suggested_score,
        min_pairs=cf.MIN_PAIRS,
        n_double_coded=len(double),
        alpha=alpha,
        alpha_label=(
            cc.reliability_label(alpha)
            if enough
            else f"data tidak cukup (butuh {cc.MIN_DOUBLE_CODED} pasangan dikode ganda)"
        ),
        items=[
            AlignmentRow(
                id=r.id,
                issue=r.issue,
                subject_a=r.subject_a,
                url_a=r.url_a,
                subject_b=r.subject_b,
                url_b=r.url_b,
                coder=r.coder,  # type: ignore[arg-type]
                code=r.code,  # type: ignore[arg-type]
                corrected=r.corrected,
                note=r.note,
            )
            for r in rows
        ],
        limitations=ALIGNMENT_LIMITATIONS,
    )


@router.put(
    "/alignment",
    response_model=AlignmentRow,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def put_alignment(
    project_id: UUID, body: AlignmentIn, session: TenantSession, user: CurrentUser
) -> AlignmentRow:
    """Simpan kode satu pasangan untuk satu lembar pengode (menimpa yang lama)."""
    await _require_project(session, project_id)
    if body.subject_a.casefold() == body.subject_b.casefold():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Dua lembaga dalam satu pasangan harus berbeda."
        )
    stmt = pg_insert(CommAlignmentPair).values(
        org_id=user.org_id,
        project_id=project_id,
        coded_by=user.user_id,
        coded_at=datetime.now(UTC),
        **body.model_dump(),
    )
    async with _tables():
        row_id = (
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["project_id", "issue", "subject_a", "subject_b", "coder"],
                    set_={
                        k: stmt.excluded[k]
                        for k in (
                            "url_a", "url_b", "code", "corrected", "note", "coded_by", "coded_at",
                        )
                    },
                ).returning(CommAlignmentPair.id)
            )
        ).scalar_one()
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="comm_alignment_put",
            entity="comm_alignment_pair",
            entity_id=row_id,
            metadata_={"issue": body.issue, "coder": body.coder, "code": body.code},
        )
    )
    return AlignmentRow(id=row_id, **body.model_dump())


@router.delete(
    "/alignment/{pair_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def delete_alignment(
    project_id: UUID, pair_id: UUID, session: TenantSession, user: CurrentUser
) -> None:
    async with _tables():
        row = (
            await session.execute(
                select(CommAlignmentPair).where(
                    CommAlignmentPair.id == pair_id, CommAlignmentPair.project_id == project_id
                )
            )
        ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pasangan tidak ditemukan.")
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="comm_alignment_delete",
            entity="comm_alignment_pair",
            entity_id=pair_id,
            metadata_={"issue": row.issue, "coder": row.coder},
        )
    )
    await session.delete(row)


# ======================================================= waktu tanggap (C4) ====


class SpikeOut(BaseModel):
    day: date
    volume: int
    ratio: float
    hours: float | None
    first_post_at: datetime | None


class ResponseTimeOut(BaseModel):
    source: str = "SOCIAL+OFFICIAL_ACCOUNT"
    indicator: str = "C4"
    method: str
    account: str
    period_start: date
    period_end: date
    timezone: str
    n_days: int
    n_official_posts: int
    median_daily_volume: float
    spikes: list[SpikeOut]
    median_hours: float | None
    n_unanswered: int
    suggested_score: int | None
    limitations: list[str]


@router.get("/response-time", response_model=ResponseTimeOut)
async def response_time(
    project_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    account: Annotated[str, Query(min_length=1, max_length=120)],
    days: Annotated[int, Query(ge=3, le=365)] = 30,
    start: date | None = StartDate,
    end: date | None = EndDate,
    tz: Literal["WIB", "WITA", "WIT"] = "WIB",
    keyword: Annotated[str | None, Query(max_length=80)] = None,
) -> ResponseTimeOut:
    """C4: jam dari hari lonjakan percakapan sampai unggahan resmi pertama.

    `keyword` menyaring unggahan resmi yang takarirnya memuat kata itu, supaya
    yang dihitung lebih dekat ke unggahan tentang isunya.
    """
    await _require_project(session, project_id)
    since, until = window(days, start, end)
    offset = TIMEZONES[tz]
    # Geser ke jam lokal dengan interval, bukan nama zona "+07:00": Postgres
    # membaca tanda zona gaya POSIX terbalik (+07 = barat UTC).
    local_day = func.date(func.timezone("UTC", Mention.published_at) + timedelta(hours=offset))
    volume_rows = (
        await session.execute(
            select(local_day.label("day"), func.count().label("n"))
            .where(
                Mention.project_id == project_id,
                Mention.source == SignalSource.SOCIAL,
                Mention.published_at >= since,
                Mention.published_at <= until,
            )
            .group_by(local_day)
        )
    ).all()
    async with _tables():
        posts_q = select(OfficialPost.posted_at).where(
            OfficialPost.project_id == project_id,
            OfficialPost.account == account,
            OfficialPost.posted_at >= since,
        )
        if keyword and keyword.strip():
            posts_q = posts_q.where(OfficialPost.caption.ilike(f"%{keyword.strip()}%"))
        posted = list((await session.execute(posts_q)).scalars().all())

    result = cf.response_time(
        {r.day: int(r.n) for r in volume_rows}, posted, tz_offset_hours=offset
    )
    limitations = list(RESPONSE_TIME_LIMITATIONS)
    if not result.spikes:
        limitations.insert(
            0,
            "Tidak ada hari lonjakan pada periode ini (butuh minimal 3 hari data dan satu hari "
            f"dengan volume {_id(cf.SPIKE_RATIO)} kali median), jadi C4 tidak bisa disarankan.",
        )
    return ResponseTimeOut(
        method=(
            f"lonjakan = hari dengan percakapan SOSIAL minimal {_id(cf.SPIKE_RATIO)} kali median "
            "harian; selang dihitung dari pukul 00.00 hari itu sampai unggahan pertama akun "
            "resmi; median antar-lonjakan yang ditanggapi; skor menurut ambang rubrik C4"
        ),
        account=account,
        period_start=since.date(),
        period_end=until.date(),
        timezone=tz,
        n_days=result.n_days,
        n_official_posts=len(posted),
        median_daily_volume=result.median_daily_volume,
        spikes=[
            SpikeOut(
                day=s.day, volume=s.volume, ratio=s.ratio, hours=s.hours,
                first_post_at=s.first_post_at,
            )
            for s in result.spikes
        ],
        median_hours=result.median_hours,
        n_unanswered=result.n_unanswered,
        suggested_score=result.suggested_score,
        limitations=limitations,
    )


# ======================================================== tingkat jawab (O8) ====


class ResponseRateIn(BaseModel):
    account: str = Field(min_length=1, max_length=120)
    max_videos: int = Field(
        default=ytc.DEFAULT_RESPONSE_VIDEOS, ge=1, le=ytc.MAX_RESPONSE_VIDEOS
    )

    _strip = field_validator("account")(_clean)


class ResponseRateOut(BaseModel):
    source: str = "OFFICIAL_ACCOUNT"
    indicator: str = "O8"
    method: str
    account: str
    platform: str = "youtube"
    n_videos: int
    n_videos_skipped: int
    n_comments: int
    n_questions: int
    n_answered: int
    n_uncertain: int
    rate_pct: float | None
    suggested_score: int | None
    min_questions: int
    quota_units: int
    limitations: list[str]


@router.post(
    "/youtube-response-rate",
    response_model=ResponseRateOut,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def youtube_response_rate(
    project_id: UUID, body: ResponseRateIn, session: TenantSession, user: CurrentUser
) -> ResponseRateOut:
    """O8 untuk kanal YouTube resmi yang videonya sudah diambil ke proyek ini.

    Membaca komentar publik lewat YouTube Data API, menghitung, lalu membuang
    teksnya. Yang kembali dan tercatat hanya jumlah.
    """
    await _require_project(session, project_id)
    async with _tables():
        video_ids = list(
            (
                await session.execute(
                    select(OfficialPost.external_id)
                    .where(
                        OfficialPost.project_id == project_id,
                        OfficialPost.platform == ytc.PLATFORM,
                        OfficialPost.account == body.account,
                        OfficialPost.comments > 0,
                    )
                    .order_by(OfficialPost.posted_at.desc())
                    .limit(body.max_videos)
                )
            )
            .scalars()
            .all()
        )
    if not video_ids:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Belum ada video YouTube berkomentar untuk akun itu di proyek ini. "
            "Ambil dulu kanalnya lewat formulir kanal YouTube resmi.",
        )
    try:
        fetched = await ytc.fetch_threads(video_ids)
    except CredentialMissing as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e
    except ConnectorError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e

    rate = cf.response_rate((t.text, t.owner_replied) for t in fetched.threads)
    uncertain = sum(1 for t in fetched.threads if t.replies_truncated and cf.is_question(t.text))
    session.add(
        AuditLog(
            org_id=user.org_id,
            actor_id=user.user_id,
            action="comm_response_rate_youtube",
            entity="project",
            entity_id=project_id,
            metadata_={
                "account": body.account,
                "n_videos": fetched.n_videos,
                "n_questions": rate.n_questions,
                "n_answered": rate.n_answered,
                "quota_units": fetched.quota_units,
            },
        )
    )
    limitations = list(RESPONSE_RATE_LIMITATIONS)
    if uncertain:
        limitations.insert(
            0,
            f"{uncertain} pertanyaan punya balasan lebih banyak daripada yang disertakan API "
            "dan dihitung belum dibalas; angka sebenarnya bisa lebih tinggi.",
        )
    return ResponseRateOut(
        method=(
            "komentar tingkat atas dari publik pada video kanal resmi; pertanyaan dikenali dari "
            "bentuknya; dibalas = ada balasan dari kanal itu sendiri; skor menurut ambang "
            f"rubrik O8 ({cp.MODEL_VERSION})"
        ),
        account=body.account,
        n_videos=fetched.n_videos,
        n_videos_skipped=fetched.n_videos_skipped,
        n_comments=rate.n_comments,
        n_questions=rate.n_questions,
        n_answered=rate.n_answered,
        n_uncertain=uncertain,
        rate_pct=rate.rate_pct,
        suggested_score=rate.suggested_score,
        min_questions=cf.MIN_QUESTIONS,
        quota_units=fetched.quota_units,
        limitations=limitations,
    )
