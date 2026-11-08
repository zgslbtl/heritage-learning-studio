from __future__ import annotations

import uuid
from collections import Counter

import pytest

from app.services.peer import _balanced_peer_assignments


def fixture(n_reviewers: int):
    reviewers = []
    works = []
    own: dict = {}
    for index in range(n_reviewers):
        run_id = uuid.uuid4()
        condition = "A" if index % 2 == 0 else "B"
        reviewers.append(
            {"run": SimpleRun(run_id, condition)}
        )
        ids = set()
        for round_no in (1, 2):
            work_id = index * 2 + round_no
            ids.add(work_id)
            works.append(
                {
                    "work": SimpleWork(work_id),
                    "run": SimpleRun(run_id, condition),
                    "round": SimpleRound(round_no, condition if round_no == 1 else ("B" if condition == "A" else "A")),
                    "round_no": round_no,
                    "image_available": True,
                }
            )
        own[run_id] = ids
    return works, reviewers, own


class SimpleWork:
    def __init__(self, work_id: int):
        self.id = work_id


class SimpleRun:
    def __init__(self, run_id, condition: str):
        self.id = run_id
        self.t1_condition = condition


class SimpleRound:
    def __init__(self, round_no: int, condition: str):
        self.round_no = round_no
        self.condition = condition


@pytest.mark.parametrize(
    "n_reviewers,expected_work,expected_reviewer",
    [
        (1, 0, 0),
        (2, 1, 2),
        (3, 2, 4),
        (4, 3, 6),
        (5, 4, 8),
        (6, 5, 10),
        (7, 6, 12),
        (30, 6, 12),
    ],
)
def test_balanced_two_round_allocation(n_reviewers, expected_work, expected_reviewer):
    works, reviewers, own = fixture(n_reviewers)
    assignments, config = _balanced_peer_assignments(works, reviewers)

    assert len(assignments) == len(set(assignments)) == config["target_total"]
    by_reviewer = Counter(run_id for run_id, _ in assignments)
    by_work = Counter(work_id for _, work_id in assignments)
    by_reviewer_round = Counter(
        (run_id, works[work_id - 1]["round_no"])
        for run_id, work_id in assignments
    )

    for run_id, work_ids in own.items():
        assert not any((run_id, work_id) in assignments for work_id in work_ids)
        if expected_reviewer:
            assert by_reviewer[run_id] == expected_reviewer
            if n_reviewers >= 2:
                assert by_reviewer_round[(run_id, 1)] == expected_reviewer // 2
                assert by_reviewer_round[(run_id, 2)] == expected_reviewer // 2

    if expected_work:
        assert set(by_work.values()) == {expected_work}
        assert config["work_count_min"] == config["work_count_max"] == expected_work
    else:
        assert not assignments

    assert config["work_target"] == expected_work
    assert config["reviewer_target"] == expected_reviewer


def test_every_author_has_both_works_rated_equally():
    works, reviewers, _ = fixture(30)
    assignments, _ = _balanced_peer_assignments(works, reviewers)
    counts = Counter(work_id for _, work_id in assignments)
    for index in range(30):
        assert counts[index * 2 + 1] == 6
        assert counts[index * 2 + 2] == 6


def test_missing_a_round_degrades_without_inventing_work():
    works, reviewers, _ = fixture(6)
    works = [item for item in works if item["work"].id != 1]
    assignments, config = _balanced_peer_assignments(works, reviewers)
    assert config["t1_work_count"] == 5
    assert config["t2_work_count"] == 6
    assert len(assignments) <= config["expected_total"]
    assert all(work_id != 1 for _, work_id in assignments)


def test_missing_round_uses_the_available_round_only():
    works, reviewers, _ = fixture(6)
    works = [item for item in works if item["round_no"] == 1]
    assignments, config = _balanced_peer_assignments(works, reviewers)
    assert config["t1_work_count"] == 6
    assert config["t2_work_count"] == 0
    assert config["round_targets"] == {"1": 5, "2": 0}
    assert len(assignments) == 30
    by_reviewer = Counter(run_id for run_id, _ in assignments)
    by_work = Counter(work_id for _, work_id in assignments)
    assert set(by_reviewer.values()) == {5}
    assert set(by_work.values()) == {5}
    assert all(work_id % 2 == 1 for _, work_id in assignments)
