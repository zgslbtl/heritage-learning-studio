"""Queue-triggered service with no public route or service binding.

Services currently needs the trigger declared explicitly. The SDK handles the
CloudEvents delivery, payload decoding, lease renewals and acknowledgement.
"""
import logging
from fastapi import FastAPI, Request, Response
from vercel.queue import SanitizedName, accept_and_handle, subscribe

from .queue_subscriber import handle_task
from .services.cloud_tasks import TOPIC

logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_subscriptions = {}


@app.post("/{path:path}")
async def receive(request: Request, path: str):
    group = request.headers.get("ce-vqsconsumergroup")
    if not group or request.headers.get("ce-vqsqueuename") != TOPIC:
        return Response(status_code=400)
    if group not in _subscriptions:
        _subscriptions[group] = subscribe(handle_task, topic=TOPIC,
                                           consumer_group=SanitizedName(group))
    await accept_and_handle(await request.body(), request.headers, lease_duration=300)
    return Response(status_code=204)
