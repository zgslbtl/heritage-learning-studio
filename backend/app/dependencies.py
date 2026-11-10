from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from fastapi import Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings
from .db import Database
from .errors import AppError
from .models import AuthSession, Participant, ClassGroup, Run
from .security import token_hash

STUDENT_COOKIE = "hls_student"
ADMIN_COOKIE = "hls_admin"


@dataclass
class StudentContext:
    auth: AuthSession
    participant: Participant


@dataclass
class AdminContext:
    auth: AuthSession


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> Database:
    return request.app.state.db


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    db: Database = request.app.state.db
    async with db.session_factory() as session:
        session.info["deployment_mode"] = request.app.state.settings.deployment_mode
        yield session
        if session.info.get("student_request"):
            await session.commit()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _load_session(
    db: AsyncSession, raw_token: Optional[str], role: str
) -> Optional[AuthSession]:
    if not raw_token:
        return None
    result = await db.execute(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash(raw_token),
            AuthSession.role == role,
            AuthSession.revoked_at.is_(None),
        )
    )
    auth = result.scalar_one_or_none()
    if not auth:
        return None
    expires = auth.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= _now():
        return None
    return auth


async def get_optional_actor(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> Optional[AuthSession]:
    admin_auth = await _load_session(db, request.cookies.get(ADMIN_COOKIE), "admin")
    if admin_auth:
        return admin_auth
    return await _load_session(db, request.cookies.get(STUDENT_COOKIE), "student")


async def get_current_student(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> StudentContext:
    raw = request.cookies.get(STUDENT_COOKIE)
    auth = await _load_session(db, raw, "student")
    if not auth or not auth.participant_id:
        raise AppError(401, "not_authenticated", "Please sign in with your PolyU email.")
    participant = await db.get(Participant, auth.participant_id)
    if not participant:
        raise AppError(401, "not_authenticated", "Please sign in with your PolyU email.")
    # Enrollment, gate opening and stopping use this same class-first lock order.
    # Keep it until the route commits; never let an in-flight save bypass a stop.
    await db.execute(select(ClassGroup).where(ClassGroup.id == participant.class_id).with_for_update())
    run = (await db.execute(select(Run).where(Run.participant_id == participant.id)
                           .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    db.info["student_request"] = True
    db.info["student_operation"] = request.method not in ("GET", "HEAD") and not request.url.path.endswith("/impression")
    if run and run.stopped_at and request.url.path != "/api/student/state":
        raise AppError(409, "participant_stopped", "管理员已停止你的任务，请联系现场研究者。 / Your task has been stopped. Please contact the researcher.")
    return StudentContext(auth=auth, participant=participant)


async def get_current_admin(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> AdminContext:
    raw = request.cookies.get(ADMIN_COOKIE)
    auth = await _load_session(db, raw, "admin")
    if not auth:
        raise AppError(401, "admin_unauthorized", "Researcher login required.")
    return AdminContext(auth=auth)


def set_session_cookie(
    response: Response,
    name: str,
    token: str,
    max_age_seconds: int,
    secure: bool,
) -> None:
    response.set_cookie(
        key=name,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, name: str) -> None:
    response.delete_cookie(name, path="/")
