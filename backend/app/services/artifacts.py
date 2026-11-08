from __future__ import annotations

import asyncio

import hashlib
import io
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..domain import SLOTS
from ..errors import AppError
from ..models import ArtifactVersion
from .storage import Storage

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_IMAGE_PIXELS = 30_000_000

# English reading aid for the formal artifacts.  It lives beside the V2 content
# and is merged into the student payload at read time, so it never becomes part
# of an artifact version, rubric or scoring key.
ARTIFACT_EN_PATH = (
    Path(__file__).resolve().parent.parent / "content" / "formal_v2" / "artifacts_en.json"
)
_artifact_en_cache: Optional[Dict[str, Any]] = None


def _artifact_en() -> Dict[str, Any]:
    global _artifact_en_cache
    if _artifact_en_cache is None:
        try:
            _artifact_en_cache = json.loads(ARTIFACT_EN_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _artifact_en_cache = {}
    return _artifact_en_cache


def _with_english(version: ArtifactVersion, payload: Dict[str, Any]) -> Dict[str, Any]:
    translation = (_artifact_en().get(version.object_code or "") or {})
    if not translation:
        return payload
    payload["title_en"] = translation.get("title_en", "")
    payload["introduction_en"] = translation.get("introduction_en", "")
    section_map = translation.get("sections") or {}
    sections = []
    for section in payload.get("sections") or []:
        merged = dict(section) if isinstance(section, dict) else section
        if isinstance(merged, dict):
            extra = section_map.get(str(merged.get("key") or "")) or {}
            if extra.get("title_en"):
                merged["title_en"] = extra["title_en"]
            if extra.get("body_en"):
                merged["body_en"] = extra["body_en"]
        sections.append(merged)
    payload["sections"] = sections
    return payload


def _clean_list(values: List[str], field: str, limit: int = 50) -> List[str]:
    result = [str(item).strip() for item in values if str(item).strip()]
    if len(result) > limit:
        raise AppError(422, "invalid_field", f"Too many entries in {field}.")
    return result


async def create_artifact_version(
    session: AsyncSession,
    settings: Settings,
    *,
    slot: str,
    title: str,
    era: str,
    artifact_type: str,
    introduction: str,
    facts: List[str],
    evidence: List[str],
    uncertainty: List[str],
    image_bytes: Optional[bytes],
    image_filename: Optional[str],
    is_demo: bool = False,
    object_code: Optional[str] = None,
    sections: Optional[List[Dict[str, Any]]] = None,
    media: Optional[List[Dict[str, Any]]] = None,
    rights_status: str = "internal-research",
) -> ArtifactVersion:
    if slot not in SLOTS:
        raise AppError(404, "artifact_slot_not_found", "Unknown artifact slot.")
    if object_code is not None and object_code not in ("M", "T"):
        raise AppError(422, "invalid_field", "Invalid object code.")
    sections = sections or []
    media = media or []
    if not isinstance(sections, list) or not isinstance(media, list):
        raise AppError(422, "invalid_field", "Sections and media must be lists.")
    content_sha256 = hashlib.sha256(
        json.dumps(
            {"sections": sections, "media": media},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    title = (title or "").strip()
    if not title:
        raise AppError(422, "invalid_field", "Artifact title is required.")
    if len(title) > 200:
        raise AppError(422, "invalid_field", "Artifact title is too long.")
    if len(introduction) > 20000:
        raise AppError(422, "invalid_field", "Introduction is too long.")

    facts = _clean_list(facts, "facts")
    evidence = _clean_list(evidence, "evidence")
    uncertainty = _clean_list(uncertainty, "uncertainty")

    await session.execute(
        select(ArtifactVersion)
        .where(ArtifactVersion.slot == slot)
        .order_by(ArtifactVersion.version.desc())
        .limit(1)
        .with_for_update()
    )
    current_max = (
        await session.execute(
            select(func.max(ArtifactVersion.version)).where(
                ArtifactVersion.slot == slot
            )
        )
    ).scalar_one()
    version_no = (current_max or 0) + 1

    previous = None
    if current_max:
        previous = (
            await session.execute(
                select(ArtifactVersion).where(
                    ArtifactVersion.slot == slot,
                    ArtifactVersion.version == current_max,
                )
            )
        ).scalar_one_or_none()

    if image_bytes:
        if len(image_bytes) > MAX_UPLOAD_BYTES:
            raise AppError(413, "image_too_large", "Artifact image is too large (12 MB max).")
        try:
            with Image.open(io.BytesIO(image_bytes)) as probe:
                probe.verify()
            with Image.open(io.BytesIO(image_bytes)) as image:
                image.load()
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise AppError(413, "image_too_large", "Artifact image dimensions are too large.")
                if image.width > 2400 or image.height > 2400:
                    image.thumbnail((2400, 2400))
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGBA")
                settings.ensure_directories()
                filename = f"{uuid.uuid4()}.png"
                absolute = settings.artifacts_dir / filename
                image.save(absolute, format="PNG", optimize=True)
                data = absolute.read_bytes()
            image_hash = hashlib.sha256(data).hexdigest()
            image_path = str(Path("artifacts") / filename)
            if Storage(settings).cloud:
                await asyncio.to_thread(Storage(settings).put_bytes, image_path, data, "image/png")
            image_mime = "image/png"
        except UnidentifiedImageError:
            raise AppError(422, "invalid_image", "Uploaded artifact image is not a valid image.")
    else:
        if previous is None or not previous.image_path:
            raise AppError(
                422,
                "image_required",
                "An artifact image is required for the first version.",
            )
        image_path = previous.image_path
        image_mime = previous.image_mime
        image_hash = previous.image_sha256

    version = ArtifactVersion(
        slot=slot,
        object_code=object_code,
        version=version_no,
        title=title,
        era=(era or "").strip()[:120],
        artifact_type=(artifact_type or "").strip()[:120],
        introduction=introduction.strip(),
        facts=facts,
        evidence=evidence,
        uncertainty=uncertainty,
        sections_json=sections,
        media_json=media,
        content_sha256=content_sha256,
        rights_status=(rights_status or "internal-research")[:32],
        image_path=image_path,
        image_mime=image_mime,
        image_sha256=image_hash,
        is_demo=is_demo,
    )
    session.add(version)
    await session.flush()
    return version


def _safe_data_path(settings: Settings, relative: Optional[str]) -> Optional[Path]:
    if not relative:
        return None
    if Storage(settings).cloud:
        try:
            return Storage(settings).materialize(relative)
        except AppError as exc:
            if exc.status_code == 404:
                return None
            raise
    path = (settings.data_dir / relative).resolve()
    try:
        path.relative_to(settings.data_dir.resolve())
    except ValueError:
        return None
    return path if path.exists() else None


def artifact_image_absolute(settings: Settings, version: ArtifactVersion) -> Optional[Path]:
    return _safe_data_path(settings, version.image_path)


def artifact_media_absolute(
    settings: Settings, version: ArtifactVersion, key: str, original: bool = False
) -> Optional[Path]:
    for item in version.media_json or []:
        if not isinstance(item, dict) or item.get("key") != key:
            continue
        field = "original_path" if original else "display_path"
        return _safe_data_path(settings, item.get(field) or item.get("path"))
    return None


def media_public_url(version_id, key: str, original: bool = False) -> str:
    suffix = "?variant=original" if original else ""
    return f"/api/files/artifacts/{version_id}/media/{key}{suffix}"


def student_artifact(version: ArtifactVersion) -> Dict[str, Any]:
    media = []
    for item in version.media_json or []:
        if not isinstance(item, dict) or not item.get("key"):
            continue
        media.append(
            {
                **item,
                "url": media_public_url(version.id, str(item["key"])),
                "original_url": media_public_url(version.id, str(item["key"]), True),
            }
        )
    payload = {
        "id": str(version.id),
        "title": version.title,
        "era": version.era,
        "type": version.artifact_type,
        "object_code": version.object_code,
        "introduction": version.introduction,
        "facts": version.facts or [],
        "evidence": version.evidence or [],
        "uncertainty": version.uncertainty or [],
        "sections": version.sections_json or [],
        "media": media,
        "rights_status": version.rights_status,
        "image_url": f"/api/files/artifacts/{version.id}/image",
    }
    return _with_english(version, payload)


def admin_artifact(version: ArtifactVersion) -> Dict[str, Any]:
    payload = student_artifact(version)
    payload.update(
        {
            "slot": version.slot,
            "object_code": version.object_code,
            "version": version.version,
            "is_demo": version.is_demo,
            "rights_status": version.rights_status,
            "content_sha256": version.content_sha256,
            "created_at": version.created_at.isoformat(),
            "image_sha256": version.image_sha256,
        }
    )
    return payload
