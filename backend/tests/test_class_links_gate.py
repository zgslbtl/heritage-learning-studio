from __future__ import annotations

import httpx
from sqlalchemy import func, select

from app.models import PeerBatch
from tests.conftest import reach_t2_active, save_t2_work, submit_assessment


async def _email_student(app, email: str, class_token: str):
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver", timeout=20
    )
    entered = await client.post(
        "/api/auth/enter",
        json={"email": email, "class_id": 1, "class_token": class_token},
    )
    assert entered.status_code == 200, entered.text
    return client, entered


async def test_class_link_binding_and_dynamic_auto_gate(app_client):
    client, app, settings = app_client
    admin = await client.post("/api/admin/login", json={"password": settings.admin_password})
    assert admin.status_code == 200, admin.text
    created = await client.post("/api/admin/class-links", json={"class_id": 1, "label": "class 1"})
    assert created.status_code == 200, created.text
    token = created.json()["token"]
    assert created.json()["url"].endswith(token)

    resolved = await client.get(f"/api/auth/class-link?token={token}")
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["class_id"] == 1

    mismatch = await client.post(
        "/api/auth/enter",
        json={"email": "mismatch@polyu.edu.hk", "class_id": 2, "class_token": token},
    )
    assert mismatch.status_code == 401
    assert mismatch.json()["error"]["code"] == "invalid_class_link"

    first, first_enter = await _email_student(app, "gate.one@polyu.edu.hk", token)
    second, _ = await _email_student(app, "gate.two@polyu.edu.hk", token)
    try:
        await reach_t2_active(first)
        await save_t2_work(first)
        await reach_t2_active(second)
        await save_t2_work(second)

        first_finish = await first.post("/api/student/rounds/2/finish")
        assert first_finish.status_code == 200, first_finish.text
        await submit_assessment(first, "k3", {"k3_text": "K3 one"})
        await submit_assessment(first, "survey", {"survey": 4})
        waiting = await first.get("/api/student/peer-assessment")
        assert waiting.status_code == 200, waiting.text
        assert waiting.json()["waiting"] is True
        assert waiting.json()["total"] == 0
        async with app.state.db.session_factory() as session:
            count = (
                await session.execute(
                    select(func.count()).select_from(PeerBatch)
                )
            ).scalar_one()
            assert count == 0

        second_finish = await second.post("/api/student/rounds/2/finish")
        assert second_finish.status_code == 200, second_finish.text
        await submit_assessment(second, "k3", {"k3_text": "K3 two"})
        await submit_assessment(second, "survey", {"survey": 4})
        opened = await first.get("/api/student/peer-assessment")
        assert opened.status_code == 200, opened.text
        assert opened.json()["waiting"] is False
        assert opened.json()["gate"]["status"] == "open"
        assert opened.json()["total"] == 2
        assert opened.json()["gate"]["valid_work_count"] == 4
        second_opened = await second.get("/api/student/peer-assessment")
        assert second_opened.status_code == 200, second_opened.text
        assert second_opened.json()["total"] == 2

        # The class is closed to new email accounts once the batch is frozen.
        late = await client.post(
            "/api/auth/enter",
            json={"email": "late@polyu.edu.hk", "class_id": 1, "class_token": token},
        )
        assert late.status_code == 409
        assert late.json()["error"]["code"] == "class_closed"

        gates = await client.get("/api/admin/class-peer-gates")
        assert gates.status_code == 200, gates.text
        class_one = next(item for item in gates.json()["classes"] if item["class_id"] == 1)
        assert class_one["status"] == "open"
        assert class_one["entered"] >= 2
        assert class_one["batch_id"]
    finally:
        await first.aclose()
        await second.aclose()


async def test_class_link_revoke(app_client):
    client, app, settings = app_client
    admin = await client.post("/api/admin/login", json={"password": settings.admin_password})
    assert admin.status_code == 200
    created = await client.post("/api/admin/class-links", json={"class_id": 2})
    link_id = created.json()["link"]["id"]
    token = created.json()["token"]
    assert (await client.get(f"/api/auth/class-link?token={token}")).status_code == 200
    revoked = await client.post(f"/api/admin/class-links/{link_id}/revoke")
    assert revoked.status_code == 200, revoked.text
    assert (await client.get(f"/api/auth/class-link?token={token}")).status_code == 401
