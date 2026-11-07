from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain import CROSSOVER_V2_DESIGN_VERSION
from ..errors import AppError
from ..models import Round, WorkRevision
from ..schemas import RationaleFields, StructuredFields, WorkUpdate

T1_FIELD_KEYS = (
    "cultural_features",
    "historical_function",
    "sources_evidence",
    "cultural_continuity",
    "cultural_translation",
    "innovation_rationale",
)

T1_FIELD_LABELS = {
    "cultural_features": "文化特征",
    "historical_function": "历史功能与社会意义",
    "sources_evidence": "资料与证据",
    "cultural_continuity": "文化延续",
    "cultural_translation": "文化转译 / 再情境化",
    "innovation_rationale": "创新与设计理由",
}

RATIONALE_FIELD_KEYS = (
    "heritage_knowledge",
    "cultural_translation",
    "design_reason",
)

RATIONALE_FIELD_LABELS = {
    "heritage_knowledge": "你从文物中学到了什么",
    "cultural_translation": "你怎样把它用到设计里",
    "design_reason": "为什么这样设计",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _is_v2(design_version: Optional[str]) -> bool:
    return design_version == CROSSOVER_V2_DESIGN_VERSION


async def latest_work(session: AsyncSession, round_id) -> Optional[WorkRevision]:
    result = await session.execute(
        select(WorkRevision)
        .where(WorkRevision.round_id == round_id)
        .order_by(WorkRevision.revision_no.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def save_work(
    session: AsyncSession,
    round_obj: Round,
    payload: WorkUpdate,
    source: str = "autosave",
    design_version: Optional[str] = None,
) -> Tuple[WorkRevision, bool]:
    if round_obj.finished_at:
        raise AppError(409, "round_finished", "This task is already finished.")
    if _aware(round_obj.deadline_at) <= _now():
        raise AppError(409, "round_expired", "The task time has ended.")

    v2 = _is_v2(design_version)
    if v2:
        structured: Dict[str, str] = {}
    else:
        raw_structured = (
            payload.structured_fields.model_dump()
            if isinstance(payload.structured_fields, StructuredFields)
            else dict(payload.structured_fields or {})
        )
        structured = {
            key: str(raw_structured.get(key, "") or "").strip()
            for key in T1_FIELD_KEYS
        }

    if v2:
        raw_rationale = (
            payload.rationale_fields.model_dump()
            if isinstance(payload.rationale_fields, RationaleFields)
            else dict(payload.rationale_fields or {})
        )
        rationale = {
            key: str(raw_rationale.get(key, "") or "").strip()
            for key in RATIONALE_FIELD_KEYS
        }
        open_statement = ""
    else:
        rationale = {}
        open_statement = (payload.open_statement or "").strip()

    result = await session.execute(
        select(Round)
        .where(Round.id == round_obj.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    locked = result.scalar_one()
    last = await latest_work(session, locked.id)
    values = {
        "product_name": (payload.product_name or "").strip(),
        "product_category": (payload.product_category or "").strip(),
        "target_audience": (payload.target_audience or "").strip(),
        "design_concept": (payload.design_concept or "").strip(),
        "structured_fields": structured,
        "rationale_fields": rationale,
        "open_statement": open_statement,
        "image_prompt": (payload.image_prompt or "").strip(),
    }
    if last is not None and all(getattr(last, key) == value for key, value in values.items()):
        return last, False

    revision_no = (last.revision_no if last else 0) + 1
    revision = WorkRevision(
        round_id=locked.id,
        revision_no=revision_no,
        source=source,
        **values,
    )
    session.add(revision)
    locked.current_work_revision = revision_no
    await session.flush()
    return revision, True


def work_payload(work: Optional[WorkRevision]) -> Dict[str, Any]:
    if work is None:
        return {
            "product_name": "",
            "product_category": "",
            "target_audience": "",
            "design_concept": "",
            "structured_fields": {key: "" for key in T1_FIELD_KEYS},
            "rationale_fields": {key: "" for key in RATIONALE_FIELD_KEYS},
            "open_statement": "",
            "image_prompt": "",
            "revision": 0,
            "updated_at": None,
        }
    structured = work.structured_fields or {}
    rationale = work.rationale_fields or {}
    return {
        "product_name": work.product_name,
        "product_category": work.product_category,
        "target_audience": work.target_audience,
        "design_concept": work.design_concept,
        "structured_fields": {
            key: str(structured.get(key, "") or "") for key in T1_FIELD_KEYS
        },
        "rationale_fields": {
            key: str(rationale.get(key, "") or "") for key in RATIONALE_FIELD_KEYS
        },
        "open_statement": work.open_statement,
        "image_prompt": work.image_prompt or "",
        "revision": work.revision_no,
        "updated_at": work.created_at.isoformat() if work.created_at else None,
    }


def work_form_for(
    round_no: int, condition: str, design_version: Optional[str] = None
) -> str:
    """Return the submission form for a round.

    Assessment V2 uses one three-part rationale for every condition and round.
    Crossover v1.0 binds the form to the AI condition (B = six-field, A = open).
    Historical v1.5 runs retain the original T1 structured / T2 open rule.
    """
    if _is_v2(design_version):
        return "rationale"
    from ..domain import CROSSOVER_V1_DESIGN_VERSION

    if design_version == CROSSOVER_V1_DESIGN_VERSION:
        return "structured" if condition == "B" else "open"
    return "structured" if round_no == 1 else "open"


def work_completion_issues(
    round_no: int,
    condition: str,
    work: Optional[WorkRevision],
    design_version: Optional[str] = None,
) -> list[str]:
    """Return the missing fields for a work submission."""

    if work is None:
        return ["work"]
    missing: list[str] = []
    if not (work.product_name or "").strip():
        missing.append("product_name")
    form = work_form_for(round_no, condition, design_version)
    if form == "rationale":
        if not (work.product_category or "").strip():
            missing.append("product_category")
        if not (work.target_audience or "").strip():
            missing.append("target_audience")
        rationale = work.rationale_fields or {}
        for key in RATIONALE_FIELD_KEYS:
            if not str(rationale.get(key, "") or "").strip():
                missing.append(f"rationale_fields.{key}")
    elif form == "structured":
        if not (work.product_category or "").strip():
            missing.append("product_category")
        if not (work.target_audience or "").strip():
            missing.append("target_audience")
        if not (work.design_concept or "").strip():
            missing.append("design_concept")
        structured = work.structured_fields or {}
        for key in T1_FIELD_KEYS:
            if not str(structured.get(key, "") or "").strip():
                missing.append(f"structured_fields.{key}")
    else:
        if not (work.open_statement or "").strip():
            missing.append("open_statement")
    return missing


def validate_work_for_finish(
    round_no: int,
    condition: str,
    work: Optional[WorkRevision],
    design_version: Optional[str] = None,
) -> None:
    """Enforce the minimum submitted record for the current form.

    Images are deliberately optional: a failed image provider must not block a
    text submission.
    """

    missing = work_completion_issues(round_no, condition, work, design_version)
    if work is None:
        raise AppError(
            422,
            "work_required",
            "Please save your product design before finishing this task.",
        )
    if missing:
        raise AppError(
            422,
            "work_incomplete",
            "Please complete the required product design fields before finishing.",
            {"missing": missing},
        )


def work_ai_context(
    work: Optional[WorkRevision], design_version: Optional[str] = None
) -> str:
    """Compact, student-authored context for the B-group design coach."""

    v2 = _is_v2(design_version)
    if work is None:
        if v2:
            return (
                "No student product design has been saved in this round yet. "
                "Do not pretend the student has already chosen a product, audience "
                "or completed the three-part statement."
            )
        return (
            "No student product design has been saved in this round yet. "
            "Do not pretend the student has already chosen cultural features or "
            "completed the six-field statement."
        )
    structured = work.structured_fields or {}
    rationale = work.rationale_fields or {}
    lines = [
        f"Product name: {work.product_name or '(empty)'}",
        f"Product category/use: {work.product_category or '(empty)'}",
        f"Target audience: {work.target_audience or '(empty)'}",
        f"Design concept draft: {work.design_concept or '(empty)'}",
    ]
    if v2:
        for key in RATIONALE_FIELD_KEYS:
            lines.append(
                f"{RATIONALE_FIELD_LABELS[key]}: {str(rationale.get(key, '') or '(empty)')}"
            )
    else:
        for key in T1_FIELD_KEYS:
            lines.append(f"{T1_FIELD_LABELS[key]}: {str(structured.get(key, '') or '(empty)')}")
        if work.open_statement:
            lines.append(f"Open statement draft: {work.open_statement}")
    if work.image_prompt:
        lines.append(f"Image prompt draft: {work.image_prompt}")
    return "\n".join(lines)
