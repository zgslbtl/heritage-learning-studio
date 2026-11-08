from __future__ import annotations

import asyncio
import csv
import io
import json
import zipfile
from uuid import uuid4

from tests.conftest import (
    code_rows,
    complete_k0,
    enter_t1,
    finish_peer_and_social,
    login_student,
    reach_t2_active,
    save_t1_work,
    save_t2_work,
    submit_assessment,
)


async def wait_for_job(client, job_id, timeout=15.0):
    deadline = asyncio.get_event_loop().time() + timeout
    last = None
    while asyncio.get_event_loop().time() < deadline:
        response = await client.get(f"/api/student/image-jobs/{job_id}")
        assert response.status_code == 200, response.text
        job = response.json()["job"]
        last = job
        if job["status"] in ("succeeded", "failed"):
            return job
        await asyncio.sleep(0.4)
    raise AssertionError(f"job did not finish: {last}")


async def test_full_v15_flow_and_admin_export(app_client):
    client, app, settings = app_client
    rows = code_rows(settings)
    row = next(item for item in rows if item["group"] in ("G3", "G4"))
    entered = await client.post(
        "/api/auth/enter",
        json={"code": row["access_code"], "class_id": int(row["class_id"])},
    )
    assert entered.status_code == 200, entered.text
    assert entered.json()["state"]["stage"] == "k0"
    assert entered.json()["state"]["total_steps"] == 6
    participant_id = entered.json()["state"]["participant"]["id"]
    assert "group" not in json.dumps(entered.json()).lower()
    assert "condition" not in json.dumps(entered.json()).lower()

    # K0
    instrument = await client.get("/api/student/instruments/k0")
    assert instrument.status_code == 200, instrument.text
    await complete_k0(client)
    state = await client.get("/api/student/state")
    assert state.json()["stage"] == "tutorial"

    # Tutorial -> T1
    tutorial = await client.post("/api/student/tutorial/complete")
    assert tutorial.status_code == 200, tutorial.text
    assert tutorial.json()["state"]["stage"] == "t1_ready"
    start = await client.post("/api/student/rounds/1/start")
    assert start.status_code == 200, start.text
    assert start.json()["state"]["stage"] == "t1_active"
    assert start.json()["round"]["task"] == "T1"
    assert start.json()["round"]["guide"] is not None
    assert start.json()["round"]["work"]["revision"] == 0

    messages = await client.get("/api/student/rounds/1/messages")
    assert messages.status_code == 200
    initial = messages.json()["messages"]
    assert initial and initial[0]["source"] == "hlsf_prompt"
    assert "先看看左侧的文物图" in initial[0]["content"]

    chat = await client.post(
        "/api/student/rounds/1/messages",
        json={
            "content": "Please help me understand the cultural features.",
            "client_message_id": str(uuid4()),
        },
    )
    assert chat.status_code == 200, chat.text
    assert "[TEST STUB]" in chat.json()["messages"][-1]["content"]

    await save_t1_work(client, "T1 test product")
    work = await client.get("/api/student/rounds/1")
    assert work.json()["work"]["revision"] == 1
    assert work.json()["work"]["structured_fields"]["cultural_features"]

    image_response = await client.post("/api/student/rounds/1/image-jobs", json={})
    assert image_response.status_code == 200, image_response.text
    assert "studio product shot" in image_response.json()["job"]["prompt"]
    assert image_response.json()["job"]["work_revision_no"] == 1
    job = await wait_for_job(client, image_response.json()["job"]["id"])
    assert job["status"] == "succeeded", job
    image = await client.get(job["image_url"])
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/png")

    finished = await client.post("/api/student/rounds/1/finish")
    assert finished.status_code == 200, finished.text
    assert finished.json()["state"]["stage"] == "k1"

    # K1 -> K2
    await submit_assessment(client, "k1", {"k1_text": "K1 independent answer"})
    await submit_assessment(client, "k2", {"k2_multi": ["x"]})
    state = await client.get("/api/student/state")
    assert state.json()["stage"] == "t2_ready"

    # T2: Standard AI, no HLSF
    start2 = await client.post("/api/student/rounds/2/start")
    assert start2.status_code == 200, start2.text
    assert start2.json()["state"]["stage"] == "t2_active"
    assert start2.json()["round"]["task"] == "T2"
    assert start2.json()["round"]["guide"] is None
    messages2 = await client.get("/api/student/rounds/2/messages")
    assert messages2.status_code == 200
    assert messages2.json()["messages"] == []
    hlsf_for_t2 = await client.post(
        "/api/student/rounds/2/hlsf/advance",
        json={"from_phase": "observe", "skip": False},
    )
    assert hlsf_for_t2.status_code == 404

    await save_t2_work(client, "T2 transfer product")
    image2 = await client.post("/api/student/rounds/2/image-jobs", json={})
    assert image2.status_code == 200, image2.text
    assert (await wait_for_job(client, image2.json()["job"]["id"]))["status"] == "succeeded"
    finish2 = await client.post(
        "/api/student/rounds/2/finish",
        json={"consent_future_research": True},
    )
    assert finish2.status_code == 200, finish2.text
    assert finish2.json()["state"]["stage"] == "k3"

    # K3 -> survey -> peer -> social -> complete
    await submit_assessment(client, "k3", {"k3_text": "K3 answer"})
    await submit_assessment(client, "survey", {"survey": 4})
    state = await client.get("/api/student/state")
    assert state.json()["stage"] == "peer_assessment"
    peer = await client.get("/api/student/peer-assessment")
    assert peer.status_code == 200, peer.text
    await finish_peer_and_social(client)
    state = await client.get("/api/student/state")
    assert state.json()["stage"] == "complete"
    assert state.json()["completed"] is True

    admin_login = await client.post(
        "/api/admin/login", json={"password": settings.admin_password}
    )
    assert admin_login.status_code == 200, admin_login.text
    overview = await client.get("/api/admin/overview")
    assert overview.status_code == 200, overview.text
    assert overview.json()["counts"]["participants"] == 120
    assert overview.json()["counts"]["completed"] == 1
    detail = await client.get(f"/api/admin/participants/{participant_id}")
    assert detail.status_code == 200, detail.text
    actions = {event["action"] for event in detail.json()["hlsf_events"]}
    assert "prompt_delivered" in actions
    assert "student_message" in actions
    assert "assistant_reply" in actions
    assert len(detail.json()["works"]) == 2
    t1_work = next(work for work in detail.json()["works"] if work["round_no"] == 1)
    assert t1_work["structured_fields"]["cultural_features"]

    exported = await client.get("/api/admin/export")
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("application/zip")
    archive = zipfile.ZipFile(io.BytesIO(exported.content))
    names = set(archive.namelist())
    runs_csv = list(
        csv.DictReader(io.StringIO(archive.read("runs.csv").decode("utf-8-sig")))
    )
    assert runs_csv
    assert runs_csv[0]["consent_future_research"] in ("True", "true", "1")
    assert runs_csv[0]["consent_version"] == "work-submit-v1"
    assert runs_csv[0]["design_version"] == "crossover-v1.0-pilot"
    assert runs_csv[0]["hlsf_prompt_version"] == "hlsf-v1.10-evidence-reading-pilot"
    assert runs_csv[0]["condition_sequence"] in ("AB", "BA")
    assert runs_csv[0]["artifact_sequence"] in ("XY", "YX")
    filtered = await client.get(
        "/api/admin/analysis.csv",
        params={
            "class_id": row["class_id"],
            "group": row["group"],
            "ai_condition": "B",
        },
    )
    assert filtered.status_code == 200, filtered.text
    filtered_rows = list(
        csv.DictReader(io.StringIO(filtered.content.decode("utf-8-sig")))
    )
    assert filtered_rows
    assert all(item["group_id"] == row["group"] for item in filtered_rows)
    assert all(item["ai_condition"] == "B" for item in filtered_rows)
    analysis_csv = list(
        csv.DictReader(io.StringIO(archive.read("analysis.csv").decode("utf-8-sig")))
    )
    assert analysis_csv
    assert analysis_csv[0]["group_id"] in ("G1", "G2", "G3", "G4")
    assert analysis_csv[0]["ai_condition"] in ("A", "B")
    assert analysis_csv[0]["artifact_slot"] in ("X", "Y")
    assert "peer_rating_count" in analysis_csv[0]
    assert "peer_review_version" in analysis_csv[0]
    assert "peer_cultural_clarity_mean" in analysis_csv[0]
    assert "peer_cultural_translation_mean" in analysis_csv[0]
    assert "peer_design_originality_mean" in analysis_csv[0]
    assert "peer_overall_mean" not in analysis_csv[0]
    for required in (
        "participants.csv",
        "analysis.csv",
        "runs.csv",
        "rounds.csv",
        "messages.csv",
        "work_revisions.csv",
        "image_jobs.csv",
        "assessments.csv",
        "peer_batches.csv",
        "peer_assignments.csv",
        "peer_ratings.csv",
        "peer_work_scores.csv",
        "social_likes.csv",
        "social_comments.csv",
        "social_events.csv",
        "manifest.json",
    ):
        assert required in names, required
    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["participants"] == 120
    assert manifest["work_revisions"] >= 2
    assert manifest["image_jobs"] >= 2
    all_text = "\n".join(
        archive.read(name).decode("utf-8", errors="ignore")
        for name in names
        if name.endswith(".csv") or name.endswith(".json")
    )
    assert "test-text-key" not in all_text
    assert row["access_code"] not in all_text
    work_files = [name for name in names if name.startswith("files/") and "/work-" in name]
    assert len(work_files) >= 2


