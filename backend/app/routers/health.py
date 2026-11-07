from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..services.storage import Storage
from ..dependencies import get_session, get_settings

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/live")
async def live():
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    database_ok = False
    database_error = None
    try:
        await db.execute(text("SELECT 1"))
        database_ok = True
    except Exception as exc:
        database_error = type(exc).__name__
    storage_ok = await asyncio.to_thread(Storage(settings).ready)
    body = {
        "status": "ok" if database_ok and storage_ok else "degraded",
        "database": database_ok,
        "database_error": database_error,
        "storage": storage_ok,
        "text_model_configured": settings.text_configured,
        "image_model_configured": settings.image_configured,
        "auth_mode": settings.auth_mode,
        "environment": settings.environment,
        "deployment_mode": settings.deployment_mode,
        "storage_backend": settings.storage_backend,
        "queue_backend": settings.queue_backend,
    }
    return JSONResponse(body, status_code=200 if database_ok and storage_ok else 503)
