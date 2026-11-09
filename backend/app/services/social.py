from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AppError
from ..models import (
    Participant,
    Round,
    Run,
    SocialComment,
    SocialEvent,
    SocialLike,
    SocialView,
    WorkRevision,
)
from .peer import eligible_works, work_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _feed_order(run_id, work_id: int) -> str:
    return hashlib.sha256(f"feed:{run_id}:{work_id}".encode("utf-8")).hexdigest()


async def _load_work_in_class(
    session: AsyncSession, work_id: int, class_id: int
) -> tuple[WorkRevision, Run]:
    result = await session.execute(
        select(WorkRevision, Run)
        .join(Round, Round.id == WorkRevision.round_id)
        .join(Run, Run.id == Round.run_id)
        .join(Participant, Participant.id == Run.participant_id)
        .where(WorkRevision.id == work_id, Participant.class_id == class_id)
    )
    row = result.first()
    if not row:
        raise AppError(404, "work_not_found", "Work not found.")
    return row[0], row[1]


async def feed_payload(
    session: AsyncSession, run: Run, participant: Participant
) -> Dict[str, Any]:
    # The work feed shows both creation rounds.  Peer review has its own
    # two-round pool; this call only changes the simulated social feed.
    works = await eligible_works(session, participant.class_id, (1, 2))
    works.sort(key=lambda item: _feed_order(run.id, item["work"].id))
    likes_result = await session.execute(
        select(SocialLike).where(
            SocialLike.run_id == run.id,
            SocialLike.work_id.in_([item["work"].id for item in works]),
        )
    )
    likes = {like.work_id: like for like in likes_result.scalars().all()}
    items = []
    for item in works:
        work = item["work"]
        own = item["participant"].id == participant.id
        items.append(
            {
                "work_id": work.id,
                "work_code": work_code(work.id),
                "round_no": item["round_no"],
                "product_name": work.product_name,
                "product_category": work.product_category,
                "design_concept": work.design_concept,
                "rationale_fields": work.rationale_fields or {},
                "open_statement": work.open_statement,
                "image_url": item["image_url"],
                "is_own": own,
                "liked_by_me": bool(likes.get(work.id) and likes[work.id].active),
            }
        )
    return {"works": items, "count": len(items)}


async def record_view(
    session: AsyncSession, run: Run, participant: Participant, work_id: int
) -> None:
    await _load_work_in_class(session, work_id, participant.class_id)
    session.add(SocialView(run_id=run.id, work_id=work_id, created_at=_now()))
    session.add(
        SocialEvent(
            run_id=run.id,
            work_id=work_id,
            event_type="view",
            meta_json={},
            created_at=_now(),
        )
    )
    await session.flush()


async def toggle_like(
    session: AsyncSession, run: Run, participant: Participant, work_id: int
) -> Dict[str, Any]:
    work, owner_run = await _load_work_in_class(session, work_id, participant.class_id)
    if owner_run.participant_id == participant.id:
        raise AppError(403, "own_work_interaction", "You cannot like your own work.")
    result = await session.execute(
        select(SocialLike).where(
            SocialLike.run_id == run.id, SocialLike.work_id == work.id
        )
    )
    like = result.scalar_one_or_none()
    if like is None:
        like = SocialLike(
            run_id=run.id,
            work_id=work.id,
            active=True,
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(like)
        action = "like"
    else:
        like.active = not like.active
        like.updated_at = _now()
        action = "like" if like.active else "unlike"
    session.add(
        SocialEvent(
            run_id=run.id,
            work_id=work.id,
            event_type=action,
            meta_json={"active": like.active},
            created_at=_now(),
        )
    )
    await session.flush()
    return {"work_id": work.id, "liked": like.active}


async def add_comment(
    session: AsyncSession,
    run: Run,
    participant: Participant,
    work_id: int,
    content: str,
) -> SocialComment:
    work, owner_run = await _load_work_in_class(session, work_id, participant.class_id)
    if owner_run.participant_id == participant.id:
        raise AppError(403, "own_work_interaction", "You cannot comment on your own work.")
    value = (content or "").strip()
    if not value:
        raise AppError(422, "comment_required", "Comment cannot be empty.")
    comment = SocialComment(
        run_id=run.id,
        work_id=work.id,
        content=value[:600],
        hidden=False,
        created_at=_now(),
    )
    session.add(comment)
    await session.flush()
    session.add(
        SocialEvent(
            run_id=run.id,
            work_id=work.id,
            event_type="comment",
            meta_json={"comment_id": comment.id},
            created_at=_now(),
        )
    )
    await session.flush()
    return comment


async def hide_comment(session: AsyncSession, comment_id: int) -> SocialComment:
    comment = await session.get(SocialComment, comment_id)
    if not comment:
        raise AppError(404, "comment_not_found", "Comment not found.")
    comment.hidden = True
    await session.flush()
    return comment
