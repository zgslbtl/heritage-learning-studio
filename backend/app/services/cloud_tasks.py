"""Transactional outbox and bounded, restart-safe Vercel task execution."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, text

from ..config import Settings
from ..db import Database
from ..models import ImageJob, RuntimeTask

logger = logging.getLogger("hls.cloud")
TOPIC = "heritage-beta-tasks"


def now():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


async def dispatch_task(session, settings, task_id):
    if settings.queue_backend != "vercel":
        return
    task = (await session.execute(select(RuntimeTask).where(
        RuntimeTask.id == task_id,
    ).with_for_update())).scalar_one_or_none()
    if not task or task.status in ("succeeded", "failed"):
        await session.commit()
        return
    if task.status == "running" and task.lease_until and aware(task.lease_until) < now():
        task.dispatch_state = "pending"
        task.checkpoint = {**task.checkpoint, "recovery": int(task.checkpoint.get("recovery", 0)) + 1}
    if task.status == "queued" and task.dispatch_state == "sent" and (
        (os.getenv("VERCEL_DEPLOYMENT_ID") and task.checkpoint.get("deployment_id") != os.getenv("VERCEL_DEPLOYMENT_ID"))
        or (now() - aware(task.updated_at)).total_seconds() > 300
    ):
        task.dispatch_state = "pending"
        task.checkpoint = {**task.checkpoint, "recovery": int(task.checkpoint.get("recovery", 0)) + 1}
    if task.dispatch_state == "sent":
        await session.commit()
        return
    try:
        from vercel.queue import QueueClient
        client = QueueClient(region=settings.vercel_region, timeout=10)
        await client.send(TOPIC, {"task_id": str(task.id)},
                          idempotency_key=f"{task.id}:{task.checkpoint.get('recovery', 0)}")
        task.dispatch_state = "sent"
        task.checkpoint = {**task.checkpoint, "deployment_id": os.getenv("VERCEL_DEPLOYMENT_ID")}
        task.error_code = None
    except Exception as exc:
        task.dispatch_state = "pending"
        task.error_code = "queue_dispatch_failed"
        logger.warning("Task dispatch failed task=%s type=%s", task.id, type(exc).__name__)
    task.updated_at = now()
    await session.commit()


async def execute_task(task_id, settings=None, database=None):
    settings = settings or Settings()
    owned = database is None
    db = database or Database(settings.database_url, pool_size=2, max_overflow=0, null_pool=settings.db_null_pool)
    task_id = uuid.UUID(str(task_id))
    try:
        async with db.session_factory() as session:
            # Enforce the image cap across instances and overlapping deployments.
            await session.execute(text("SELECT pg_advisory_xact_lock(7819015)"))
            task = await session.get(RuntimeTask, task_id, with_for_update=True)
            if not task or task.kind not in ("image", "export") or task.status in ("succeeded", "failed"):
                return
            if task.status == "running" and task.lease_until and aware(task.lease_until) > now():
                from vercel.queue import RetryAfter
                raise RetryAfter(30)
            if task.kind == "image":
                active = (await session.execute(select(func.count()).select_from(RuntimeTask).where(
                    RuntimeTask.kind == "image", RuntimeTask.status == "running",
                    RuntimeTask.lease_until > now(), RuntimeTask.id != task_id,
                ))).scalar_one()
                if active >= settings.image_max_concurrency:
                    from vercel.queue import RetryAfter
                    raise RetryAfter(30)
            task.status = "running"
            task.lease_until = now() + timedelta(seconds=290)
            task.updated_at = now()
            kind = task.kind
            if kind == "image":
                image = await session.get(ImageJob, task.id, with_for_update=True)
                if not image:
                    task.status, task.error_code = "failed", "image_job_missing"
                    await session.commit()
                    return
                if image.status == "succeeded":
                    task.status = "succeeded"
                    await session.commit()
                    return
                image.status = "running"
                image.started_at = image.started_at or now()
                image.attempts = max(1, image.attempts)
            await session.commit()
        try:
            async with asyncio.timeout(270):
                if kind == "image":
                    from .image_queue import ImageWorker
                    await ImageWorker(settings, db)._process_job(task_id)
                    async with db.session_factory() as session:
                        image = await session.get(ImageJob, task_id)
                        task = await session.get(RuntimeTask, task_id, with_for_update=True)
                        task.status = "succeeded" if image.status == "succeeded" else "failed"
                        task.error_code = image.error_code
                        task.file_key = image.file_path
                        task.updated_at = now()
                        task.lease_until = None
                        await session.commit()
                else:
                    from .export import build_export
                    from .storage import Storage
                    async with db.session_factory() as session:
                        path, manifest = await build_export(session, settings)
                    try:
                        key = f"exports/{task_id}.zip"
                        await asyncio.to_thread(Storage(settings).put_file, key, path, "application/zip", overwrite=True)
                        async with db.session_factory() as session:
                            task = await session.get(RuntimeTask, task_id, with_for_update=True)
                            task.status, task.file_key = "succeeded", key
                            task.checkpoint = {"manifest": manifest}
                            task.updated_at, task.lease_until = now(), None
                            await session.commit()
                    finally:
                        path.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Cloud task failed task=%s type=%s", task_id, type(exc).__name__)
            async with db.session_factory() as session:
                task = await session.get(RuntimeTask, task_id, with_for_update=True)
                task.status = "failed"
                task.error_code = "task_timeout" if isinstance(exc, TimeoutError) else "task_failed"
                task.updated_at, task.lease_until = now(), None
                if kind == "image":
                    image = await session.get(ImageJob, task_id)
                    if image and image.status != "succeeded":
                        image.status, image.error_code = "failed", task.error_code
                        image.error_message = "The cloud task stopped. Retry manually to start a new attempt."
                        image.finished_at = now()
                await session.commit()
    finally:
        if owned:
            await db.dispose()
