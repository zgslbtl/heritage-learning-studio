from __future__ import annotations

from sqlalchemy import select

from app.models import Participant
from tests.conftest import complete_k0, enter_t1, save_t1_work


async def _state(client, email: str, class_id: int = 0):
    return await client.post(
        "/api/auth/enter", json={"email": email, "class_id": class_id}
    )


async def test_email_login_gate_unique_email_and_per_class_blocks(app_client):
    client, app, settings = app_client

    rejected = await _state(client, "student@example.com")
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "polyu_email_required"

    first = await _state(client, "  STUDENT0@POLYU.EDU.HK  ")
    assert first.status_code == 200, first.text
    first_participant = first.json()["state"]["participant"]["id"]

    repeated = await _state(client, "student0@polyu.edu.hk")
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["state"]["participant"]["id"] == first_participant

    other_class = await _state(client, "student0@polyu.edu.hk", class_id=1)
    assert other_class.status_code == 409
    assert other_class.json()["error"]["code"] == "email_class_mismatch"

    created = []
    emails = [f"block{index}@polyu.edu.hk" for index in range(1, 8)]
    for email in emails:
        response = await _state(client, email)
        assert response.status_code == 200, response.text
        participant_id = response.json()["state"]["participant"]["id"]
        async with app.state.db.session_factory() as session:
            participant = await session.get(Participant, participant_id)
            assert participant is not None
            assert participant.email == email
            assert participant.access_code_hmac is None
            created.append(participant.group_name)

    async with app.state.db.session_factory() as session:
        rows = list(
            (
                await session.execute(
                    select(Participant)
                    .where(Participant.class_id == 0)
                    .order_by(Participant.created_at, Participant.id)
                )
            ).scalars()
        )
    assert len(rows) == 8
    assert all(participant.email for participant in rows)
    groups = [participant.group_name for participant in rows]
    assert set(groups) <= {"G1", "G2", "G3", "G4"}
    assert len(groups) == 8
    assert created == groups[1:]


async def test_polyu_email_can_complete_k0_and_t1(app_client):
    client, app, settings = app_client
    entered = await client.post(
        "/api/auth/enter",
        json={"email": "flow.student@polyu.edu.hk", "class_id": 0},
    )
    assert entered.status_code == 200, entered.text
    assert entered.json()["state"]["stage"] == "k0"
    await complete_k0(client)
    await enter_t1(client)
    await save_t1_work(client, "Email flow product")
    finished = await client.post("/api/student/rounds/1/finish")
    assert finished.status_code == 200, finished.text
    assert finished.json()["state"]["stage"] == "k1"