async def test_portfolio_payload_contains_both_own_rounds(app_client):
    client, app, settings = app_client
    rows = code_rows(settings)
    row = next(item for item in rows if item["group"] in ("G3", "G4"))
    entered = await client.post(
        "/api/auth/enter",
        json={"code": row["access_code"], "class_id": int(row["class_id"])},
    )
    assert entered.status_code == 200, entered.text
    await reach_t2_active(client)
    await save_t2_work(client, "Portfolio T2")
    finish2 = await client.post(
        "/api/student/rounds/2/finish",
        json={"consent_future_research": True},
    )
    assert finish2.status_code == 200, finish2.text
    await submit_assessment(client, "k3", {"k3_text": "K3 answer"})
    await submit_assessment(client, "survey", {"survey": 4})
    peer = await client.post("/api/student/peer-assessment/complete")
    assert peer.status_code == 200, peer.text
    social = await client.get("/api/student/social-feed")
    assert social.status_code == 200, social.text
    portfolio = await client.get("/api/student/portfolio")
    assert portfolio.status_code == 200, portfolio.text
    payload = portfolio.json()
    assert len(payload["works"]) == 2
    assert {item["round_no"] for item in payload["works"]} == {1, 2}
    assert all("statement" in item for item in payload["works"])


async def test_hlsf_v15_completion_and_hint_limit(app_client):
    client, app, settings = app_client
    rows = code_rows(settings)
    row = next(item for item in rows if item["group"] in ("G3", "G4"))
    response = await client.post(
        "/api/auth/enter",
        json={"code": row["access_code"], "class_id": int(row["class_id"])},
    )
    assert response.status_code == 200
    await complete_k0(client)
    await enter_t1(client)

    hint = await client.post(
        "/api/student/rounds/1/hlsf/hint", json={"phase": "observe"}
    )
    assert hint.status_code == 200, hint.text
    assert hint.json()["guide"]["hint_used"] is True
    assert hint.json()["guide"]["version"] == "hlsf-v1.10-evidence-reading-pilot"
    hint_again = await client.post(
        "/api/student/rounds/1/hlsf/hint", json={"phase": "observe"}
    )
    assert hint_again.status_code == 409

    for index, phase in enumerate(("observe", "explain", "create", "reflect")):
        advanced = await client.post(
            "/api/student/rounds/1/hlsf/advance",
            json={"from_phase": phase, "skip": index == 1},
        )
        assert advanced.status_code == 200, advanced.text
        guide = advanced.json()["guide"]
        if index < 3:
            assert guide["phase"] == ("explain", "create", "reflect")[index]
            assert len(advanced.json()["messages"]) == 1
        else:
            assert guide["phase"] == "complete"
    completed = await client.get("/api/student/rounds/1/messages")
    assert completed.status_code == 200
    assert any("文创设计" in message["content"] for message in completed.json()["messages"])


async def test_multiple_generated_images_and_select_one(app_client):
    client, app, settings = app_client
    await login_student(client, settings)
    await complete_k0(client)
    await enter_t1(client)
    await save_t1_work(client, "Gallery product")

    first = await client.post("/api/student/rounds/1/image-jobs", json={})
    assert first.status_code == 200, first.text
    first_job = await wait_for_job(client, first.json()["job"]["id"])
    assert first_job["status"] == "succeeded"

    second = await client.post("/api/student/rounds/1/image-jobs", json={})
    assert second.status_code == 200, second.text
    second_job = await wait_for_job(client, second.json()["job"]["id"])
    assert second_job["status"] == "succeeded"

    round_payload = (await client.get("/api/student/rounds/1")).json()
    assert len([job for job in round_payload["image_jobs"] if job["status"] == "succeeded"]) == 2
    assert round_payload["selected_image_job_id"] == first_job["id"]

    selected = await client.post(
        f"/api/student/rounds/1/image-jobs/{second_job['id']}/select"
    )
    assert selected.status_code == 200, selected.text
    round_after = (await client.get("/api/student/rounds/1")).json()
    assert round_after["selected_image_job_id"] == second_job["id"]
