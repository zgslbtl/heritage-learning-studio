from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..dependencies import (
    ADMIN_COOKIE,
    STUDENT_COOKIE,
    clear_session_cookie,
    get_session,
    get_settings,
    set_session_cookie,
    get_current_admin,
)
from ..errors import AppError
from ..models import AuthSession, ClassEntryLink, ClassGroup, ClassPeerGate, Participant
from ..schemas import AdminLoginRequest, EnterRequest
from ..security import (
    code_hmac,
    is_valid_code_shape,
    new_opaque_token,
    normalize_code,
    passwords_equal,
    token_hash,
)
from ..services.assignment import group_for_index
from ..services.coordination import allow_login
from ..services.run_state import create_or_resume_run, student_state

router = APIRouter(prefix="/api/auth", tags=["auth"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin-auth"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/config")
async def entry_config(settings: Settings = Depends(get_settings)):
    class_ids = settings.enabled_class_ids
    return {
        "deployment_mode": settings.deployment_mode,
        "classes": [
            {"id": class_id, "name": "班级 0 / 内部测试" if class_id == 0 else f"班级 {class_id} / Class {class_id}"}
            for class_id in class_ids
        ],
        "login_rule": "contains_polyu",
    }


@router.get("/class-link")
async def resolve_class_link(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Resolve a class-specific entry link. The raw token is never stored."""

    allowed, retry_after = await allow_login(db,
        f"class-link:{_client_ip(request)}", limit=120, window_seconds=600
    )
    if not allowed:
        raise AppError(
            429,
            "too_many_attempts",
            "Too many link checks. Please wait and try again.",
            {"retry_after_seconds": retry_after},
        )
    result = await db.execute(
        select(ClassEntryLink).where(
            ClassEntryLink.token_hash == token_hash(token),
            ClassEntryLink.active.is_(True),
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise AppError(401, "invalid_class_link", "This class link is invalid or has been revoked.")
    class_group = await db.get(ClassGroup, link.class_id)
    if not class_group or not settings.class_allowed(class_group.id):
        raise AppError(401, "invalid_class_link", "This class link is invalid.")
    return {
        "class_id": class_group.id,
        "class_name": class_group.name,
        "label": link.label,
    }


@router.post("/enter")
async def enter_study(
    payload: EnterRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    allowed, retry_after = await allow_login(db,
        f"enter:{_client_ip(request)}", limit=200, window_seconds=600
    )
    if not allowed:
        raise AppError(
            429,
            "too_many_attempts",
            "Too many access attempts. Please wait and try again.",
            {"retry_after_seconds": retry_after},
        )
    if not settings.class_allowed(payload.class_id):
        raise AppError(401, "invalid_access", "The class or sign-in details are not valid.")
    if payload.class_token:
        link_result = await db.execute(
            select(ClassEntryLink).where(
                ClassEntryLink.token_hash == token_hash(payload.class_token),
                ClassEntryLink.active.is_(True),
            )
        )
        link = link_result.scalar_one_or_none()
        if not link or link.class_id != payload.class_id:
            raise AppError(401, "invalid_class_link", "This class link is invalid or already closed.")
    class_group = await db.get(ClassGroup, payload.class_id)
    if not class_group:
        raise AppError(401, "invalid_access", "The class or sign-in details are not valid.")

    if payload.email:
        normalized_email = payload.email.strip().lower()
        if "polyu" not in normalized_email:
            raise AppError(
                403,
                "polyu_email_required",
                "Please use a PolyU email address containing 'polyu'.",
            )
        # Serialize new-user allocation per class. This also prevents two
        # concurrent registrations from receiving the same block position.
        locked_class = await db.execute(
            select(ClassGroup)
            .where(ClassGroup.id == payload.class_id)
            .with_for_update()
        )
        if locked_class.scalar_one_or_none() is None:
            raise AppError(401, "invalid_access", "The class or sign-in details are not valid.")
        existing_result = await db.execute(
            select(Participant).where(Participant.email == normalized_email)
        )
        participant = existing_result.scalar_one_or_none()
        if participant:
            if participant.class_id != payload.class_id:
                raise AppError(
                    409,
                    "email_class_mismatch",
                    "This email is already registered in another class. Select the original class.",
                )
        else:
            gate = await db.get(ClassPeerGate, payload.class_id)
            if gate is not None and gate.status == "open" and payload.class_id != 0:
                raise AppError(
                    409,
                    "class_closed",
                    "This class has already started peer assessment and cannot accept a new participant.",
                )
            alias_count = (
                await db.execute(
                    select(func.count())
                    .select_from(Participant)
                    .where(
                        Participant.class_id == payload.class_id,
                        Participant.email.is_not(None),
                    )
                )
            ).scalar_one()
            if (
                payload.class_id != 0
                and alias_count >= settings.participants_per_class
            ):
                raise AppError(
                    409,
                    "class_full",
                    "This class has reached its participant limit.",
                )
            group = group_for_index(
                settings.anon_code_pepper,
                payload.class_id,
                alias_count,
                settings.participants_per_class,
            )
            participant = Participant(
                class_id=payload.class_id,
                group_name=group,
                email=normalized_email,
            )
            db.add(participant)
            try:
                await db.flush()
            except IntegrityError:
                await db.rollback()
                raise AppError(
                    409,
                    "email_already_registered",
                    "This email was just registered. Please sign in again.",
                )
    else:
        normalized = normalize_code(payload.code or "")
        if not is_valid_code_shape(normalized):
            raise AppError(
                401,
                "invalid_access",
                "The access code or class is not valid.",
            )
        result = await db.execute(
            select(Participant).where(
                Participant.access_code_hmac
                == code_hmac(normalized, settings.anon_code_pepper),
                Participant.class_id == payload.class_id,
            )
        )
        participant = result.scalar_one_or_none()
        if not participant:
            raise AppError(401, "invalid_access", "The access code or class is not valid.")

    run = await create_or_resume_run(
        session=db, participant=participant, settings=settings
    )
    raw_token = new_opaque_token()
    expires = _now() + timedelta(hours=settings.session_ttl_hours)
    auth = AuthSession(
        token_hash=token_hash(raw_token),
        role="student",
        participant_id=participant.id,
        expires_at=expires,
    )
    db.add(auth)
    await db.commit()
    state = await student_state(db, run, participant)
    response = JSONResponse({"state": state})
    set_session_cookie(
        response,
        STUDENT_COOKIE,
        raw_token,
        max_age_seconds=settings.session_ttl_hours * 3600,
        secure=settings.cookie_secure,
    )
    return response


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    raw = request.cookies.get(STUDENT_COOKIE)
    if raw:
        result = await db.execute(
            select(AuthSession).where(
                AuthSession.token_hash == token_hash(raw), AuthSession.role == "student"
            )
        )
        auth = result.scalar_one_or_none()
        if auth:
            auth.revoked_at = _now()
            await db.commit()
    response = JSONResponse({"ok": True})
    clear_session_cookie(response, STUDENT_COOKIE)
    return response


@admin_router.post("/login")
async def admin_login(
    payload: AdminLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    allowed, retry_after = await allow_login(db,
        f"admin:{_client_ip(request)}", limit=6, window_seconds=600
    )
    if not allowed:
        raise AppError(
            429,
            "too_many_attempts",
            "Too many login attempts. Please wait and try again.",
            {"retry_after_seconds": retry_after},
        )
    if not settings.admin_password:
        raise AppError(
            503,
            "admin_not_configured",
            "Researcher login is not configured on this server.",
        )
    if not passwords_equal(payload.password, settings.admin_password):
        raise AppError(401, "admin_invalid", "Incorrect researcher password.")
    raw_token = new_opaque_token()
    auth = AuthSession(
        token_hash=token_hash(raw_token),
        role="admin",
        expires_at=_now() + timedelta(hours=settings.admin_session_hours),
    )
    db.add(auth)
    await db.commit()
    response = JSONResponse({"ok": True})
    set_session_cookie(
        response,
        ADMIN_COOKIE,
        raw_token,
        max_age_seconds=settings.admin_session_hours * 3600,
        secure=settings.cookie_secure,
    )
    return response


@admin_router.post("/logout")
async def admin_logout(
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    raw = request.cookies.get(ADMIN_COOKIE)
    if raw:
        result = await db.execute(
            select(AuthSession).where(
                AuthSession.token_hash == token_hash(raw), AuthSession.role == "admin"
            )
        )
        auth = result.scalar_one_or_none()
        if auth:
            auth.revoked_at = _now()
            await db.commit()
    response = JSONResponse({"ok": True})
    clear_session_cookie(response, ADMIN_COOKIE)
    return response


@admin_router.get("/session")
async def admin_session_status(
    admin=Depends(get_current_admin),
):
    return {"authenticated": True}
