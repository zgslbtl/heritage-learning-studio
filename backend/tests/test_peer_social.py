from __future__ import annotations

import httpx

from tests.conftest import code_rows, reach_t2_active, save_t2_work, submit_assessment


async def _student(app, row):
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver", timeout=20
    )
    entered = await client.post(
        "/api/auth/enter",
        json={"code": row["access_code"], "class_id": int(row["class_id"])},
    )
    assert entered.status_code == 200, entered.text
    await reach_t2_active(client)
    await save_t2_work(client)
    return client


async def test_peer_assignment_and_social_interactions(app_client):
    client, app, settings = app_client
    rows = code_rows(settings)
    first_row, second_row = rows[0], rows[1]
    first = await _student(app, first_row)
    second = await _student(app, second_row)
    try:
        first_finish = await first.post("/api/student/rounds/2/finish")
        assert first_finish.status_code == 200, first_finish.text
        second_finish = await second.post("/api/student/rounds/2/finish")
        assert second_finish.status_code == 200, second_finish.text
        for reviewer in (first, second):
            await submit_assessment(reviewer, "k3", {"k3_text": "K3 answer"})
            await submit_assessment(reviewer, "survey", {"survey": 4})
        first_peer = await first.get("/api/student/peer-assessment")
        second_peer = await second.get("/api/student/peer-assessment")
        assert first_peer.status_code == 200, first_peer.text
        assert second_peer.status_code == 200, second_peer.text
        first_payload = first_peer.json()
        second_payload = second_peer.json()
        assert first_payload["total"] == 1
        assert second_payload["total"] == 1
        first_assignment = first_payload["assignments"][0]
        second_assignment = second_payload["assignments"][0]
        assert first_assignment["assignment_id"] != second_assignment["assignment_id"]
        assert first_assignment["work_code"]

        impression = await first.post(
            f"/api/student/peer-assessment/{first_assignment['assignment_id']}/impression",
            json={"viewed_ms": 1200},
        )
        assert impression.status_code == 200, impression.text
        assert impression.json()["viewed_ms"] == 1200
        impression_again = await first.post(
            f"/api/student/peer-assessment/{first_assignment['assignment_id']}/impression",
            json={"viewed_ms": 800},
        )
        assert impression_again.status_code == 200, impression_again.text
        assert impression_again.json()["viewed_ms"] == 1200

        submitted = await first.post(
            f"/api/student/peer-assessment/{first_assignment['assignment_id']}",
            json={
                "scores": {"clarity": 4, "evidence_link": 3, "attraction": 5},
                "comment": "Clear cultural idea.",
            },
        )
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["submitted"] == 1
        assert submitted.json()["completed"] is True

        # The other reviewer still has to submit before continuing.
        incomplete = await first.post("/api/student/peer-assessment/complete")
        assert incomplete.status_code == 200
        # First is now in social_feed; second is still in peer_assessment.
        second_submit = await second.post(
            f"/api/student/peer-assessment/{second_assignment['assignment_id']}",
            json={"scores": {"clarity": 5, "evidence_link": 4, "attraction": 4}},
        )
        assert second_submit.status_code == 200, second_submit.text
        second_complete = await second.post("/api/student/peer-assessment/complete")
        assert second_complete.status_code == 200, second_complete.text

        feed = await first.get("/api/student/social-feed")
        assert feed.status_code == 200, feed.text
        works = feed.json()["works"]
        assert len(works) == 2
        own = next(work for work in works if work["is_own"])
        other = next(work for work in works if not work["is_own"])
        own_like = await first.post(f"/api/student/social/works/{own['work_id']}/like")
        assert own_like.status_code == 403
        own_comment = await first.post(
            f"/api/student/social/works/{own['work_id']}/comment",
            json={"content": "self comment"},
        )
        assert own_comment.status_code == 403
        liked = await first.post(f"/api/student/social/works/{other['work_id']}/like")
        assert liked.status_code == 200, liked.text
        assert liked.json()["liked"] is True
        unliked = await first.post(f"/api/student/social/works/{other['work_id']}/like")
        assert unliked.json()["liked"] is False
        comment = await first.post(
            f"/api/student/social/works/{other['work_id']}/comment",
            json={"content": "Specific and respectful comment."},
        )
        assert comment.status_code == 200, comment.text
        completed = await first.post("/api/student/social/complete")
        assert completed.status_code == 200, completed.text
        assert completed.json()["state"]["stage"] == "complete"
    finally:
        await first.aclose()
        await second.aclose()
