from __future__ import annotations

from typing import Any, Dict

from ..models import ImageJob, Message, Round


def message_payload(message: Message) -> Dict[str, Any]:
    return {
        "id": message.id,
        "role": message.role,
        "source": message.source,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
    }


def image_job_payload(job: ImageJob) -> Dict[str, Any]:
    return {
        "id": str(job.id),
        "status": job.status,
        "prompt": job.prompt,
        "source_prompt": job.source_prompt,
        "prompt_optimizer_version": job.prompt_optimizer_version,
        "reference_image_used": job.reference_image_used,
        "attempts": job.attempts,
        "work_revision_no": job.work_revision_no,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "image_url": f"/api/files/keyframes/{job.id}"
        if job.status == "succeeded" and job.file_path
        else None,
        "width": job.width,
        "height": job.height,
        "created_at": job.created_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def round_summary(round_obj: Round) -> Dict[str, Any]:
    return {
        "id": str(round_obj.id),
        "round_no": round_obj.round_no,
        "started_at": round_obj.started_at.isoformat(),
        "deadline_at": round_obj.deadline_at.isoformat(),
        "finished_at": round_obj.finished_at.isoformat()
        if round_obj.finished_at
        else None,
        "finish_reason": round_obj.finish_reason,
    }
