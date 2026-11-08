from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain import HLSF_ORDER, Condition
from ..errors import AppError
from ..models import HLSFEvent, HLSFState, Message, Round
from ..prompts.hlsf import (
    PHASE_LABELS,
    hlsf_version_for_design,
    phase_coaching,
    phase_hint,
    phase_prompt,
)


def _version(design_version: Optional[str], prompt_version: Optional[str]) -> str:
    return prompt_version or hlsf_version_for_design(design_version)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_hlsf_round(round_obj: Round) -> bool:
    return round_obj.condition == Condition.B.value


def guide_payload(
    state: Optional[HLSFState],
    round_obj: Round,
    design_version: Optional[str] = None,
    prompt_version: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not _is_hlsf_round(round_obj):
        return None
    if not state:
        return None
    return {
        "version": _version(design_version, prompt_version),
        "phase": state.phase,
        "hint_used": state.hint_used,
        "completed_at": state.completed_at.isoformat()
        if state.completed_at
        else None,
        "phases": [
            {
                "id": phase,
                "label_zh": PHASE_LABELS[phase]["zh"],
                "label_en": PHASE_LABELS[phase]["en"],
            }
            for phase in HLSF_ORDER
        ],
    }


async def start_guide(
    session: AsyncSession,
    round_obj: Round,
    design_version: Optional[str] = None,
    prompt_version: Optional[str] = None,
) -> Optional[HLSFState]:
    if not _is_hlsf_round(round_obj):
        return None
    state = HLSFState(round_id=round_obj.id, phase=HLSF_ORDER[0], hint_used=False)
    session.add(state)
    message = Message(
        round_id=round_obj.id,
        role="assistant",
        source="hlsf_prompt",
        content=phase_prompt(
            round_obj.round_no, HLSF_ORDER[0], design_version, prompt_version
        ),
    )
    session.add(message)
    await session.flush()
    session.add(
        HLSFEvent(
            round_id=round_obj.id,
            phase=HLSF_ORDER[0],
            action="prompt_delivered",
            message_id=message.id,
            meta_json={"prompt_version": _version(design_version, prompt_version)},
        )
    )
    await session.flush()
    return state


async def load_state(session: AsyncSession, round_id) -> Optional[HLSFState]:
    return await session.get(HLSFState, round_id)


async def advance_guide(
    session: AsyncSession,
    round_obj: Round,
    from_phase: str,
    skip: bool,
    design_version: Optional[str] = None,
    prompt_version: Optional[str] = None,
) -> tuple[HLSFState, list[Message]]:
    if not _is_hlsf_round(round_obj):
        raise AppError(404, "not_found", "Not found.")
    state = await session.get(HLSFState, round_obj.id, with_for_update=True)
    if not state:
        raise AppError(409, "guide_not_started", "The learning guide has not started.")
    if state.phase != from_phase:
        raise AppError(
            409,
            "guide_phase_changed",
            "The learning guide has already advanced.",
            {"current_phase": state.phase},
        )
    if state.phase == "complete":
        raise AppError(409, "guide_complete", "The learning guide is already complete.")

    phase_index = HLSF_ORDER.index(state.phase)
    session.add(
        HLSFEvent(
            round_id=round_obj.id,
            phase=state.phase,
            action="skipped" if skip else "advanced",
            meta_json={"prompt_version": _version(design_version, prompt_version)},
        )
    )
    new_messages: list[Message] = []
    if phase_index == len(HLSF_ORDER) - 1:
        state.phase = "complete"
        state.completed_at = _now()
        state.updated_at = _now()
        state.hint_used = False
        session.add(
            HLSFEvent(
                round_id=round_obj.id,
                phase="complete",
                action="guide_completed",
                meta_json={"prompt_version": _version(design_version, prompt_version)},
            )
        )
    else:
        next_phase = HLSF_ORDER[phase_index + 1]
        state.phase = next_phase
        state.hint_used = False
        state.updated_at = _now()
        message = Message(
            round_id=round_obj.id,
            role="assistant",
            source="hlsf_prompt",
            content=phase_prompt(
                round_obj.round_no, next_phase, design_version, prompt_version
            ),
        )
        session.add(message)
        await session.flush()
        new_messages.append(message)
        session.add(
            HLSFEvent(
                round_id=round_obj.id,
                phase=next_phase,
                action="prompt_delivered",
                message_id=message.id,
                meta_json={"prompt_version": _version(design_version, prompt_version)},
            )
        )
    await session.flush()
    return state, new_messages


async def deliver_hint(
    session: AsyncSession,
    round_obj: Round,
    phase: str,
    design_version: Optional[str] = None,
    prompt_version: Optional[str] = None,
) -> tuple[HLSFState, Message]:
    if not _is_hlsf_round(round_obj):
        raise AppError(404, "not_found", "Not found.")
    state = await session.get(HLSFState, round_obj.id, with_for_update=True)
    if not state:
        raise AppError(409, "guide_not_started", "The learning guide has not started.")
    if state.phase != phase or state.phase == "complete":
        raise AppError(
            409,
            "guide_phase_changed",
            "This guide phase is no longer active.",
            {"current_phase": state.phase},
        )
    if state.hint_used:
        raise AppError(
            409,
            "hint_already_used",
            "A hint has already been delivered for this phase.",
        )
    message = Message(
        round_id=round_obj.id,
        role="assistant",
        source="hlsf_hint",
        content=phase_hint(round_obj.round_no, phase, design_version, prompt_version),
    )
    session.add(message)
    state.hint_used = True
    state.updated_at = _now()
    await session.flush()
    session.add(
        HLSFEvent(
            round_id=round_obj.id,
            phase=phase,
            action="hint_delivered",
            message_id=message.id,
            meta_json={"prompt_version": _version(design_version, prompt_version)},
        )
    )
    await session.flush()
    return state, message
