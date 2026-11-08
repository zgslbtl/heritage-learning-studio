from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..domain import STAGE_ORDER
from ..dependencies import StudentContext, get_current_student, get_session, get_settings
from ..errors import AppError
from ..models import (
    ArtifactVersion,
    EvidenceEvent,
    HLSFEvent,
    ImageJob,
    Message,
    Participant,
    PeerAssignment,
    Round,
    Run,
)
from ..schemas import (
    AssessmentDraft,
    ChatCreate,
    EvidenceView,
    HLSFAdvance,
    HLSFHint,
    HLSFNudge,
    FinishRequest,
    ImageJobCreate,
    PeerImpressionRequest,
    PeerRatingRequest,
    ScriptUpdate,
    SocialCommentRequest,
    WorkUpdate,
)
from ..services.ai_text import list_messages, request_chat_reply
from ..services.assessments import (
    assessment_payload,
    save_draft,
    submit_assessment,
)
from ..services.hlsf import advance_guide, deliver_hint, guide_payload, load_state
from ..services.image_queue import enqueue_image_job, select_image_job
from ..services.peer import (
    maybe_auto_open_gate,
    peer_gate_is_open,
    peer_payload,
    peer_progress,
    record_peer_impression,
    submit_peer_rating,
)
from ..services.run_state import (
    complete_tutorial,
    current_round,
    finish_round,
    get_run,
    now_utc,
    require_active_round,
    round_payload,
    start_round,
    student_state,
    sync_expired_stage,
    transition_stage,
    aware,
)
from ..services.scripts import save_script
from ..services.serialization import image_job_payload, message_payload
from ..services.social import add_comment, feed_payload, record_view, toggle_like
from ..services.works import (
    latest_work,
    save_work,
    work_payload,
    T1_FIELD_LABELS,
    RATIONALE_FIELD_LABELS,
)

router = APIRouter(prefix="/api/student", tags=["student"])


def _student_round_or_404(message: str = "Task not found."):
    return AppError(404, "not_found", message)


async def _load_run(
    db: AsyncSession,
    student: StudentContext,
) -> Run:
    run = await get_run(db, student.participant.id)
    if not run:
        raise AppError(401, "run_not_found", "Please sign in again with your PolyU email.")
    if run.stage not in STAGE_ORDER:
        raise AppError(
            409,
            "legacy_run",
            "This participant belongs to an older study flow. Please use a fresh participant record.",
        )
    if run.stage in ("t1_active", "t2_active"):
        run = await sync_expired_stage(db, run)
    run.last_activity_at = now_utc()
    await db.commit()
    return run


async def _active_round_for(
    db: AsyncSession, run: Run, round_no: int
) -> Round:
    round_obj = await require_active_round(db, run, round_no)
    if aware(round_obj.deadline_at) <= now_utc():
        raise AppError(409, "round_expired", "The task time has ended.")
    return round_obj


