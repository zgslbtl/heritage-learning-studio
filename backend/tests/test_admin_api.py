from __future__ import annotations

import json

from tests.conftest import login_student


async def test_admin_code_csv_content_versions_and_detail(app_client):
    client, app, settings = app_client
    login = await client.post("/api/admin/login", json={"password": settings.admin_password})
    assert login.status_code == 200

    codes = await client.get("/api/admin/cohort/codes.csv")
    assert codes.status_code == 200
    assert "access_code" in codes.text
    assert len([line for line in codes.text.splitlines() if line.strip()]) == 121

    artifact = await client.post(
        "/api/admin/artifacts/X/versions",
        data={
            "title": "Updated evidence pack",
            "era": "Test era",
            "artifact_type": "Test type",
            "introduction": "Updated introduction",
            "facts_json": json.dumps(["One fact"]),
            "evidence_json": json.dumps(["One source"]),
            "uncertainty_json": json.dumps(["One uncertainty"]),
        },
    )
    assert artifact.status_code == 200, artifact.text
    assert artifact.json()["artifact"]["version"] == 2
    assert artifact.json()["artifact"]["is_demo"] is False

    instrument_payload = {
        "title": "Updated instrument",
        "instructions": "Updated instructions",
        "questions": [
            {
                "id": "q1",
                "type": "short_text",
                "prompt": "Updated question",
                "required": True,
                "max_length": 150,
            }
        ],
    }
    instrument = await client.post(
        "/api/admin/instruments/k3/versions", json=instrument_payload
    )
    assert instrument.status_code == 200, instrument.text
    assert instrument.json()["instrument"]["version"] == 2

    invalid = await client.post(
        "/api/admin/instruments/k3/versions",
        json={
            "title": "Invalid",
            "instructions": "",
            "questions": [
                {
                    "id": "bad",
                    "type": "single_choice",
                    "prompt": "Needs two options",
                    "required": True,
                    "options": [{"value": "a", "label": "A"}],
                }
            ],
        },
    )
    assert invalid.status_code == 422

    student_client = await login_student(client, settings)
    overview = await client.get("/api/admin/overview")
    assert overview.status_code == 200
    current = next(
        row for row in overview.json()["participants"] if row["stage"] == "k0"
    )
    detail = await client.get(f"/api/admin/participants/{current['participant_id']}")
    assert detail.status_code == 200
    assert detail.json()["participant"]["group"] in ("G1", "G2", "G3", "G4")
    assert detail.json()["participant"]["code_last4"]


async def test_cross_origin_mutation_is_rejected(app_client):
    client, app, settings = app_client
    settings.public_origin = "https://allowed.example"
    response = await client.post(
        "/api/auth/enter",
        headers={"Origin": "https://evil.example"},
        json={"code": "AAAAAAAA", "class_id": 1},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_rejected"
