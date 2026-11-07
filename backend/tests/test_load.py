from __future__ import annotations

import asyncio
import time
from uuid import uuid4

import httpx

from tests.conftest import code_rows, complete_k0, enter_t1, save_t1_work


async def _job_poll(client, job_id, timeout=30.0):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        response = await client.get(f"/api/student/image-jobs/{job_id}")
        assert response.status_code == 200, response.text
        job = response.json()["job"]
        if job["status"] in ("succeeded", "failed"):
            return job
        await asyncio.sleep(0.2)
    raise AssertionError("image job timeout")


async def test_thirty_concurrent_participants(app_client):
    client, app, settings = app_client
    app.state.fake_ai_state.image_delay = 0.15
    rows = code_rows(settings)[:30]

    async def run_one(row, index):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver", timeout=30
        ) as student:
            enter = await student.post(
                "/api/auth/enter",
                json={"code": row["access_code"], "class_id": int(row["class_id"])},
            )
            assert enter.status_code == 200, enter.text
            await complete_k0(student)
            await enter_t1(student)
            chat = await student.post(
                "/api/student/rounds/1/messages",
                json={
                    "content": f"Concurrent participant {index} asks a question.",
                    "client_message_id": str(uuid4()),
                },
            )
            assert chat.status_code == 200, chat.text
            await save_t1_work(student, f"Concurrent product {index}")
            image = await student.post("/api/student/rounds/1/image-jobs", json={})
            assert image.status_code == 200, image.text
            job_id = image.json()["job"]["id"]
            finished = await student.post("/api/student/rounds/1/finish")
            assert finished.status_code == 200, finished.text
            result = await _job_poll(student, job_id)
            assert result["status"] == "succeeded", result
            return student

    started = time.monotonic()
    await asyncio.gather(*(run_one(row, index) for index, row in enumerate(rows)))
    elapsed = time.monotonic() - started
    assert elapsed < 90
    assert app.state.fake_ai_state.max_image_inflight <= settings.image_max_concurrency

    admin = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver", timeout=30
    )
    async with admin:
        login = await admin.post("/api/admin/login", json={"password": settings.admin_password})
        assert login.status_code == 200
        overview = await admin.get("/api/admin/overview")
        assert overview.status_code == 200
        body = overview.json()
        assert body["counts"]["started"] == 30
        assert body["counts"]["by_stage"].get("k1") == 30
