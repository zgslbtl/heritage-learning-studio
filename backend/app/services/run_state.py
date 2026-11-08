from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..domain import (
    ASSESSMENT_KINDS,
    ASSESSMENT_STAGE_KIND,
    KIND_LABELS,
    assessment_version_for_design,
    design_version_for_assessment,
    rationale_schema_for_design,
    LEGACY_STAGES,
    NEXT_AFTER_ASSESSMENT,
    Stage,
    TASK_LABELS,
    group_artifact_order,
    group_artifact_sequence,
    group_condition_sequence,
    group_t1_condition,
    class_group_quota,
    round_assignment,
)
from .assignment import allocation_seed_hash
from ..errors import AppError
from ..prompts.hlsf import HLSF_V110_VERSION
from ..models import (
    ArtifactVersion,
    ClassGroup,
    HLSFState,
    ImageJob,
    InstrumentVersion,
    Participant,
    ProtocolAssessmentForm,
    ProtocolVersion,
    Round,
    Run,
    StageEvent,
    WorkRevision,
)
from ..schemas import WorkUpdate
from .artifacts import student_artifact
from .hlsf import guide_payload, load_state, start_guide
from .readiness import active_protocol
from .works import latest_work, validate_work_for_finish, work_form_for, work_payload

ROUND_STAGE = {
    1: Stage.T1_ACTIVE.value,
    2: Stage.T2_ACTIVE.value,
}
READY_STAGE = {
    1: Stage.T1_READY.value,
    2: Stage.T2_READY.value,
}
NEXT_ROUND_STAGE = {
    1: Stage.K1.value,
    2: Stage.K3.value,
}
STEP_BY_STAGE = {
    Stage.K0.value: 1,
    Stage.TUTORIAL.value: 1,
    Stage.T1_READY.value: 2,
    Stage.T1_ACTIVE.value: 2,
    Stage.K1.value: 3,
    Stage.K2.value: 3,
    Stage.T2_READY.value: 4,
    Stage.T2_ACTIVE.value: 4,
    Stage.K3.value: 5,
    Stage.SURVEY.value: 5,
    Stage.PEER_ASSESSMENT.value: 6,
    Stage.SOCIAL_FEED.value: 6,
    Stage.COMPLETE.value: 6,
}
STAGE_LABELS = {
    Stage.K0.value: "K0 · 文物知识前测 / Knowledge Pre-test",
    Stage.TUTORIAL.value: "操作说明 / Tutorial",
    Stage.T1_READY.value: "T1 · 文物理解与文创共创",
    Stage.T1_ACTIVE.value: "T1 · 文物理解与文创共创",
    Stage.K1.value: "K1 · T1 知识后测 / T1 Knowledge Post-test",
    Stage.K2.value: "K2 · T2 文物知识前测 / T2 Knowledge Pre-test",
    Stage.T2_READY.value: "T2 · 新文物迁移共创",
    Stage.T2_ACTIVE.value: "T2 · 新文物迁移共创",
    Stage.K3.value: "K3 · T2 知识后测 / T2 Knowledge Post-test",
    Stage.SURVEY.value: "体验问卷 / Experience Survey",
    Stage.PEER_ASSESSMENT.value: "同伴互评 / Peer Assessment",
    Stage.SOCIAL_FEED.value: "作品广场 · 模拟 Instagram / Work Feed",
    Stage.COMPLETE.value: "完成 / Complete",
    # Legacy labels keep historical rows readable in the researcher console.
    "pre_test": "旧版前测 / Legacy Pre-test",
    "round1_ready": "旧版任务 1 / Legacy Task 1",
    "round1_active": "旧版任务 1 / Legacy Task 1",
    "r1_test": "旧版 R1 测试 / Legacy R1 Assessment",
    "round2_ready": "旧版任务 2 / Legacy Task 2",
    "round2_active": "旧版任务 2 / Legacy Task 2",
    "post_test": "旧版后测 / Legacy Post-test",
    "transfer": "旧版迁移题 / Legacy Transfer",
    "questionnaire": "旧版问卷 / Legacy Questionnaire",
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def iso(value: Optional[datetime]) -> Optional[str]:
    return aware(value).isoformat() if value else None


async def get_run(session: AsyncSession, participant_id) -> Optional[Run]:
    result = await session.execute(
        select(Run).where(Run.participant_id == participant_id)
    )
    return result.scalar_one_or_none()


async def get_run_locked(session: AsyncSession, run_id) -> Run:
    result = await session.execute(
        select(Run)
        .where(Run.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise AppError(404, "run_not_found", "Study run not found.")
    return run


async def get_protocol(session: AsyncSession, run: Run) -> ProtocolVersion:
    protocol = await session.get(ProtocolVersion, run.protocol_version_id)
    if not protocol:
        raise AppError(500, "protocol_missing", "The frozen study protocol is missing.")
    return protocol


async def get_class_name(session: AsyncSession, class_id: int) -> str:
    group = await session.get(ClassGroup, class_id)
    return group.name if group else f"班级 {class_id} / Class {class_id}"


def protocol_is_v15(protocol: ProtocolVersion) -> bool:
    keys = set((protocol.instrument_versions or {}).keys())
    return set(ASSESSMENT_KINDS).issubset(keys)


async def create_or_resume_run(
    session: AsyncSession,
    *,
    participant: Participant,
    settings: Settings,
) -> Run:
    existing = await get_run(session, participant.id)
    if existing:
        if existing.stage not in [stage.value for stage in Stage]:
            raise AppError(
                409,
                "legacy_run",
                "This participant belongs to an older study flow. Please use a fresh participant record.",
            )
        return existing
    protocol = await active_protocol(session)
    if not protocol:
        raise AppError(
            503,
            "study_setup_incomplete",
            "The study is not open yet: the researcher has not activated a protocol.",
        )
    if settings.is_production and protocol.is_demo:
        raise AppError(
            503,
            "study_setup_incomplete",
            "The study is not open for data collection.",
        )
    if not protocol_is_v15(protocol):
        raise AppError(
            503,
            "study_setup_incomplete",
            "The active protocol is not configured for the T1/T2 + K0-K3 study flow.",
        )
    try:
        t1_condition = group_t1_condition(participant.group_name)
        artifact_order = "".join(group_artifact_order(participant.group_name))
        condition_sequence = group_condition_sequence(participant.group_name)
        artifact_sequence = group_artifact_sequence(participant.group_name)
    except ValueError:
        raise AppError(500, "invalid_group", "The participant group is invalid.")
    artifact_x = await session.get(ArtifactVersion, protocol.artifact_x_version_id)
    artifact_y = await session.get(ArtifactVersion, protocol.artifact_y_version_id)
    slot_to_object = {
        "X": (artifact_x.object_code if artifact_x and artifact_x.object_code else "M"),
        "Y": (artifact_y.object_code if artifact_y and artifact_y.object_code else "T"),
    }
    object_order = "".join(slot_to_object[slot] for slot in artifact_order)
    # Measurement forms A/B are balanced within the participant's assigned
    # condition/object block. This is independent of the experimental condition.
    # Serialise the AB/BA counter within a class × group so concurrent first
    # logins cannot receive the same parity.  The lock is transaction-scoped.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"hlsf-form:{participant.class_id}:{participant.group_name}"},
    )
    prior_group_runs = (
        await session.execute(
            select(func.count())
            .select_from(Run)
            .join(Participant, Participant.id == Run.participant_id)
            .where(
                Participant.class_id == participant.class_id,
                Participant.group_name == participant.group_name,
            )
        )
    ).scalar_one()
    test_form_order = "AB" if prior_group_runs % 2 == 0 else "BA"
    design_version = design_version_for_assessment(protocol.assessment_version)
    run = Run(
        participant_id=participant.id,
        protocol_version_id=protocol.id,
        stage=Stage.K0.value,
        design_version=design_version,
        hlsf_prompt_version=HLSF_V110_VERSION,
        t1_condition=t1_condition,
        condition_sequence=condition_sequence,
        artifact_sequence=artifact_sequence,
        artifact_order=artifact_order,
        object_order=object_order,
        test_form_order=test_form_order,
        created_at=now_utc(),
        last_activity_at=now_utc(),
    )
    session.add(run)
    await session.flush()
    session.add(
        StageEvent(
            run_id=run.id,
            stage=Stage.K0.value,
            entered_at=now_utc(),
            meta_json={
                "assignment_method": "balanced-crossover-v1",
                "design_version": design_version,
                "hlsf_prompt_version": HLSF_V110_VERSION,
                "assessment_version": assessment_version_for_design(design_version),
                "rationale_schema_version": rationale_schema_for_design(design_version),
                "group": participant.group_name,
                "class_quota": class_group_quota(
                    participant.class_id, settings.participants_per_class
                ),
                "seed_hash": allocation_seed_hash(
                    settings.anon_code_pepper, participant.class_id
                ),
            },
        )
    )
    await session.flush()
    return run


async def transition_stage(
    session: AsyncSession,
    run: Run,
    new_stage: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    current_time = now_utc()
    last_result = await session.execute(
        select(StageEvent)
        .where(StageEvent.run_id == run.id, StageEvent.completed_at.is_(None))
        .order_by(StageEvent.id.desc())
        .limit(1)
    )
    previous_event = last_result.scalar_one_or_none()
    if previous_event:
        previous_event.completed_at = current_time
        previous_event.duration_seconds = max(
            0,
            int((current_time - aware(previous_event.entered_at)).total_seconds()),
        )
    run.stage = new_stage
    run.last_activity_at = current_time
    if new_stage == Stage.COMPLETE.value:
        run.completed_at = current_time
    session.add(
        StageEvent(
            run_id=run.id,
            stage=new_stage,
            entered_at=current_time,
            meta_json=meta or {},
        )
    )
    await session.flush()


async def get_round(session: AsyncSession, run_id, round_no: int) -> Optional[Round]:
    result = await session.execute(
        select(Round).where(Round.run_id == run_id, Round.round_no == round_no)
    )
    return result.scalar_one_or_none()


async def current_round(session: AsyncSession, run: Run) -> Optional[Round]:
    if run.stage == Stage.T1_ACTIVE.value:
        return await get_round(session, run.id, 1)
    if run.stage == Stage.T2_ACTIVE.value:
        return await get_round(session, run.id, 2)
    return None


async def require_active_round(
    session: AsyncSession, run: Run, round_no: int
) -> Round:
    if run.stage != ROUND_STAGE.get(round_no):
        raise AppError(
            409,
            "stage_not_active",
            "This task is not active. Refresh to see your current stage.",
        )
    round_obj = await get_round(session, run.id, round_no)
    if not round_obj:
        raise AppError(409, "round_not_started", "This task has not started.")
    return round_obj


async def sync_expired_stage(session: AsyncSession, run: Run) -> Run:
    if run.stage not in (Stage.T1_ACTIVE.value, Stage.T2_ACTIVE.value):
        return run
    locked_run = await get_run_locked(session, run.id)
    round_no = 1 if locked_run.stage == Stage.T1_ACTIVE.value else 2
    result = await session.execute(
        select(Round)
        .where(Round.run_id == locked_run.id, Round.round_no == round_no)
        .with_for_update()
    )
    round_obj = result.scalar_one_or_none()
    if not round_obj or round_obj.finished_at:
        return locked_run
    if aware(round_obj.deadline_at) > now_utc():
        return locked_run
    round_obj.finished_at = aware(round_obj.deadline_at)
    round_obj.finish_reason = "timeout"
    await transition_stage(
        session,
        locked_run,
        NEXT_ROUND_STAGE[round_no],
        {"reason": "timeout", "round_no": round_no},
    )
    return locked_run


async def start_round(
    session: AsyncSession, run: Run, round_no: int, settings: Settings
) -> Round:
    if run.stage != READY_STAGE.get(round_no):
        raise AppError(
            409,
            "stage_not_ready",
            "This task is not ready to start. Refresh to see your current stage.",
        )
    existing = await get_round(session, run.id, round_no)
    if existing:
        raise AppError(409, "round_already_started", "This task has already started.")
    protocol = await get_protocol(session, run)
    participant = await session.get(Participant, run.participant_id)
    if not participant:
        raise AppError(401, "not_authenticated", "Please sign in with your PolyU email.")
    slot, condition = round_assignment(
        participant.group_name, round_no, run.design_version
    )
    artifact_id = (
        protocol.artifact_x_version_id
        if slot == "X"
        else protocol.artifact_y_version_id
    )
    started = now_utc()
    duration = (
        settings.t1_duration_seconds if round_no == 1 else settings.t2_duration_seconds
    )
    round_obj = Round(
        run_id=run.id,
        round_no=round_no,
        artifact_version_id=artifact_id,
        condition=condition,
        started_at=started,
        deadline_at=started + timedelta(seconds=duration),
        current_work_revision=0,
    )
    session.add(round_obj)
    await session.flush()
    await transition_stage(
        session,
        run,
        ROUND_STAGE[round_no],
        {"round_no": round_no, "task": "T1" if round_no == 1 else "T2"},
    )
    # HLSF is enabled whenever this round's condition is B.  In the crossover
    # pilot that can be T1 (G3/G4) or T2 (G1/G2).
    if condition == "B":
        await start_guide(
            session, round_obj, run.design_version, run.hlsf_prompt_version
        )
    return round_obj


async def _class_id_for_run(session: AsyncSession, run: Run) -> int:
    participant = await session.get(Participant, run.participant_id)
    if not participant:
        raise AppError(401, "not_authenticated", "Please sign in with your PolyU email.")
    return participant.class_id


async def finish_round(
    session: AsyncSession,
    run: Run,
    round_no: int,
    settings: Settings,
    consent_future_research: Optional[bool] = None,
) -> Round:
    round_obj = await require_active_round(session, run, round_no)
    if round_obj.finished_at:
        return round_obj
    work = await latest_work(session, round_obj.id)
    validate_work_for_finish(
        round_no, round_obj.condition, work, run.design_version
    )
    current = now_utc()
    deadline = aware(round_obj.deadline_at)
    reason = "student_finished" if current <= deadline else "timeout"
    round_obj.finished_at = current if reason == "student_finished" else deadline
    round_obj.finish_reason = reason
    if round_no == 2 and consent_future_research is not None:
        run.consent_future_research = bool(consent_future_research)
        run.consent_recorded_at = current
        run.consent_version = "work-submit-v1"
    await transition_stage(
        session,
        run,
        NEXT_ROUND_STAGE[round_no],
        {"reason": reason, "round_no": round_no},
    )
    if round_no == 2:
        # Local import avoids a module import cycle: peer.py lazily imports
        # run_state to finalize expired T2 rounds.
        from .peer import maybe_auto_open_gate

        class_id = await _class_id_for_run(session, run)
        await maybe_auto_open_gate(session, class_id)
    return round_obj


async def complete_tutorial(session: AsyncSession, run: Run) -> Run:
    if run.stage != Stage.TUTORIAL.value:
        raise AppError(409, "stage_not_active", "The tutorial is not active.")
    await transition_stage(session, run, Stage.T1_READY.value, {"action": "tutorial_ack"})
    return run


def _form_for_stage(run: Run, kind: str) -> tuple[str, str]:
    """Return (object_code, form_code) for a K-stage.

    K0/K1 use the T1 object; K2/K3 use the T2 object.  The first form in
    ``test_form_order`` is used for K0/K2, the second for K1/K3.
    """
    object_order = run.object_order or ("MT" if run.artifact_order == "XY" else "TM")
    t1_object, t2_object = object_order[0], object_order[1]
    first, second = (run.test_form_order or "AB")
    form = first if kind in ("k0", "k2") else second
    object_code = t1_object if kind in ("k0", "k1") else t2_object
    return object_code, form


async def protocol_instrument(
    session: AsyncSession, run: Run, kind: str
) -> InstrumentVersion:
    protocol = await get_protocol(session, run)
    object_code, form_code = _form_for_stage(run, kind)
    form_row = (
        await session.execute(
            select(ProtocolAssessmentForm).where(
                ProtocolAssessmentForm.protocol_version_id == protocol.id,
                ProtocolAssessmentForm.kind == kind,
                ProtocolAssessmentForm.object_code == object_code,
                ProtocolAssessmentForm.form_code == form_code,
            )
        )
    ).scalar_one_or_none()
    if form_row:
        version = await session.get(InstrumentVersion, form_row.instrument_version_id)
        if version:
            return version
    # Legacy/demo protocols have one instrument per kind.
    raw = (protocol.instrument_versions or {}).get(kind)
    if not raw:
        raise AppError(
            503,
            "instrument_missing",
            "This assessment has not been configured for the active protocol.",
        )
    version = await session.get(InstrumentVersion, uuid.UUID(str(raw)))
    if not version:
        raise AppError(503, "instrument_missing", "This assessment version is missing.")
    return version


async def protocol_artifact(
    session: AsyncSession, run: Run, round_obj: Round
) -> ArtifactVersion:
    artifact = await session.get(ArtifactVersion, round_obj.artifact_version_id)
    if not artifact:
        raise AppError(503, "artifact_missing", "The artifact pack is missing.")
    return artifact


def stage_summary(run: Run) -> Dict[str, Any]:
    return {
        "stage": run.stage,
        "stage_label": STAGE_LABELS.get(run.stage, run.stage),
        "step": STEP_BY_STAGE.get(run.stage, 1),
        "total_steps": 6,
        "completed": run.stage == Stage.COMPLETE.value,
    }


def _hlsf_active_for(round_obj: Round) -> bool:
    return round_obj.condition == "B"


async def student_state(
    session: AsyncSession, run: Run, participant: Participant
) -> Dict[str, Any]:
    guide = None
    active_round = None
    round_obj = await current_round(session, run)
    if round_obj:
        remaining = max(
            0, int((aware(round_obj.deadline_at) - now_utc()).total_seconds())
        )
        guide_state = await load_state(session, round_obj.id)
        guide = guide_payload(
            guide_state, round_obj, run.design_version, run.hlsf_prompt_version
        )
        artifact = await session.get(ArtifactVersion, round_obj.artifact_version_id)
        active_round = {
            "round_no": round_obj.round_no,
            "task": "T1" if round_obj.round_no == 1 else "T2",
            "started_at": iso(round_obj.started_at),
            "deadline_at": iso(round_obj.deadline_at),
            "remaining_seconds": remaining,
            "artifact_title": artifact.title if artifact else "",
            "guide": guide,
        }
    assessment_kind = ASSESSMENT_STAGE_KIND.get(run.stage)
    return {
        "participant": {
            "id": str(participant.id),
            "class_id": participant.class_id,
            "class_name": await get_class_name(session, participant.class_id),
        },
        "run_id": str(run.id),
        **stage_summary(run),
        "assessment_kind": assessment_kind,
        "assessment_label": KIND_LABELS.get(assessment_kind)
        if assessment_kind
        else None,
        "active_round": active_round,
        "server_time": now_utc().isoformat(),
    }


async def round_payload(
    session: AsyncSession, run: Run, round_obj: Round
) -> Dict[str, Any]:
    artifact = await protocol_artifact(session, run, round_obj)
    revision = await latest_work(session, round_obj.id)
    jobs_result = await session.execute(
        select(ImageJob)
        .where(ImageJob.round_id == round_obj.id)
        .order_by(ImageJob.created_at.desc())
    )
    jobs = list(jobs_result.scalars().all())
    guide_state = await load_state(session, round_obj.id)
    remaining = max(0, int((aware(round_obj.deadline_at) - now_utc()).total_seconds()))
    return {
        "round_no": round_obj.round_no,
        "task": "T1" if round_obj.round_no == 1 else "T2",
        "task_label": TASK_LABELS.get(round_obj.round_no, ""),
        "work_form": work_form_for(
            round_obj.round_no, round_obj.condition, run.design_version
        ),
        "artifact": student_artifact(artifact),
        "work": work_payload(revision),
        "started_at": iso(round_obj.started_at),
        "deadline_at": iso(round_obj.deadline_at),
        "remaining_seconds": remaining,
        "finished": round_obj.finished_at is not None,
        "selected_image_job_id": str(round_obj.selected_image_job_id)
        if round_obj.selected_image_job_id
        else None,
        "image_jobs": [
            {
                "id": str(job.id),
                "status": job.status,
                "prompt": job.prompt,
                "attempts": job.attempts,
                "error_code": job.error_code,
                "error_message": job.error_message,
                "image_url": f"/api/files/keyframes/{job.id}"
                if job.status == "succeeded" and job.file_path
                else None,
                "width": job.width,
                "height": job.height,
                "created_at": job.created_at.isoformat(),
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            }
            for job in jobs
        ],
        "image_job_limit": 0,
        "guide": guide_payload(
            guide_state, round_obj, run.design_version, run.hlsf_prompt_version
        ),
    }
