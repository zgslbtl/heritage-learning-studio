from __future__ import annotations

import asyncio
import io
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
import zipfile

import httpx
import pytest
from sqlalchemy import select

from app.errors import AppError
from app.models import RuntimeTask
from app.services.storage import Storage, safe_key
from tests.conftest import reach_t2_active, save_t2_work, submit_assessment, enter_t1, complete_k0, save_t1_work


async def enter_beta(app, email):
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
    response = await client.post("/api/auth/enter", json={"email": email, "class_id": 0})
    assert response.status_code == 200, response.text
    return client, response.json()


async def finish_beta_creation(client):
    await reach_t2_active(client)
    await save_t2_work(client)
    response = await client.post("/api/student/rounds/2/finish")
    assert response.status_code == 200, response.text
    await submit_assessment(client, "k3", {"k3_text": "K3 beta"})
    await submit_assessment(client, "survey", {"survey": 4})


async def test_beta_entry_rule_and_server_side_class_restriction(app_client):
    client, app, settings = app_client
    settings.deployment_mode = "beta"
    config = (await client.get("/api/auth/config")).json()
    assert [item["id"] for item in config["classes"]] == [0]
    denied = await client.post("/api/auth/enter", json={"email": "user@example.com", "class_id": 0})
    assert denied.status_code == 403
    denied = await client.post("/api/auth/enter", json={"email": "POLYU-user", "class_id": 1})
    assert denied.status_code == 401
    first = await client.post("/api/auth/enter", json={"email": "  POLYU-user  ", "class_id": 0})
    assert first.status_code == 200, first.text
    again = await client.post("/api/auth/enter", json={"email": "polyu-user", "class_id": 0})
    assert again.json()["state"]["participant"]["id"] == first.json()["state"]["participant"]["id"]
    await client.post("/api/admin/login", json={"password": settings.admin_password})
    bad_link = await client.post("/api/admin/class-links", json={"class_id": 1})
    assert bad_link.status_code == 404
    link = await client.post("/api/admin/class-links", json={"class_id": 0})
    assert link.status_code == 200, link.text
    assert (await client.get("/api/auth/class-link", params={"token": link.json()["token"]})).json()["class_id"] == 0


@pytest.mark.parametrize("deployment_mode", ["beta", "study"])
async def test_class_zero_continuous_entry_and_frozen_individual_snapshots(app_client, deployment_mode):
    _client, app, settings = app_client
    settings.deployment_mode = deployment_mode
    first, _ = await enter_beta(app, "first-polyu")
    second = third = None
    try:
        await finish_beta_creation(first)
        empty = await first.get("/api/student/peer-assessment")
        assert empty.status_code == 200, empty.text
        assert empty.json()["waiting"] is False
        assert empty.json()["total"] == 0
        empty_batch = empty.json()["batch"]["id"]
        # A later participant is allowed even after the first person's gate opened.
        second, _ = await enter_beta(app, "second-polyu")
        await finish_beta_creation(second)
        second_peer = (await second.get("/api/student/peer-assessment")).json()
        assert second_peer["total"] == 2
        second_assignments = second_peer["assignments"]
        repeated_first = (await first.get("/api/student/peer-assessment")).json()
        assert repeated_first["batch"]["id"] == empty_batch
        assert repeated_first["total"] == 0
        third, _ = await enter_beta(app, "third-polyu")
        await finish_beta_creation(third)
        assert (await third.get("/api/student/peer-assessment")).json()["total"] == 4
        assert (await second.get("/api/student/peer-assessment")).json()["assignments"] == second_assignments
        assert (await first.post("/api/student/peer-assessment/complete")).status_code == 200
        feed = (await first.get("/api/student/social-feed")).json()
        assert len(feed["works"]) == 6
        assert {work["round_no"] for work in feed["works"]} == {1, 2}
    finally:
        await first.aclose()
        if second: await second.aclose()
        if third: await third.aclose()


