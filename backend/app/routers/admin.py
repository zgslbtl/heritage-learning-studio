from __future__ import annotations

import csv
import io
import json
import secrets
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from ..config import Settings
from ..dependencies import AdminContext, get_current_admin, get_session, get_settings
from ..domain import ASSESSMENT_KINDS, SLOTS
from ..errors import AppError
from ..models import (
    AiCall,
    ApiError,
    ArtifactVersion,
    AssessmentResponse,
    ClassEntryLink,
    ClassGroup,
    ClassPeerGate,
    ClassPeerGateEvent,
    EvidenceEvent,
    HLSFEvent,
    ImageJob,
    InstrumentVersion,
    Message,
    Participant,
    PeerAssignment,
    PeerRating,
    ProtocolVersion,
    Round,
    Run,
    ScriptRevision,
    SocialComment,
    SocialEvent,
    SocialLike,
    SocialView,
    StageEvent,
    WorkRevision,
)
from ..schemas import ClassLinkCreate, InstrumentPayload
from ..services.artifacts import admin_artifact, create_artifact_version
from ..services.export import build_export, make_csv
from ..services.instruments import admin_instrument, create_instrument_version
from ..services.peer import gate_counts, peer_scores_received
from ..services.readiness import (
    activate_protocol,
    active_protocol,
    artifact_summary,
    build_readiness,
    instrument_summary,
    latest_artifact,
    latest_content,
    latest_instrument,
    protocol_summary,
)
from ..domain import assessment_version_for_design, rationale_schema_for_design
from ..services.run_state import STEP_BY_STAGE, STAGE_LABELS
from ..security import token_hash
from ..services.social import hide_comment

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _parse_string_list(raw: str, field: str) -> List[str]:
    if not raw or not raw.strip():
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        raise AppError(422, "invalid_field", f"{field} must be a JSON array of strings.")
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AppError(422, "invalid_field", f"{field} must be a JSON array of strings.")
    return value


