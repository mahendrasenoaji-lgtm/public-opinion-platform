"""Survey builder, question management, respondent + response ingest.

Survey builder mendukung 9 tipe pertanyaan (schema.sql enum question_type).
Ingest respons otomatis menjalankan quality assessment dan menyimpan flag-nya.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.deps import CurrentUser, Role, TenantSession, require_role
from app.models.survey import Question, QuestionType, Respondent, Response, Survey
from app.schemas.survey import (
    QuestionCreate,
    QuestionOut,
    QuestionReorder,
    RespondentOut,
    ResponseBulk,
    ResponseOut,
    SurveyCreate,
    SurveyOut,
    SurveyUpdate,
    WeightingReport,
    WeightingTargets,
)
from app.services import weighting
from app.services.quality import assess

router = APIRouter(prefix="/surveys", tags=["surveys"])

_VALID_TYPES = {t.value for t in QuestionType}


# ── Survey CRUD ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[SurveyOut])
async def list_surveys(
    project_id: UUID | None = None,
    session: TenantSession = None,
    user: CurrentUser = None,
):
    q = select(Survey)
    if project_id:
        q = q.where(Survey.project_id == project_id)
    q = q.order_by(Survey.created_at.desc())
    result = await session.execute(q)
    return [SurveyOut.model_validate(s) for s in result.scalars()]


@router.get("/{survey_id}", response_model=SurveyOut)
async def get_survey(survey_id: UUID, session: TenantSession, user: CurrentUser):
    result = await session.execute(select(Survey).where(Survey.id == survey_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Survei tidak ditemukan.")
    return SurveyOut.model_validate(s)


@router.post(
    "",
    response_model=SurveyOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def create_survey(body: SurveyCreate, session: TenantSession, user: CurrentUser):
    survey = Survey(
        org_id=user.org_id,
        project_id=body.project_id,
        wave=body.wave,
        title=body.title,
        sampling_method=body.sampling_method,
        target_n=body.target_n,
        fielded_from=body.fielded_from,
        fielded_to=body.fielded_to,
        sampling_params=body.sampling_params or {},
    )
    session.add(survey)
    await session.flush()
    await session.refresh(survey)
    return SurveyOut.model_validate(survey)


@router.patch(
    "/{survey_id}",
    response_model=SurveyOut,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def update_survey(survey_id: UUID, body: SurveyUpdate, session: TenantSession):
    result = await session.execute(select(Survey).where(Survey.id == survey_id))
    survey = result.scalar_one_or_none()
    if not survey:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Survei tidak ditemukan.")

    for field in ("title", "sampling_method", "target_n", "fielded_from", "fielded_to"):
        val = getattr(body, field)
        if val is not None:
            setattr(survey, field, val)

    await session.flush()
    await session.refresh(survey)
    return SurveyOut.model_validate(survey)


# ── Question builder ────────────────────────────────────────────────────────

@router.get("/{survey_id}/questions", response_model=list[QuestionOut])
async def list_questions(survey_id: UUID, session: TenantSession, user: CurrentUser):
    result = await session.execute(
        select(Question)
        .where(Question.survey_id == survey_id)
        .order_by(Question.position)
    )
    return [QuestionOut.model_validate(q) for q in result.scalars()]


@router.post(
    "/{survey_id}/questions",
    response_model=QuestionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def add_question(
    survey_id: UUID,
    body: QuestionCreate,
    session: TenantSession,
    user: CurrentUser,
):
    if body.type not in _VALID_TYPES:
        raise HTTPException(
            422, f"Tipe pertanyaan tidak valid. Pilih dari: {', '.join(sorted(_VALID_TYPES))}",
        )

    # Pastikan survei ada (RLS sudah memfilter tenant)
    srv = await session.execute(select(Survey).where(Survey.id == survey_id))
    survey = srv.scalar_one_or_none()
    if not survey:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Survei tidak ditemukan.")

    q = Question(
        org_id=user.org_id,
        survey_id=survey_id,
        position=body.position,
        code=body.code,
        type=body.type,
        text=body.text,
        options=body.options or [],
        required=body.required,
        poi_dimension=body.poi_dimension,
        reverse_scored=body.reverse_scored,
    )
    session.add(q)
    await session.flush()
    await session.refresh(q)
    return QuestionOut.model_validate(q)


@router.put(
    "/{survey_id}/questions/reorder",
    response_model=list[QuestionOut],
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def reorder_questions(
    survey_id: UUID,
    body: QuestionReorder,
    session: TenantSession,
    user: CurrentUser,
):
    result = await session.execute(
        select(Question).where(Question.survey_id == survey_id)
    )
    by_id = {q.id: q for q in result.scalars()}

    for pos, qid in enumerate(body.question_ids):
        if qid not in by_id:
            raise HTTPException(422, f"Question {qid} tidak ditemukan di survei ini.")
        by_id[qid].position = pos

    await session.flush()
    return [
        QuestionOut.model_validate(by_id[qid])
        for qid in body.question_ids
    ]


@router.delete(
    "/{survey_id}/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def delete_question(survey_id: UUID, question_id: UUID, session: TenantSession):
    result = await session.execute(
        select(Question)
        .where(Question.survey_id == survey_id, Question.id == question_id)
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pertanyaan tidak ditemukan.")
    await session.delete(q)


# ── Response ingest ─────────────────────────────────────────────────────────

@router.post(
    "/{survey_id}/responses",
    response_model=RespondentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def ingest_responses(
    survey_id: UUID,
    body: ResponseBulk,
    session: TenantSession,
    user: CurrentUser,
):
    """Ingest satu respondent beserta seluruh jawabannya.

    Otomatis menjalankan quality assessment:
    - speeding: durasi vs median durasi lapangan
    - straight-lining: variasi nol pada item Likert
    - inconsistency: (belum ada trap pairs di request; bisa ditambah nanti)

    Flag disimpan di respondent, bukan di response. Keputusan mengeluarkan
    respondent tetap di manusia (CLAUDE.md §3).
    """
    srv = await session.execute(select(Survey).where(Survey.id == survey_id))
    survey = srv.scalar_one_or_none()
    if not survey:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Survei tidak ditemukan.")

    respondent = Respondent(
        org_id=user.org_id,
        survey_id=survey_id,
        anon_code=body.respondent.anon_code,
        age_band=body.respondent.age_band,
        gender=body.respondent.gender,
        education=body.respondent.education,
        occupation=body.respondent.occupation,
        province_code=body.respondent.province_code,
        urbanicity=body.respondent.urbanicity,
        duration_sec=body.respondent.duration_sec,
        completed_at=datetime.now(UTC),
    )
    session.add(respondent)
    await session.flush()

    for ans in body.answers:
        resp = Response(
            org_id=user.org_id,
            respondent_id=respondent.id,
            question_id=ans.question_id,
            value_num=ans.value_num,
            value_text=ans.value_text,
            value_json=ans.value_json,
        )
        session.add(resp)

    # Quality assessment — compute median duration from existing respondents
    median_q = await session.execute(
        select(func.percentile_cont(0.5).within_group(Respondent.duration_sec))
        .where(
            Respondent.survey_id == survey_id,
            Respondent.duration_sec.is_not(None),
        )
    )
    median_dur = median_q.scalar() or 0

    # Collect Likert/scale answers for straight-lining check
    scale_values: list[float] = []
    for ans in body.answers:
        if ans.value_num is not None:
            scale_values.append(float(ans.value_num))

    quality = assess(
        duration_sec=body.respondent.duration_sec or 0,
        median_duration_sec=float(median_dur),
        scale_answers=scale_values,
    )
    respondent.quality_score = quality.score
    respondent.quality_flags = [f.value for f in quality.flags]

    await session.flush()
    await session.refresh(respondent)
    return RespondentOut.model_validate(respondent)


@router.get("/{survey_id}/respondents", response_model=list[RespondentOut])
async def list_respondents(
    survey_id: UUID,
    session: TenantSession,
    user: CurrentUser,
    limit: int = 100,
    offset: int = 0,
):
    result = await session.execute(
        select(Respondent)
        .where(Respondent.survey_id == survey_id)
        .order_by(Respondent.completed_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [RespondentOut.model_validate(r) for r in result.scalars()]


@router.get("/{survey_id}/respondents/{respondent_id}/responses", response_model=list[ResponseOut])
async def get_responses(
    survey_id: UUID,
    respondent_id: UUID,
    session: TenantSession,
    user: CurrentUser,
):
    result = await session.execute(
        select(Response).where(Response.respondent_id == respondent_id)
    )
    return [ResponseOut.model_validate(r) for r in result.scalars()]


# ── Bobot pasca-stratifikasi ────────────────────────────────────────────────

@router.post(
    "/{survey_id}/weights/compute",
    response_model=WeightingReport,
    dependencies=[Depends(require_role(Role.RESEARCHER))],
)
async def compute_weights(
    survey_id: UUID,
    body: WeightingTargets,
    session: TenantSession,
    user: CurrentUser,
):
    """Hitung dan simpan bobot pasca-stratifikasi (raking) untuk semua
    responden survei ini.

    Menimpa `Respondent.weight` yang ada. Logika raking murni ada di
    services/weighting.py — router ini cuma memuat responden, memanggilnya,
    dan menyimpan hasilnya. Peringatan dari raking (non-konvergensi, kategori
    tanpa target, bobot dipangkas) dikembalikan apa adanya; UI wajib
    menampilkannya, bukan menyembunyikannya.
    """
    srv = await session.execute(select(Survey).where(Survey.id == survey_id))
    survey = srv.scalar_one_or_none()
    if not survey:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Survei tidak ditemukan.")

    result = await session.execute(select(Respondent).where(Respondent.survey_id == survey_id))
    respondents = list(result.scalars())
    if not respondents:
        raise HTTPException(422, "Survei ini belum punya responden.")

    strata: dict[str, dict[str, str | None]] = {
        str(r.id): {
            "age_band": r.age_band,
            "gender": r.gender,
            "education": r.education,
            "occupation": r.occupation,
            "province_code": r.province_code,
            "urbanicity": r.urbanicity,
        }
        for r in respondents
    }

    try:
        raked = weighting.rake_weights(
            strata,
            body.targets,
            max_iterations=body.max_iterations,
            trim_ratio=body.trim_ratio,
        )
    except ValueError as e:
        raise HTTPException(422, str(e)) from e

    for r in respondents:
        r.weight = Decimal(str(raked.weights[str(r.id)])).quantize(Decimal("0.0001"))

    await session.flush()

    return WeightingReport(
        survey_id=survey_id,
        respondent_count=len(respondents),
        iterations=raked.iterations,
        converged=raked.converged,
        trimmed_count=raked.trimmed_count,
        max_weight=raked.max_weight,
        min_weight=raked.min_weight,
        warnings=raked.warnings,
    )
