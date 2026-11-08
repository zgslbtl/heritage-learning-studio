from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain import ASSESSMENT_KINDS
from ..errors import AppError
from ..models import InstrumentVersion
from ..schemas import InstrumentPayload, Question


async def create_instrument_version(
    session: AsyncSession,
    *,
    kind: str,
    payload: InstrumentPayload,
    is_demo: bool = False,
    object_code: Optional[str] = None,
    form_code: Optional[str] = None,
) -> InstrumentVersion:
    if kind not in ASSESSMENT_KINDS:
        raise AppError(404, "instrument_not_found", "Unknown assessment instrument.")
    if object_code is not None and object_code not in ("M", "T"):
        raise AppError(422, "invalid_field", "Invalid object code.")
    if form_code is not None and form_code not in ("A", "B"):
        raise AppError(422, "invalid_field", "Invalid form code.")
    await session.execute(
        select(InstrumentVersion)
        .where(InstrumentVersion.kind == kind)
        .order_by(InstrumentVersion.version.desc())
        .limit(1)
        .with_for_update()
    )
    current_max = (
        await session.execute(
            select(func.max(InstrumentVersion.version)).where(
                InstrumentVersion.kind == kind
            )
        )
    ).scalar_one()
    version_no = (current_max or 0) + 1
    schema_json = payload.model_dump()
    version = InstrumentVersion(
        kind=kind,
        object_code=object_code,
        form_code=form_code,
        version=version_no,
        title=payload.title,
        instructions=payload.instructions,
        schema_json=schema_json,
        is_demo=is_demo,
    )
    session.add(version)
    await session.flush()
    return version


def instrument_payload(version: InstrumentVersion) -> Dict[str, Any]:
    data = dict(version.schema_json or {})
    payload = {
        "id": str(version.id),
        "kind": version.kind,
        "version": version.version,
        "title": data.get("title", version.title),
        "instructions": data.get("instructions", ""),
        "questions": data.get("questions", []),
        "is_demo": version.is_demo,
    }
    # English reading aids are optional and never used for validation or scoring.
    if data.get("title_en"):
        payload["title_en"] = data["title_en"]
    if data.get("instructions_en"):
        payload["instructions_en"] = data["instructions_en"]
    return payload


def _value_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and not value:
        return True
    return False


def _question_map(payload: Dict[str, Any]) -> Dict[str, Question]:
    result: Dict[str, Question] = {}
    for raw in payload.get("questions", []):
        question = Question.model_validate(raw)
        result[question.id] = question
    return result


def validate_answers(
    payload: Dict[str, Any],
    answers: Dict[str, Any],
    require_complete: bool,
) -> Tuple[Dict[str, Any], List[str], List[Tuple[str, str]]]:
    questions = _question_map(payload)
    cleaned: Dict[str, Any] = {}
    missing: List[str] = []
    invalid: List[Tuple[str, str]] = []

    for key in answers:
        if key not in questions:
            invalid.append((str(key), "Unknown question"))
    if invalid:
        raise AppError(
            422,
            "invalid_answers",
            "Some answers do not match this instrument.",
            {"invalid": invalid},
        )

    for qid, question in questions.items():
        value = answers.get(qid)
        if _value_missing(value):
            if require_complete and question.required:
                missing.append(qid)
            continue

        if question.type == "single_choice":
            allowed = {option.value: option for option in question.options}
            if isinstance(value, dict):
                selected = value.get("value")
                option = allowed.get(str(selected)) if selected is not None else None
                other_text = value.get("text", "")
                if (
                    option is None
                    or not option.allow_text
                    or not isinstance(other_text, str)
                ):
                    invalid.append((qid, "Invalid choice"))
                    continue
                other_text = other_text.strip()
                if len(other_text) > 200:
                    invalid.append((qid, "Other text is too long"))
                    continue
                if require_complete and not other_text:
                    missing.append(qid)
                    continue
                cleaned[qid] = {"value": option.value, "text": other_text}
                continue
            if not isinstance(value, str) or value not in allowed:
                invalid.append((qid, "Invalid choice"))
                continue
            cleaned[qid] = value
        elif question.type == "multi_choice":
            allowed = {option.value for option in question.options}
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                invalid.append((qid, "Expected a list of choices"))
                continue
            unique_values = list(dict.fromkeys(value))
            if any(v not in allowed for v in unique_values):
                invalid.append((qid, "Invalid choice"))
                continue
            if question.required and require_complete and not unique_values:
                missing.append(qid)
            elif unique_values:
                cleaned[qid] = unique_values
        elif question.type == "short_text":
            if not isinstance(value, str):
                invalid.append((qid, "Expected text"))
                continue
            text_value = value.strip()
            max_length = question.max_length or 200
            if len(text_value) > max_length:
                invalid.append((qid, f"Maximum {max_length} characters"))
                continue
            cleaned[qid] = text_value
        elif question.type == "evidence_judgment":
            allowed_rows = {row.id for row in question.rows}
            if not isinstance(value, dict):
                invalid.append((qid, "Expected a row-to-judgement mapping"))
                continue
            row_answers: Dict[str, str] = {}
            for row_id, judgement in value.items():
                if row_id not in allowed_rows or judgement not in ("yes", "no"):
                    invalid.append((qid, "Invalid evidence judgement"))
                    break
                row_answers[row_id] = judgement
            else:
                if question.required and require_complete:
                    if set(row_answers) != allowed_rows:
                        missing.append(qid)
                        continue
                if row_answers:
                    cleaned[qid] = row_answers
        elif question.type == "likert":
            if isinstance(value, bool) or not isinstance(value, int):
                invalid.append((qid, "Expected a number"))
                continue
            low = question.scale_min or 1
            high = question.scale_max or 5
            if not (low <= value <= high):
                invalid.append((qid, f"Expected {low} to {high}"))
                continue
            cleaned[qid] = value
        else:
            invalid.append((qid, "Unsupported question type"))

    if invalid:
        raise AppError(
            422,
            "invalid_answers",
            "Some answers are invalid.",
            {"invalid": invalid},
        )
    if require_complete and missing:
        raise AppError(
            422,
            "answers_incomplete",
            "Please answer all required questions.",
            {"missing": missing},
        )
    return cleaned, missing, invalid


def admin_instrument(version: InstrumentVersion) -> Dict[str, Any]:
    payload = instrument_payload(version)
    payload.update(
        {
            "object_code": version.object_code,
            "form_code": version.form_code,
        }
    )
    return payload