@router.get("/state")
async def state(
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    run = await _load_run(db, student)
    payload = await student_state(db, run, student.participant)
    if payload.get("active_round"):
        payload["active_round"]["image_job_limit"] = (
            settings.image_job_limit_per_round
        )
    return payload


@router.get("/rounds/{round_no}")
async def get_round_payload(
    round_no: int,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    run = await _load_run(db, student)
    round_obj = await require_active_round(db, run, round_no)
    payload = await round_payload(db, run, round_obj)
    payload["image_job_limit"] = settings.image_job_limit_per_round
    return payload


@router.post("/rounds/{round_no}/start")
async def begin_round(
    round_no: int,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    run = await _load_run(db, student)
    round_obj = await start_round(db, run, round_no, settings)
    await db.commit()
    state_payload = await student_state(db, run, student.participant)
    payload = await round_payload(db, run, round_obj)
    payload["image_job_limit"] = settings.image_job_limit_per_round
    return {"state": state_payload, "round": payload}


@router.post("/rounds/{round_no}/finish")
async def end_round(
    round_no: int,
    payload: Optional[FinishRequest] = None,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    run = await _load_run(db, student)
    if run.stage not in ("t1_active", "t2_active"):
        return {"state": await student_state(db, run, student.participant)}
    if (round_no == 1 and run.stage != "t1_active") or (
        round_no == 2 and run.stage != "t2_active"
    ):
        raise AppError(409, "stage_not_active", "This task is not active.")
    round_obj = await finish_round(
        db,
        run,
        round_no,
        settings,
        consent_future_research=payload.consent_future_research if payload else None,
    )
    await db.commit()
    return {
        "state": await student_state(db, run, student.participant),
        "finished_at": round_obj.finished_at.isoformat()
        if round_obj.finished_at
        else None,
    }


@router.post("/tutorial/complete")
async def tutorial_complete(
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    await complete_tutorial(db, run)
    await db.commit()
    return {"state": await student_state(db, run, student.participant)}


@router.put("/rounds/{round_no}/work")
async def update_work(
    round_no: int,
    payload: WorkUpdate,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    round_obj = await require_active_round(db, run, round_no)
    if aware(round_obj.deadline_at) <= now_utc():
        raise AppError(409, "round_expired", "The task time has ended.")
    revision, created = await save_work(
        db, round_obj, payload, source="autosave", design_version=run.design_version
    )
    await db.commit()
    return {
        "work": work_payload(revision),
        "revision": revision.revision_no if revision else None,
        "created": created,
    }


@router.put("/rounds/{round_no}/script")
async def update_script(
    round_no: int,
    payload: ScriptUpdate,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    round_obj = await require_active_round(db, run, round_no)
    if aware(round_obj.deadline_at) <= now_utc():
        raise AppError(409, "round_expired", "The task time has ended.")
    revision, created = await save_script(
        db, round_obj, payload.title, payload.body, source="autosave"
    )
    await db.commit()
    return {
        "revision": revision.revision_no if revision else None,
        "created": created,
        "title": revision.title if revision else "",
        "body": revision.body if revision else "",
        "updated_at": revision.created_at.isoformat() if revision else None,
    }


@router.get("/rounds/{round_no}/messages")
async def messages(
    round_no: int,
    after_id: Optional[int] = None,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    round_obj = await require_active_round(db, run, round_no)
    result = await list_messages(db, round_obj.id, after_id)
    guide_state = await load_state(db, round_obj.id)
    return {
        "messages": [message_payload(message) for message in result],
        "guide": guide_payload(
            guide_state, round_obj, run.design_version, run.hlsf_prompt_version
        ),
    }


@router.post("/rounds/{round_no}/messages")
async def send_message(
    round_no: int,
    payload: ChatCreate,
    request: Request,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    run = await _load_run(db, student)
    round_obj = await require_active_round(db, run, round_no)
    if aware(round_obj.deadline_at) <= now_utc():
        raise AppError(409, "round_expired", "The task time has ended.")
    existing = await db.execute(
        select(Message).where(
            Message.round_id == round_obj.id,
            Message.client_message_id == payload.client_message_id,
        )
    )
    duplicate = existing.scalar_one_or_none()
    if duplicate:
        return {
            "duplicate": True,
            "messages": [message_payload(duplicate)],
        }
    last_result = await db.execute(
        select(Message)
        .where(Message.round_id == round_obj.id)
        .order_by(Message.id.desc())
        .limit(1)
    )
    last = last_result.scalar_one_or_none()
    if last and last.role == "user":
        raise AppError(
            409,
            "message_pending",
            "The previous message did not receive a reply. Retry it before sending another.",
            {"message_id": last.id},
        )
    user_message = Message(
        round_id=round_obj.id,
        role="user",
        source="student",
        content=payload.content.strip(),
        client_message_id=payload.client_message_id,
    )
    db.add(user_message)
    await db.flush()
    if round_obj.condition == "B":
        hlsf_state = await load_state(db, round_obj.id)
        if hlsf_state and hlsf_state.phase != "complete":
            db.add(
                HLSFEvent(
                    round_id=round_obj.id,
                    phase=hlsf_state.phase,
                    action="student_message",
                    message_id=user_message.id,
                )
            )
    await db.commit()
    await db.refresh(user_message)
    from ..services.coordination import chat_lock
    async with chat_lock(request.app.state.db, round_obj.id):
        assistant = await request_chat_reply(db, settings, run, round_obj)
    guide_state = await load_state(db, round_obj.id)
    return {
        "duplicate": False,
        "messages": [message_payload(user_message), message_payload(assistant)],
        "guide": guide_payload(
            guide_state, round_obj, run.design_version, run.hlsf_prompt_version
        ),
    }


@router.post("/rounds/{round_no}/messages/{message_id}/retry")
async def retry_message(
    round_no: int,
    message_id: int,
    request: Request,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    run = await _load_run(db, student)
    round_obj = await require_active_round(db, run, round_no)
    if aware(round_obj.deadline_at) <= now_utc():
        raise AppError(409, "round_expired", "The task time has ended.")
    target = await db.get(Message, message_id)
    if not target or target.round_id != round_obj.id or target.role != "user":
        raise AppError(404, "message_not_found", "Message not found.")
    latest_result = await db.execute(
        select(Message)
        .where(Message.round_id == round_obj.id)
        .order_by(Message.id.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()
    if latest and latest.id != target.id:
        raise AppError(
            409,
            "message_not_latest",
            "Only the latest unanswered message can be retried.",
        )
    from ..services.coordination import chat_lock
    async with chat_lock(request.app.state.db, round_obj.id):
        assistant = await request_chat_reply(
            db, settings, run, round_obj, purpose="chat_retry"
        )
    return {"messages": [message_payload(assistant)]}


@router.post("/rounds/{round_no}/hlsf/advance")
async def hlsf_advance(
    round_no: int,
    payload: HLSFAdvance,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    round_obj = await require_active_round(db, run, round_no)
    if round_obj.condition != "B":
        raise AppError(404, "not_found", "Not found.")
    if aware(round_obj.deadline_at) <= now_utc():
        raise AppError(409, "round_expired", "The task time has ended.")
    guide_state, new_messages = await advance_guide(
        db,
        round_obj,
        payload.from_phase,
        payload.skip,
        run.design_version,
        run.hlsf_prompt_version,
    )
    await db.commit()
    return {
        "guide": guide_payload(
            guide_state, round_obj, run.design_version, run.hlsf_prompt_version
        ),
        "messages": [message_payload(message) for message in new_messages],
    }


@router.post("/rounds/{round_no}/hlsf/hint")
async def hlsf_hint(
    round_no: int,
    payload: HLSFHint,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    round_obj = await require_active_round(db, run, round_no)
    if round_obj.condition != "B":
        raise AppError(404, "not_found", "Not found.")
    if aware(round_obj.deadline_at) <= now_utc():
        raise AppError(409, "round_expired", "The task time has ended.")
    guide_state, message = await deliver_hint(
        db,
        round_obj,
        payload.phase,
        run.design_version,
        run.hlsf_prompt_version,
    )
    await db.commit()
    return {
        "guide": guide_payload(
            guide_state, round_obj, run.design_version, run.hlsf_prompt_version
        ),
        "messages": [message_payload(message)],
    }


@router.post("/rounds/{round_no}/hlsf/nudge")
async def hlsf_nudge(
    round_no: int,
    payload: HLSFNudge,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    """Record that the phase-stall prompt was shown, dismissed or acted on.

    The prompt is a client-side affordance; this endpoint only keeps the research
    trail.  A stale phase is reported as "not recorded" instead of an error so a
    race with Next/Skip never surfaces to the student.
    """
    run = await _load_run(db, student)
    round_obj = await require_active_round(db, run, round_no)
    if round_obj.condition != "B":
        raise AppError(404, "not_found", "Not found.")
    guide_state = await load_state(db, round_obj.id)
    if (
        not guide_state
        or guide_state.phase == "complete"
        or guide_state.phase != payload.phase
    ):
        return {"recorded": False}
    event = HLSFEvent(
        round_id=round_obj.id,
        phase=guide_state.phase,
        action=f"nudge_{payload.action}",
        meta_json={"user_turns": payload.user_turns},
    )
    db.add(event)
    await db.commit()
    return {"recorded": True, "id": event.id}


@router.post("/rounds/{round_no}/evidence-events")
async def record_evidence_event(
    round_no: int,
    payload: EvidenceView,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    round_obj = await require_active_round(db, run, round_no)
    event = EvidenceEvent(
        round_id=round_obj.id,
        section=payload.section,
        event_type=payload.event_type,
        duration_ms=payload.duration_ms,
        meta_json=payload.meta,
    )
    db.add(event)
    await db.commit()
    return {"ok": True, "id": event.id}


@router.post("/rounds/{round_no}/image-jobs")
async def create_image_job(
    round_no: int,
    payload: ImageJobCreate,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    run = await _load_run(db, student)
    round_obj = await require_active_round(db, run, round_no)
    job = await enqueue_image_job(
        db, settings, run, round_obj, retry_of=payload.retry_of
    )
    await db.commit()
    from ..services.cloud_tasks import dispatch_task
    await dispatch_task(db, settings, job.id)
    return {"job": image_job_payload(job)}


@router.post("/rounds/{round_no}/image-jobs/{job_id}/select")
async def select_round_image(
    round_no: int,
    job_id: str,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    round_obj = await require_active_round(db, run, round_no)
    await select_image_job(db, round_obj, job_id)
    await db.commit()
    return {"ok": True, "selected_image_job_id": str(round_obj.selected_image_job_id)}


@router.get("/image-jobs/{job_id}")
async def get_image_job(
    job_id: str,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    import uuid as uuid_module

    try:
        job_uuid = uuid_module.UUID(job_id)
    except ValueError:
        raise AppError(404, "image_job_not_found", "Image task not found.")
    result = await db.execute(
        select(ImageJob)
        .join(Round, Round.id == ImageJob.round_id)
        .join(Run, Run.id == Round.run_id)
        .where(
            ImageJob.id == job_uuid,
            Run.participant_id == student.participant.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise AppError(404, "image_job_not_found", "Image task not found.")
    if settings.queue_backend == "vercel" and job.status in ("queued", "running"):
        from ..services.cloud_tasks import dispatch_task
        await dispatch_task(db, settings, job.id)
        await db.refresh(job)
    return {"job": image_job_payload(job)}


@router.get("/instruments/{kind}")
async def get_assessment(
    kind: str,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    payload = await assessment_payload(db, run, kind)
    await db.commit()
    payload["server_time"] = now_utc().isoformat()
    return payload


@router.put("/instruments/{kind}/draft")
async def save_assessment_draft(
    kind: str,
    payload: AssessmentDraft,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    response = await save_draft(db, run, kind, payload.answers)
    await db.commit()
    return {
        "status": response.status,
        "answers": response.answers_json,
        "updated_at": response.updated_at.isoformat(),
    }


@router.post("/instruments/{kind}/submit")
async def submit_assessment_route(
    kind: str,
    payload: AssessmentDraft,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    response = await submit_assessment(db, run, kind, payload.answers)
    await db.commit()
    return {
        "status": response.status,
        "submitted_at": response.submitted_at.isoformat()
        if response.submitted_at
        else None,
        "state": await student_state(db, run, student.participant),
    }


@router.get("/peer-assessment")
async def get_peer_assessment(
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    if run.stage != "peer_assessment":
        raise AppError(409, "stage_not_active", "Peer assessment is not active.")
    payload = await peer_payload(db, run, student.participant)
    await db.commit()
    return payload


@router.post("/peer-assessment/complete")
async def complete_peer_assessment(
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    if run.stage != "peer_assessment":
        raise AppError(409, "stage_not_active", "Peer assessment is not active.")
    await maybe_auto_open_gate(db, student.participant.class_id)
    if student.participant.class_id == 0:
        await peer_payload(db, run, student.participant)
    if not await peer_gate_is_open(db, student.participant.class_id):
        raise AppError(409, "peer_gate_not_open", "The class has not finished T2 yet.")
    submitted, total = await peer_progress(db, run)
    if total and submitted < total:
        raise AppError(
            409,
            "peer_incomplete",
            "Please submit every assigned peer assessment before continuing.",
            {"submitted": submitted, "total": total},
        )
    await transition_stage(db, run, "social_feed", {"action": "peer_complete"})
    await db.commit()
    return {"state": await student_state(db, run, student.participant)}


@router.post("/peer-assessment/{assignment_id}/impression")
async def record_peer_assessment_impression(
    assignment_id: str,
    payload: PeerImpressionRequest,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    if run.stage != "peer_assessment":
        raise AppError(409, "stage_not_active", "Peer assessment is not active.")
    if not await peer_gate_is_open(db, student.participant.class_id):
        raise AppError(409, "peer_gate_not_open", "The class has not finished T2 yet.")
    impression = await record_peer_impression(
        db, run, assignment_id, payload.viewed_ms
    )
    await db.commit()
    return {
        "ok": True,
        "assignment_id": str(impression.assignment_id),
        "viewed_ms": impression.viewed_ms,
        "shown_at": impression.shown_at.isoformat(),
    }


@router.post("/peer-assessment/{assignment_id}")
async def submit_peer_assessment(
    assignment_id: str,
    payload: PeerRatingRequest,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    if run.stage != "peer_assessment":
        raise AppError(409, "stage_not_active", "Peer assessment is not active.")
    if not await peer_gate_is_open(db, student.participant.class_id):
        raise AppError(409, "peer_gate_not_open", "The class has not finished T2 yet.")
    rating = await submit_peer_rating(db, run, assignment_id, payload)
    await db.commit()
    data = await peer_payload(db, run, student.participant)
    await db.commit()
    return {
        "rating": {
            "assignment_id": str(rating.assignment_id),
            "scores": rating.scores_json,
            "comment": rating.comment,
        },
        **data,
    }


@router.get("/portfolio")
async def get_portfolio(
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    """Own T1/T2 works and selected images for the final PDF export."""
    run = await _load_run(db, student)
    if run.stage not in ("social_feed", "complete"):
        raise AppError(409, "stage_not_active", "The work feed is not active.")
    rounds = list(
        (
            await db.execute(
                select(Round)
                .where(Round.run_id == run.id)
                .order_by(Round.round_no)
            )
        ).scalars()
    )
    works = []
    for round_obj in rounds:
        work = await latest_work(db, round_obj.id)
        if not work:
            continue
        artifact = await db.get(ArtifactVersion, round_obj.artifact_version_id)
        job = None
        if round_obj.selected_image_job_id:
            job = await db.get(ImageJob, round_obj.selected_image_job_id)
        if not job or job.status != "succeeded" or not job.file_path:
            result = await db.execute(
                select(ImageJob)
                .where(ImageJob.round_id == round_obj.id, ImageJob.status == "succeeded")
                .order_by(ImageJob.created_at.desc())
                .limit(1)
            )
            job = result.scalar_one_or_none()
        structured = work.structured_fields or {}
        rationale = work.rationale_fields or {}
        statement = (work.open_statement or "").strip()
        if not statement and rationale:
            statement = " ".join(
                f"{RATIONALE_FIELD_LABELS[key]}：{str(value).strip()}"
                for key, value in rationale.items()
                if str(value).strip()
            )
        if not statement and structured:
            statement = " ".join(
                f"{T1_FIELD_LABELS[key]}：{str(value).strip()}"
                for key, value in structured.items()
                if str(value).strip()
            )
        works.append(
            {
                "round_no": round_obj.round_no,
                "artifact_title": artifact.title if artifact else "",
                "image_url": f"/api/files/keyframes/{job.id}"
                if job and job.status == "succeeded" and job.file_path
                else None,
                "product_name": work.product_name or "未命名作品",
                "product_category": work.product_category or "",
                "target_audience": work.target_audience or "",
                "design_concept": work.design_concept or "",
                "statement": statement,
            }
        )
    return {"works": works}


@router.get("/social-feed")
async def get_social_feed(
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    if run.stage != "social_feed":
        raise AppError(409, "stage_not_active", "The work feed is not active.")
    return await feed_payload(db, run, student.participant)


@router.post("/social/works/{work_id}/view")
async def record_social_view(
    work_id: int,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    if run.stage != "social_feed":
        raise AppError(409, "stage_not_active", "The work feed is not active.")
    await record_view(db, run, student.participant, work_id)
    await db.commit()
    return {"ok": True}


@router.post("/social/works/{work_id}/like")
async def toggle_social_like(
    work_id: int,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    if run.stage != "social_feed":
        raise AppError(409, "stage_not_active", "The work feed is not active.")
    result = await toggle_like(db, run, student.participant, work_id)
    await db.commit()
    return result


@router.post("/social/works/{work_id}/comment")
async def post_social_comment(
    work_id: int,
    payload: SocialCommentRequest,
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    if run.stage != "social_feed":
        raise AppError(409, "stage_not_active", "The work feed is not active.")
    comment = await add_comment(db, run, student.participant, work_id, payload.content)
    await db.commit()
    return {
        "comment": {
            "id": comment.id,
            "content": comment.content,
            "created_at": comment.created_at.isoformat(),
        }
    }


@router.post("/social/complete")
async def complete_social_feed(
    student: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_session),
):
    run = await _load_run(db, student)
    if run.stage != "social_feed":
        raise AppError(409, "stage_not_active", "The work feed is not active.")
    await transition_stage(db, run, "complete", {"action": "social_complete"})
    await db.commit()
    return {"state": await student_state(db, run, student.participant)}
