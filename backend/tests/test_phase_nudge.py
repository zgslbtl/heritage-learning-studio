from __future__ import annotations

import httpx

from tests.conftest import code_rows, complete_k0, enter_t1


async def _enter(client, settings, groups):
    rows = code_rows(settings)
    row = next(item for item in rows if item["group"] in groups)
    entered = await client.post(
        "/api/auth/enter",
        json={"code": row["access_code"], "class_id": int(row["class_id"])},
    )
    assert entered.status_code == 200, entered.text
    return entered.json()["state"]["participant"]["id"]


async def test_b_phase_nudge_events_are_recorded(app_client):
    client, app, settings = app_client
    participant_id = await _enter(client, settings, {"G3", "G4"})
    await complete_k0(client)
    await enter_t1(client)

    shown = await client.post(
        "/api/student/rounds/1/hlsf/nudge",
        json={"action": "shown", "phase": "observe", "user_turns": 3},
    )
    assert shown.status_code == 200, shown.text
    assert shown.json()["recorded"] is True

    advanced = await client.post(
        "/api/student/rounds/1/hlsf/nudge",
        json={"action": "advance", "phase": "observe", "user_turns": 3},
    )
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["recorded"] is True

    admin = await client.post("/api/admin/login", json={"password": settings.admin_password})
    assert admin.status_code == 200, admin.text
    detail = await client.get(f"/api/admin/participants/{participant_id}")
    assert detail.status_code == 200, detail.text
    actions = [event["action"] for event in detail.json()["hlsf_events"]]
    assert "nudge_shown" in actions
    assert "nudge_advance" in actions
    meta = next(
        event["meta"]
        for event in detail.json()["hlsf_events"]
        if event["action"] == "nudge_shown"
    )
    assert meta["user_turns"] == 3


async def test_phase_nudge_ignores_stale_phase(app_client):
    client, _app, settings = app_client
    await _enter(client, settings, {"G3", "G4"})
    await complete_k0(client)
    await enter_t1(client)

    stale = await client.post(
        "/api/student/rounds/1/hlsf/nudge",
        json={"action": "dismissed", "phase": "explain", "user_turns": 4},
    )
    assert stale.status_code == 200, stale.text
    assert stale.json()["recorded"] is False


async def test_phase_nudge_is_b_only(app_client):
    client, _app, settings = app_client
    await _enter(client, settings, {"G1", "G2"})
    await complete_k0(client)
    await enter_t1(client)

    response = await client.post(
        "/api/student/rounds/1/hlsf/nudge",
        json={"action": "shown", "phase": "observe", "user_turns": 3},
    )
    assert response.status_code == 404


async def test_phase_nudge_rejects_unknown_action(app_client):
    client, _app, settings = app_client
    await _enter(client, settings, {"G3", "G4"})
    await complete_k0(client)
    await enter_t1(client)

    response = await client.post(
        "/api/student/rounds/1/hlsf/nudge",
        json={"action": "exploded", "phase": "observe", "user_turns": 3},
    )
    assert response.status_code == 422
