from __future__ import annotations

from app.domain import GROUP_ASSIGNMENTS, round_assignment
from tests.conftest import code_rows, login_student


async def test_cohort_and_login(app_client):
    client, app, settings = app_client
    rows = code_rows(settings)
    assert len(rows) == 120
    counts = {}
    for row in rows:
        counts[(int(row["class_id"]), row["group"])] = counts.get((int(row["class_id"]), row["group"]), 0) + 1
    for class_id in range(1, 5):
        values = sorted(counts[(class_id, group)] for group in ("G1", "G2", "G3", "G4"))
        assert values == [7, 7, 8, 8]
    data = await login_student(client, settings)
    assert data["body"]["state"]["stage"] == "k0"
    state = await client.get("/api/student/state")
    assert state.status_code == 200
    assert "group" not in state.json()
    assert "condition" not in state.text.lower()


def test_group_mapping():
    expected = {
        "G1": [("X", "A"), ("Y", "B")],
        "G2": [("Y", "A"), ("X", "B")],
        "G3": [("X", "B"), ("Y", "A")],
        "G4": [("Y", "B"), ("X", "A")],
    }
    for group, rounds in expected.items():
        assert round_assignment(group, 1, "crossover-v1.0-pilot") == rounds[0]
        assert round_assignment(group, 2, "crossover-v1.0-pilot") == rounds[1]
