from __future__ import annotations

import asyncio

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..dependencies import get_optional_actor, get_session, get_settings
from ..errors import AppError
from ..models import ArtifactVersion, AuthSession, ImageJob, ProtocolVersion, Round, Run
from ..services.artifacts import artifact_image_absolute, artifact_media_absolute
from ..services.storage import Storage

router = APIRouter(prefix="/api/files", tags=["files"])


async def _require_actor(
    request: Request, db: AsyncSession
) -> AuthSession:
    auth = await get_optional_actor(request, db)
    if not auth:
        raise AppError(401, "not_authenticated", "Please sign in again.")
    return auth


def _private_file_response(path: Path, media_type: str, filename: str) -> FileResponse:
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )


async def _student_can_view_artifact(
    db: AsyncSession, participant_id, version: ArtifactVersion
) -> bool:
    run = (
        await db.execute(select(Run).where(Run.participant_id == participant_id))
    ).scalar_one_or_none()
    if not run:
        return False
    protocol = await db.get(ProtocolVersion, run.protocol_version_id)
    if protocol and version.id in (
        protocol.artifact_x_version_id,
        protocol.artifact_y_version_id,
    ):
        return True
    result = await db.execute(
        select(Round.id)
        .join(Run, Run.id == Round.run_id)
        .where(
            Run.participant_id == participant_id,
            Round.artifact_version_id == version.id,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


@router.get("/artifacts/{version_id}/image")
async def artifact_image(
    version_id: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    auth = await _require_actor(request, db)
    try:
        version_uuid = uuid.UUID(version_id)
    except ValueError:
        raise AppError(404, "artifact_not_found", "Artifact image not found.")
    version = await db.get(ArtifactVersion, version_uuid)
    if not version or not version.image_path:
        raise AppError(404, "artifact_not_found", "Artifact image not found.")
    if auth.role == "student":
        if not auth.participant_id or not await _student_can_view_artifact(
            db, auth.participant_id, version
        ):
            raise AppError(404, "artifact_not_found", "Artifact image not found.")
    if settings.storage_backend == "blob":
        return await asyncio.to_thread(Storage(settings).response, version.image_path,
                      version.image_mime or "image/png", f"artifact-{version.slot}.png")
    path = artifact_image_absolute(settings, version)
    if not path:
        raise AppError(404, "artifact_image_missing", "Artifact image file is missing.")
    return _private_file_response(
        path, version.image_mime or "application/octet-stream", f"artifact-{version.slot}.png"
    )


@router.get("/artifacts/{version_id}/media/{media_key}")
async def artifact_media(
    version_id: str,
    media_key: str,
    request: Request,
    variant: str = "display",
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    auth = await _require_actor(request, db)
    try:
        version_uuid = uuid.UUID(version_id)
    except ValueError:
        raise AppError(404, "artifact_media_not_found", "Artifact media not found.")
    version = await db.get(ArtifactVersion, version_uuid)
    if not version:
        raise AppError(404, "artifact_media_not_found", "Artifact media not found.")
    if auth.role == "student":
        if not auth.participant_id or not await _student_can_view_artifact(
            db, auth.participant_id, version
        ):
            raise AppError(404, "artifact_media_not_found", "Artifact media not found.")
    item = next(
        (
            entry
            for entry in (version.media_json or [])
            if isinstance(entry, dict) and entry.get("key") == media_key
        ),
        None,
    )
    if not item:
        raise AppError(404, "artifact_media_not_found", "Artifact media not found.")
    if settings.storage_backend == "blob":
        item = next((item for item in version.media_json or [] if item.get("key") == media_key), None)
        if not item:
            raise AppError(404, "artifact_media_not_found", "Artifact media not found.")
        original = variant == "original"
        key = item.get("original_path" if original else "display_path") or item.get("path")
        if not key:
            raise AppError(404, "artifact_media_not_found", "Artifact media not found.")
        return await asyncio.to_thread(Storage(settings).response, key,
                      item.get("original_mime" if original else "mime") or "image/png", f"artifact-{version.slot}-{media_key}")
    path = artifact_media_absolute(
        settings, version, media_key, original=(variant == "original")
    )
    if not path:
        raise AppError(404, "artifact_media_missing", "Artifact media file is missing.")
    mime = str(
        (item.get("original_mime") if variant == "original" else item.get("mime"))
        or "application/octet-stream"
    )
    return _private_file_response(path, mime, f"artifact-{version.slot}-{media_key}")


@router.get("/keyframes/{job_id}")
async def keyframe_image(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    auth = await _require_actor(request, db)
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise AppError(404, "image_not_found", "Image not found.")
    result = await db.execute(
        select(ImageJob, Run)
        .join(Round, Round.id == ImageJob.round_id)
        .join(Run, Run.id == Round.run_id)
        .where(ImageJob.id == job_uuid)
    )
    row = result.first()
    if not row:
        raise AppError(404, "image_not_found", "Image not found.")
    job, run = row
    if auth.role == "student" and auth.participant_id != run.participant_id:
        # A peer assignment or same-class work feed grants access to T2 images,
        # never arbitrary other users' drafts or another class's media.
        from ..models import Participant, PeerAssignment, WorkRevision
        viewer = await db.get(Participant, auth.participant_id)
        owner = await db.get(Participant, run.participant_id)
        viewer_run = (await db.execute(select(Run).where(Run.participant_id == auth.participant_id))).scalar_one_or_none()
        round_obj = await db.get(Round, job.round_id)
        permitted = False
        if viewer and owner and viewer.class_id == owner.class_id and viewer_run and round_obj:
            from ..services.peer import eligible_works
            from ..models import WorkRevision
            if viewer_run.stage in ("social_feed", "complete") and round_obj.round_no == 2:
                for item in await eligible_works(db, viewer.class_id):
                    if item["run"].id == run.id and item["image_url"] == f"/api/files/keyframes/{job.id}":
                        permitted = True
                        break
            elif viewer_run.stage == "peer_assessment":
                # Peer assignments may point at T1 or T2; authorize exactly the
                # current work revision in the job's round, never an arbitrary draft.
                assigned = (await db.execute(
                    select(PeerAssignment.id)
                    .join(WorkRevision, WorkRevision.id == PeerAssignment.work_id)
                    .where(
                        PeerAssignment.reviewer_run_id == viewer_run.id,
                        WorkRevision.round_id == job.round_id,
                        WorkRevision.revision_no == round_obj.current_work_revision,
                    )
                    .limit(1)
                )).scalar_one_or_none()
                permitted = assigned is not None
        if not permitted:
            raise AppError(404, "image_not_found", "Image not found.")
    if job.status != "succeeded" or not job.file_path:
        raise AppError(404, "image_not_ready", "Image not ready.")
    if settings.storage_backend == "blob":
        return await asyncio.to_thread(Storage(settings).response, job.file_path,
                      job.mime or "image/png", f"keyframe-{job.id}.png")
    absolute = (settings.data_dir / job.file_path).resolve()
    try:
        absolute.relative_to(settings.data_dir.resolve())
    except ValueError:
        raise AppError(404, "image_not_found", "Image not found.")
    if not absolute.exists():
        raise AppError(404, "image_missing", "Image file is missing.")
    return _private_file_response(absolute, job.mime or "image/png", f"keyframe-{job.id}.png")
