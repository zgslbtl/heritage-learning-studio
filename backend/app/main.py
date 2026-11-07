from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from sqlalchemy import text
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .bootstrap import bootstrap_cohort
from .config import Settings
from .db import Database
from .errors import error_payload, install_error_handlers
from .routers import admin, auth, cloud, files, health, student
from .services.image_queue import ImageWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("hls")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or Settings()
    if settings.is_production:
        if len(settings.admin_password) < 16:
            raise RuntimeError("Production requires ADMIN_PASSWORD with at least 16 characters")
        if len(settings.anon_code_pepper) < 16:
            raise RuntimeError(
                "Production requires ANON_CODE_PEPPER with at least 16 characters"
            )
        if not settings.cookie_secure:
            raise RuntimeError("Production requires COOKIE_SECURE=true")
        if not settings.public_origin or not settings.public_origin.startswith("https://"):
            raise RuntimeError("Production requires an https PUBLIC_ORIGIN")
    db = Database(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        null_pool=settings.db_null_pool,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.ensure_directories()
        async with db.session_factory() as session:
            await session.execute(text("SELECT 1"))
        if settings.auto_bootstrap and settings.queue_backend != "vercel":
            async with db.session_factory() as session:
                await bootstrap_cohort(session, settings)
        worker = ImageWorker(settings, db)
        app.state.image_worker = worker
        if settings.queue_backend != "vercel":
            await worker.start()
        logger.info(
            "Heritage Learning Studio started environment=%s site=%s",
            settings.environment,
            settings.site_address,
        )
        try:
            yield
        finally:
            await worker.stop()
            await db.dispose()

    app = FastAPI(
        title="Heritage Learning Studio",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/api/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/api/openapi.json",
    )
    app.state.settings = settings
    app.state.db = db

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and settings.allowed_origins:
                normalized = origin.rstrip("/")
                if normalized not in settings.allowed_origins:
                    response = JSONResponse(
                        status_code=403,
                        content=error_payload(
                            "origin_rejected",
                            "This request origin is not allowed.",
                            request_id,
                        ),
                    )
                    response.headers["X-Request-ID"] = request_id
                    return response
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled request failure request_id=%s", request_id)
            raise
        response.headers["X-Request-ID"] = request_id
        return response

    app.add_middleware(SecurityHeadersMiddleware)
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(auth.admin_router)
    app.include_router(student.router)
    app.include_router(admin.router)
    app.include_router(cloud.router)
    app.include_router(files.router)
    return app


app = create_app()
