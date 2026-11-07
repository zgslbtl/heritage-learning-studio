from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..db import Database
from ..errors import AppError
from ..models import (
    ApiError,
    ArtifactVersion,
    ImageJob,
    Participant,
    Round,
    Run,
    ScriptRevision,
    WorkRevision,
    RuntimeTask,
)
from .ai_text import IMAGE_PROMPT_OPTIMIZER_VERSION, optimize_image_prompt
from .artifacts import artifact_image_absolute, artifact_media_absolute
from .run_state import aware, protocol_artifact
from .works import latest_work

logger = logging.getLogger("hls.images")
MAX_RESULT_BYTES = 25 * 1024 * 1024
MAX_RESULT_PIXELS = 40_000_000
IMAGE_PROMPT_VERSION = "image-v2"


def _compact_prompt(value: str, maximum: int = 1200) -> str:
    text = " ".join((value or "").split())
    return text[:maximum].rstrip()


def _artifact_reference_data_url(
    settings: Settings, artifact: ArtifactVersion
) -> Optional[str]:
    if not settings.image_reference_enabled:
        return None
    for item in artifact.media_json or []:
        if not isinstance(item, dict) or not item.get("key"):
            continue
        path = artifact_media_absolute(settings, artifact, str(item["key"]), original=False)
        if path and path.exists():
            mime = str(item.get("mime") or "image/jpeg")
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{encoded}"
    path = artifact_image_absolute(settings, artifact)
    if path and path.exists():
        mime = artifact.image_mime or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _current_script(
    session: AsyncSession, round_id
) -> Optional[ScriptRevision]:
    result = await session.execute(
        select(ScriptRevision)
        .where(ScriptRevision.round_id == round_id)
        .order_by(ScriptRevision.revision_no.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def build_image_prompt(
    artifact: ArtifactVersion, script: Optional[ScriptRevision]
) -> str:
    """Legacy short-video keyframe prompt (kept for old rounds)."""

    title = script.title.strip() if script and script.title else artifact.title
    body = script.body.strip() if script else ""
    evidence = "; ".join(str(item) for item in (artifact.evidence or [])[:8])
    facts = "; ".join(str(item) for item in (artifact.facts or [])[:12])
    return (
        "Create one historically grounded keyframe illustration for a one-minute "
        "cultural-heritage educational short video. This is a visual accompaniment to "
        "the student's script, not a replacement for museum evidence.\n\n"
        f"Artifact: {artifact.title} ({artifact.era}; {artifact.artifact_type}).\n"
        f"Evidence and facts: {facts}. {evidence}.\n"
        f"Student script title: {title}.\n"
        f"Student script: {body[:6000]}\n\n"
        "Visual direction: elegant museum-education illustration, respectful and "
        "non-sensational, coherent period-appropriate material culture, clear focal "
        "subject, cinematic wide composition. Do not add readable text, captions, "
        "watermarks, logos, or invented inscriptions. Avoid anachronistic objects."
    )


def _artifact_reading_summary(artifact: ArtifactVersion) -> str:
    """Concise, design-neutral evidence for the image model.

    Formal artifacts store their curated reading in sections_json; legacy
    artifacts use facts/evidence.  The image prompt gets a bounded summary so
    the visual model knows the object's documented features without receiving
    the whole long-form reading page.
    """
    sections = [
        section
        for section in (artifact.sections_json or [])
        if isinstance(section, dict)
        and section.get("key") not in ("sources",)
        and section.get("body")
    ]
    if sections:
        text = "\n\n".join(
            f"{section.get('title', section.get('key', ''))}: {section.get('body', '')}"
            for section in sections
        )
        return text[:3000]
    return ""


def build_product_prompt(
    artifact: ArtifactVersion, work: WorkRevision
) -> str:
    """v1.5 cultural-heritage product concept image prompt."""

    evidence = "; ".join(str(item) for item in (artifact.evidence or [])[:8])
    facts = "; ".join(str(item) for item in (artifact.facts or [])[:12])
    reading = _artifact_reading_summary(artifact)
    student_visual = (work.image_prompt or "").strip()
    structured = work.structured_fields or {}
    field_lines = "; ".join(
        f"{key}: {str(value).strip()}"
        for key, value in structured.items()
        if str(value).strip()
    )
    rationale = work.rationale_fields or {}
    rationale_lines = "; ".join(
        f"{key}: {str(value).strip()}"
        for key, value in rationale.items()
        if str(value).strip()
    )
    open_part = (
        f"Open design statement: {work.open_statement[:3000]}\n"
        if work.open_statement
        else ""
    )
    concept_line = (
        f"Design concept: {work.design_concept[:3000]}\n"
        if work.design_concept.strip()
        else ""
    )
    rationale_line = (
        f"Three-part rationale: {rationale_lines[:4000]}\n"
        if rationale_lines
        else ""
    )
    return (
        "Create one polished visual concept rendering of a contemporary cultural-"
        "heritage-inspired product for a museum-education design workshop. The image "
        "should communicate the student's design idea, not imitate a film still and "
        "not replace museum evidence.\n\n"
        f"Artifact: {artifact.title} ({artifact.era}; {artifact.artifact_type}).\n"
        f"Evidence and facts: {facts}. {evidence}.\n"
        f"Product name: {work.product_name or artifact.title}.\n"
        f"Product category/use: {work.product_category or 'contemporary cultural product'}.\n"
        f"Target audience: {work.target_audience or 'general museum audience'}.\n"
        f"{concept_line}"
        f"Student visual description (primary visual direction): {student_visual[:6000] or 'Not provided; use the rationale and product fields.'}\n"
        f"Supporting structured design notes: {field_lines[:4000]}\n"
        f"{rationale_line}"
        f"{open_part}"
        f"Curated artifact reading (supporting evidence only; do not turn it into a design instruction):\n{reading or 'No additional reading summary.'}\n\n"
        "Visual direction: clean product-design concept art or studio product "
        "visualisation, coherent period-appropriate cultural references, clear product "
        "form and materials, respectful and non-sensational, one hero product, simple "
        "neutral background. Do not add readable text, captions, watermarks, logos, "
        "brand marks or invented inscriptions. Avoid anachronistic or stereotyped "
        "cultural elements. The product itself must remain the visual focus."
    )


async def select_image_job(
    session: AsyncSession, round_obj: Round, job_id: str
) -> ImageJob:
    if round_obj.finished_at:
        raise AppError(409, "round_finished", "This task is already finished.")
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise AppError(404, "image_job_not_found", "Image task not found.")
    job = await session.get(ImageJob, job_uuid)
    if not job or job.round_id != round_obj.id:
        raise AppError(404, "image_job_not_found", "Image task not found.")
    if job.status != "succeeded" or not job.file_path:
        raise AppError(409, "image_not_ready", "This image is not ready to submit.")
    round_obj.selected_image_job_id = job.id
    await session.flush()
    return job


async def enqueue_image_job(
    session: AsyncSession,
    settings: Settings,
    run: Run,
    round_obj: Round,
    retry_of: Optional[str] = None,
) -> ImageJob:
    if not settings.image_configured:
        raise AppError(
            503,
            "image_model_not_configured",
            "The image AI service is not configured on this server.",
        )
    if round_obj.finished_at or aware(round_obj.deadline_at) <= _now():
        raise AppError(409, "round_expired", "The task time has ended.")
    locked_round = await session.execute(
        select(Round)
        .where(Round.id == round_obj.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    round_obj = locked_round.scalar_one()
    work = await latest_work(session, round_obj.id)
    script = await _current_script(session, round_obj.id)
    if work is None and (script is None or not script.body.strip()):
        raise AppError(
            422,
            "work_required",
            "Write and save your product design before generating a concept image.",
        )

    jobs_result = await session.execute(
        select(ImageJob)
        .where(ImageJob.round_id == round_obj.id)
        .order_by(ImageJob.created_at.asc())
    )
    jobs = list(jobs_result.scalars().all())
    if any(job.status in ("queued", "running") for job in jobs):
        raise AppError(
            409,
            "image_job_active",
            "An image task is already running. Wait for it to finish.",
        )
    if (
        settings.image_job_limit_per_round > 0
        and len(jobs) >= settings.image_job_limit_per_round
    ):
        raise AppError(
            429,
            "image_quota_exhausted",
            "No image generation attempts remain for this round.",
            {"limit": settings.image_job_limit_per_round},
        )
    retry_job = None
    if retry_of:
        try:
            retry_uuid = uuid.UUID(retry_of)
        except ValueError:
            raise AppError(422, "invalid_retry", "Invalid retry task.")
        retry_job = await session.get(ImageJob, retry_uuid)
        if not retry_job or retry_job.round_id != round_obj.id:
            raise AppError(404, "image_job_not_found", "Image task not found.")
        if retry_job.status != "failed":
            raise AppError(409, "invalid_retry", "Only a failed image task can be retried.")

    artifact = await protocol_artifact(session, run, round_obj)
    if work is not None:
        prompt = build_product_prompt(artifact, work)
    else:
        prompt = build_image_prompt(artifact, script)
    job = ImageJob(
        round_id=round_obj.id,
        script_revision_no=script.revision_no if script else None,
        work_revision_no=work.revision_no if work else None,
        prompt=prompt,
        source_prompt=prompt,
        status="queued",
        model=settings.image_model_name,
        retry_of_id=retry_job.id if retry_job else None,
    )
    session.add(job)
    await session.flush()
    if settings.queue_backend == "vercel":
        session.add(RuntimeTask(id=job.id, kind="image", status="queued", dispatch_state="pending",
                                payload={"job_id": str(job.id)}, checkpoint={}))
        await session.flush()
    return job


async def _parse_image_response(
    data: Dict[str, Any], settings: Settings
) -> tuple[bytes, int]:
    try:
        item = data["data"][0]
    except (KeyError, IndexError, TypeError):
        raise AppError(
            502,
            "image_model_bad_response",
            "The image AI returned an unusable response.",
            retryable=True,
        )
    image_bytes: Optional[bytes] = None
    if isinstance(item, dict) and item.get("b64_json"):
        try:
            image_bytes = base64.b64decode(str(item["b64_json"]))
        except (ValueError, TypeError):
            raise AppError(
                502,
                "image_model_bad_response",
                "The image AI returned invalid image data.",
                retryable=True,
            )
        status = 200
    elif isinstance(item, dict) and item.get("url"):
        url = str(item["url"])
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise AppError(
                502,
                "image_model_bad_response",
                "The image AI returned an unsafe image URL.",
            )
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.image_model_timeout_seconds),
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
        except httpx.HTTPError:
            raise AppError(
                502,
                "image_download_failed",
                "The generated image could not be downloaded.",
                retryable=True,
            )
        status = response.status_code
        if response.status_code < 200 or response.status_code >= 300:
            raise AppError(
                502,
                "image_download_failed",
                f"The generated image URL returned HTTP {response.status_code}.",
                retryable=True,
            )
        image_bytes = response.content
        if len(image_bytes) > MAX_RESULT_BYTES:
            raise AppError(
                413,
                "image_result_too_large",
                "The generated image file is too large.",
            )
    else:
        raise AppError(
            502,
            "image_model_bad_response",
            "The image AI response contained neither image data nor a URL.",
            retryable=True,
        )
    if not image_bytes or len(image_bytes) > MAX_RESULT_BYTES:
        raise AppError(
            502,
            "image_model_bad_response",
            "The generated image was empty or too large.",
            retryable=True,
        )
    return image_bytes, status


async def _call_image_provider(
    settings: Settings,
    prompt: str,
    reference_data_url: Optional[str] = None,
) -> tuple[bytes, Dict[str, Any], int]:
    if not settings.image_configured:
        raise AppError(
            503,
            "image_model_not_configured",
            "The image AI service is not configured on this server.",
        )
    url = settings.image_model_base_url.rstrip("/") + "/images/generations"  # type: ignore[union-attr]
    payload = {
        "model": settings.image_model_name,
        "prompt": prompt,
        "size": settings.image_model_size,
    }
    if reference_data_url and settings.image_reference_enabled:
        payload["image"] = reference_data_url
    if settings.image_model_response_format:
        payload["response_format"] = settings.image_model_response_format
    if settings.image_model_watermark is not None:
        payload["watermark"] = settings.image_model_watermark
    headers = {
        "Authorization": f"Bearer {settings.image_model_api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.image_model_timeout_seconds)
        ) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise AppError(
            504,
            "image_model_timeout",
            "The image AI did not respond in time.",
            retryable=True,
        )
    except httpx.HTTPError as exc:
        logger.warning("Image provider transport failed type=%s detail=%s", type(exc).__name__, str(exc)[:200])
        raise AppError(
            502,
            "image_model_unavailable",
            "The image AI service could not be reached.",
            retryable=True,
        )
    if response.status_code < 200 or response.status_code >= 300:
        detail = ""
        try:
            body = response.json()
            error = body.get("error") if isinstance(body, dict) else None
            if isinstance(error, dict):
                detail = str(error.get("message", ""))[:500]
            elif error:
                detail = str(error)[:500]
        except (ValueError, TypeError):
            detail = response.text[:500]
        raise AppError(
            502,
            "image_model_error",
            f"The image AI returned an error (HTTP {response.status_code}). "
            + (f"Upstream: {detail}" if detail else ""),
            {"upstream_status": response.status_code},
            retryable=True,
        )
    try:
        data = response.json()
    except ValueError:
        raise AppError(
            502,
            "image_model_bad_response",
            "The image AI returned invalid JSON.",
            retryable=True,
        )
    image_bytes, download_status = await _parse_image_response(data, settings)
    return image_bytes, data, response.status_code or download_status


def _validate_and_store(
    settings: Settings,
    participant_id,
    round_no: int,
    job_id,
    image_bytes: bytes,
) -> tuple[str, str, int, int, str]:
    try:
        with Image.open(io.BytesIO(image_bytes)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.load()
            if image.width * image.height > MAX_RESULT_PIXELS:
                raise AppError(
                    413,
                    "image_result_too_large",
                    "The generated image dimensions are too large.",
                )
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA")
            settings.ensure_directories()
            target_dir = settings.keyframes_dir / str(participant_id) / f"round-{round_no}"
            target_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{job_id}.png"
            absolute = target_dir / filename
            tmp = target_dir / f".{job_id}.tmp"
            image.save(tmp, format="PNG", optimize=True)
            tmp.replace(absolute)
            digest = hashlib.sha256(absolute.read_bytes()).hexdigest()
            width, height = image.width, image.height
    except UnidentifiedImageError:
        raise AppError(
            502,
            "image_result_invalid",
            "The image AI returned bytes that are not a valid image.",
            retryable=True,
        )
    relative = (
        Path("keyframes") / str(participant_id) / f"round-{round_no}" / filename
    )
    return str(relative), "image/png", width, height, digest


class ImageWorker:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        concurrency: Optional[int] = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self.concurrency = max(
            1, min(concurrency or settings.image_max_concurrency, 8)
        )
        self._tasks: list[asyncio.Task] = []
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if not self.settings.image_worker_enabled:
            return
        await self._mark_interrupted_jobs()
        if not self.settings.image_configured:
            logger.warning("Image worker not started: image model is not configured")
            return
        self._stopping.clear()
        for index in range(self.concurrency):
            self._tasks.append(
                asyncio.create_task(self._loop(index), name=f"image-worker-{index}")
            )
        logger.info("Image worker started with concurrency=%s", self.concurrency)

    async def stop(self) -> None:
        self._stopping.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _mark_interrupted_jobs(self) -> None:
        async with self.db.session_factory() as session:
            result = await session.execute(
                select(ImageJob).where(ImageJob.status == "running")
            )
            jobs = list(result.scalars().all())
            for job in jobs:
                job.status = "failed"
                job.error_code = "server_restart"
                job.error_message = (
                    "The server restarted while this image task was running. "
                    "Retry to start a new attempt."
                )
                job.finished_at = _now()
            if jobs:
                await session.commit()
                logger.warning("Marked %s interrupted image job(s) as failed", len(jobs))

    async def _claim_job(self) -> Optional[uuid.UUID]:
        async with self.db.session_factory() as session:
            result = await session.execute(
                select(ImageJob)
                .where(ImageJob.status == "queued")
                .order_by(ImageJob.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            job = result.scalar_one_or_none()
            if not job:
                return None
            job.status = "running"
            job.attempts += 1
            job.started_at = _now()
            await session.commit()
            return job.id

    async def _loop(self, index: int) -> None:
        while not self._stopping.is_set():
            job_id = await self._claim_job()
            if job_id is None:
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                continue
            try:
                await self._process_job(job_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unhandled image worker error for job %s", job_id)

    async def _process_job(self, job_id: uuid.UUID) -> None:
        started = time.perf_counter()
        async with self.db.session_factory() as session:
            job = await session.get(ImageJob, job_id)
            if not job:
                return
            round_obj = await session.get(Round, job.round_id)
            if not round_obj:
                await self._fail(session, job, "round_missing", "The round is missing.")
                await session.commit()
                return
            run = await session.get(Run, round_obj.run_id)
            participant = await session.get(Participant, run.participant_id) if run else None
            if not participant:
                await self._fail(session, job, "participant_missing", "Participant missing.")
                await session.commit()
                return
            artifact = await session.get(ArtifactVersion, round_obj.artifact_version_id)
            source_prompt = job.source_prompt or job.prompt
            reference_data_url = (
                _artifact_reference_data_url(self.settings, artifact)
                if artifact
                else None
            )
            optimized_prompt = _compact_prompt(source_prompt)
            optimizer_version: Optional[str] = None
            task = await session.get(RuntimeTask, job_id) if self.settings.queue_backend == "vercel" else None
            checkpoint = dict(task.checkpoint or {}) if task else {}
            if checkpoint.get("optimized_prompt"):
                optimized_prompt = checkpoint["optimized_prompt"]
                optimizer_version = checkpoint.get("optimizer_version")
            elif self.settings.image_prompt_optimizer_enabled and artifact:
                try:
                    optimized_prompt = await optimize_image_prompt(
                        session,
                        self.settings,
                        run,
                        round_obj,
                        source_prompt,
                        reference_data_url,
                    )
                    optimizer_version = IMAGE_PROMPT_OPTIMIZER_VERSION
                except AppError as exc:
                    logger.warning(
                        "Image prompt optimization failed for job %s: %s",
                        job.id,
                        exc.code,
                    )
                    optimized_prompt = _compact_prompt(source_prompt)
                    optimizer_version = "fallback-compact-v1"
            job.prompt = optimized_prompt
            job.prompt_optimizer_version = optimizer_version
            job.reference_image_used = bool(reference_data_url)
            if task:
                checkpoint.update(optimized_prompt=optimized_prompt, optimizer_version=optimizer_version)
                task.checkpoint = checkpoint
            await session.commit()
        reference_used = bool(reference_data_url)
        try:
            if task:
                from .storage import Storage
                storage = Storage(self.settings)
                raw_key = f"provider-results/{job.id}.bin"
                if checkpoint.get("provider_started"):
                    try:
                        image_bytes = await asyncio.to_thread(storage.read_bytes, raw_key)
                    except AppError as exc:
                        if exc.status_code != 404:
                            raise
                        raise AppError(502, "image_result_uncertain",
                            "The provider request was interrupted. Its result is unknown; retry manually if needed.")
                    raw, http_status = {}, 200
                else:
                    async with self.db.session_factory() as session:
                        durable = await session.get(RuntimeTask, job.id, with_for_update=True)
                        durable.checkpoint = {**durable.checkpoint, "provider_started": True}
                        await session.commit()
                    image_bytes, raw, http_status = await _call_image_provider(
                        self.settings, optimized_prompt, reference_data_url)
                    await asyncio.to_thread(storage.put_bytes, raw_key, image_bytes, "application/octet-stream")
                    async with self.db.session_factory() as session:
                        durable = await session.get(RuntimeTask, job.id, with_for_update=True)
                        durable.checkpoint = {**durable.checkpoint, "provider_result_key": raw_key}
                        await session.commit()
            else:
                try:
                    image_bytes, raw, http_status = await _call_image_provider(
                        self.settings, optimized_prompt, reference_data_url
                    )
                except AppError as exc:
                    if reference_data_url and exc.code in ("image_model_unavailable", "image_model_error"):
                        logger.warning("Image provider rejected reference image; retrying text-to-image: %s", exc.code)
                        reference_used = False
                        image_bytes, raw, http_status = await _call_image_provider(
                            self.settings, optimized_prompt, None)
                    else:
                        raise
            path, mime, width, height, digest = _validate_and_store(
                self.settings,
                participant.id,
                round_obj.round_no,
                job.id,
                image_bytes,
            )
            if task:
                await asyncio.to_thread(storage.put_file, path, self.settings.data_dir / path, mime, overwrite=True)
        except AppError as exc:
            async with self.db.session_factory() as session:
                failed_job = await session.get(ImageJob, job.id)
                if failed_job:
                    await self._fail(session, failed_job, exc.code, exc.message)
                    session.add(
                        ApiError(
                            participant_id=participant.id,
                            run_id=run.id if run else None,
                            category="image_ai",
                            endpoint="image-worker",
                            status_code=exc.status_code,
                            error_code=exc.code,
                            message=exc.message,
                        )
                    )
                    await session.commit()
            return
        except Exception as exc:
            logger.exception("Image generation failed unexpectedly")
            async with self.db.session_factory() as session:
                failed_job = await session.get(ImageJob, job.id)
                if failed_job:
                    await self._fail(
                        session,
                        failed_job,
                        "image_internal_error",
                        "The image task failed unexpectedly.",
                    )
                    session.add(
                        ApiError(
                            participant_id=participant.id,
                            run_id=run.id if run else None,
                            category="image_ai",
                            endpoint="image-worker",
                            status_code=500,
                            error_code="image_internal_error",
                            message=type(exc).__name__,
                        )
                    )
                    await session.commit()
            return

        async with self.db.session_factory() as session:
            succeeded = await session.get(ImageJob, job.id)
            if succeeded:
                succeeded.status = "succeeded"
                succeeded.file_path = path
                succeeded.mime = mime
                succeeded.sha256 = digest
                succeeded.width = width
                succeeded.height = height
                succeeded.http_status = http_status
                succeeded.reference_image_used = reference_used
                succeeded.error_code = None
                succeeded.error_message = None
                succeeded.finished_at = _now()
                round_obj = await session.get(Round, succeeded.round_id)
                if round_obj and round_obj.selected_image_job_id is None:
                    round_obj.selected_image_job_id = succeeded.id
                await session.commit()

    async def _fail(
        self, session: AsyncSession, job: ImageJob, code: str, message: str
    ) -> None:
        job.status = "failed"
        job.error_code = code
        job.error_message = message[:2000]
        job.finished_at = _now()
        await session.flush()