@pytest.mark.parametrize("deployment_mode,expected", [("study", [0, 1, 2, 3, 4]), ("beta", [0])])
async def test_production_class_bootstrap_and_entry_config(settings, deployment_mode, expected):
    from app.bootstrap import bootstrap_cohort
    from app.db import Base, Database
    from app.main import create_app
    from app.models import ClassGroup

    settings.environment = "production"
    settings.deployment_mode = deployment_mode
    settings.auth_mode = "email"
    settings.cookie_secure = True
    settings.public_origin = "https://testserver"
    settings.auto_bootstrap = False
    db = Database(settings.database_url)
    app = None
    try:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with db.session_factory() as session:
            await bootstrap_cohort(session, settings)
            assert list((await session.execute(select(ClassGroup.id).order_by(ClassGroup.id))).scalars()) == expected
        app = create_app(settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://testserver") as client:
            config = (await client.get("/api/auth/config")).json()
            assert [item["id"] for item in config["classes"]] == expected
        assert all(settings.class_allowed(class_id) == (class_id in expected) for class_id in range(6))
    finally:
        if app:
            await app.state.db.dispose()
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await db.dispose()


async def test_login_limit_is_shared_between_app_instances(app_client):
    client, app, settings = app_client
    from app.main import create_app
    other = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=other), base_url="http://testserver") as second:
        for index in range(6):
            chosen = client if index % 2 else second
            assert (await chosen.post("/api/admin/login", json={"password": "wrong"})).status_code == 401
        assert (await second.post("/api/admin/login", json={"password": settings.admin_password})).status_code == 429
    await other.state.db.dispose()


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Vercel task runtime uses Python 3.12")
async def test_cloud_image_duplicate_delivery_does_not_regenerate(app_client):
    client, app, settings = app_client
    settings.deployment_mode = "beta"
    await app.state.image_worker.stop()
    settings.queue_backend = "vercel"
    await client.post("/api/auth/enter", json={"email": "image-polyu", "class_id": 0})
    await complete_k0(client)
    await enter_t1(client)
    await save_t1_work(client)
    response = await client.post("/api/student/rounds/1/image-jobs", json={})
    assert response.status_code == 200, response.text
    task_id = uuid.UUID(response.json()["job"]["id"])
    from app.services.cloud_tasks import execute_task
    await execute_task(task_id, settings, app.state.db)
    await execute_task(task_id, settings, app.state.db)
    job = (await client.get(f"/api/student/image-jobs/{task_id}")).json()["job"]
    assert job["status"] == "succeeded", job
    assert app.state.fake_ai_state.image_calls == 1
    async with app.state.db.session_factory() as session:
        task = await session.get(RuntimeTask, task_id)
        assert task.status == "succeeded"
        assert task.checkpoint["provider_result_key"]


def test_storage_rejects_traversal_and_preserves_local_bytes(tmp_path):
    from app.config import Settings
    storage = Storage(Settings(_env_file=None, data_dir=tmp_path))
    for key in ("../secret", "/secret", "a/../../x", "https://example.org/x", "a\\b"):
        with pytest.raises(AppError): safe_key(key)
    storage.put_bytes("keyframes/test.png", b"example", "image/png")
    assert storage.read_bytes("keyframes/test.png") == b"example"


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Vercel task runtime uses Python 3.12")
@pytest.mark.parametrize("saved_result", [True, False])
async def test_interrupted_provider_is_recovered_without_second_charge(app_client, saved_result):
    client, app, settings = app_client
    settings.deployment_mode = "beta"
    await app.state.image_worker.stop()
    settings.queue_backend = "vercel"
    await client.post("/api/auth/enter", json={"email": "recovery-polyu", "class_id": 0})
    await complete_k0(client)
    await enter_t1(client)
    await save_t1_work(client)
    response = await client.post("/api/student/rounds/1/image-jobs", json={})
    task_id = uuid.UUID(response.json()["job"]["id"])
    async with app.state.db.session_factory() as session:
        task = await session.get(RuntimeTask, task_id)
        task.status = "running"
        task.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        task.checkpoint = {"provider_started": True, "optimized_prompt": "synthetic recovery test"}
        await session.commit()
    if saved_result:
        from tests.conftest import demo_image
        Storage(settings).put_bytes(f"provider-results/{task_id}.bin", demo_image(), "application/octet-stream")
    from app.services.cloud_tasks import execute_task
    await execute_task(task_id, settings, app.state.db)
    job = (await client.get(f"/api/student/image-jobs/{task_id}")).json()["job"]
    assert job["status"] == ("succeeded" if saved_result else "failed")
    if not saved_result:
        assert job["error_code"] == "image_result_uncertain"
    assert app.state.fake_ai_state.image_calls == 0


@pytest.mark.skipif(sys.version_info < (3, 10), reason="Official Queue SDK requires Python 3.10+")
async def test_explicit_queue_callback_uses_cloudevent_queue_name(monkeypatch):
    from app import queue_consumer
    called = []

    async def accept(body, headers, lease_duration):
        called.append((body, headers["ce-vqsqueuename"], lease_duration))

    monkeypatch.setattr(queue_consumer, "accept_and_handle", accept)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=queue_consumer.app), base_url="http://testserver") as client:
        assert (await client.post("/", content=b"{}" )).status_code == 400
        response = await client.post("/", content=b"{}", headers={
            "ce-vqsconsumergroup": "test_callback", "ce-vqsqueuename": "heritage-beta-tasks",
        })
        assert response.status_code == 204
        assert called == [(b"{}", "heritage-beta-tasks", 300)]


async def test_sent_outbox_poll_releases_its_database_lock(app_client):
    _client, app, settings = app_client
    settings.queue_backend = "vercel"
    task_id = uuid.uuid4()
    async with app.state.db.session_factory() as session:
        session.add(RuntimeTask(id=task_id, kind="image", status="queued", dispatch_state="sent",
                                payload={}, checkpoint={}))
        await session.commit()
        from app.services.cloud_tasks import dispatch_task
        await dispatch_task(session, settings, task_id)
        assert not session.in_transaction()
        async with app.state.db.session_factory() as other:
            found = (await other.execute(select(RuntimeTask).where(RuntimeTask.id == task_id).with_for_update(nowait=True))).scalar_one()
            assert found.dispatch_state == "sent"
