from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ClassGroup(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)


class RuntimeTask(Base):
    """Durable outbox, execution lease and checkpoints for cloud jobs."""
    __tablename__ = "runtime_tasks"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", index=True)
    dispatch_state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    checkpoint: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    file_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    lease_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (
        UniqueConstraint("email", name="uq_participant_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id"), nullable=False, index=True
    )
    group_name: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(
        String(320), nullable=True, index=True
    )
    access_code_hmac: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    access_code_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    participant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("participants.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ArtifactVersion(Base):
    __tablename__ = "artifact_versions"
    __table_args__ = (
        UniqueConstraint("slot", "version", name="uq_artifact_slot_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slot: Mapped[str] = mapped_column(String(1), nullable=False, index=True)
    object_code: Mapped[Optional[str]] = mapped_column(String(1), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    era: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    artifact_type: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    introduction: Mapped[str] = mapped_column(Text, nullable=False, default="")
    facts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    uncertainty: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sections_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    media_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    content_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rights_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="internal-research"
    )
    image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    image_mime: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    image_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class InstrumentVersion(Base):
    __tablename__ = "instrument_versions"
    __table_args__ = (
        UniqueConstraint("kind", "version", name="uq_instrument_kind_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    object_code: Mapped[Optional[str]] = mapped_column(String(1), nullable=True, index=True)
    form_code: Mapped[Optional[str]] = mapped_column(String(1), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ProtocolVersion(Base):
    __tablename__ = "protocol_versions"
    __table_args__ = (
        Index(
            "uq_protocol_single_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artifact_x_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifact_versions.id"), nullable=False
    )
    artifact_y_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifact_versions.id"), nullable=False
    )
    instrument_versions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    research_rubric_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    assessment_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participants.id"), nullable=False, unique=True, index=True
    )
    protocol_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("protocol_versions.id"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    # Crossover pilot: the design version distinguishes new BA/AB runs from
    # historical v1.5 rows that had T2 = Standard AI.
    design_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Prompt version is frozen per run so a new pilot prompt cannot silently
    # change an already-started v1.8 participant's later stages.
    hlsf_prompt_version: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    # Fixed for audit; derived from the group and design version at run creation.
    t1_condition: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    condition_sequence: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    artifact_sequence: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    artifact_order: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    object_order: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    test_form_order: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    consent_future_research: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    consent_recorded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consent_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_operation_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stop_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class StageEvent(Base):
    __tablename__ = "stage_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class Round(Base):
    __tablename__ = "rounds"
    __table_args__ = (UniqueConstraint("run_id", "round_no", name="uq_run_round"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id"), nullable=False, index=True
    )
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifact_versions.id"), nullable=False
    )
    condition: Mapped[str] = mapped_column(String(1), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    deadline_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finish_reason: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    current_script_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    current_work_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    selected_image_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ScriptRevision(Base):
    __tablename__ = "script_revisions"
    __table_args__ = (
        UniqueConstraint("round_id", "revision_no", name="uq_script_revision"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    round_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rounds.id"), nullable=False, index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="autosave")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class WorkRevision(Base):
    """Versioned T1/T2 product-design submission.

    T1 stores six structured fields under ``structured_fields``.  T2 stores the
    open response under ``open_statement``.  Legacy short-video script data
    remains in ``script_revisions`` and is never deleted by this migration.
    """

    __tablename__ = "work_revisions"
    __table_args__ = (
        UniqueConstraint("round_id", "revision_no", name="uq_work_revision"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    round_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rounds.id"), nullable=False, index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    product_category: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    target_audience: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    design_concept: Mapped[str] = mapped_column(Text, nullable=False, default="")
    structured_fields: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    rationale_fields: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    open_statement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="autosave")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "round_id", "client_message_id", name="uq_message_client_id"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    round_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rounds.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="student")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    client_message_id: Mapped[Optional[str]] = mapped_column(
        String(80), nullable=True
    )
    ai_call_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class HLSFState(Base):
    __tablename__ = "hlsf_states"

    round_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rounds.id"), primary_key=True
    )
    phase: Mapped[str] = mapped_column(String(16), nullable=False)
    hint_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class HLSFEvent(Base):
    __tablename__ = "hlsf_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    round_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rounds.id"), nullable=False, index=True
    )
    phase: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("messages.id"), nullable=True
    )
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AiCall(Base):
    __tablename__ = "ai_calls"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id"), nullable=False, index=True
    )
    round_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("rounds.id"), nullable=True, index=True
    )
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_response_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ImageJob(Base):
    __tablename__ = "image_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    round_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rounds.id"), nullable=False, index=True
    )
    script_revision_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    work_revision_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    source_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt_optimizer_version: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )
    reference_image_used: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_of_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    model: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    mime: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class EvidenceEvent(Base):
    __tablename__ = "evidence_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    round_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rounds.id"), nullable=False, index=True
    )
    section: Mapped[str] = mapped_column(String(80), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AssessmentResponse(Base):
    __tablename__ = "assessment_responses"
    __table_args__ = (
        UniqueConstraint("run_id", "kind", name="uq_assessment_run_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instrument_versions.id"), nullable=False
    )
    answers_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    score_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scoring_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    scored_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ProtocolAssessmentForm(Base):
    __tablename__ = "protocol_assessment_forms"
    __table_args__ = (
        UniqueConstraint(
            "protocol_version_id",
            "kind",
            "object_code",
            "form_code",
            name="uq_protocol_assessment_form",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    protocol_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("protocol_versions.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    object_code: Mapped[str] = mapped_column(String(1), nullable=False)
    form_code: Mapped[str] = mapped_column(String(1), nullable=False)
    instrument_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instrument_versions.id"), nullable=False
    )


class AssessmentItemKey(Base):
    __tablename__ = "assessment_item_keys"
    __table_args__ = (
        UniqueConstraint(
            "instrument_version_id", "question_id", name="uq_assessment_item_key"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instrument_versions.id"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(String(60), nullable=False)
    correct_value: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    construct: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    dimension: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class ApiError(Base):
    __tablename__ = "api_errors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    participant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    endpoint: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class PeerBatch(Base):
    """Frozen peer-assessment assignment batch for one class."""

    __tablename__ = "peer_batches"
    __table_args__ = (
        Index("uq_peer_batch_active", "class_id", unique=True,
              postgresql_where=text("status <> 'superseded' AND (class_id <> 0 OR algorithm_version <> 'beta-continuous-v1')")),
        Index("uq_beta_peer_reviewer_snapshot", text("(config_json ->> 'reviewer_run_id')"), unique=True,
              postgresql_where=text("class_id = 0 AND algorithm_version = 'beta-continuous-v1'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="frozen")
    algorithm_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="peer-v1"
    )
    scale_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="peer-scale-v1"
    )
    eligible_work_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    frozen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PeerAssignment(Base):
    __tablename__ = "peer_assignments"
    __table_args__ = (
        UniqueConstraint(
            "batch_id", "reviewer_run_id", "work_id", name="uq_peer_assignment"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("peer_batches.id"), nullable=False, index=True
    )
    reviewer_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id"), nullable=False, index=True
    )
    work_id: Mapped[int] = mapped_column(
        ForeignKey("work_revisions.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    allocation_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="main", server_default="main")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class PeerImpression(Base):
    __tablename__ = "peer_impressions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("peer_assignments.id"), nullable=False, unique=True, index=True
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("peer_batches.id"), nullable=False, index=True
    )
    reviewer_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id"), nullable=False, index=True
    )
    work_id: Mapped[int] = mapped_column(
        ForeignKey("work_revisions.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shown_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    viewed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class PeerRating(Base):
    __tablename__ = "peer_ratings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("peer_assignments.id"), nullable=False, unique=True, index=True
    )
    scores_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class SocialView(Base):
    __tablename__ = "social_views"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id"), nullable=False, index=True
    )
    work_id: Mapped[int] = mapped_column(
        ForeignKey("work_revisions.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class SocialLike(Base):
    __tablename__ = "social_likes"
    __table_args__ = (
        UniqueConstraint("run_id", "work_id", name="uq_social_like"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id"), nullable=False, index=True
    )
    work_id: Mapped[int] = mapped_column(
        ForeignKey("work_revisions.id"), nullable=False, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class SocialComment(Base):
    __tablename__ = "social_comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id"), nullable=False, index=True
    )
    work_id: Mapped[int] = mapped_column(
        ForeignKey("work_revisions.id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class SocialEvent(Base):
    __tablename__ = "social_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id"), nullable=False, index=True
    )
    work_id: Mapped[int] = mapped_column(
        ForeignKey("work_revisions.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ClassEntryLink(Base):
    """Per-class entry link; recoverable tokens are derived, never stored raw."""

    __tablename__ = "class_entry_links"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    token_scheme: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ClassPeerGate(Base):
    """Per-class progress gate with immutable opening policy and membership.

    Historical opened gates and assignments retain their original semantics.
    """

    __tablename__ = "class_peer_gates"

    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="collecting")
    policy_version: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)
    timer_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    opening_reason: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    membership_frozen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    peer_opened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    entered_count_at_open: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    t2_ended_count_at_open: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    valid_work_count_at_open: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("peer_batches.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ClassPeerGateEvent(Base):
    __tablename__ = "class_peer_gate_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    counts_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    peer_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
