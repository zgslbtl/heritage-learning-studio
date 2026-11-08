from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain import ASSESSMENT_STAGE_KIND, NEXT_AFTER_ASSESSMENT
from ..errors import AppError
from ..models import AssessmentItemKey, ArtifactVersion, AssessmentResponse, Run
from ..schemas import InstrumentPayload
from .instruments import instrument_payload, validate_answers
from .survey import SURVEY_V3, survey_v3_scores
from .run_state import get_protocol, protocol_instrument, transition_stage, aware


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def assessment_context(
    session: AsyncSession, run: Run, kind: str
) -> Tuple[Any, AssessmentResponse]:
    # Serialize draft creation per run. React development mode and real browser
    # retries can issue concurrent GETs; without this lock both requests can miss
    # the row and race the (run_id, kind) unique constraint.
    await session.execute(
        select(Run.id)
        .where(Run.id == run.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    expected = ASSESSMENT_STAGE_KIND.get(run.stage)
    if expected != kind:
        raise AppError(
            409,
            "assessment_not_active",
            "This assessment is not active. Refresh to see your current stage.",
        )
    version = await protocol_instrument(session, run, kind)
    result = await session.execute(
        select(AssessmentResponse).where(
            AssessmentResponse.run_id == run.id, AssessmentResponse.kind == kind
        )
    )
    response = result.scalar_one_or_none()
    if response is None:
        response = AssessmentResponse(
            run_id=run.id,
            kind=kind,
            instrument_version_id=version.id,
            answers_json={},
            status="draft",
        )
        session.add(response)
        await session.flush()
    return version, response


async def assessment_payload(
    session: AsyncSession, run: Run, kind: str, create: bool = True
) -> Dict[str, Any]:
    if create:
        version, response = await assessment_context(session, run, kind)
    else:
        expected = ASSESSMENT_STAGE_KIND.get(run.stage)
        if expected != kind:
            raise AppError(409, "assessment_not_active", "This assessment is not active.")
        version = await protocol_instrument(session, run, kind)
        result = await session.execute(
            select(AssessmentResponse).where(
                AssessmentResponse.run_id == run.id,
                AssessmentResponse.kind == kind,
            )
        )
        response = result.scalar_one_or_none()
    payload = instrument_payload(version)
    payload.pop("is_demo", None)
    image_url = None
    if kind in ("k0", "k1", "k2", "k3"):
        protocol = await get_protocol(session, run)
        order = run.artifact_order or "XY"
        slot = order[0] if kind in ("k0", "k1") else order[1]
        artifact_id = (
            protocol.artifact_x_version_id if slot == "X" else protocol.artifact_y_version_id
        )
        artifact = await session.get(ArtifactVersion, artifact_id)
        if artifact:
            primary_key = next(
                (
                    str(item.get("key"))
                    for item in (artifact.media_json or [])
                    if isinstance(item, dict) and item.get("key")
                ),
                None,
            )
            if primary_key:
                image_url = f"/api/files/artifacts/{artifact.id}/media/{primary_key}"
            elif artifact.image_path:
                image_url = f"/api/files/artifacts/{artifact.id}/image"
    return {
        "instrument": payload,
        "answers": response.answers_json if response else {},
        "status": response.status if response else "draft",
        "started_at": response.started_at.isoformat() if response else None,
        "updated_at": response.updated_at.isoformat() if response else None,
        "artifact_image_url": image_url,
    }


async def save_draft(
    session: AsyncSession, run: Run, kind: str, answers: Dict[str, Any]
) -> AssessmentResponse:
    version, response = await assessment_context(session, run, kind)
    if response.status == "submitted":
        raise AppError(409, "assessment_submitted", "This assessment is already submitted.")
    cleaned, _, _ = validate_answers(
        version.schema_json or InstrumentPayload(
            title="", questions=[]
        ).model_dump(),
        answers,
        require_complete=False,
    )
    response.answers_json = cleaned
    response.updated_at = _now()
    await session.flush()
    return response


async def submit_assessment(
    session: AsyncSession, run: Run, kind: str, answers: Dict[str, Any]
) -> AssessmentResponse:
    version, response = await assessment_context(session, run, kind)
    if response.status == "submitted":
        raise AppError(409, "assessment_submitted", "This assessment is already submitted.")
    cleaned, _, _ = validate_answers(
        version.schema_json or {}, answers, require_complete=True
    )
    submitted = _now()
    response.answers_json = cleaned
    response.status = "submitted"
    response.submitted_at = submitted
    response.updated_at = submitted
    response.duration_seconds = max(
        0, int((submitted - aware(response.started_at)).total_seconds())
    )
    await _score_submission(session, version, response, cleaned)
    next_stage = NEXT_AFTER_ASSESSMENT[kind]
    await transition_stage(
        session,
        run,
        next_stage,
        {"assessment": kind, "duration_seconds": response.duration_seconds},
    )
    await session.flush()
    return response


async def _score_submission(
    session: AsyncSession, version, response: AssessmentResponse, answers: Dict[str, Any]
) -> None:
    """Score objective items for researcher use only.

    The student payload never includes this result. Short-answer items have no
    ``correct_value`` and remain for manual scoring outside the student UI.
    """
    if version.kind == "survey" and (version.schema_json or {}).get("survey_version") == SURVEY_V3:
        response.score_json = survey_v3_scores(SURVEY_V3, answers)
        response.score_total = None
        response.scoring_version = SURVEY_V3
        response.scored_at = _now()
        return
    keys = (
        await session.execute(
            select(AssessmentItemKey).where(
                AssessmentItemKey.instrument_version_id == version.id
            )
        )
    ).scalars().all()
    if not keys:
        return
    by_question = {key.question_id: key for key in keys}
    scores: Dict[str, Any] = {}
    total = 0
    for question in (version.schema_json or {}).get("questions", []):
        qid = question.get("id")
        key = by_question.get(qid)
        if not key or not key.correct_value:
            continue
        answer = answers.get(qid)
        is_correct = isinstance(answer, str) and answer == key.correct_value
        score = key.max_score if is_correct else 0
        total += score
        scores[qid] = {
            "answer": answer,
            "correct_value": key.correct_value,
            "correct": is_correct,
            "score": score,
            "max_score": key.max_score,
            "construct": key.construct,
        }
    if scores:
        response.score_json = scores
        response.score_total = total
        response.scoring_version = str(
            (version.schema_json or {}).get("scoring_version") or "k-v1.0"
        )
        response.scored_at = _now()