@router.get("/readiness")
async def readiness(
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await build_readiness(db, settings)


@router.get("/overview")
async def overview(
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    readiness_data = await build_readiness(db, settings)
    result = await db.execute(
        select(Participant, ClassGroup, Run)
        .join(ClassGroup, ClassGroup.id == Participant.class_id)
        .outerjoin(Run, Run.participant_id == Participant.id)
        .order_by(Participant.class_id, Participant.created_at)
    )
    rows = []
    stage_counts: Dict[str, int] = {}
    group_counts: Dict[str, int] = {}
    completed = 0
    for participant, class_group, run in result.all():
        stage = run.stage if run else "not_started"
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        group_counts[participant.group_name] = (
            group_counts.get(participant.group_name, 0) + 1
        )
        if stage == "complete":
            completed += 1
        rows.append(
            {
                "participant_id": str(participant.id),
                "class_id": participant.class_id,
                "class_name": class_group.name,
                "group": participant.group_name,
                "email": participant.email,
                "code_last4": participant.access_code_last4,
                "run_id": str(run.id) if run else None,
                "stage": stage,
                "stage_label": STAGE_LABELS.get(stage, "未开始 / Not started"),
                "step": STEP_BY_STAGE.get(stage, 0),
                "last_activity_at": run.last_activity_at.isoformat() if run else None,
                "completed_at": run.completed_at.isoformat()
                if run and run.completed_at
                else None,
                "completed": stage == "complete",
            }
        )
    protocol = await active_protocol(db)
    return {
        "readiness": readiness_data,
        "protocol": protocol_summary(protocol) if protocol else None,
        "participants": rows,
        "counts": {
            "participants": len(rows),
            "started": len(rows) - stage_counts.get("not_started", 0),
            "completed": completed,
            "by_stage": stage_counts,
            "by_group": group_counts,
        },
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/participants/{participant_id}")
async def participant_detail(
    participant_id: str,
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
):
    try:
        participant_uuid = uuid.UUID(participant_id)
    except ValueError:
        raise AppError(404, "participant_not_found", "Participant not found.")
    participant = await db.get(Participant, participant_uuid)
    if not participant:
        raise AppError(404, "participant_not_found", "Participant not found.")
    class_group = await db.get(ClassGroup, participant.class_id)
    run_result = await db.execute(
        select(Run).where(Run.participant_id == participant.id)
    )
    run = run_result.scalar_one_or_none()
    rounds: List[Round] = []
    messages: List[Message] = []
    scripts: List[ScriptRevision] = []
    works: List[WorkRevision] = []
    peer_assignments: List[PeerAssignment] = []
    peer_ratings: List[PeerRating] = []
    peer_scores = []
    social_events: List[SocialEvent] = []
    images: List[ImageJob] = []
    hlsf_events: List[HLSFEvent] = []
    evidence_events: List[EvidenceEvent] = []
    assessments: List[AssessmentResponse] = []
    ai_calls: List[AiCall] = []
    api_errors: List[ApiError] = []
    stage_events: List[StageEvent] = []
    artifacts: Dict[str, ArtifactVersion] = {}
    protocol = None
    if run:
        protocol = await db.get(ProtocolVersion, run.protocol_version_id)
        round_result = await db.execute(
            select(Round).where(Round.run_id == run.id).order_by(Round.round_no)
        )
        rounds = list(round_result.scalars().all())
        for round_obj in rounds:
            artifact = await db.get(ArtifactVersion, round_obj.artifact_version_id)
            if artifact:
                artifacts[str(artifact.id)] = artifact
        round_ids = [round_obj.id for round_obj in rounds]
        if round_ids:
            message_result = await db.execute(
                select(Message)
                .where(Message.round_id.in_(round_ids))
                .order_by(Message.id)
            )
            messages = list(message_result.scalars().all())
            script_result = await db.execute(
                select(ScriptRevision)
                .where(ScriptRevision.round_id.in_(round_ids))
                .order_by(ScriptRevision.round_id, ScriptRevision.revision_no)
            )
            scripts = list(script_result.scalars().all())
            work_result = await db.execute(
                select(WorkRevision)
                .where(WorkRevision.round_id.in_(round_ids))
                .order_by(WorkRevision.round_id, WorkRevision.revision_no)
            )
            works = list(work_result.scalars().all())
            peer_result = await db.execute(
                select(PeerAssignment)
                .where(PeerAssignment.reviewer_run_id == run.id)
                .order_by(PeerAssignment.position)
            )
            peer_assignments = list(peer_result.scalars().all())
            if peer_assignments:
                rating_result = await db.execute(
                    select(PeerRating).where(
                        PeerRating.assignment_id.in_(
                            [assignment.id for assignment in peer_assignments]
                        )
                    )
                )
                peer_ratings = list(rating_result.scalars().all())
            peer_scores = await peer_scores_received(db, run.id, participant.class_id)
            social_result = await db.execute(
                select(SocialEvent)
                .where(SocialEvent.run_id == run.id)
                .order_by(SocialEvent.id)
            )
            social_events = list(social_result.scalars().all())
            image_result = await db.execute(
                select(ImageJob)
                .where(ImageJob.round_id.in_(round_ids))
                .order_by(ImageJob.created_at)
            )
            images = list(image_result.scalars().all())
            hlsf_result = await db.execute(
                select(HLSFEvent)
                .where(HLSFEvent.round_id.in_(round_ids))
                .order_by(HLSFEvent.id)
            )
            hlsf_events = list(hlsf_result.scalars().all())
            evidence_result = await db.execute(
                select(EvidenceEvent)
                .where(EvidenceEvent.round_id.in_(round_ids))
                .order_by(EvidenceEvent.id)
            )
            evidence_events = list(evidence_result.scalars().all())
        assessment_result = await db.execute(
            select(AssessmentResponse)
            .where(AssessmentResponse.run_id == run.id)
            .order_by(AssessmentResponse.started_at)
        )
        assessments = list(assessment_result.scalars().all())
        ai_result = await db.execute(
            select(AiCall)
            .where(AiCall.run_id == run.id)
            .order_by(AiCall.created_at)
        )
        ai_calls = list(ai_result.scalars().all())
        error_result = await db.execute(
            select(ApiError)
            .where(
                (ApiError.run_id == run.id)
                | (ApiError.participant_id == participant.id)
            )
            .order_by(ApiError.created_at)
        )
        api_errors = list(error_result.scalars().all())
        stage_result = await db.execute(
            select(StageEvent)
            .where(StageEvent.run_id == run.id)
            .order_by(StageEvent.id)
        )
        stage_events = list(stage_result.scalars().all())

    artifacts_by_id = {str(artifact.id): artifact for artifact in artifacts.values()}
    return {
        "participant": {
            "id": str(participant.id),
            "class_id": participant.class_id,
            "class_name": class_group.name if class_group else "",
            "group": participant.group_name,
            "email": participant.email,
            "code_last4": participant.access_code_last4,
            "created_at": participant.created_at.isoformat(),
        },
        "run": {
            "id": str(run.id),
            "design_version": run.design_version or "legacy-v1.5",
            "assessment_version": assessment_version_for_design(run.design_version),
            "rationale_schema_version": rationale_schema_for_design(run.design_version),
            "condition_sequence": run.condition_sequence or "",
            "artifact_sequence": run.artifact_sequence or "",
            "test_form_sequence": run.test_form_order or "",
            "stage": run.stage,
            "stage_label": STAGE_LABELS.get(run.stage, run.stage),
            "created_at": run.created_at.isoformat(),
            "last_activity_at": run.last_activity_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "protocol": protocol_summary(protocol) if protocol else None,
        }
        if run
        else None,
        "stage_events": [
            {
                "stage": event.stage,
                "entered_at": event.entered_at.isoformat(),
                "completed_at": event.completed_at.isoformat()
                if event.completed_at
                else None,
                "duration_seconds": event.duration_seconds,
                "meta": event.meta_json,
            }
            for event in stage_events
        ],
        "rounds": [
            {
                "round_no": round_obj.round_no,
                "condition": round_obj.condition,
                "ai_condition": round_obj.condition,
                "artifact": admin_artifact(artifacts_by_id[str(round_obj.artifact_version_id)])
                if str(round_obj.artifact_version_id) in artifacts_by_id
                else None,
                "started_at": round_obj.started_at.isoformat(),
                "deadline_at": round_obj.deadline_at.isoformat(),
                "finished_at": round_obj.finished_at.isoformat()
                if round_obj.finished_at
                else None,
                "finish_reason": round_obj.finish_reason,
                "current_script_revision": round_obj.current_script_revision,
                "current_work_revision": round_obj.current_work_revision,
                "task": "T1" if round_obj.round_no == 1 else "T2",
            }
            for round_obj in rounds
        ],
        "scripts": [
            {
                "round_no": next(
                    (
                        round_obj.round_no
                        for round_obj in rounds
                        if round_obj.id == script.round_id
                    ),
                    None,
                ),
                "revision_no": script.revision_no,
                "title": script.title,
                "body": script.body,
                "source": script.source,
                "created_at": script.created_at.isoformat(),
            }
            for script in scripts
        ],
        "works": [
            {
                "round_no": next(
                    (
                        round_obj.round_no
                        for round_obj in rounds
                        if round_obj.id == work.round_id
                    ),
                    None,
                ),
                "revision_no": work.revision_no,
                "product_name": work.product_name,
                "product_category": work.product_category,
                "target_audience": work.target_audience,
                "design_concept": work.design_concept,
                "structured_fields": work.structured_fields,
                "rationale_fields": work.rationale_fields or {},
                "open_statement": work.open_statement,
                "source": work.source,
                "created_at": work.created_at.isoformat(),
            }
            for work in works
        ],
        "peer_scores_received": peer_scores,
        "peer_assignments": [
            {
                "assignment_id": str(assignment.id),
                "work_id": assignment.work_id,
                "status": assignment.status,
                "scores": next(
                    (
                        rating.scores_json
                        for rating in peer_ratings
                        if rating.assignment_id == assignment.id
                    ),
                    {},
                ),
                "comment": next(
                    (
                        rating.comment
                        for rating in peer_ratings
                        if rating.assignment_id == assignment.id
                    ),
                    "",
                ),
                "created_at": assignment.created_at.isoformat(),
            }
            for assignment in peer_assignments
        ],
        "social_events": [
            {
                "work_id": event.work_id,
                "event_type": event.event_type,
                "meta": event.meta_json,
                "created_at": event.created_at.isoformat(),
            }
            for event in social_events
        ],
        "messages": [
            {
                "id": message.id,
                "round_no": next(
                    (
                        round_obj.round_no
                        for round_obj in rounds
                        if round_obj.id == message.round_id
                    ),
                    None,
                ),
                "role": message.role,
                "source": message.source,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            }
            for message in messages
        ],
        "hlsf_events": [
            {
                "round_no": next(
                    (
                        round_obj.round_no
                        for round_obj in rounds
                        if round_obj.id == event.round_id
                    ),
                    None,
                ),
                "phase": event.phase,
                "action": event.action,
                "message_id": event.message_id,
                "meta": event.meta_json,
                "created_at": event.created_at.isoformat(),
            }
            for event in hlsf_events
        ],
        "evidence_events": [
            {
                "round_no": next(
                    (
                        round_obj.round_no
                        for round_obj in rounds
                        if round_obj.id == event.round_id
                    ),
                    None,
                ),
                "section": event.section,
                "event_type": event.event_type,
                "duration_ms": event.duration_ms,
                "meta": event.meta_json,
                "created_at": event.created_at.isoformat(),
            }
            for event in evidence_events
        ],
        "image_jobs": [
            {
                "id": str(job.id),
                "round_no": next(
                    (
                        round_obj.round_no
                        for round_obj in rounds
                        if round_obj.id == job.round_id
                    ),
                    None,
                ),
                "status": job.status,
                "attempts": job.attempts,
                "prompt": job.prompt,
                "error_code": job.error_code,
                "error_message": job.error_message,
                "attempts_limit": None,
                "image_url": f"/api/files/keyframes/{job.id}"
                if job.status == "succeeded" and job.file_path
                else None,
                "created_at": job.created_at.isoformat(),
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            }
            for job in images
        ],
        "assessments": [
            {
                "kind": response.kind,
                "status": response.status,
                "answers": response.answers_json,
                "started_at": response.started_at.isoformat(),
                "submitted_at": response.submitted_at.isoformat()
                if response.submitted_at
                else None,
                "duration_seconds": response.duration_seconds,
            }
            for response in assessments
        ],
        "ai_calls": [
            {
                "id": str(call.id),
                "purpose": call.purpose,
                "status": call.status,
                "model": call.model,
                "prompt_version": call.prompt_version,
                "http_status": call.http_status,
                "error_code": call.error_code,
                "error_message": call.error_message,
                "latency_ms": call.latency_ms,
                "created_at": call.created_at.isoformat(),
                "request": call.request_json,
                "response_text": call.response_text,
            }
            for call in ai_calls
        ],
        "api_errors": [
            {
                "category": error.category,
                "endpoint": error.endpoint,
                "status_code": error.status_code,
                "error_code": error.error_code,
                "message": error.message,
                "created_at": error.created_at.isoformat(),
            }
            for error in api_errors
        ],
    }


@router.get("/artifacts")
async def list_artifacts(
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
):
    payload = {}
    for slot in SLOTS:
        result = await db.execute(
            select(ArtifactVersion)
            .where(ArtifactVersion.slot == slot)
            .order_by(ArtifactVersion.version.desc())
        )
        versions = list(result.scalars().all())
        payload[slot] = {
            "latest": admin_artifact(versions[0]) if versions else None,
            "versions": [artifact_summary(version) for version in versions],
        }
    return payload


@router.post("/artifacts/{slot}/versions")
async def create_artifact(
    slot: str,
    title: str = Form(...),
    era: str = Form(""),
    artifact_type: str = Form(""),
    introduction: str = Form(""),
    facts_json: str = Form("[]"),
    evidence_json: str = Form("[]"),
    uncertainty_json: str = Form("[]"),
    image: Optional[UploadFile] = File(None),
    upload_id: Optional[str] = Form(None),
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    facts = _parse_string_list(facts_json, "facts_json")
    evidence = _parse_string_list(evidence_json, "evidence_json")
    uncertainty = _parse_string_list(uncertainty_json, "uncertainty_json")
    image_bytes = None
    if upload_id:
        if image is not None or settings.storage_backend != "blob":
            raise AppError(422, "invalid_upload", "Use one image upload method.")
        from .cloud import read_upload
        image_bytes = await read_upload(db, settings, upload_id)
    elif image is not None:
        image_bytes = await image.read()
        if image_bytes is not None and len(image_bytes) == 0:
            image_bytes = None
    version = await create_artifact_version(
        db,
        settings,
        slot=slot,
        title=title,
        era=era,
        artifact_type=artifact_type,
        introduction=introduction,
        facts=facts,
        evidence=evidence,
        uncertainty=uncertainty,
        image_bytes=image_bytes,
        image_filename=image.filename if image else None,
    )
    await db.commit()
    return {"artifact": admin_artifact(version)}


@router.get("/instruments")
async def list_instruments(
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
):
    payload = {}
    for kind in ASSESSMENT_KINDS:
        result = await db.execute(
            select(InstrumentVersion)
            .where(InstrumentVersion.kind == kind)
            .order_by(InstrumentVersion.version.desc())
        )
        versions = list(result.scalars().all())
        payload[kind] = {
            "latest": admin_instrument(versions[0]) if versions else None,
            "versions": [instrument_summary(version) for version in versions],
        }
    return payload


@router.post("/instruments/{kind}/versions")
async def create_instrument(
    kind: str,
    payload: InstrumentPayload,
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
):
    version = await create_instrument_version(db, kind=kind, payload=payload)
    await db.commit()
    return {"instrument": admin_instrument(version)}


@router.post("/protocol/activate")
async def activate(
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    protocol = await activate_protocol(db, settings, allow_demo=not settings.is_production)
    await db.commit()
    return {
        "protocol": protocol_summary(protocol),
        "readiness": await build_readiness(db, settings),
    }


@router.get("/cohort/codes.csv")
async def cohort_codes(
    admin: AdminContext = Depends(get_current_admin),
    settings: Settings = Depends(get_settings),
):
    if settings.auth_mode == "email":
        raise AppError(
            404,
            "codes_not_used",
            "This deployment uses PolyU email login; access-code CSV is not used.",
        )
    path = settings.codes_csv_path
    if not path.exists():
        raise AppError(
            404,
            "codes_csv_missing",
            "The cohort code CSV is missing. Do not regenerate it after distribution.",
        )
    return FileResponse(
        path,
        media_type="text/csv; charset=utf-8",
        filename="heritage-access-codes.csv",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/social/comments/{comment_id}/hide")
async def hide_social_comment(
    comment_id: int,
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
):
    comment = await hide_comment(db, comment_id)
    await db.commit()
    return {
        "comment": {
            "id": comment.id,
            "work_id": comment.work_id,
            "hidden": comment.hidden,
        }
    }



@router.get("/class-peer-gates")
async def list_class_peer_gates(
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Read-only monitoring of automatic per-class peer gates."""

    payload = []
    for class_id in settings.enabled_class_ids:
        class_group = await db.get(ClassGroup, class_id)
        counts = await gate_counts(db, class_id)
        gate: ClassPeerGate = counts["gate"]
        last_result = await db.execute(
            select(ClassPeerGateEvent)
            .where(ClassPeerGateEvent.class_id == class_id)
            .order_by(ClassPeerGateEvent.id.desc())
            .limit(1)
        )
        last_event = last_result.scalar_one_or_none()
        payload.append(
            {
                "class_id": class_id,
                "deployment_mode": settings.deployment_mode,
                "continuous_entry": settings.is_beta,
                "class_name": class_group.name if class_group else f"Class {class_id}",
                "status": gate.status,
                "entered": counts["entered"],
                "t2_ended": counts["t2_ended"],
                "valid_work_count": counts["valid_work_count"],
                "t1_work_count": counts.get("t1_work_count", 0),
                "t2_work_count": counts.get("t2_work_count", 0),
                "can_open": counts["can_open"],
                "membership_frozen_at": gate.membership_frozen_at.isoformat()
                if gate.membership_frozen_at
                else None,
                "peer_opened_at": gate.peer_opened_at.isoformat()
                if gate.peer_opened_at
                else None,
                "entered_count_at_open": gate.entered_count_at_open,
                "t2_ended_count_at_open": gate.t2_ended_count_at_open,
                "valid_work_count_at_open": gate.valid_work_count_at_open,
                "batch_id": str(gate.batch_id) if gate.batch_id else None,
                "last_event": {
                    "event_type": last_event.event_type,
                    "counts": last_event.counts_json,
                    "created_at": last_event.created_at.isoformat(),
                }
                if last_event
                else None,
            }
        )
    await db.commit()
    return {"classes": payload}


@router.get("/class-links")
async def list_class_links(
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(
        select(ClassEntryLink).order_by(ClassEntryLink.class_id, ClassEntryLink.created_at.desc())
    )
    links = list(result.scalars().all())
    return {
        "links": [
            {
                "id": str(link.id),
                "class_id": link.class_id,
                "label": link.label,
                "active": link.active,
                "created_at": link.created_at.isoformat(),
                "revoked_at": link.revoked_at.isoformat() if link.revoked_at else None,
            }
            for link in links
        ]
    }


def _class_link_url(settings: Settings, token: str) -> str:
    base = (settings.public_origin or "").rstrip("/")
    return f"{base}/join?token={token}" if base else f"/join?token={token}"


@router.post("/class-links")
async def create_class_link(
    payload: ClassLinkCreate,
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    class_group = await db.get(ClassGroup, payload.class_id)
    if not class_group or not settings.class_allowed(payload.class_id):
        raise AppError(404, "class_not_found", "Class not found.")
    token = secrets.token_urlsafe(24)
    link = ClassEntryLink(
        class_id=payload.class_id,
        token_hash=token_hash(token),
        label=payload.label or class_group.name,
        active=True,
    )
    db.add(link)
    await db.commit()
    return {
        "link": {
            "id": str(link.id),
            "class_id": link.class_id,
            "class_name": class_group.name,
            "label": link.label,
            "active": link.active,
        },
        "token": token,
        "url": _class_link_url(settings, token),
        "warning": "This token is shown once. Copy it now; only its hash is stored.",
    }


@router.post("/class-links/{link_id}/revoke")
async def revoke_class_link(
    link_id: str,
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
):
    try:
        link_uuid = uuid.UUID(link_id)
    except ValueError:
        raise AppError(404, "class_link_not_found", "Class link not found.")
    link = await db.get(ClassEntryLink, link_uuid)
    if not link:
        raise AppError(404, "class_link_not_found", "Class link not found.")
    link.active = False
    link.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True, "id": str(link.id), "active": link.active}


@router.post("/class-links/{link_id}/rotate")
async def rotate_class_link(
    link_id: str,
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    try:
        link_uuid = uuid.UUID(link_id)
    except ValueError:
        raise AppError(404, "class_link_not_found", "Class link not found.")
    old = await db.get(ClassEntryLink, link_uuid)
    if not old:
        raise AppError(404, "class_link_not_found", "Class link not found.")
    class_group = await db.get(ClassGroup, old.class_id)
    old.active = False
    old.revoked_at = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(24)
    new = ClassEntryLink(
        class_id=old.class_id,
        token_hash=token_hash(token),
        label=old.label,
        active=True,
    )
    db.add(new)
    await db.commit()
    return {
        "link": {
            "id": str(new.id),
            "class_id": new.class_id,
            "class_name": class_group.name if class_group else "",
            "label": new.label,
            "active": new.active,
        },
        "token": token,
        "url": _class_link_url(settings, token),
        "warning": "This token is shown once. Copy it now; only its hash is stored.",
    }


@router.get("/analysis.csv")
async def export_analysis(
    student_id: Optional[str] = None,
    class_id: Optional[int] = None,
    group: Optional[str] = None,
    round_no: Optional[int] = None,
    artifact: Optional[str] = None,
    ai_condition: Optional[str] = None,
    design_version: Optional[str] = None,
    assessment_version: Optional[str] = None,
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Filtered student-by-round analysis export.

    The full export remains available at /api/admin/export; this endpoint is a
    convenience view for quick balance checks and the T1 A/B comparison.
    """
    path, _manifest = await build_export(db, settings)
    try:
        with zipfile.ZipFile(path) as archive:
            raw = archive.read("analysis.csv").decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(raw)))
        filters = {
            "student_id": student_id,
            "class_id": class_id,
            "group_id": group,
            "round_no": round_no,
            "artifact_slot": artifact,
            "ai_condition": ai_condition,
            "design_version": design_version,
            "assessment_version": assessment_version,
        }
        filtered = [
            row
            for row in rows
            if all(
                value in (None, "") or str(row.get(key, "")) == str(value)
                for key, value in filters.items()
            )
        ]
        fieldnames = list(rows[0].keys()) if rows else [
            "student_id", "class_id", "class_name", "group_id", "design_version",
            "run_id", "round_no", "artifact_id", "artifact_slot", "ai_condition",
            "condition_sequence", "artifact_sequence", "test_form_sequence",
            "prompt_versions", "stage_events", "student_messages",
            "assistant_messages", "design_versions", "final_submission",
            "assessment_version", "mc_max", "rationale_schema_version",
            "knowledge_pretest_score", "knowledge_posttest_score",
            "knowledge_pretest_mc", "knowledge_posttest_mc",
            "posttest_short_score_0_2", "peer_batch_id", "peer_review_version",
            "peer_rating_count", "peer_cultural_clarity_mean",
            "peer_cultural_translation_mean", "peer_design_originality_mean",
            "peer_clarity_mean", "peer_evidence_link_mean",
            "peer_attraction_mean",
            "final_rationale_fields", "task_start_time", "task_end_time",
        ]
        return Response(
            content=make_csv(fieldnames, filtered),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="hlsf-analysis.csv"',
                "Cache-Control": "no-store",
            },
        )
    finally:
        path.unlink(missing_ok=True)


@router.get("/export")
async def export_research_data(
    admin: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    if settings.queue_backend == "vercel":
        raise AppError(409, "async_export_required", "Start the export using the researcher dashboard.")
    path, manifest = await build_export(db, settings)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"heritage-research-export-{stamp}.zip",
        headers={"Cache-Control": "no-store"},
        background=BackgroundTask(path.unlink, missing_ok=True),
    )
