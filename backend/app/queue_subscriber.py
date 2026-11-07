"""Shared handler bound by the private queue service."""
from .services.cloud_tasks import execute_task


async def handle_task(payload: dict[str, str]) -> None:
    await execute_task(payload["task_id"])
