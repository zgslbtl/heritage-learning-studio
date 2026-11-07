from __future__ import annotations

import asyncio
import io
import json
from uuid import uuid4

import httpx
from sqlalchemy import select

from app.db import Database
from app.models import Participant
from tests.conftest import (
    code_rows,
    complete_k0,
    enter_t1,
    login_student,
    save_t1_work,
)
from tests.test_flow import wait_for_job


async def test_code_security_and_student_isolation(app_client):
    client, app, settings = app_client
    rows = code_rows(settings)
    # Wrong class and unknown code reveal nothing useful.
    wrong_class = await client.post(
        "/api/auth/enter",
        json={"code": rows[0]["access_code"], "class_id": 99 if int(rows[0]["class_id"]) != 1 else 2},
    )
    assert wrong_class.status_code in (401, 422)
    unknown = await client.post(
        "/api/auth/enter", json={"code": "ZZZZZZZZ", "class_id": 1}
    )
    assert unknown.status_code == 401
    assert unknown.json()["error"]["code"] == "invalid_access"

    first = rows[0]
    login = await client.post(
        "/api/auth/enter",
        json={"code": first["access_code"], "class_id": int(first["class_id"])},
    )
    assert login.status_code == 200
    await complete_k0(client)
    await enter_t1(client)
    await save_t1_work(client, "Secret product")
    job = await client.post("/api/student/rounds/1/image-jobs", json={})
    assert job.status_code == 200
    job_id = job.json()["job"]["id"]
    await wait_for_job(client, job_id)

    # A second student has a separate client/cookie and cannot read the job.
    student2 = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
    async with student2:
        other = next(row for row in rows if row["participant_id"] != first["participant_id"])
        login2 = await student2.post(
            "/api/auth/enter",
            json={"code": other["access_code"], "class_id": int(other["class_id"])},
        )
        assert login2.status_code == 200
        denied = await student2.get(f"/api/student/image-jobs/{job_id}")
        assert denied.status_code == 404
        denied_file = await student2.get(f"/api/files/keyframes/{job_id}")
        assert denied_file.status_code == 404
        admin_denied = await student2.get("/api/admin/overview")
        assert admin_denied.status_code == 401


async def test_admin_auth_and_protocol_lock(app_client):
    client, app, settings = app_client
    assert (await client.get("/api/admin/overview")).status_code == 401
    bad = await client.post("/api/admin/login", json={"password": "wrong-password"})
    assert bad.status_code == 401
    good = await client.post("/api/admin/login", json={"password": settings.admin_password})
    assert good.status_code == 200
    readiness = await client.get("/api/admin/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["active_protocol"] is not None
    assert readiness.json()["demo_present"] is True

    # Starting a run locks protocol changes.
    await login_student(client, settings)
    activate = await client.post("/api/admin/protocol/activate")
    assert activate.status_code == 409


async def test_server_timer_finalizes_and_blocks_writes(app_client):
    client, app, settings = app_client
    settings.round_duration_seconds = 1
    settings.t1_duration_seconds = 1
    await login_student(client, settings)
    await complete_k0(client)
    await enter_t1(client)
    await asyncio.sleep(1.3)
    state = await client.get("/api/student/state")
    assert state.status_code == 200, state.text
    assert state.json()["stage"] == "k1"
    late_save = await client.put(
        "/api/student/rounds/1/work",
        json={
            "product_name": "late",
            "product_category": "x",
            "target_audience": "x",
            "design_concept": "x",
            "structured_fields": {},
            "open_statement": "",
        },
    )
    assert late_save.status_code == 409


async def test_image_failure_visible_and_retry(app_client):
    client, app, settings = app_client
    await login_student(client, settings)
    await complete_k0(client)
    await enter_t1(client)
    await save_t1_work(client, "Image test product")
    state = app.state.fake_ai_state
    state.fail_image = True
    first = await client.post("/api/student/rounds/1/image-jobs", json={})
    assert first.status_code == 200, first.text
    failed = await wait_for_job(client, first.json()["job"]["id"])
    assert failed["status"] == "failed"
    assert failed["error_message"]
    state.fail_image = False
    retried = await client.post(
        "/api/student/rounds/1/image-jobs",
        json={"retry_of": failed["id"]},
    )
    assert retried.status_code == 200, retried.text
    succeeded = await wait_for_job(client, retried.json()["job"]["id"])
    assert succeeded["status"] == "succeeded"
    assert succeeded["image_url"]


async def test_image_prompt_optimizer_condenses_and_uses_artifact_reference(app_client):
    client, app, settings = app_client
    settings.image_prompt_optimizer_enabled = True
    settings.text_model_vision_enabled = False
    await login_student(client, settings)
    await complete_k0(client)
    await enter_t1(client)
    await save_t1_work(client, "Optimizer product")
    created = await client.post("/api/student/rounds/1/image-jobs", json={})
    assert created.status_code == 200, created.text
    finished = await wait_for_job(client, created.json()["job"]["id"])
    assert finished["status"] == "succeeded"
    assert finished["prompt_optimizer_version"] == "image-opt-v1"
    assert finished["source_prompt"]
    assert finished["prompt"] != finished["source_prompt"]
    assert len(finished["prompt"]) <= 180
    assert finished["reference_image_used"] is True
    payload = app.state.fake_ai_state.last_image_payload
    assert payload is not None
    assert payload["image"].startswith("data:image/")


async def test_code_hash_storage(app_client):
    client, app, settings = app_client
    rows = code_rows(settings)
    db = Database(settings.database_url)
    try:
        async with db.session_factory() as session:
            participants = list((await session.execute(select(Participant))).scalars().all())
        assert len(participants) == 120
        for participant, row in zip(sorted(participants, key=lambda p: p.created_at), rows):
            assert participant.access_code_hmac != row["access_code"]
            assert len(participant.access_code_hmac) == 64
            assert row["access_code"] not in participant.access_code_hmac
    finally:
        await db.dispose()


async def test_concurrent_assessment_get_is_idempotent(app_client):
    client, app, settings = app_client
    await login_student(client, settings)
    first, second = await asyncio.gather(
        client.get("/api/student/instruments/k0"),
        client.get("/api/student/instruments/k0"),
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["instrument"]["kind"] == "k0"
    assert second.json()["instrument"]["kind"] == "k0"


async def test_volcengine_image_payload_fields_are_forwarded(app_client):
    client, app, settings = app_client
    settings.image_model_size = "2K"
    settings.image_model_response_format = "url"
    settings.image_model_watermark = False
    await login_student(client, settings)
    await complete_k0(client)
    await enter_t1(client)
    await save_t1_work(client, "Image payload product")
    created = await client.post("/api/student/rounds/1/image-jobs", json={})
    assert created.status_code == 200, created.text
    fake = app.state.fake_ai_state
    for _ in range(30):
        if fake.image_calls:
            break
        await asyncio.sleep(0.2)
    assert fake.last_image_payload is not None
    payload = fake.last_image_payload
    assert payload["size"] == "2K"
    assert payload["response_format"] == "url"
    assert payload["watermark"] is False
