from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AppError
from ..models import Round, ScriptRevision
from .run_state import aware


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def save_script(
    session: AsyncSession,
    round_obj: Round,
    title: str,
    body: str,
    source: str = "autosave",
) -> Tuple[Optional[ScriptRevision], bool]:
    if round_obj.finished_at:
        raise AppError(409, "round_finished", "This task is already finished.")
    if aware(round_obj.deadline_at) <= _now():
        raise AppError(409, "round_expired", "The task time has ended.")
    title = (title or "").strip()
    body = body or ""
    if len(title) > 200 or len(body) > 10000:
        raise AppError(422, "script_too_long", "The script exceeds the allowed length.")
    result = await session.execute(
        select(Round)
        .where(Round.id == round_obj.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    locked = result.scalar_one()
    last_result = await session.execute(
        select(ScriptRevision)
        .where(ScriptRevision.round_id == locked.id)
        .order_by(ScriptRevision.revision_no.desc())
        .limit(1)
    )
    latest = last_result.scalar_one_or_none()
    if latest and latest.title == title and latest.body == body:
        return latest, False
    revision_no = (latest.revision_no if latest else 0) + 1
    revision = ScriptRevision(
        round_id=locked.id,
        revision_no=revision_no,
        title=title,
        body=body,
        source=source,
    )
    session.add(revision)
    locked.current_script_revision = revision_no
    await session.flush()
    return revision, True
