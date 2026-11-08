from __future__ import annotations

from typing import Any, Dict, Literal, Optional, List

from pydantic import BaseModel, Field, model_validator


QuestionType = Literal[
    "single_choice", "multi_choice", "short_text", "evidence_judgment", "likert"
]


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None
    retryable: bool = False


class ErrorResponse(BaseModel):
    error: ErrorBody


class EnterRequest(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=32)
    email: Optional[str] = Field(default=None, min_length=1, max_length=320)
    class_id: int = Field(ge=0, le=4)
    class_token: Optional[str] = Field(default=None, min_length=8, max_length=80)

    @model_validator(mode="after")
    def exactly_one_credential(self):
        if bool(self.code) == bool(self.email):
            raise ValueError("Provide exactly one of code or email")
        return self


class AdminLoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class ClassLinkCreate(BaseModel):
    class_id: int = Field(ge=0, le=4)
    label: str = Field(default="", max_length=120)


class ScriptUpdate(BaseModel):
    title: str = Field(default="", max_length=200)
    body: str = Field(default="", max_length=10000)


class StructuredFields(BaseModel):
    cultural_features: str = Field(default="", max_length=2000)
    historical_function: str = Field(default="", max_length=2000)
    sources_evidence: str = Field(default="", max_length=2000)
    cultural_continuity: str = Field(default="", max_length=2000)
    cultural_translation: str = Field(default="", max_length=2000)
    innovation_rationale: str = Field(default="", max_length=2000)


class RationaleFields(BaseModel):
    heritage_knowledge: str = Field(default="", max_length=1000)
    cultural_translation: str = Field(default="", max_length=1000)
    design_reason: str = Field(default="", max_length=1000)


class WorkUpdate(BaseModel):
    product_name: str = Field(default="", max_length=200)
    product_category: str = Field(default="", max_length=160)
    target_audience: str = Field(default="", max_length=300)
    design_concept: str = Field(default="", max_length=4000)
    structured_fields: StructuredFields = Field(default_factory=StructuredFields)
    rationale_fields: RationaleFields = Field(default_factory=RationaleFields)
    open_statement: str = Field(default="", max_length=4000)
    image_prompt: str = Field(default="", max_length=6000)


class ChatCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    client_message_id: str = Field(min_length=8, max_length=80)


class HLSFAdvance(BaseModel):
    from_phase: str = Field(min_length=3, max_length=16)
    skip: bool = False


class HLSFHint(BaseModel):
    phase: str = Field(min_length=3, max_length=16)


class HLSFNudge(BaseModel):
    action: Literal["shown", "dismissed", "hint", "advance"]
    phase: str = Field(min_length=3, max_length=16)
    user_turns: int = Field(default=0, ge=0, le=50)


class EvidenceView(BaseModel):
    section: str = Field(min_length=1, max_length=80)
    event_type: str = Field(default="view", max_length=40)
    duration_ms: Optional[int] = Field(default=None, ge=0, le=86_400_000)
    meta: dict = Field(default_factory=dict)


class ImageJobCreate(BaseModel):
    retry_of: Optional[str] = None


class AssessmentDraft(BaseModel):
    answers: dict = Field(default_factory=dict)


class FinishRequest(BaseModel):
    consent_future_research: Optional[bool] = None


class PeerRatingRequest(BaseModel):
    scores: dict = Field(default_factory=dict)
    comment: str = Field(default="", max_length=1000)


class PeerImpressionRequest(BaseModel):
    viewed_ms: int = Field(default=0, ge=0, le=86_400_000)


class SocialCommentRequest(BaseModel):
    content: str = Field(min_length=1, max_length=600)


class Option(BaseModel):
    value: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=500)
    # Optional English reading aid; answer values and scoring never depend on it.
    label_en: Optional[str] = Field(default=None, max_length=500)
    allow_text: bool = False


class QuestionRow(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    label: str = Field(min_length=1, max_length=1000)


class Question(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,60}$")
    type: QuestionType
    prompt: str = Field(min_length=1, max_length=2000)
    # Optional English reading aid; the Chinese prompt remains the instrument text.
    prompt_en: Optional[str] = Field(default=None, max_length=2000)
    section: Optional[str] = Field(default=None, max_length=120)
    section_en: Optional[str] = Field(default=None, max_length=160)
    subsection: Optional[str] = Field(default=None, max_length=120)
    subsection_en: Optional[str] = Field(default=None, max_length=160)
    heading: Optional[str] = Field(default=None, max_length=120)
    heading_en: Optional[str] = Field(default=None, max_length=160)
    required: bool = True
    options: List[Option] = Field(default_factory=list)
    max_length: Optional[int] = Field(default=200, ge=1, le=4000)
    rows: List[QuestionRow] = Field(default_factory=list)
    scale_min: Optional[int] = Field(default=1, ge=0, le=10)
    scale_max: Optional[int] = Field(default=5, ge=1, le=10)
    scale_labels: List[str] = Field(default_factory=list)
    scale_anchors: Dict[int, str] = Field(default_factory=dict)
    scale_anchors_en: Dict[int, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_question(self):
        if self.type in ("single_choice", "multi_choice"):
            if len(self.options) < 2:
                raise ValueError("Choice questions need at least two options")
            values = [option.value for option in self.options]
            if len(set(values)) != len(values):
                raise ValueError("Option values must be unique")
        if self.type == "evidence_judgment":
            if not self.rows:
                raise ValueError("Evidence judgement needs at least one row")
            row_ids = [row.id for row in self.rows]
            if len(set(row_ids)) != len(row_ids):
                raise ValueError("Evidence row ids must be unique")
        if self.type == "likert":
            if self.scale_min is None or self.scale_max is None:
                raise ValueError("Likert scale bounds are required")
            if self.scale_min >= self.scale_max:
                raise ValueError("Likert minimum must be lower than maximum")
            for point in self.scale_anchors.keys() | self.scale_anchors_en.keys():
                if not self.scale_min <= point <= self.scale_max:
                    raise ValueError("Scale anchors must be within the scale bounds")
        return self


class InstrumentPayload(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    title_en: Optional[str] = Field(default=None, max_length=200)
    instructions: str = Field(default="", max_length=4000)
    instructions_en: Optional[str] = Field(default=None, max_length=4000)
    scoring_version: str = Field(default="k-v1.0", max_length=32)
    # Content revision tag (currently used by the experience survey).  Stored
    # inside schema_json so historical instrument versions keep their own tag
    # without a database migration.
    survey_version: str = Field(default="", max_length=64)
    # Researcher metadata is stored with the frozen version, never sent to students.
    research_notes: Dict[str, Any] = Field(default_factory=dict)
    questions: List[Question] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ids(self):
        ids = [question.id for question in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError("Question ids must be unique")
        if not self.questions:
            raise ValueError("At least one question is required")
        return self


class ProtocolActivate(BaseModel):
    demo: bool = False
