from __future__ import annotations

import csv
import io
import json
import zipfile

import httpx

from app.services.export import build_export
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
        assert first_payload["total"] == 2
        assert second_payload["total"] == 2
        first_assignment = first_payload["assignments"][0]
        second_assignment = second_payload["assignments"][0]
        assert {item["round_no"] for item in first_payload["assignments"]} == {1, 2}
        assert {item["round_no"] for item in second_payload["assignments"]} == {1, 2}
        assert first_assignment["assignment_id"] != second_assignment["assignment_id"]
        assert first_assignment["work_code"]
        assert first_payload["review"]["version"] == "peer-review-v2.1-pilot"
        assert [dimension["key"] for dimension in first_payload["review"]["dimensions"]] == [
            "cultural_clarity",
            "cultural_translation",
            "design_originality",
        ]
        assert all(item.get("artifact_title") for item in first_payload["assignments"])
        assert all(item.get("artifact_introduction") for item in first_payload["assignments"])
        serialized_payload = json.dumps(first_payload, ensure_ascii=False)
        for hidden in ("reviewer_participant_id", "reviewed_student_id", "group_name", "ai_condition"):
            assert hidden not in serialized_payload

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
                "scores": {
                    "cultural_clarity": 4,
                    "cultural_translation": 3,
                    "design_originality": 5,
                },
                "comment": "Clear cultural idea.",
            },
        )
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["submitted"] == 1
        assert submitted.json()["completed"] is False
        for assignment in first_payload["assignments"][1:]:
            response = await first.post(
                f"/api/student/peer-assessment/{assignment['assignment_id']}",
                json={
                    "scores": {
                        "cultural_clarity": 4,
                        "cultural_translation": 4,
                        "design_originality": 4,
                    },
                    "comment": "Useful design link.",
                },
            )
            assert response.status_code == 200, response.text
        assert response.json()["submitted"] == 2
        assert response.json()["completed"] is True

        incomplete = await first.post("/api/student/peer-assessment/complete")
        assert incomplete.status_code == 200
        # First is now in social_feed; second is still in peer_assessment.
        for assignment in second_payload["assignments"]:
            second_submit = await second.post(
                f"/api/student/peer-assessment/{assignment['assignment_id']}",
                json={
                    "scores": {
                        "cultural_clarity": 5,
                        "cultural_translation": 4,
                        "design_originality": 4,
                    }
                },
            )
            assert second_submit.status_code == 200, second_submit.text
        second_complete = await second.post("/api/student/peer-assessment/complete")
        assert second_complete.status_code == 200, second_complete.text

        first_state = (await first.get("/api/student/state")).json()
        admin = await first.post(
            "/api/admin/login", json={"password": settings.admin_password}
        )
        assert admin.status_code == 200, admin.text
        detail = await first.get(
            f"/api/admin/participants/{first_state['participant']['id']}"
        )
        assert detail.status_code == 200, detail.text
        received = detail.json()["peer_scores_received"]
        assert {item["round_no"] for item in received} == {1, 2}
        assert all(item["rating_count"] == 1 for item in received)
        assert all(
            item["review_version"] == "peer-review-v2.1-pilot" for item in received
        )

        async with app.state.db.session_factory() as session:
            path, _ = await build_export(session, settings)
        try:
            with zipfile.ZipFile(path) as archive:
                rating_rows = list(
                    csv.DictReader(
                        io.StringIO(
                            archive.read("peer_ratings.csv").decode("utf-8-sig")
                        )
                    )
                )
                assert len(rating_rows) == 4
                assert {row["review_version"] for row in rating_rows} == {
                    "peer-review-v2.1-pilot"
                }
                assert {row["reviewed_round_no"] for row in rating_rows} == {"1", "2"}
                assert all(row["cultural_clarity"] for row in rating_rows)
                assert all(row["cultural_translation"] for row in rating_rows)
                assert all(row["design_originality"] for row in rating_rows)
                assert all(row["reviewed_student_id"] for row in rating_rows)
                assert all(row["reviewed_ai_condition"] in ("A", "B") for row in rating_rows)
                score_rows = list(
                    csv.DictReader(
                        io.StringIO(
                            archive.read("peer_work_scores.csv").decode("utf-8-sig")
                        )
                    )
                )
                assert len(score_rows) == 4
                assert {row["rating_count"] for row in score_rows} == {"1"}
                assert "overall_mean" not in score_rows[0]
                assert all(row["review_version"] for row in score_rows)
        finally:
            path.unlink(missing_ok=True)

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
