from __future__ import annotations

from uuid import uuid4

from tests.conftest import complete_k0, enter_t1, login_student


async def test_text_failure_is_recorded_and_retryable(app_client):
    client, app, settings = app_client
    state = app.state.fake_ai_state
    await login_student(client, settings)
    await complete_k0(client)
    await enter_t1(client)
    state.fail_text = True
    failed = await client.post(
        "/api/student/rounds/1/messages",
        json={"content": "This request will fail.", "client_message_id": str(uuid4())},
    )
    assert failed.status_code == 502, failed.text
    messages = await client.get("/api/student/rounds/1/messages")
    assert messages.status_code == 200
    assert messages.json()["messages"][-1]["role"] == "user"
    user_message_id = messages.json()["messages"][-1]["id"]

    admin_login = await client.post(
        "/api/admin/login", json={"password": settings.admin_password}
    )
    assert admin_login.status_code == 200
    # Find the participant through the overview, then inspect recorded error categories.
    overview = await client.get("/api/admin/overview")
    assert overview.status_code == 200
    current = next(row for row in overview.json()["participants"] if row["stage"] == "t1_active")
    detail = await client.get(f"/api/admin/participants/{current['participant_id']}")
    assert detail.status_code == 200
    assert any(error["category"] == "text_ai" for error in detail.json()["api_errors"])
    assert any(call["status"] == "failed" for call in detail.json()["ai_calls"])

    state.fail_text = False
    retried = await client.post(
        f"/api/student/rounds/1/messages/{user_message_id}/retry"
    )
    assert retried.status_code == 200, retried.text
    assert "[TEST STUB]" in retried.json()["messages"][0]["content"]


async def test_deepseek_thinking_toggle_is_forwarded(app_client):
    client, app, settings = app_client
    settings.text_model_thinking = "disabled"
    await login_student(client, settings)
    await complete_k0(client)
    await enter_t1(client)
    sent = await client.post(
        "/api/student/rounds/1/messages",
        json={
            "content": "A payload test.",
            "client_message_id": str(uuid4()),
        },
    )
    assert sent.status_code == 200, sent.text
    payload = app.state.fake_ai_state.last_chat_payload
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["model"] == settings.text_model_name
