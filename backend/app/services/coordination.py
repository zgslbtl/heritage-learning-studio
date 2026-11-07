"""PostgreSQL coordination shared by all serverless instances."""
from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from ..errors import AppError
from ..models import RateLimitBucket


async def allow_login(session, key: str, limit: int, window_seconds: int):
    now = datetime.now(timezone.utc)
    digest = hashlib.sha256(key.encode()).hexdigest()
    await session.execute(insert(RateLimitBucket).values(
        key=digest, window_start=now, count=0,
    ).on_conflict_do_nothing(index_elements=["key"]))
    bucket = (await session.execute(select(RateLimitBucket).where(
        RateLimitBucket.key == digest,
    ).with_for_update())).scalar_one()
    start = bucket.window_start
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    remaining = (start + timedelta(seconds=window_seconds) - now).total_seconds()
    if remaining <= 0:
        bucket.window_start, bucket.count = now, 0
        remaining = window_seconds
    allowed = bucket.count < limit
    if allowed:
        bucket.count += 1
    # Login failures must not roll back the limit counter.
    await session.commit()
    return allowed, 0 if allowed else max(1, int(remaining))


@asynccontextmanager
async def chat_lock(database, round_id):
    # Keep a row lock on a separate transaction while chat code commits replies.
    async with database.session_factory() as lock_session:
        await lock_session.execute(text("SET LOCAL lock_timeout = '2s'"))
        from ..models import RuntimeTask
        lock_id = hashlib.sha256(f"chat:{round_id}".encode()).hexdigest()[:32]
        import uuid
        task_id = uuid.UUID(hex=lock_id)
        await lock_session.execute(insert(RuntimeTask).values(
            id=task_id, kind="chat_lock", status="lock", dispatch_state="none",
            payload={}, checkpoint={}, created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ).on_conflict_do_nothing(index_elements=["id"]))
        await lock_session.commit()
        try:
            await lock_session.execute(select(RuntimeTask.id).where(
                RuntimeTask.id == task_id,
            ).with_for_update(nowait=True))
        except Exception:
            await lock_session.rollback()
            raise AppError(409, "chat_busy", "An AI reply is already in progress. Please wait.")
        try:
            yield
        finally:
            await lock_session.rollback()
