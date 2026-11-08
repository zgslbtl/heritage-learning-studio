"""Recover class entry URLs for authenticated administrators without raw-token storage."""
from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from typing import Optional

from ..config import Settings
from ..errors import AppError
from ..models import ClassEntryLink
from ..security import token_hash

TOKEN_SCHEME = "hmac-sha256-v1"


def class_link_token(settings: Settings, link_id: uuid.UUID, class_id: int) -> str:
    if not settings.anon_code_pepper:
        raise AppError(503, "class_links_not_configured", "Class links are not configured.")
    # A versioned domain separates this use from allocation and access-code HMACs.
    message = f"heritage-class-entry-link:v1:{link_id}:{class_id}".encode("utf-8")
    digest = hmac.new(settings.anon_code_pepper.encode("utf-8"), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def saved_class_link_url(settings: Settings, link: ClassEntryLink) -> Optional[str]:
    if not link.active or link.token_scheme != TOKEN_SCHEME:
        return None
    token = class_link_token(settings, link.id, link.class_id)
    if not hmac.compare_digest(token_hash(token), link.token_hash):
        return None
    return class_link_url(settings, token)


def class_link_url(settings: Settings, token: str) -> str:
    base = (settings.public_origin or "").rstrip("/")
    return f"{base}/join?token={token}" if base else f"/join?token={token}"


def new_class_link(settings: Settings, class_id: int, label: str):
    link_id = uuid.uuid4()
    token = class_link_token(settings, link_id, class_id)
    return ClassEntryLink(
        id=link_id, class_id=class_id, label=label, active=True,
        token_scheme=TOKEN_SCHEME, token_hash=token_hash(token),
    ), token
