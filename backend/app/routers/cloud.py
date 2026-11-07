from __future__ import annotations

import asyncio
import uuid
import httpx
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from ..config import Settings
from ..dependencies import AdminContext, get_current_admin, get_session, get_settings
from ..errors import AppError
from ..models import RuntimeTask
from ..services.cloud_tasks import dispatch_task
from ..services.storage import Storage, UPLOAD_TYPES

router = APIRouter(prefix="/api/admin", tags=["admin-cloud"])


class UploadStart(BaseModel):
    size: int = Field(gt=0, le=12 * 1024 * 1024)
    mime: str = Field(max_length=100)


@router.get("/runtime")
async def runtime(admin: AdminContext = Depends(get_current_admin), settings: Settings = Depends(get_settings)):
    return {"deployment_mode": settings.deployment_mode, "direct_upload": settings.storage_backend == "blob",
            "async_export": settings.queue_backend == "vercel"}


@router.get("/provider-connectivity")
async def provider_connectivity(admin: AdminContext = Depends(get_current_admin),
                                settings: Settings = Depends(get_settings)):
    """Read-only transport diagnosis. Does not send a key or generate content."""
    results = {}
    for name, base in (("text", settings.text_model_base_url), ("image", settings.image_model_base_url)):
        if not base:
            results[name] = {"configured": False}
            continue
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(base.rstrip("/") + "/models")
            results[name] = {"reachable": True, "http_status": response.status_code}
        except httpx.HTTPError as exc:
            results[name] = {"reachable": False, "error_type": type(exc).__name__, "detail": str(exc)[:200]}
    return {"region": settings.vercel_region, "providers": results,
            "note": "Connectivity only; this does not establish working generation."}


@router.post("/uploads")
async def start_upload(payload: UploadStart, admin: AdminContext = Depends(get_current_admin),
                       db=Depends(get_session), settings: Settings = Depends(get_settings)):
    if settings.storage_backend != "blob":
        return {"direct_upload": False}
    if payload.mime not in UPLOAD_TYPES:
        raise AppError(422, "invalid_image_type", "Use a PNG, JPEG or WebP image.")
    task_id = uuid.uuid4()
    key = f"uploads/{task_id}/original"
    task = RuntimeTask(id=task_id, kind="upload", status="queued", dispatch_state="none",
                       payload={"key": key, "size": payload.size, "mime": payload.mime}, checkpoint={})
    signed_url = await asyncio.to_thread(Storage(settings).signed, key, "put", maximum=payload.size, mime=payload.mime)
    db.add(task)
    await db.commit()
    return {"direct_upload": True, "upload_id": str(task_id), "url": signed_url,
            "headers": {"x-api-version": "12", "x-content-type": payload.mime,
                        "Content-Type": payload.mime, "x-vercel-blob-access": "private"}}


async def read_upload(db, settings, upload_id):
    try:
        task_id = uuid.UUID(upload_id)
    except ValueError:
        raise AppError(422, "invalid_upload", "Invalid upload.")
    task = await db.get(RuntimeTask, task_id, with_for_update=True)
    if not task or task.kind != "upload" or task.status != "queued":
        raise AppError(422, "invalid_upload", "Upload is unavailable or already used.")
    created = task.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if created + timedelta(minutes=15) < datetime.now(timezone.utc):
        raise AppError(422, "upload_expired", "Upload expired; select the image again.")
    body = await asyncio.to_thread(Storage(settings).read_bytes, task.payload["key"], maximum=12 * 1024 * 1024)
    if len(body) != task.payload["size"]:
        raise AppError(422, "upload_size_mismatch", "The uploaded image is incomplete.")
    task.status = "succeeded"
    return body


@router.post("/export-tasks")
async def start_export(admin: AdminContext = Depends(get_current_admin), db=Depends(get_session),
                       settings: Settings = Depends(get_settings)):
    if settings.queue_backend != "vercel":
        return {"status": "succeeded", "download_url": "/api/admin/export"}
    await db.execute(text("SELECT pg_advisory_xact_lock(7819014)"))
    task = (await db.execute(select(RuntimeTask).where(
        RuntimeTask.kind == "export", RuntimeTask.status.in_(["queued", "running"]),
    ).order_by(RuntimeTask.created_at.desc()).limit(1))).scalar_one_or_none()
    if not task:
        task = RuntimeTask(kind="export", status="queued", dispatch_state="pending",
                           payload={"deployment_mode": settings.deployment_mode}, checkpoint={})
        db.add(task)
        await db.flush()
    await db.commit()
    await dispatch_task(db, settings, task.id)
    return {"id": str(task.id), "status": task.status}


@router.get("/export-tasks/{task_id}")
async def export_status(task_id: uuid.UUID, admin: AdminContext = Depends(get_current_admin),
                        db=Depends(get_session), settings: Settings = Depends(get_settings)):
    task = await db.get(RuntimeTask, task_id)
    if not task or task.kind != "export":
        raise AppError(404, "export_not_found", "Export not found.")
    await dispatch_task(db, settings, task.id)
    await db.refresh(task)
    return {"id": str(task.id), "status": task.status, "error_code": task.error_code,
            "download_url": f"/api/admin/export-tasks/{task.id}/download" if task.status == "succeeded" else None,
            "deployment_mode": task.payload.get("deployment_mode")}


@router.get("/export-tasks/{task_id}/download")
async def download_export(task_id: uuid.UUID, admin: AdminContext = Depends(get_current_admin),
                          db=Depends(get_session), settings: Settings = Depends(get_settings)):
    task = await db.get(RuntimeTask, task_id)
    if not task or task.kind != "export" or task.status != "succeeded" or not task.file_key:
        raise AppError(404, "export_not_ready", "Export not ready.")
    return await asyncio.to_thread(Storage(settings).response, task.file_key, "application/zip",
                                   f"heritage-beta-{task.id}.zip", download=True)
