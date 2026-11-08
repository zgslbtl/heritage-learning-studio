from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..domain import (
    CONDITION_LABELS,
    assessment_version_for_design,
    mc_max_for_design,
    rationale_schema_for_design,
)
from .peer_scales import peer_scale, peer_scale_for_batch, score_keys_for_scale
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
    PeerBatch,
    PeerImpression,
    PeerRating,
    ProtocolAssessmentForm,
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

EXPORT_VERSION = "export-v1"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, (dict, list)):
        value = _json(value)
    if isinstance(value, uuid.UUID):
        value = str(value)
    if isinstance(value, str):
        value = value.replace("\x00", "")
        if value.startswith(("=", "+", "-", "@", "\t", "\r")):
            value = "'" + value
    return value


def make_csv(fieldnames: Sequence[str], rows: Iterable[Dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    buffer.write("\ufeff")
    writer = csv.DictWriter(buffer, fieldnames=list(fieldnames), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _cell(row.get(key)) for key in fieldnames})
    return buffer.getvalue().encode("utf-8")


def _data_dictionary() -> str:
    return """# Heritage Learning Studio research export

This export contains raw research records from the MVP. It does not include access codes,
session tokens, password hashes, or API keys. Participants are identified only by the
anonymous UUID assigned by the server. Objective MCQ scores are included for researcher use only; the student UI never
shows them. Short-answer and T2 rubric scoring remain outside the student platform.

- participants.csv — one row per pre-generated anonymous participant.
- runs.csv — one row per participant study run and frozen protocol.
- stage_events.csv — stage entry/exit times and durations.
- rounds.csv — both creation rounds per run, artifact and condition assignment.
- messages.csv — full visible AI dialogue with timestamps (HLSF prompts/hints included).
- hlsf_events.csv — B-only scaffold delivery/advance/skip/hint events.
- evidence_events.csv — artifact section open/close, media open and source click events, including meta_json.
- script_revisions.csv — every distinct legacy short-video script revision.
- work_revisions.csv — every T1/T2 product-design revision, including legacy six-field/open fields and the V2 three-part rationale.
- image_jobs.csv — image prompts, status, errors and result file references.
- analysis.csv — one row per student × round with design/assessment version, group, sequence, condition, artifact, MC scores, post-test short-answer placeholder, peer-score summary (per-dimension, no composite), rationale and outcome fields.
- assessments.csv — raw K0-K3/survey answers, measurement form, assessment version and researcher-only objective score.
- assessment_answers.csv — one row per answered question with question/form metadata.
- survey.csv — one row per submitted survey. Raw S1–S7 are always included;
  survey_version / survey_instrument_version identify the content revision. The
  canonical s1_exploration_r1 … s6_mental_effort_r2 columns are populated only
  for survey-v2.1-pilot; older surveys leave them empty so historical S1
  meanings are not mislabelled. s7_preferred_round / s7_preferred_ai_condition
  are populated only when the response used the single-choice preference item.
  No survey total score is produced.
- ai_calls.csv — sanitized model request context, status, errors and latency.
- api_errors.csv — application/upstream errors captured by the server.
- peer_batches.csv — frozen peer-assignment batch metadata per class, including scale_version and the frozen scale definition snapshot.
- peer_assignments.csv — reviewer-to-work assignment links, status and T1/T2 round.
- peer_ratings.csv — one row per submitted peer rating. review_version identifies
  the peer-review content version. New batches use cultural_clarity /
  cultural_translation / design_originality; legacy batches use clarity /
  evidence_link / attraction. The legacy attraction dimension is NOT
  design_originality. reviewed_round_no / reviewed_ai_condition / artifact fields
  let a mixed T1+T2 student list be split for analysis.
- peer_work_scores.csv — descriptive per-work summary for the current batch:
  rating count and the three dimension means for that batch's scale version.
  No composite overall score is produced; raw ratings remain in peer_ratings.csv.
- peer_impressions.csv — actual peer-card exposure, position, shown_at and viewed_ms.
- social_views.csv — simulated Instagram exposure/view events.
- social_likes.csv — like state per viewer and work.
- social_comments.csv — comments, with researcher hidden flag.
- social_events.csv — like/unlike/comment/view event audit.
- class_entry_links.csv — class link metadata (no token/hash).
- class_peer_gates.csv — automatic class peer-gate status and opening counts.
- class_peer_gate_events.csv — automatic gate audit events.
- protocol.json — frozen artifact sections/media hashes, measurement forms, assessment version, rubric and content definitions.
- files/ — original keyframes, current legacy script text and current product work grouped by participant UUID and round.
- manifest.json — export counts and missing-file notices.

CSV files are UTF-8 with BOM. Text cells beginning with spreadsheet formula characters are
prefixed with an apostrophe to reduce CSV-injection risk; this changes the cell's literal
representation but preserves the source value in the corresponding JSON fields.
"""


def _safe_file_name(value: str) -> str:
    return "".join(ch for ch in value if ch.isalnum() or ch in "-_")


def _work_code(work_id: int) -> str:
    return "W-" + hashlib.sha256(str(work_id).encode("utf-8")).hexdigest()[:6].upper()


async def build_export(
    session: AsyncSession, settings: Settings
) -> tuple[Path, Dict[str, Any]]:
    settings.ensure_directories()
    participants = list(
        (await session.execute(select(Participant).order_by(Participant.created_at)))
        .scalars()
        .all()
    )
    classes = {
        cls.id: cls.name
        for cls in (await session.execute(select(ClassGroup))).scalars().all()
    }
    runs = list((await session.execute(select(Run))).scalars().all())
    runs_by_id = {run.id: run for run in runs}
    participants_by_id = {participant.id: participant for participant in participants}
    participant_order = {participant.id: index for index, participant in enumerate(participants)}
    run_by_participant = {run.participant_id: run for run in runs}

    protocols = list((await session.execute(select(ProtocolVersion))).scalars().all())
    protocols_by_id = {protocol.id: protocol for protocol in protocols}
    protocol_forms = list(
        (await session.execute(select(ProtocolAssessmentForm))).scalars().all()
    )
    artifact_versions = list(
        (await session.execute(select(ArtifactVersion))).scalars().all()
    )
    artifacts_by_id = {artifact.id: artifact for artifact in artifact_versions}
    instrument_versions = list(
        (await session.execute(select(InstrumentVersion))).scalars().all()
    )
    instruments_by_id = {inst.id: inst for inst in instrument_versions}
    rounds = list((await session.execute(select(Round))).scalars().all())
    rounds_by_id = {round_obj.id: round_obj for round_obj in rounds}
    run_by_round = {round_obj.id: runs_by_id.get(round_obj.run_id) for round_obj in rounds}
    participant_by_round = {
        round_obj.id: participants_by_id.get(run.participant_id) if run else None
        for round_obj, run in ((r, runs_by_id.get(r.run_id)) for r in rounds)
    }
    participant_by_run_id = {
        run.id: participants_by_id.get(run.participant_id) for run in runs
    }

    def participant_fields(participant: Optional[Participant]) -> Dict[str, Any]:
        if not participant:
            return {
                "participant_id": "",
                "class_id": "",
                "class_name": "",
                "group": "",
            }
        return {
            "participant_id": str(participant.id),
            "class_id": participant.class_id,
            "class_name": classes.get(participant.class_id, ""),
            "group": participant.group_name,
        }

    def work_owner_fields(work: WorkRevision) -> Dict[str, Any]:
        return participant_fields(participant_by_round.get(work.round_id))

    stage_events = list(
        (await session.execute(select(StageEvent).order_by(StageEvent.id))).scalars().all()
    )
    messages = list(
        (await session.execute(select(Message).order_by(Message.id))).scalars().all()
    )
    hlsf_events = list(
        (await session.execute(select(HLSFEvent).order_by(HLSFEvent.id))).scalars().all()
    )
    evidence_events = list(
        (
            await session.execute(
                select(EvidenceEvent).order_by(EvidenceEvent.id)
            )
        )
        .scalars()
        .all()
    )
    scripts = list(
        (
            await session.execute(
                select(ScriptRevision).order_by(ScriptRevision.round_id, ScriptRevision.revision_no)
            )
        )
        .scalars()
        .all()
    )
    scripts_by_round: Dict[uuid.UUID, List[ScriptRevision]] = {}
    for script in scripts:
        scripts_by_round.setdefault(script.round_id, []).append(script)
    works = list(
        (
            await session.execute(
                select(WorkRevision).order_by(
                    WorkRevision.round_id, WorkRevision.revision_no
                )
            )
        )
        .scalars()
        .all()
    )
    works_by_round: Dict[uuid.UUID, List[WorkRevision]] = {}
    works_by_id = {work.id: work for work in works}
    for work in works:
        works_by_round.setdefault(work.round_id, []).append(work)
    class_entry_links = list(
        (await session.execute(select(ClassEntryLink).order_by(ClassEntryLink.created_at))).scalars().all()
    )
    class_peer_gates = list(
        (await session.execute(select(ClassPeerGate).order_by(ClassPeerGate.class_id))).scalars().all()
    )
    class_peer_gate_events = list(
        (
            await session.execute(
                select(ClassPeerGateEvent).order_by(ClassPeerGateEvent.id)
            )
        )
        .scalars()
        .all()
    )
    peer_batches = list(
        (await session.execute(select(PeerBatch).order_by(PeerBatch.created_at))).scalars().all()
    )
    peer_batches_by_id = {batch.id: batch for batch in peer_batches}
    peer_assignments = list(
        (await session.execute(select(PeerAssignment).order_by(PeerAssignment.created_at))).scalars().all()
    )
    peer_ratings = list(
        (await session.execute(select(PeerRating).order_by(PeerRating.submitted_at))).scalars().all()
    )
    peer_impressions = list(
        (await session.execute(select(PeerImpression).order_by(PeerImpression.shown_at))).scalars().all()
    )
    image_jobs = list(
        (await session.execute(select(ImageJob).order_by(ImageJob.created_at))).scalars().all()
    )
    peer_ratings_by_assignment = {rating.assignment_id: rating for rating in peer_ratings}
    image_jobs_by_id = {job.id: job for job in image_jobs}

    peer_score_rows: List[Dict[str, Any]] = []
    peer_scores_by_work: Dict[int, Dict[str, Any]] = {}
    active_peer_batch_ids = {
        batch.id for batch in peer_batches if batch.status != "superseded"
    }
    for assignment in peer_assignments:
        if assignment.batch_id not in active_peer_batch_ids:
            continue
        work = works_by_id.get(assignment.work_id)
        round_obj = rounds_by_id.get(work.round_id) if work else None
        if not work or not round_obj:
            continue
        owner_run = runs_by_id.get(round_obj.run_id)
        owner = participants_by_id.get(owner_run.participant_id) if owner_run else None
        if not owner:
            continue
        batch = peer_batches_by_id.get(assignment.batch_id)
        scale = peer_scale_for_batch(batch) if batch is not None else peer_scale(None)
        score_keys = score_keys_for_scale(scale)
        review_version = scale.get("version", getattr(batch, "scale_version", ""))
        artifact = artifacts_by_id.get(round_obj.artifact_version_id)
        entry = peer_scores_by_work.setdefault(
            int(work.id),
            {
                "batch_id": str(assignment.batch_id),
                "class_id": owner.class_id,
                "class_name": classes.get(owner.class_id, ""),
                "participant_id": str(owner.id),
                "group_id": owner.group_name,
                "run_id": str(owner_run.id),
                "round_no": round_obj.round_no,
                "work_id": int(work.id),
                "work_code": _work_code(int(work.id)),
                "review_version": review_version,
                "artifact_id": str(round_obj.artifact_version_id),
                "artifact_slot": artifact.slot if artifact else "",
                "object_code": artifact.object_code if artifact else "",
                "ai_condition": round_obj.condition,
                "condition_sequence": owner_run.condition_sequence or "",
                "artifact_sequence": owner_run.artifact_sequence or "",
                "image_available": bool(round_obj.selected_image_job_id)
                and bool(
                    image_jobs_by_id.get(round_obj.selected_image_job_id)
                    and image_jobs_by_id[round_obj.selected_image_job_id].status == "succeeded"
                ),
                "rating_count": 0,
                "dimension_scores": {key: [] for key in score_keys},
            },
        )
        rating = peer_ratings_by_assignment.get(assignment.id)
        if rating:
            entry["rating_count"] += 1
            for key in score_keys:
                value = (rating.scores_json or {}).get(key)
                if isinstance(value, int) and not isinstance(value, bool):
                    entry["dimension_scores"][key].append(value)
    for entry in peer_scores_by_work.values():
        dimension_scores = entry.pop("dimension_scores")
        for key, values in dimension_scores.items():
            entry[f"{key}_mean"] = round(sum(values) / len(values), 3) if values else ""
        peer_score_rows.append(entry)
    peer_score_rows.sort(key=lambda item: (item["class_id"], item["round_no"], item["work_id"]))
    social_views = list(
        (await session.execute(select(SocialView).order_by(SocialView.id))).scalars().all()
    )
    social_likes = list(
        (await session.execute(select(SocialLike).order_by(SocialLike.updated_at))).scalars().all()
    )
    social_comments = list(
        (await session.execute(select(SocialComment).order_by(SocialComment.id))).scalars().all()
    )
    social_events = list(
        (await session.execute(select(SocialEvent).order_by(SocialEvent.id))).scalars().all()
    )
    assessments = list(
        (
            await session.execute(
                select(AssessmentResponse).order_by(AssessmentResponse.started_at)
            )
        )
        .scalars()
        .all()
    )
    ai_calls = list(
        (await session.execute(select(AiCall).order_by(AiCall.created_at))).scalars().all()
    )
    api_errors = list(
        (await session.execute(select(ApiError).order_by(ApiError.id))).scalars().all()
    )

    file_missing: List[str] = []
    manifest: Dict[str, Any] = {
        "deployment_mode": settings.deployment_mode,
        "internal_testing": settings.is_beta,
        "peer_policy": "beta-continuous-v1" if settings.is_beta else "class-frozen",
        "export_version": EXPORT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "participants": len(participants),
        "runs": len(runs),
        "rounds": len(rounds),
        "messages": len(messages),
        "script_revisions": len(scripts),
        "work_revisions": len(works),
        "image_jobs": len(image_jobs),
        "assessments": len(assessments),
        "peer_assignments": len(peer_assignments),
        "peer_ratings": len(peer_ratings),
        "peer_work_scores": len(peer_score_rows),
        "social_events": len(social_events),
        "missing_files": file_missing,
        "notes": (
            "Objective MCQ scores are included for researcher use only; short-answer "
            "and T2 rubric scoring remain outside the student platform. Peer scores "
            "cover both T1 and T2 works and are descriptive, not D1–D4 research "
            "rubric scores. The two rounds are repeated measures within a student, "
            "not independent participants; T2 effects may carry over from T1."
        ),
    }

    assessments_by_run_kind = {
        (response.run_id, response.kind): response for response in assessments
    }
    stage_counts_by_run: Dict[uuid.UUID, int] = {}
    for event in stage_events:
        stage_counts_by_run[event.run_id] = stage_counts_by_run.get(event.run_id, 0) + 1
    message_counts_by_round: Dict[uuid.UUID, Dict[str, int]] = {}
    for message in messages:
        bucket = message_counts_by_round.setdefault(
            message.round_id, {"student": 0, "assistant": 0}
        )
        if message.role == "user":
            bucket["student"] += 1
        elif message.role == "assistant":
            bucket["assistant"] += 1
    prompt_versions_by_round: Dict[uuid.UUID, set] = {}
    for call in ai_calls:
        if call.round_id:
            prompt_versions_by_round.setdefault(call.round_id, set()).add(
                call.prompt_version or ""
            )

    analysis_rows = []
    for run in runs:
        participant = participants_by_id.get(run.participant_id)
        if not participant:
            continue
        for round_obj in [r for r in rounds if r.run_id == run.id]:
            artifact = artifacts_by_id.get(round_obj.artifact_version_id)
            latest_work = (works_by_round.get(round_obj.id) or [None])[-1]
            counts_by_message = message_counts_by_round.get(
                round_obj.id, {"student": 0, "assistant": 0}
            )
            if round_obj.round_no == 1:
                pre_kind, post_kind = "k0", "k1"
            else:
                pre_kind, post_kind = "k2", "k3"
            pre = assessments_by_run_kind.get((run.id, pre_kind))
            post = assessments_by_run_kind.get((run.id, post_kind))
            peer_score = (
                peer_scores_by_work.get(int(latest_work.id))
                if latest_work is not None
                else None
            )
            final_submission = None
            if latest_work is not None:
                final_submission = {
                    "product_name": latest_work.product_name,
                    "product_category": latest_work.product_category,
                    "target_audience": latest_work.target_audience,
                    "design_concept": latest_work.design_concept,
                    "structured_fields": latest_work.structured_fields,
                    "rationale_fields": latest_work.rationale_fields or {},
                    "open_statement": latest_work.open_statement,
                    "image_prompt": latest_work.image_prompt,
                    "revision_no": latest_work.revision_no,
                }
            analysis_rows.append(
                {
                    "student_id": str(participant.id),
                    "class_id": participant.class_id,
                    "class_name": classes.get(participant.class_id, ""),
                    "group_id": participant.group_name,
                    "design_version": run.design_version or "legacy-v1.5",
                    "hlsf_prompt_version": run.hlsf_prompt_version or "",
                    "run_id": str(run.id),
                    "round_no": round_obj.round_no,
                    "artifact_id": str(round_obj.artifact_version_id),
                    "artifact_slot": artifact.slot if artifact else "",
                    "ai_condition": round_obj.condition,
                    "condition_sequence": run.condition_sequence or "",
                    "artifact_sequence": run.artifact_sequence or "",
                    "test_form_sequence": run.test_form_order or "",
                    "prompt_versions": ",".join(
                        sorted(
                            version
                            for version in prompt_versions_by_round.get(
                                round_obj.id, set()
                            )
                            if version
                        )
                    ),
                    "stage_events": stage_counts_by_run.get(run.id, 0),
                    "student_messages": counts_by_message["student"],
                    "assistant_messages": counts_by_message["assistant"],
                    "design_versions": len(works_by_round.get(round_obj.id, [])),
                    "final_submission": final_submission,
                    "assessment_version": assessment_version_for_design(run.design_version),
                    "mc_max": mc_max_for_design(run.design_version) or "",
                    "rationale_schema_version": rationale_schema_for_design(run.design_version),
                    "knowledge_pretest_score": pre.score_total if pre else "",
                    "knowledge_posttest_score": post.score_total if post else "",
                    "knowledge_pretest_mc": pre.score_total if pre else "",
                    "knowledge_posttest_mc": post.score_total if post else "",
                    "posttest_short_score_0_2": "",
                    "peer_batch_id": peer_score.get("batch_id", "") if peer_score else "",
                    "peer_review_version": peer_score.get("review_version", "")
                    if peer_score
                    else "",
                    "peer_rating_count": peer_score.get("rating_count", "") if peer_score else "",
                    "peer_cultural_clarity_mean": peer_score.get("cultural_clarity_mean", "")
                    if peer_score
                    else "",
                    "peer_cultural_translation_mean": peer_score.get(
                        "cultural_translation_mean", ""
                    )
                    if peer_score
                    else "",
                    "peer_design_originality_mean": peer_score.get(
                        "design_originality_mean", ""
                    )
                    if peer_score
                    else "",
                    "peer_clarity_mean": peer_score.get("clarity_mean", "") if peer_score else "",
                    "peer_evidence_link_mean": peer_score.get("evidence_link_mean", "") if peer_score else "",
                    "peer_attraction_mean": peer_score.get("attraction_mean", "") if peer_score else "",
                    "final_rationale_fields": (latest_work.rationale_fields or {}) if latest_work else {},
                    "task_start_time": round_obj.started_at,
                    "task_end_time": round_obj.finished_at or round_obj.deadline_at,
                }
            )

    counts = {
        "analysis.csv": len(analysis_rows),
        "participants.csv": len(participants),
        "stage_events.csv": len(stage_events),
        "messages.csv": len(messages),
        "hlsf_events.csv": len(hlsf_events),
        "evidence_events.csv": len(evidence_events),
        "script_revisions.csv": len(scripts),
        "work_revisions.csv": len(works),
        "image_jobs.csv": len(image_jobs),
        "assessments.csv": len(assessments),
        "class_entry_links.csv": len(class_entry_links),
        "class_peer_gates.csv": len(class_peer_gates),
        "class_peer_gate_events.csv": len(class_peer_gate_events),
        "peer_batches.csv": len(peer_batches),
        "peer_assignments.csv": len(peer_assignments),
        "peer_ratings.csv": len(peer_ratings),
        "peer_work_scores.csv": len(peer_score_rows),
        "peer_impressions.csv": len(peer_impressions),
        "social_views.csv": len(social_views),
        "social_likes.csv": len(social_likes),
        "social_comments.csv": len(social_comments),
        "social_events.csv": len(social_events),
        "ai_calls.csv": len(ai_calls),
        "api_errors.csv": len(api_errors),
    }

    handle = tempfile.NamedTemporaryFile(
        prefix="heritage-export-", suffix=".zip", dir=str(settings.exports_dir), delete=False
    )
    path = Path(handle.name)
    handle.close()
    try:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "participants.csv",
                make_csv(
                    [
                        "participant_id",
                        "class_id",
                        "class_name",
                        "group",
                        "created_at",
                    ],
                    [
                        {
                            "participant_id": str(p.id),
                            "class_id": p.class_id,
                            "class_name": classes.get(p.class_id, ""),
                            "group": p.group_name,
                            "created_at": p.created_at,
                        }
                        for p in participants
                    ],
                ),
            )
            zf.writestr(
                "runs.csv",
                make_csv(
                    [
                        "participant_id",
                        "class_id",
                        "class_name",
                        "group",
                        "run_id",
                        "protocol_version_id",
                        "design_version",
                        "hlsf_prompt_version",
                        "assessment_version",
                        "rationale_schema_version",
                        "stage",
                        "t1_condition",
                        "condition_sequence",
                        "artifact_sequence",
                        "artifact_order",
                        "object_order",
                        "test_form_order",
                        "test_form_sequence",
                        "consent_future_research",
                        "consent_recorded_at",
                        "consent_version",
                        "created_at",
                        "last_activity_at",
                        "completed_at",
                    ],
                    [
                        {
                            **participant_fields(participant_by_run_id.get(run.id)),
                            "run_id": str(run.id),
                            "protocol_version_id": str(run.protocol_version_id),
                            "design_version": run.design_version or "legacy-v1.5",
                            "hlsf_prompt_version": run.hlsf_prompt_version or "",
                            "assessment_version": assessment_version_for_design(run.design_version),
                            "rationale_schema_version": rationale_schema_for_design(run.design_version),
                            "stage": run.stage,
                            "t1_condition": run.t1_condition or "",
                            "condition_sequence": run.condition_sequence or "",
                            "artifact_sequence": run.artifact_sequence or "",
                            "artifact_order": run.artifact_order or "",
                            "object_order": run.object_order or "",
                            "test_form_order": run.test_form_order or "",
                            "test_form_sequence": run.test_form_order or "",
                            "consent_future_research": run.consent_future_research,
                            "consent_recorded_at": run.consent_recorded_at,
                            "consent_version": run.consent_version or "",
                            "created_at": run.created_at,
                            "last_activity_at": run.last_activity_at,
                            "completed_at": run.completed_at,
                        }
                        for run in runs
                    ],
                ),
            )
            zf.writestr(
                "stage_events.csv",
                make_csv(
                    [
                        "participant_id",
                        "run_id",
                        "stage",
                        "entered_at",
                        "completed_at",
                        "duration_seconds",
                        "meta_json",
                    ],
                    [
                        {
                            "participant_id": participant_fields(
                                participant_by_run_id.get(event.run_id)
                            )["participant_id"],
                            "run_id": str(event.run_id),
                            "stage": event.stage,
                            "entered_at": event.entered_at,
                            "completed_at": event.completed_at,
                            "duration_seconds": event.duration_seconds,
                            "meta_json": event.meta_json,
                        }
                        for event in stage_events
                    ],
                ),
            )
            zf.writestr(
                "rounds.csv",
                make_csv(
                    [
                        "participant_id",
                        "class_id",
                        "class_name",
                        "group",
                        "group_id",
                        "round_no",
                        "condition",
                        "ai_condition",
                        "artifact_id",
                        "artifact_slot",
                        "artifact_title",
                        "started_at",
                        "deadline_at",
                        "finished_at",
                        "finish_reason",
                        "current_script_revision",
                        "current_work_revision",
                        "selected_image_job_id",
                        "task",
                    ],
                    [
                        {
                            **participant_fields(participant_by_round.get(round_obj.id)),
                            "group_id": participant_fields(
                                participant_by_round.get(round_obj.id)
                            )["group"],
                            "round_no": round_obj.round_no,
                            "condition": round_obj.condition,
                            "ai_condition": round_obj.condition,
                            "artifact_id": str(round_obj.artifact_version_id),
                            "artifact_slot": artifacts_by_id.get(
                                round_obj.artifact_version_id
                            ).slot
                            if artifacts_by_id.get(round_obj.artifact_version_id)
                            else "",
                            "artifact_title": artifacts_by_id.get(
                                round_obj.artifact_version_id
                            ).title
                            if artifacts_by_id.get(round_obj.artifact_version_id)
                            else "",
                            "started_at": round_obj.started_at,
                            "deadline_at": round_obj.deadline_at,
                            "finished_at": round_obj.finished_at,
                            "finish_reason": round_obj.finish_reason,
                            "current_script_revision": round_obj.current_script_revision,
                            "current_work_revision": round_obj.current_work_revision,
                            "selected_image_job_id": str(round_obj.selected_image_job_id)
                            if round_obj.selected_image_job_id
                            else "",
                            "task": "T1" if round_obj.round_no == 1 else "T2",
                        }
                        for round_obj in rounds
                    ],
                ),
            )
            zf.writestr(
                "messages.csv",
                make_csv(
                    [
                        "participant_id",
                        "class_id",
                        "group",
                        "run_id",
                        "round_no",
                        "message_id",
                        "role",
                        "source",
                        "content",
                        "created_at",
                    ],
                    [
                        {
                            **participant_fields(participant_by_round.get(message.round_id)),
                            "run_id": str(
                                rounds_by_id[message.round_id].run_id
                            )
                            if message.round_id in rounds_by_id
                            else "",
                            "round_no": rounds_by_id[message.round_id].round_no
                            if message.round_id in rounds_by_id
                            else "",
                            "message_id": message.id,
                            "role": message.role,
                            "source": message.source,
                            "content": message.content,
                            "created_at": message.created_at,
                        }
                        for message in messages
                    ],
                ),
            )
            zf.writestr(
                "hlsf_events.csv",
                make_csv(
                    [
                        "participant_id",
                        "round_no",
                        "phase",
                        "action",
                        "message_id",
                        "meta_json",
                        "created_at",
                    ],
                    [
                        {
                            **participant_fields(participant_by_round.get(event.round_id)),
                            "round_no": rounds_by_id[event.round_id].round_no
                            if event.round_id in rounds_by_id
                            else "",
                            "phase": event.phase,
                            "action": event.action,
                            "message_id": event.message_id,
                            "meta_json": event.meta_json,
                            "created_at": event.created_at,
                        }
                        for event in hlsf_events
                    ],
                ),
            )
            zf.writestr(
                "evidence_events.csv",
                make_csv(
                    [
                        "participant_id",
                        "round_no",
                        "section",
                        "event_type",
                        "duration_ms",
                        "meta_json",
                        "created_at",
                    ],
                    [
                        {
                            **participant_fields(participant_by_round.get(event.round_id)),
                            "round_no": rounds_by_id[event.round_id].round_no
                            if event.round_id in rounds_by_id
                            else "",
                            "section": event.section,
                            "event_type": event.event_type,
                            "duration_ms": event.duration_ms,
                            "meta_json": event.meta_json,
                            "created_at": event.created_at,
                        }
                        for event in evidence_events
                    ],
                ),
            )
            zf.writestr(
                "script_revisions.csv",
                make_csv(
                    [
                        "participant_id",
                        "round_no",
                        "revision_no",
                        "title",
                        "body",
                        "source",
                        "created_at",
                    ],
                    [
                        {
                            **participant_fields(participant_by_round.get(script.round_id)),
                            "round_no": rounds_by_id[script.round_id].round_no
                            if script.round_id in rounds_by_id
                            else "",
                            "revision_no": script.revision_no,
                            "title": script.title,
                            "body": script.body,
                            "source": script.source,
                            "created_at": script.created_at,
                        }
                        for script in scripts
                    ],
                ),
            )
            latest_scripts: Dict[uuid.UUID, ScriptRevision] = {}
            for script in scripts:
                latest_scripts[script.round_id] = script
            for round_obj in rounds:
                participant = participant_by_round.get(round_obj.id)
                latest = latest_scripts.get(round_obj.id)
                if not participant or not latest:
                    continue
                folder = f"files/{participant.id}/round-{round_obj.round_no}"
                zf.writestr(
                    f"{folder}/script-r{latest.revision_no}.txt",
                    latest.title + "\n\n" + latest.body,
                )

            latest_works: Dict[uuid.UUID, WorkRevision] = {}
            for work in works:
                latest_works[work.round_id] = work
            for round_obj in rounds:
                participant = participant_by_round.get(round_obj.id)
                latest_work = latest_works.get(round_obj.id)
                if not participant or not latest_work:
                    continue
                folder = f"files/{participant.id}/round-{round_obj.round_no}"
                structured = latest_work.structured_fields or {}
                lines = [
                    f"Task: {'T1' if round_obj.round_no == 1 else 'T2'}",
                    f"Product name: {latest_work.product_name}",
                    f"Product category/use: {latest_work.product_category}",
                    f"Target audience: {latest_work.target_audience}",
                    f"Design concept: {latest_work.design_concept}",
                    "Structured fields:",
                ]
                for key in (
                    "cultural_features",
                    "historical_function",
                    "sources_evidence",
                    "cultural_continuity",
                    "cultural_translation",
                    "innovation_rationale",
                ):
                    lines.append(f"- {key}: {structured.get(key, '')}")
                lines.append(f"Open statement: {latest_work.open_statement}")
                zf.writestr(
                    f"{folder}/work-r{latest_work.revision_no}.txt",
                    "\n".join(lines),
                )

            work_rows = []
            for work in works:
                round_obj = rounds_by_id.get(work.round_id)
                participant = participant_by_round.get(work.round_id)
                run = runs_by_id.get(round_obj.run_id) if round_obj else None
                work_rows.append(
                    {
                        **participant_fields(participant),
                        "run_id": str(round_obj.run_id) if round_obj else "",
                        "round_no": round_obj.round_no if round_obj else "",
                        "assessment_version": assessment_version_for_design(
                            run.design_version if run else None
                        ),
                        "rationale_schema_version": rationale_schema_for_design(
                            run.design_version if run else None
                        ),
                        "task": "T1" if round_obj and round_obj.round_no == 1 else "T2",
                        "revision_no": work.revision_no,
                        "product_name": work.product_name,
                        "product_category": work.product_category,
                        "target_audience": work.target_audience,
                        "design_concept": work.design_concept,
                        "structured_fields_json": work.structured_fields,
                        "rationale_fields_json": work.rationale_fields or {},
                        "open_statement": work.open_statement,
                        "image_prompt": work.image_prompt or "",
                        "source": work.source,
                        "created_at": work.created_at,
                    }
                )
            zf.writestr(
                "work_revisions.csv",
                make_csv(
                    [
                        "participant_id",
                        "class_id",
                        "class_name",
                        "group",
                        "run_id",
                        "round_no",
                        "task",
                        "revision_no",
                        "product_name",
                        "product_category",
                        "target_audience",
                        "assessment_version",
                        "rationale_schema_version",
                        "design_concept",
                        "structured_fields_json",
                        "rationale_fields_json",
                        "open_statement",
                        "image_prompt",
                        "source",
                        "created_at",
                    ],
                    work_rows,
                ),
            )

            job_rows = []
            for job in image_jobs:
                round_obj = rounds_by_id.get(job.round_id)
                participant = participant_by_round.get(job.round_id)
                zip_media = ""
                if job.status == "succeeded" and job.file_path:
                    from .storage import Storage
                    source = Storage(settings).materialize(job.file_path)
                    try:
                        if source:
                            source.relative_to(settings.data_dir.resolve())
                    except ValueError:
                        source = None
                    if source and source.exists() and participant and round_obj:
                        safe_job = _safe_file_name(str(job.id))
                        zip_media = (
                            f"files/{participant.id}/round-{round_obj.round_no}/"
                            f"keyframe-{safe_job}.png"
                        )
                        zf.write(source, zip_media)
                    else:
                        file_missing.append(str(job.id))
                elif job.status == "succeeded":
                    file_missing.append(str(job.id))
                job_rows.append(
                    {
                        **participant_fields(participant),
                        "round_no": round_obj.round_no if round_obj else "",
                        "job_id": str(job.id),
                        "status": job.status,
                        "attempts": job.attempts,
                        "work_revision_no": job.work_revision_no,
                        "prompt": job.prompt,
                        "model": job.model,
                        "error_code": job.error_code,
                        "error_message": job.error_message,
                        "file": zip_media,
                        "created_at": job.created_at,
                        "started_at": job.started_at,
                        "finished_at": job.finished_at,
                        "width": job.width,
                        "height": job.height,
                        "sha256": job.sha256,
                    }
                )
            zf.writestr(
                "image_jobs.csv",
                make_csv(
                    [
                        "participant_id",
                        "class_id",
                        "group",
                        "round_no",
                        "job_id",
                        "status",
                        "attempts",
                        "work_revision_no",
                        "prompt",
                        "model",
                        "error_code",
                        "error_message",
                        "file",
                        "created_at",
                        "started_at",
                        "finished_at",
                        "width",
                        "height",
                        "sha256",
                    ],
                    job_rows,
                ),
            )

            assessment_rows = []
            answer_rows = []
            for response in assessments:
                run = runs_by_id.get(response.run_id)
                participant = participant_by_run_id.get(response.run_id)
                instrument = instruments_by_id.get(response.instrument_version_id)
                schema = (instrument.schema_json if instrument else {}) or {}
                question_map = {
                    question.get("id"): question
                    for question in schema.get("questions", [])
                    if isinstance(question, dict)
                }
                assessment_rows.append(
                    {
                        **participant_fields(participant),
                        "assessment_version": assessment_version_for_design(
                            run.design_version if run else None
                        ),
                        "mc_max": mc_max_for_design(
                            run.design_version if run else None
                        )
                        or "",
                        "short_answer_pending": any(
                            question.get("type") == "short_text"
                            for question in question_map.values()
                        ),
                        "kind": response.kind,
                        "instrument_version_id": str(response.instrument_version_id),
                        "instrument_version": instrument.version if instrument else "",
                        "object_code": instrument.object_code if instrument else "",
                        "form_code": instrument.form_code if instrument else "",
                        "status": response.status,
                        "answers_json": response.answers_json,
                        "score_json": response.score_json,
                        "score_total": response.score_total,
                        "scoring_version": response.scoring_version,
                        "survey_version": str(schema.get("survey_version") or "")
                        if response.kind == "survey"
                        else "",
                        "started_at": response.started_at,
                        "submitted_at": response.submitted_at,
                        "duration_seconds": response.duration_seconds,
                    }
                )
                for qid, value in (response.answers_json or {}).items():
                    question = question_map.get(qid, {})
                    answer_rows.append(
                        {
                            **participant_fields(participant),
                            "kind": response.kind,
                            "object_code": instrument.object_code if instrument else "",
                            "form_code": instrument.form_code if instrument else "",
                            "question_id": qid,
                            "question_section": question.get("section", ""),
                            "question_type": question.get("type", ""),
                            "question_prompt": question.get("prompt", ""),
                            "answer_json": value,
                            "answer_text": value
                            if isinstance(value, str)
                            else _json(value),
                            "submitted_at": response.submitted_at,
                        }
                    )
            zf.writestr(
                "assessments.csv",
                make_csv(
                    [
                        "participant_id",
                        "class_id",
                        "class_name",
                        "group",
                        "kind",
                        "assessment_version",
                        "mc_max",
                        "short_answer_pending",
                        "instrument_version_id",
                        "instrument_version",
                        "object_code",
                        "form_code",
                        "status",
                        "answers_json",
                        "score_json",
                        "score_total",
                        "scoring_version",
                        "survey_version",
                        "started_at",
                        "submitted_at",
                        "duration_seconds",
                    ],
                    assessment_rows,
                ),
            )
            zf.writestr(
                "assessment_answers.csv",
                make_csv(
                    [
                        "participant_id",
                        "class_id",
                        "class_name",
                        "group",
                        "kind",
                        "object_code",
                        "form_code",
                        "question_id",
                        "question_section",
                        "question_type",
                        "question_prompt",
                        "answer_json",
                        "answer_text",
                        "submitted_at",
                    ],
                    answer_rows,
                ),
            )
            survey_rows = []
            rounds_by_run_no = {
                (round_obj.run_id, round_obj.round_no): round_obj for round_obj in rounds
            }
            s7_labels = {
                "first": "第一轮",
                "second": "第二轮",
                "same": "两种差不多",
                "uncertain": "不确定",
            }
            for response in assessments:
                if response.kind != "survey":
                    continue
                run = runs_by_id.get(response.run_id)
                participant = participant_by_run_id.get(response.run_id)
                if run is None or participant is None:
                    continue
                r1 = rounds_by_run_no.get((response.run_id, 1))
                r2 = rounds_by_run_no.get((response.run_id, 2))
                a1 = artifacts_by_id.get(r1.artifact_version_id) if r1 else None
                a2 = artifacts_by_id.get(r2.artifact_version_id) if r2 else None
                instrument = instruments_by_id.get(response.instrument_version_id)
                schema = (instrument.schema_json or {}) if instrument else {}
                survey_version = str(schema.get("survey_version") or "")
                v21 = survey_version == "survey-v2.1-pilot"
                question_map = {
                    str(question.get("id")): question
                    for question in (schema.get("questions") or [])
                    if question.get("id")
                }
                s7_question = question_map.get("S7") or {}
                s7_is_preference = s7_question.get("type") == "single_choice"
                answers = response.answers_json or {}
                s7_value = answers.get("S7", "")
                preferred_round = str(s7_value) if s7_is_preference else ""
                preferred_label = (
                    s7_labels.get(str(s7_value), "") if s7_is_preference else ""
                )
                preferred_code = ""
                preferred_condition = ""
                if s7_is_preference and s7_value == "first" and r1 is not None:
                    preferred_code = r1.condition
                elif s7_is_preference and s7_value == "second" and r2 is not None:
                    preferred_code = r2.condition
                if preferred_code:
                    preferred_condition = CONDITION_LABELS.get(preferred_code, "")
                elif s7_is_preference and s7_value == "same":
                    preferred_condition = "Similar"
                elif s7_is_preference and s7_value == "uncertain":
                    preferred_condition = "Unsure"
                v21_answers = {
                    "s1_exploration_r1": answers.get("S1", "") if v21 else "",
                    "s2_autonomy_r1": answers.get("S2", "") if v21 else "",
                    "s3_mental_effort_r1": answers.get("S3", "") if v21 else "",
                    "s4_exploration_r2": answers.get("S4", "") if v21 else "",
                    "s5_autonomy_r2": answers.get("S5", "") if v21 else "",
                    "s6_mental_effort_r2": answers.get("S6", "") if v21 else "",
                }
                survey_rows.append(
                    {
                        **participant_fields(participant),
                        "student_id": str(participant.id),
                        "group_id": participant.group_name,
                        "run_id": str(run.id),
                        "design_version": run.design_version or "legacy-v1.5",
                        "assessment_version": assessment_version_for_design(
                            run.design_version
                        ),
                        "survey_version": survey_version,
                        "survey_instrument_version": instrument.version
                        if instrument
                        else "",
                        "condition_sequence": run.condition_sequence or "",
                        "artifact_sequence": run.artifact_sequence or "",
                        "round1_ai_condition": r1.condition if r1 else "",
                        "round1_artifact_id": str(r1.artifact_version_id) if r1 else "",
                        "round1_artifact_slot": a1.slot if a1 else "",
                        "round1_object_code": a1.object_code if a1 else "",
                        "round2_ai_condition": r2.condition if r2 else "",
                        "round2_artifact_id": str(r2.artifact_version_id) if r2 else "",
                        "round2_artifact_slot": a2.slot if a2 else "",
                        "round2_object_code": a2.object_code if a2 else "",
                        **{f"S{i}": answers.get(f"S{i}", "") for i in range(1, 8)},
                        **v21_answers,
                        "s7_preferred_round": preferred_round,
                        "s7_preferred_round_label": preferred_label,
                        "s7_preferred_ai_condition": preferred_condition,
                        "s7_preferred_condition_code": preferred_code,
                        "S7_label": s7_labels.get(str(s7_value), "")
                        if s7_is_preference
                        else "",
                        "submitted_at": response.submitted_at,
                    }
                )
            counts["survey.csv"] = len(survey_rows)
            zf.writestr(
                "survey.csv",
                make_csv(
                    [
                        "participant_id",
                        "student_id",
                        "class_id",
                        "class_name",
                        "group",
                        "group_id",
                        "run_id",
                        "design_version",
                        "assessment_version",
                        "survey_version",
                        "survey_instrument_version",
                        "condition_sequence",
                        "artifact_sequence",
                        "round1_ai_condition",
                        "round1_artifact_id",
                        "round1_artifact_slot",
                        "round1_object_code",
                        "round2_ai_condition",
                        "round2_artifact_id",
                        "round2_artifact_slot",
                        "round2_object_code",
                        "S1",
                        "S2",
                        "S3",
                        "S4",
                        "S5",
                        "S6",
                        "S7",
                        "s1_exploration_r1",
                        "s2_autonomy_r1",
                        "s3_mental_effort_r1",
                        "s4_exploration_r2",
                        "s5_autonomy_r2",
                        "s6_mental_effort_r2",
                        "s7_preferred_round",
                        "s7_preferred_round_label",
                        "s7_preferred_ai_condition",
                        "s7_preferred_condition_code",
                        "S7_label",
                        "submitted_at",
                    ],
                    survey_rows,
                ),
            )
            zf.writestr(
                "analysis.csv",
                make_csv(
                    [
                        "student_id",
                        "class_id",
                        "class_name",
                        "group_id",
                        "design_version",
                        "run_id",
                        "round_no",
                        "artifact_id",
                        "artifact_slot",
                        "ai_condition",
                        "condition_sequence",
                        "artifact_sequence",
                        "test_form_sequence",
                        "prompt_versions",
                        "stage_events",
                        "student_messages",
                        "assistant_messages",
                        "design_versions",
                        "final_submission",
                        "assessment_version",
                        "mc_max",
                        "rationale_schema_version",
                        "knowledge_pretest_score",
                        "knowledge_posttest_score",
                        "knowledge_pretest_mc",
                        "knowledge_posttest_mc",
                        "posttest_short_score_0_2",
                        "peer_batch_id",
                        "peer_review_version",
                        "peer_rating_count",
                        "peer_cultural_clarity_mean",
                        "peer_cultural_translation_mean",
                        "peer_design_originality_mean",
                        "peer_clarity_mean",
                        "peer_evidence_link_mean",
                        "peer_attraction_mean",
                        "final_rationale_fields",
                        "task_start_time",
                        "task_end_time",
                    ],
                    analysis_rows,
                ),
            )
            zf.writestr(
                "ai_calls.csv",
                make_csv(
                    [
                        "participant_id",
                        "run_id",
                        "round_no",
                        "purpose",
                        "status",
                        "model",
                        "prompt_version",
                        "request_json",
                        "response_text",
                        "http_status",
                        "error_code",
                        "error_message",
                        "latency_ms",
                        "created_at",
                        "completed_at",
                    ],
                    [
                        {
                            "participant_id": participant_fields(
                                participant_by_run_id.get(call.run_id)
                            )["participant_id"],
                            "run_id": str(call.run_id),
                            "round_no": rounds_by_id[call.round_id].round_no
                            if call.round_id in rounds_by_id
                            else "",
                            "purpose": call.purpose,
                            "status": call.status,
                            "model": call.model,
                            "prompt_version": call.prompt_version,
                            "request_json": call.request_json,
                            "response_text": call.response_text,
                            "http_status": call.http_status,
                            "error_code": call.error_code,
                            "error_message": call.error_message,
                            "latency_ms": call.latency_ms,
                            "created_at": call.created_at,
                            "completed_at": call.completed_at,
                        }
                        for call in ai_calls
                    ],
                ),
            )
            zf.writestr(
                "api_errors.csv",
                make_csv(
                    [
                        "participant_id",
                        "run_id",
                        "category",
                        "endpoint",
                        "status_code",
                        "error_code",
                        "message",
                        "created_at",
                    ],
                    [
                        {
                            "participant_id": str(error.participant_id)
                            if error.participant_id
                            else "",
                            "run_id": str(error.run_id) if error.run_id else "",
                            "category": error.category,
                            "endpoint": error.endpoint,
                            "status_code": error.status_code,
                            "error_code": error.error_code,
                            "message": error.message,
                            "created_at": error.created_at,
                        }
                        for error in api_errors
                    ],
                ),
            )
            zf.writestr(
                "class_entry_links.csv",
                make_csv(
                    [
                        "link_id",
                        "class_id",
                        "class_name",
                        "label",
                        "active",
                        "created_at",
                        "revoked_at",
                    ],
                    [
                        {
                            "link_id": str(link.id),
                            "class_id": link.class_id,
                            "class_name": classes.get(link.class_id, ""),
                            "label": link.label,
                            "active": link.active,
                            "created_at": link.created_at,
                            "revoked_at": link.revoked_at,
                        }
                        for link in class_entry_links
                    ],
                ),
            )
            zf.writestr(
                "class_peer_gates.csv",
                make_csv(
                    [
                        "class_id",
                        "class_name",
                        "status",
                        "membership_frozen_at",
                        "peer_opened_at",
                        "entered_count_at_open",
                        "t2_ended_count_at_open",
                        "valid_work_count_at_open",
                        "batch_id",
                    ],
                    [
                        {
                            "class_id": gate.class_id,
                            "class_name": classes.get(gate.class_id, ""),
                            "status": gate.status,
                            "membership_frozen_at": gate.membership_frozen_at,
                            "peer_opened_at": gate.peer_opened_at,
                            "entered_count_at_open": gate.entered_count_at_open,
                            "t2_ended_count_at_open": gate.t2_ended_count_at_open,
                            "valid_work_count_at_open": gate.valid_work_count_at_open,
                            "batch_id": str(gate.batch_id) if gate.batch_id else "",
                        }
                        for gate in class_peer_gates
                    ],
                ),
            )
            zf.writestr(
                "class_peer_gate_events.csv",
                make_csv(
                    [
                        "event_id",
                        "class_id",
                        "event_type",
                        "counts_json",
                        "peer_batch_id",
                        "created_at",
                    ],
                    [
                        {
                            "event_id": event.id,
                            "class_id": event.class_id,
                            "event_type": event.event_type,
                            "counts_json": event.counts_json,
                            "peer_batch_id": str(event.peer_batch_id)
                            if event.peer_batch_id
                            else "",
                            "created_at": event.created_at,
                        }
                        for event in class_peer_gate_events
                    ],
                ),
            )
            zf.writestr(
                "peer_batches.csv",
                make_csv(
                    [
                        "batch_id",
                        "class_id",
                        "class_name",
                        "status",
                        "algorithm_version",
                        "scale_version",
                        "eligible_work_count",
                        "config_json",
                        "created_at",
                        "frozen_at",
                    ],
                    [
                        {
                            "batch_id": str(batch.id),
                            "class_id": batch.class_id,
                            "class_name": classes.get(batch.class_id, ""),
                            "status": batch.status,
                            "algorithm_version": batch.algorithm_version,
                            "scale_version": batch.scale_version,
                            "eligible_work_count": batch.eligible_work_count,
                            "config_json": batch.config_json,
                            "created_at": batch.created_at,
                            "frozen_at": batch.frozen_at,
                        }
                        for batch in peer_batches
                    ],
                ),
            )
            assignment_rows = []
            for assignment in peer_assignments:
                work = works_by_id.get(assignment.work_id)
                round_obj = rounds_by_id.get(work.round_id) if work else None
                reviewer = participant_by_run_id.get(assignment.reviewer_run_id)
                owner = work_owner_fields(work) if work else {}
                batch = peer_batches_by_id.get(assignment.batch_id)
                artifact = (
                    artifacts_by_id.get(round_obj.artifact_version_id)
                    if round_obj
                    else None
                )
                assignment_rows.append(
                    {
                        "assignment_id": str(assignment.id),
                        "batch_id": str(assignment.batch_id),
                        "review_version": batch.scale_version if batch else "",
                        "reviewer_participant_id": str(reviewer.id) if reviewer else "",
                        "reviewer_student_id": str(reviewer.id) if reviewer else "",
                        "reviewer_group_id": reviewer.group_name if reviewer else "",
                        "reviewer_run_id": str(assignment.reviewer_run_id),
                        "work_id": assignment.work_id,
                        "reviewed_work_id": assignment.work_id,
                        "work_code": _work_code(assignment.work_id),
                        "work_owner_participant_id": owner.get("participant_id", ""),
                        "reviewed_student_id": owner.get("participant_id", ""),
                        "reviewed_group_id": owner.get("group", ""),
                        "round_no": round_obj.round_no if round_obj else "",
                        "reviewed_round_no": round_obj.round_no if round_obj else "",
                        "ai_condition": round_obj.condition if round_obj else "",
                        "reviewed_ai_condition": round_obj.condition if round_obj else "",
                        "artifact_id": str(round_obj.artifact_version_id)
                        if round_obj
                        else "",
                        "reviewed_artifact_id": str(round_obj.artifact_version_id)
                        if round_obj
                        else "",
                        "artifact_slot": artifact.slot if artifact else "",
                        "status": assignment.status,
                        "created_at": assignment.created_at,
                    }
                )
            zf.writestr(
                "peer_assignments.csv",
                make_csv(
                    [
                        "assignment_id",
                        "batch_id",
                        "review_version",
                        "reviewer_participant_id",
                        "reviewer_student_id",
                        "reviewer_group_id",
                        "reviewer_run_id",
                        "work_id",
                        "reviewed_work_id",
                        "work_code",
                        "work_owner_participant_id",
                        "reviewed_student_id",
                        "reviewed_group_id",
                        "round_no",
                        "reviewed_round_no",
                        "ai_condition",
                        "reviewed_ai_condition",
                        "artifact_id",
                        "reviewed_artifact_id",
                        "artifact_slot",
                        "status",
                        "created_at",
                    ],
                    assignment_rows,
                ),
            )
            rating_rows = []
            for rating in peer_ratings:
                assignment = next(
                    (
                        item
                        for item in peer_assignments
                        if item.id == rating.assignment_id
                    ),
                    None,
                )
                work_id = assignment.work_id if assignment else None
                work = works_by_id.get(work_id) if work_id else None
                round_obj = rounds_by_id.get(work.round_id) if work else None
                owner = work_owner_fields(work) if work else {}
                owner_run = runs_by_id.get(round_obj.run_id) if round_obj else None
                artifact = (
                    artifacts_by_id.get(round_obj.artifact_version_id)
                    if round_obj
                    else None
                )
                reviewer = (
                    participant_by_run_id.get(assignment.reviewer_run_id)
                    if assignment
                    else None
                )
                batch = (
                    peer_batches_by_id.get(assignment.batch_id) if assignment else None
                )
                scores = rating.scores_json or {}
                rating_rows.append(
                    {
                        "assignment_id": str(rating.assignment_id),
                        "batch_id": str(assignment.batch_id) if assignment else "",
                        "review_version": batch.scale_version if batch else "",
                        "reviewer_participant_id": str(reviewer.id) if reviewer else "",
                        "reviewer_student_id": str(reviewer.id) if reviewer else "",
                        "reviewer_group_id": reviewer.group_name if reviewer else "",
                        "reviewer_run_id": str(assignment.reviewer_run_id) if assignment else "",
                        "work_id": work_id or "",
                        "reviewed_work_id": work_id or "",
                        "work_code": _work_code(work_id) if work_id else "",
                        "work_owner_participant_id": owner.get("participant_id", ""),
                        "reviewed_student_id": owner.get("participant_id", ""),
                        "reviewed_group_id": owner.get("group", ""),
                        "round_no": round_obj.round_no if round_obj else "",
                        "reviewed_round_no": round_obj.round_no if round_obj else "",
                        "ai_condition": round_obj.condition if round_obj else "",
                        "reviewed_ai_condition": round_obj.condition if round_obj else "",
                        "reviewed_ai_condition_label": CONDITION_LABELS.get(
                            round_obj.condition, ""
                        )
                        if round_obj
                        else "",
                        "artifact_id": str(round_obj.artifact_version_id)
                        if round_obj
                        else "",
                        "reviewed_artifact_id": str(round_obj.artifact_version_id)
                        if round_obj
                        else "",
                        "artifact_slot": artifact.slot if artifact else "",
                        "reviewed_artifact_slot": artifact.slot if artifact else "",
                        "object_code": artifact.object_code if artifact else "",
                        "condition_sequence": owner_run.condition_sequence
                        if owner_run
                        else "",
                        "artifact_sequence": owner_run.artifact_sequence
                        if owner_run
                        else "",
                        "scores_json": scores,
                        "clarity": scores.get("clarity", ""),
                        "evidence_link": scores.get("evidence_link", ""),
                        "attraction": scores.get("attraction", ""),
                        "cultural_clarity": scores.get("cultural_clarity", ""),
                        "cultural_translation": scores.get("cultural_translation", ""),
                        "design_originality": scores.get("design_originality", ""),
                        "comment": rating.comment,
                        "optional_comment": rating.comment,
                        "submitted_at": rating.submitted_at,
                        "updated_at": rating.updated_at,
                    }
                )
            zf.writestr(
                "peer_ratings.csv",
                make_csv(
                    [
                        "assignment_id",
                        "batch_id",
                        "review_version",
                        "reviewer_participant_id",
                        "reviewer_student_id",
                        "reviewer_group_id",
                        "reviewer_run_id",
                        "work_id",
                        "reviewed_work_id",
                        "work_code",
                        "work_owner_participant_id",
                        "reviewed_student_id",
                        "reviewed_group_id",
                        "round_no",
                        "reviewed_round_no",
                        "ai_condition",
                        "reviewed_ai_condition",
                        "reviewed_ai_condition_label",
                        "artifact_id",
                        "reviewed_artifact_id",
                        "artifact_slot",
                        "reviewed_artifact_slot",
                        "object_code",
                        "condition_sequence",
                        "artifact_sequence",
                        "scores_json",
                        "clarity",
                        "evidence_link",
                        "attraction",
                        "cultural_clarity",
                        "cultural_translation",
                        "design_originality",
                        "comment",
                        "optional_comment",
                        "submitted_at",
                        "updated_at",
                    ],
                    rating_rows,
                ),
            )
            zf.writestr(
                "peer_work_scores.csv",
                make_csv(
                    [
                        "batch_id",
                        "class_id",
                        "class_name",
                        "participant_id",
                        "group_id",
                        "run_id",
                        "round_no",
                        "work_id",
                        "work_code",
                        "review_version",
                        "artifact_id",
                        "artifact_slot",
                        "object_code",
                        "ai_condition",
                        "condition_sequence",
                        "artifact_sequence",
                        "image_available",
                        "rating_count",
                        "cultural_clarity_mean",
                        "cultural_translation_mean",
                        "design_originality_mean",
                        "clarity_mean",
                        "evidence_link_mean",
                        "attraction_mean",
                    ],
                    peer_score_rows,
                ),
            )
            zf.writestr(
                "peer_impressions.csv",
                make_csv(
                    [
                        "participant_id",
                        "class_id",
                        "group",
                        "assignment_id",
                        "work_id",
                        "work_code",
                        "work_owner_participant_id",
                        "round_no",
                        "position",
                        "shown_at",
                        "viewed_ms",
                        "batch_id",
                    ],
                    [
                        {
                            **participant_fields(participant_by_run_id.get(item.reviewer_run_id)),
                            "assignment_id": str(item.assignment_id),
                            "work_id": item.work_id,
                            "work_code": _work_code(item.work_id),
                            "work_owner_participant_id": work_owner_fields(
                                works_by_id.get(item.work_id)
                            )["participant_id"]
                            if works_by_id.get(item.work_id)
                            else "",
                            "round_no": rounds_by_id.get(
                                works_by_id[item.work_id].round_id
                            ).round_no
                            if item.work_id in works_by_id
                            and works_by_id[item.work_id].round_id in rounds_by_id
                            else "",
                            "position": item.position,
                            "shown_at": item.shown_at,
                            "viewed_ms": item.viewed_ms,
                            "batch_id": str(item.batch_id),
                        }
                        for item in peer_impressions
                    ],
                ),
            )
            zf.writestr(
                "social_views.csv",
                make_csv(
                    [
                        "participant_id",
                        "work_id",
                        "work_code",
                        "created_at",
                    ],
                    [
                        {
                            "participant_id": participant_fields(
                                participant_by_run_id.get(view.run_id)
                            )["participant_id"],
                            "work_id": view.work_id,
                            "work_code": _work_code(view.work_id),
                            "created_at": view.created_at,
                        }
                        for view in social_views
                    ],
                ),
            )
            zf.writestr(
                "social_likes.csv",
                make_csv(
                    [
                        "participant_id",
                        "work_id",
                        "work_code",
                        "active",
                        "created_at",
                        "updated_at",
                    ],
                    [
                        {
                            "participant_id": participant_fields(
                                participant_by_run_id.get(like.run_id)
                            )["participant_id"],
                            "work_id": like.work_id,
                            "work_code": _work_code(like.work_id),
                            "active": like.active,
                            "created_at": like.created_at,
                            "updated_at": like.updated_at,
                        }
                        for like in social_likes
                    ],
                ),
            )
            zf.writestr(
                "social_comments.csv",
                make_csv(
                    [
                        "comment_id",
                        "participant_id",
                        "work_id",
                        "work_code",
                        "content",
                        "hidden",
                        "created_at",
                    ],
                    [
                        {
                            "comment_id": comment.id,
                            "participant_id": participant_fields(
                                participant_by_run_id.get(comment.run_id)
                            )["participant_id"],
                            "work_id": comment.work_id,
                            "work_code": _work_code(comment.work_id),
                            "content": comment.content,
                            "hidden": comment.hidden,
                            "created_at": comment.created_at,
                        }
                        for comment in social_comments
                    ],
                ),
            )
            zf.writestr(
                "social_events.csv",
                make_csv(
                    [
                        "event_id",
                        "participant_id",
                        "work_id",
                        "work_code",
                        "event_type",
                        "meta_json",
                        "created_at",
                    ],
                    [
                        {
                            "event_id": event.id,
                            "participant_id": participant_fields(
                                participant_by_run_id.get(event.run_id)
                            )["participant_id"],
                            "work_id": event.work_id,
                            "work_code": _work_code(event.work_id),
                            "event_type": event.event_type,
                            "meta_json": event.meta_json,
                            "created_at": event.created_at,
                        }
                        for event in social_events
                    ],
                ),
            )
            protocol_payload = {
                "export_version": EXPORT_VERSION,
                "active_protocol": next(
                    (
                        {
                            "id": str(protocol.id),
                            "artifact_x_version_id": str(
                                protocol.artifact_x_version_id
                            ),
                            "artifact_y_version_id": str(
                                protocol.artifact_y_version_id
                            ),
                            "instrument_versions": protocol.instrument_versions,
                            "assessment_version": protocol.assessment_version or "",
                            "research_rubric": protocol.research_rubric_json,
                            "assessment_forms": [
                                {
                                    "kind": form.kind,
                                    "object_code": form.object_code,
                                    "form_code": form.form_code,
                                    "instrument_version_id": str(form.instrument_version_id),
                                }
                                for form in protocol_forms
                                if form.protocol_version_id == protocol.id
                            ],
                            "is_demo": protocol.is_demo,
                            "activated_at": protocol.activated_at.isoformat()
                            if protocol.activated_at
                            else None,
                        }
                        for protocol in protocols
                        if protocol.is_active
                    ),
                    None,
                ),
                "artifact_versions": [
                    {
                        "id": str(artifact.id),
                        "slot": artifact.slot,
                        "object_code": artifact.object_code,
                        "version": artifact.version,
                        "title": artifact.title,
                        "era": artifact.era,
                        "type": artifact.artifact_type,
                        "introduction": artifact.introduction,
                        "facts": artifact.facts,
                        "evidence": artifact.evidence,
                        "uncertainty": artifact.uncertainty,
                        "sections": artifact.sections_json,
                        "media": artifact.media_json,
                        "content_sha256": artifact.content_sha256,
                        "rights_status": artifact.rights_status,
                        "image_sha256": artifact.image_sha256,
                        "is_demo": artifact.is_demo,
                        "created_at": artifact.created_at.isoformat(),
                    }
                    for artifact in artifact_versions
                ],
                "instrument_versions": [
                    {
                        "id": str(instrument.id),
                        "kind": instrument.kind,
                        "object_code": instrument.object_code,
                        "form_code": instrument.form_code,
                        "version": instrument.version,
                        "title": instrument.title,
                        "instructions": instrument.instructions,
                        "schema": instrument.schema_json,
                        "is_demo": instrument.is_demo,
                        "created_at": instrument.created_at.isoformat(),
                    }
                    for instrument in instrument_versions
                ],
            }
            zf.writestr("protocol.json", json.dumps(protocol_payload, ensure_ascii=False, indent=2))
            zf.writestr("README_data_dictionary.md", _data_dictionary())
            zf.writestr(
                "manifest.json",
                json.dumps(
                    {
                        **manifest,
                        "csv_rows": counts,
                        "missing_files": file_missing,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path, manifest
