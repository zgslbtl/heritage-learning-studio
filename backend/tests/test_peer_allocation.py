from __future__ import annotations

import uuid
from collections import Counter
from types import SimpleNamespace

import pytest

from app.services.peer import _balanced_peer_assignments


def fixture(n_reviewers: int, n_works: int, a_count: int):
    reviewer_ids = [uuid.uuid4() for _ in range(n_reviewers)]
    work_ids = list(range(1, n_works + 1))
    works = []
    for index, work_id in enumerate(work_ids):
        condition = "A" if index < a_count else "B"
        works.append(
            {
                "work": SimpleNamespace(id=work_id),
                "run": SimpleNamespace(id=reviewer_ids[index], t1_condition=condition),
            }
        )
    reviewers = [{"run": SimpleNamespace(id=run_id)} for run_id in reviewer_ids]
    return works, reviewers, {run_id: work_id for run_id, work_id in zip(reviewer_ids, work_ids)}


@pytest.mark.parametrize(
    "n_reviewers,n_works,a_count,expected_reviewer,expected_work",
    [
        (1, 1, 1, 0, 0),
        (2, 2, 1, 1, 1),
        (5, 5, 2, 4, 4),
        (8, 8, 4, 6, 6),
        (29, 29, 15, 6, 6),
        (29, 28, 15, None, 6),
        (29, 20, 10, None, 6),
    ],
)
def test_balanced_peer_allocation_for_absent_or_small_classes(
    n_reviewers, n_works, a_count, expected_reviewer, expected_work
):
    works, reviewers, own = fixture(n_reviewers, n_works, a_count)
    assignments, config = _balanced_peer_assignments(works, reviewers)
    assert len(assignments) == config["target_total"]
    assert len(set(assignments)) == len(assignments)
    by_reviewer = Counter(run_id for run_id, _ in assignments)
    by_work = Counter(work_id for _, work_id in assignments)
    for run_id, work_id in own.items():
        assert (run_id, work_id) not in assignments
        if expected_reviewer is not None:
            assert by_reviewer[run_id] == expected_reviewer
    for work_id in range(1, n_works + 1):
        assert by_work[work_id] <= 6
        if expected_work is not None:
            assert by_work[work_id] == expected_work
    # For a full class, every reviewer gets exactly 6 and every work 6.
    if (n_reviewers, n_works) == (29, 29):
        assert sum(by_reviewer.values()) == 174
        assert set(by_reviewer.values()) == {6}
        assert set(by_work.values()) == {6}
        # A/B quotas should not collapse into a single pool.
        a_by_reviewer = Counter(
            run_id
            for run_id, work_id in assignments
            if works[work_id - 1]["run"].t1_condition == "A"
        )
        assert all(2 <= a_by_reviewer[run_id] <= 4 for run_id in own)
