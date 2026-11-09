from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AppError
from ..models import (
    ClassPeerGate,
    ClassPeerGateEvent,
    ImageJob,
    Participant,
    PeerAssignment,
    PeerBatch,
    PeerImpression,
    PeerRating,
    Round,
    ArtifactVersion,
    Run,
    WorkRevision,
)
from ..schemas import PeerRatingRequest
from .peer_scales import (
    DEFAULT_PEER_SCALE_VERSION,
    peer_scale,
    peer_scale_for_batch,
    score_keys_for_scale,
)
from .works import work_completion_issues

PEER_ALGORITHM_VERSION = "peer-v3-two-rounds"
# Formal classes: six T1 and six T2 works per reviewer (12 total), six ratings
# per work in each round.  Small classes degrade to the number of other works.
PEER_WORK_TARGET = 6
# Class 0 is a continuous internal-test mode; keep its paired snapshot light.
PEER_BETA_TARGET_PER_ROUND = 3


def is_beta_class(session: AsyncSession, class_id: int) -> bool:
    return class_id == 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def work_code(work_id: int) -> str:
    return "W-" + hashlib.sha256(str(work_id).encode("utf-8")).hexdigest()[:6].upper()


def _order_key(run_id, work_id: int) -> str:
    return hashlib.sha256(f"{run_id}:{work_id}".encode("utf-8")).hexdigest()


async def _selected_image_url(session: AsyncSession, round_obj: Round) -> Optional[str]:
    job = None
    if round_obj.selected_image_job_id:
        job = await session.get(ImageJob, round_obj.selected_image_job_id)
    if not job or job.status != "succeeded" or not job.file_path:
        # Legacy T2 rounds predate explicit selection.
        result = await session.execute(
            select(ImageJob)
            .where(ImageJob.round_id == round_obj.id, ImageJob.status == "succeeded")
            .order_by(ImageJob.created_at.desc())
            .limit(1)
        )
        job = result.scalar_one_or_none()
    if not job or job.status != "succeeded" or not job.file_path:
        return None
    return f"/api/files/keyframes/{job.id}"


async def eligible_works(
    session: AsyncSession,
    class_id: int,
    round_nos: tuple = (2,),
) -> List[Dict[str, Any]]:
    """Latest *valid* submitted work per requested round in one class.

    Peer assessment and the social feed explicitly request (1, 2).
    The default remains available for callers that only need T2 works.
    """

    result = await session.execute(
        select(WorkRevision, Round, Run, Participant)
        .join(Round, Round.id == WorkRevision.round_id)
        .join(Run, Run.id == Round.run_id)
        .join(Participant, Participant.id == Run.participant_id)
        .where(
            Participant.class_id == class_id,
            Round.round_no.in_(round_nos),
            Round.finished_at.is_not(None),
            WorkRevision.revision_no == Round.current_work_revision,
        )
        .order_by(Round.round_no, WorkRevision.id)
    )
    works = []
    for work, round_obj, run, participant in result.all():
        if work_completion_issues(
            round_obj.round_no, round_obj.condition, work, run.design_version
        ):
            continue
        image_url = await _selected_image_url(session, round_obj)
        works.append(
            {
                "work": work,
                "round": round_obj,
                "round_no": round_obj.round_no,
                "run": run,
                "participant": participant,
                "image_url": image_url,
                "image_available": bool(image_url),
            }
        )
    return works


async def eligible_reviewers(session: AsyncSession, class_id: int) -> List[Dict[str, Any]]:
    """All class members whose T2 round has ended, even if work is incomplete."""

    result = await session.execute(
        select(Run, Round)
        .join(Round, Round.run_id == Run.id)
        .join(Participant, Participant.id == Run.participant_id)
        .where(
            Participant.class_id == class_id,
            Round.round_no == 2,
            Round.finished_at.is_not(None),
        )
        .order_by(Run.id)
    )
    seen = set()
    reviewers = []
    for run, round_obj in result.all():
        if run.id in seen:
            continue
        seen.add(run.id)
        reviewers.append({"run": run, "round": round_obj})
    return reviewers


async def get_or_create_gate(session: AsyncSession, class_id: int) -> ClassPeerGate:
    gate = await session.get(ClassPeerGate, class_id, with_for_update=True)
    if gate is None:
        gate = ClassPeerGate(
            class_id=class_id,
            status="collecting",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(gate)
        await session.flush()
    return gate


async def _finalize_expired_t2(session: AsyncSession, class_id: int) -> None:
    """Lazily close T2 rounds past deadline so a waiting class can progress."""

    from .run_state import sync_expired_stage

    result = await session.execute(
        select(Run, Round)
        .join(Round, Round.run_id == Run.id)
        .join(Participant, Participant.id == Run.participant_id)
        .where(
            Participant.class_id == class_id,
            Run.stage == "t2_active",
            Round.round_no == 2,
            Round.finished_at.is_(None),
            Round.deadline_at <= _now(),
        )
    )
    for run, _round in result.all():
        await sync_expired_stage(session, run)


async def gate_counts(session: AsyncSession, class_id: int) -> Dict[str, Any]:
    gate = await get_or_create_gate(session, class_id)
    entered = (
        await session.execute(
            select(func.count())
            .select_from(Run)
            .join(Participant, Participant.id == Run.participant_id)
            .where(Participant.class_id == class_id)
        )
    ).scalar_one()
    t2_ended = (
        await session.execute(
            select(func.count())
            .select_from(Round)
            .join(Run, Run.id == Round.run_id)
            .join(Participant, Participant.id == Run.participant_id)
            .where(
                Participant.class_id == class_id,
                Round.round_no == 2,
                Round.finished_at.is_not(None),
            )
        )
    ).scalar_one()
    works = await eligible_works(session, class_id, (1, 2))
    t1_work_count = sum(1 for item in works if item["round_no"] == 1)
    t2_work_count = sum(1 for item in works if item["round_no"] == 2)
    return {
        "gate": gate,
        "entered": int(entered),
        "t2_ended": int(t2_ended),
        "valid_work_count": len(works),
        "t1_work_count": t1_work_count,
        "t2_work_count": t2_work_count,
        "works": works,
        "can_open": int(entered) > 0 and int(t2_ended) >= int(entered),
    }


async def maybe_auto_open_gate(session: AsyncSession, class_id: int) -> Optional[PeerBatch]:
    """Open the class gate when every entered user has ended T2.

    Called after a T2 finish and from the peer waiting-page GET.  The gate row
    lock makes the operation idempotent under concurrent final submissions.
    """

    gate = await get_or_create_gate(session, class_id)
    if is_beta_class(session, class_id):
        gate.status = "open"
        gate.peer_opened_at = gate.peer_opened_at or _now()
        gate.updated_at = _now()
        # Each beta reviewer freezes an individual snapshot; membership stays open.
        await session.flush()
        return None
    if gate.status == "open":
        return await _batch_for_class(session, class_id)

    await _finalize_expired_t2(session, class_id)
    counts = await gate_counts(session, class_id)
    gate = counts["gate"]
    if not counts["can_open"]:
        gate.updated_at = _now()
        await session.flush()
        return None

    works = counts["works"]
    reviewers = await eligible_reviewers(session, class_id)
    batch = await _create_batch(session, class_id, works, reviewers)
    gate.status = "open"
    gate.membership_frozen_at = _now()
    gate.peer_opened_at = _now()
    gate.entered_count_at_open = counts["entered"]
    gate.t2_ended_count_at_open = counts["t2_ended"]
    gate.valid_work_count_at_open = counts["valid_work_count"]
    gate.batch_id = batch.id
    gate.updated_at = _now()
    session.add(
        ClassPeerGateEvent(
            class_id=class_id,
            event_type="auto_open",
            counts_json={
                "entered": counts["entered"],
                "t2_ended": counts["t2_ended"],
                "valid_work": counts["valid_work_count"],
            },
            peer_batch_id=batch.id,
            created_at=_now(),
        )
    )
    await session.flush()
    return batch


async def peer_gate_is_open(session: AsyncSession, class_id: int) -> bool:
    gate = await get_or_create_gate(session, class_id)
    return gate.status == "open"


async def _batch_for_class(
    session: AsyncSession, class_id: int
) -> Optional[PeerBatch]:
    result = await session.execute(
        select(PeerBatch)
        .where(PeerBatch.class_id == class_id, PeerBatch.status != "superseded")
        .order_by(PeerBatch.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


class _Dinic:
    """Small deterministic max-flow implementation for 30-person classes."""

    def __init__(self, size: int) -> None:
        self.graph: List[List[List[int]]] = [[] for _ in range(size)]

    def add_edge(self, source: int, target: int, capacity: int) -> tuple[int, int]:
        forward = [target, len(self.graph[target]), capacity]
        backward = [source, len(self.graph[source]), 0]
        self.graph[source].append(forward)
        self.graph[target].append(backward)
        return source, len(self.graph[source]) - 1

    def max_flow(self, source: int, sink: int) -> int:
        total = 0
        size = len(self.graph)
        while True:
            level = [-1] * size
            level[source] = 0
            queue = [source]
            for node in queue:
                for edge in self.graph[node]:
                    if edge[2] > 0 and level[edge[0]] < 0:
                        level[edge[0]] = level[node] + 1
                        queue.append(edge[0])
            if level[sink] < 0:
                return total
            cursor = [0] * size

            def send(node: int, amount: int) -> int:
                if node == sink:
                    return amount
                while cursor[node] < len(self.graph[node]):
                    edge = self.graph[node][cursor[node]]
                    if edge[2] > 0 and level[edge[0]] == level[node] + 1:
                        pushed = send(edge[0], min(amount, edge[2]))
                        if pushed:
                            edge[2] -= pushed
                            self.graph[edge[0]][edge[1]][2] += pushed
                            return pushed
                    cursor[node] += 1
                return 0

            while True:
                pushed = send(source, 10**9)
                if not pushed:
                    break
                total += pushed


def _work_condition(item: Dict[str, Any]) -> str:
    return str(getattr(item["round"], "condition", "") or "")


def _round_target_counts(
    works: List[Dict[str, Any]], n_reviewers: int
) -> Dict[int, int]:
    """Per-round work target.

    A formal class targets six ratings per work in each round.  When one round
    has fewer valid works (or is absent), that round degrades independently
    instead of driving the whole batch to zero.
    """

    if n_reviewers <= 1 or not works:
        return {1: 0, 2: 0}
    by_round = {1: 0, 2: 0}
    for item in works:
        round_no = int(item.get("round_no") or 0)
        if round_no in by_round:
            by_round[round_no] += 1
    return {
        round_no: (
            max(0, min(PEER_WORK_TARGET, n_reviewers - 1, by_round[round_no]))
            if by_round[round_no]
            else 0
        )
        for round_no in (1, 2)
    }


def _greedy_round_fill(
    assignments: set,
    reviewer_ids: List[Any],
    work_by_id: Dict[int, Dict[str, Any]],
    own_by_run: Dict[Any, set],
    targets: Dict[int, int],
) -> set:
    """Deterministic fallback if the max flow is short.

    Respects per-reviewer round targets, per-work caps and self-review
    exclusion.  It never invents work; if the pool is exhausted the reviewer
    simply receives fewer assignments.
    """

    filled = set(assignments)
    work_counts = {
        work_id: sum(1 for _, item_work in filled if item_work == work_id)
        for work_id in work_by_id
    }
    reviewer_round_counts = {
        (run_id, round_no): sum(
            1
            for item_run, work_id in filled
            if item_run == run_id
            and int(work_by_id[work_id].get("round_no") or 0) == round_no
        )
        for run_id in reviewer_ids
        for round_no in (1, 2)
    }
    for round_no in (1, 2):
        target = targets.get(round_no, 0)
        round_work_ids = [
            work_id
            for work_id, item in work_by_id.items()
            if int(item.get("round_no") or 0) == round_no
        ]
        if target <= 0 or not round_work_ids:
            continue
        for run_id in reviewer_ids:
            while reviewer_round_counts.get((run_id, round_no), 0) < target:
                candidates = [
                    work_id
                    for work_id in round_work_ids
                    if work_id not in own_by_run.get(run_id, set())
                    and (run_id, work_id) not in filled
                    and work_counts.get(work_id, 0) < target
                ]
                if not candidates:
                    break
                chosen = min(
                    candidates,
                    key=lambda work_id: (
                        work_counts.get(work_id, 0),
                        _order_key(run_id, work_id),
                    ),
                )
                filled.add((run_id, chosen))
                work_counts[chosen] = work_counts.get(chosen, 0) + 1
                reviewer_round_counts[(run_id, round_no)] = (
                    reviewer_round_counts.get((run_id, round_no), 0) + 1
                )
    return filled


def _best_effort_condition_balance(
    assignments: set,
    work_by_id: Dict[int, Dict[str, Any]],
    own_by_run: Dict[Any, set],
    per_round_target: int,
) -> set:
    """Swap reviews across reviewers to reduce A/B concentration.

    Every swap is one-for-one within the same round, so reviewer counts,
    per-work counts, and T1/T2 counts stay unchanged.  The routine is
    deliberately best-effort; it never drops an assignment.
    """
    if per_round_target < 2 or len(assignments) < 4:
        return assignments

    reviewer_ids = sorted({run_id for run_id, _ in assignments})

    def deviation(current: set, run_id) -> float:
        value = 0.0
        for round_no in (1, 2):
            ids = [
                work_id
                for item_run, work_id in current
                if item_run == run_id
                and int(work_by_id[work_id].get("round_no") or 0) == round_no
            ]
            if not ids:
                continue
            a_count = sum(
                1 for work_id in ids
                if _work_condition(work_by_id[work_id]) == "A"
            )
            value += abs(a_count - (len(ids) / 2.0))
        return value

    current = set(assignments)
    for _ in range(4):
        improved = False
        for i, first in enumerate(reviewer_ids):
            for second in reviewer_ids[i + 1:]:
                before = deviation(current, first) + deviation(current, second)
                swapped = False
                first_ids = [
                    work_id for run_id, work_id in current
                    if run_id == first
                    and _work_condition(work_by_id[work_id]) == "A"
                ]
                second_ids = [
                    work_id for run_id, work_id in current
                    if run_id == second
                    and _work_condition(work_by_id[work_id]) == "B"
                ]
                for left in first_ids:
                    for right in second_ids:
                        if int(work_by_id[left].get("round_no") or 0) != int(
                            work_by_id[right].get("round_no") or 0
                        ):
                            continue
                        if right in own_by_run.get(first, set()):
                            continue
                        if left in own_by_run.get(second, set()):
                            continue
                        if (first, right) in current or (second, left) in current:
                            continue
                        candidate = set(current)
                        candidate.discard((first, left))
                        candidate.discard((second, right))
                        candidate.add((first, right))
                        candidate.add((second, left))
                        if deviation(candidate, first) + deviation(candidate, second) < before:
                            current = candidate
                            improved = True
                            swapped = True
                            break
                    if swapped:
                        break
                if swapped:
                    break
            if swapped:
                break
        if not improved:
            break
    return current


def _balanced_peer_assignments(
    works: List[Dict[str, Any]], reviewers: List[Dict[str, Any]]
) -> tuple[List[tuple[Any, int]], Dict[str, Any]]:
    """Assign T1 and T2 works with equal per-work and per-reviewer counts.

    For N participants with both rounds available:
      - C = min(6, N-1) ratings per work in each round;
      - every reviewer receives C T1 + C T2 = 2C reviews;
      - no reviewer receives either of their own works;
      - exact counts are solved with a reviewer-round / work max flow.
    Small classes fall back to every other work (N=2 -> 1 per work, etc.).
    A missing/limited round degrades independently.  Missing works reduce that
    round's target rather than inventing work.  A/B balance is applied as a
    best-effort one-for-one swap after the exact round assignment.
    """
    reviewer_runs = [item["run"] for item in reviewers]
    work_by_id = {int(item["work"].id): item for item in works}
    reviewer_ids = [run.id for run in reviewer_runs]
    work_ids = list(work_by_id.keys())
    own_by_run: Dict[Any, set] = {
        run.id: {int(item["work"].id) for item in works if item["run"].id == run.id}
        for run in reviewer_runs
    }
    n_reviewers = len(reviewer_ids)
    n_works = len(work_ids)
    targets = _round_target_counts(works, n_reviewers)
    max_target = max(targets.values()) if targets else 0
    reviewer_target = sum(targets.values())
    base_config = {
        "algorithm": PEER_ALGORITHM_VERSION,
        "reviewer_count": n_reviewers,
        "work_count": n_works,
        "work_target": max_target,
        "reviewer_target": reviewer_target,
        "round_targets": {str(round_no): value for round_no, value in targets.items()},
        "target_total": 0,
        "expected_total": 0,
        "reviewer_targets": {},
        "work_targets": {},
        "t1_work_count": sum(1 for item in works if int(item.get("round_no") or 0) == 1),
        "t2_work_count": sum(1 for item in works if int(item.get("round_no") or 0) == 2),
        "a_work_count": sum(1 for item in works if _work_condition(item) == "A"),
        "b_work_count": sum(1 for item in works if _work_condition(item) == "B"),
        "condition_balance": "best_effort",
        "missing_work_rounds": [],
    }
    if n_reviewers <= 1 or n_works == 0 or reviewer_target <= 0:
        base_config["missing_work_rounds"] = [
            round_no for round_no in (1, 2)
            if not any(int(item.get("round_no") or 0) == round_no for item in works)
        ]
        return [], base_config

    source = 0
    next_node = 1
    reviewer_nodes: Dict[tuple, int] = {}
    for run_id in reviewer_ids:
        for round_no in (1, 2):
            reviewer_nodes[(run_id, round_no)] = next_node
            next_node += 1
    work_nodes: Dict[int, int] = {}
    for work_id in work_ids:
        work_nodes[work_id] = next_node
        next_node += 1
    sink = next_node
    flow = _Dinic(sink + 1)
    edges: Dict[tuple, tuple] = {}

    round_has_works = {
        round_no: any(int(item.get("round_no") or 0) == round_no for item in works)
        for round_no in (1, 2)
    }
    for run_id in reviewer_ids:
        for round_no in (1, 2):
            if targets.get(round_no, 0) > 0:
                flow.add_edge(
                    source,
                    reviewer_nodes[(run_id, round_no)],
                    targets[round_no],
                )
    for work_id, item in work_by_id.items():
        round_no = int(item.get("round_no") or 0)
        if targets.get(round_no, 0) > 0:
            flow.add_edge(work_nodes[work_id], sink, targets[round_no])
    for run_id in reviewer_ids:
        for round_no in (1, 2):
            node = reviewer_nodes[(run_id, round_no)]
            for work_id, item in work_by_id.items():
                if int(item.get("round_no") or 0) != round_no:
                    continue
                if item["run"].id == run_id:
                    continue
                edges[(run_id, round_no, work_id)] = flow.add_edge(
                    node, work_nodes[work_id], 1
                )
    expected_total = sum(targets.values()) * n_reviewers
    flow_total = flow.max_flow(source, sink)
    assignments: set = set()
    for (run_id, _round_no, work_id), (node, edge_index) in edges.items():
        if flow.graph[node][edge_index][2] == 0:
            assignments.add((run_id, work_id))
    if len(assignments) < expected_total:
        # Defensive fallback: the flow is feasible for all expected class
        # sizes, but never leave a reviewer with missing rounds silently.
        assignments = _greedy_round_fill(
            assignments, reviewer_ids, work_by_id, own_by_run, targets
        )
    assignments = _best_effort_condition_balance(
        assignments, work_by_id, own_by_run, max_target
    )

    reviewer_counts = {
        run_id: sum(1 for item_run, _ in assignments if item_run == run_id)
        for run_id in reviewer_ids
    }
    work_counts = {
        work_id: sum(1 for _, item_work in assignments if item_work == work_id)
        for work_id in work_ids
    }
    base_config.update(
        {
            "target_total": len(assignments),
            "expected_total": expected_total,
            "flow_total": flow_total,
            "reviewer_targets": {
                str(run_id): {
                    "t1": targets.get(1, 0) if round_has_works[1] else 0,
                    "t2": targets.get(2, 0) if round_has_works[2] else 0,
                    "total": reviewer_counts.get(run_id, 0),
                }
                for run_id in reviewer_ids
            },
            "work_targets": {
                str(work_id): targets.get(int(item.get("round_no") or 0), 0)
                for work_id, item in work_by_id.items()
            },
            "reviewer_counts": {str(key): value for key, value in reviewer_counts.items()},
            "work_counts": {str(key): value for key, value in work_counts.items()},
            "reviewer_count_min": min(reviewer_counts.values()) if reviewer_counts else 0,
            "reviewer_count_max": max(reviewer_counts.values()) if reviewer_counts else 0,
            "work_count_min": min(work_counts.values()) if work_counts else 0,
            "work_count_max": max(work_counts.values()) if work_counts else 0,
            "missing_work_rounds": [
                round_no for round_no in (1, 2) if not round_has_works[round_no]
            ],
        }
    )
    return sorted(assignments), base_config


async def _create_batch(
    session: AsyncSession,
    class_id: int,
    works: List[Dict[str, Any]],
    reviewers: List[Dict[str, Any]],
) -> PeerBatch:
    batch = PeerBatch(
        class_id=class_id,
        status="frozen",
        algorithm_version=PEER_ALGORITHM_VERSION,
        scale_version=DEFAULT_PEER_SCALE_VERSION,
        eligible_work_count=len(works),
        config_json={},
        created_at=_now(),
        frozen_at=_now(),
    )
    session.add(batch)
    await session.flush()

    assignments, config = _balanced_peer_assignments(works, reviewers)
    config = {
        **config,
        "scale": peer_scale(DEFAULT_PEER_SCALE_VERSION),
        "scale_version": DEFAULT_PEER_SCALE_VERSION,
    }
    batch.config_json = config
    works_by_id = {int(item["work"].id): item for item in works}
    by_reviewer: Dict[Any, List[int]] = {}
    for run_id, work_id in assignments:
        by_reviewer.setdefault(run_id, []).append(work_id)
    for run_id, chosen_ids in by_reviewer.items():
        chosen_ids.sort(key=lambda work_id: _order_key(run_id, work_id))
        for position, work_id in enumerate(chosen_ids):
            session.add(
                PeerAssignment(
                    batch_id=batch.id,
                    reviewer_run_id=run_id,
                    work_id=work_id,
                    position=position,
                    status="pending",
                )
            )
    await session.flush()
    return batch


async def _beta_batch(session: AsyncSession, run: Run) -> PeerBatch:
    # The run lock also protects empty snapshots, which have no assignment rows.
    await session.execute(select(Run.id).where(Run.id == run.id).with_for_update())
    existing = (await session.execute(
        select(PeerBatch).where(
            PeerBatch.class_id == 0,
            PeerBatch.algorithm_version == "beta-continuous-v1",
            PeerBatch.config_json["reviewer_run_id"].as_string() == str(run.id),
        )
    )).scalar_one_or_none()
    if existing:
        return existing
    candidates = [
        item for item in await eligible_works(session, 0, (1, 2))
        if item["run"].id != run.id
    ]
    candidates.sort(key=lambda item: _order_key(run.id, item["work"].id))
    # Beta continuous mode has no class-wide freeze.  Keep snapshots useful by
    # showing both rounds of up to three other authors (six works), rather than
    # an arbitrary mix of only T2.  This mode intentionally does not promise
    # the global equal-count guarantee used by formal frozen classes.
    beta_target = PEER_BETA_TARGET_PER_ROUND * 2
    by_run: Dict[Any, list] = {}
    for item in candidates:
        by_run.setdefault(item["run"].id, []).append(item)
    chosen = []
    for group in by_run.values():
        pair = sorted(group, key=lambda item: int(item.get("round_no") or 0))
        if len(pair) >= 2 and len(chosen) + 2 <= beta_target:
            chosen.extend(pair[:2])
        if len(chosen) >= beta_target:
            break
    selected_ids = {item["work"].id for item in chosen}
    chosen.extend(
        item for item in candidates
        if item["work"].id not in selected_ids
        and len(chosen) < beta_target
    )
    chosen = chosen[:beta_target]
    chosen.sort(key=lambda item: _order_key(run.id, item["work"].id))
    scale = peer_scale(DEFAULT_PEER_SCALE_VERSION)
    batch = PeerBatch(
        class_id=0, status="frozen", algorithm_version="beta-continuous-v1",
        scale_version=DEFAULT_PEER_SCALE_VERSION, eligible_work_count=len(candidates),
        config_json={
            "deployment_mode": "beta",
            "reviewer_run_id": str(run.id),
            "snapshot_work_ids": [item["work"].id for item in chosen],
            "scale_version": DEFAULT_PEER_SCALE_VERSION,
            "scale": scale,
            "round_targets": {
                str(round_no): PEER_BETA_TARGET_PER_ROUND
                for round_no in (1, 2)
            },
            "reviewer_target": beta_target,
            "target_total": len(chosen),
        },
        created_at=_now(), frozen_at=_now(),
    )
    session.add(batch)
    await session.flush()
    for position, item in enumerate(chosen):
        session.add(PeerAssignment(batch_id=batch.id, reviewer_run_id=run.id,
                                   work_id=item["work"].id, position=position, status="pending"))
    await session.flush()
    return batch


async def peer_payload(session: AsyncSession, run: Run, participant: Participant) -> Dict[str, Any]:
    batch = await maybe_auto_open_gate(session, participant.class_id)
    gate = await get_or_create_gate(session, participant.class_id)
    counts = await gate_counts(session, participant.class_id)
    beta = is_beta_class(session, participant.class_id)
    if beta:
        batch = await _beta_batch(session, run)
    if gate.status != "open":
        return {
            "waiting": True,
            "gate": {
                "status": gate.status,
                "entered": counts["entered"],
                "t2_ended": counts["t2_ended"],
                "valid_work_count": counts["valid_work_count"],
                "t1_work_count": counts.get("t1_work_count", 0),
                "t2_work_count": counts.get("t2_work_count", 0),
                "can_open": counts["can_open"],
                "message": "请等待全班完成 T2。系统会在全班结束后自动开放互评。",
            },
            "batch": None,
            "review": peer_scale(DEFAULT_PEER_SCALE_VERSION),
            "assignments": [],
            "completed": False,
            "submitted": 0,
            "total": 0,
        }
    if batch is None:
        batch = await _batch_for_class(session, participant.class_id)
    if batch is None:
        works = await eligible_works(session, participant.class_id, (1, 2))
        reviewers = await eligible_reviewers(session, participant.class_id)
        batch = await _create_batch(session, participant.class_id, works, reviewers)
        gate.batch_id = batch.id
        gate.updated_at = _now()
        await session.flush()

    result = await session.execute(
        select(PeerAssignment)
        .where(
            PeerAssignment.batch_id == batch.id,
            PeerAssignment.reviewer_run_id == run.id,
        )
        .order_by(PeerAssignment.position)
    )
    assignments = list(result.scalars().all())
    ratings_result = await session.execute(
        select(PeerRating).where(
            PeerRating.assignment_id.in_([item.id for item in assignments])
        )
    )
    ratings = {rating.assignment_id: rating for rating in ratings_result.scalars().all()}
    payload = []
    for assignment in assignments:
        work = await session.get(WorkRevision, assignment.work_id)
        if not work:
            continue
        round_obj = await session.get(Round, work.round_id)
        image_url = await _selected_image_url(session, round_obj) if round_obj else None
        artifact = (
            await session.get(ArtifactVersion, round_obj.artifact_version_id)
            if round_obj
            else None
        )
        payload.append(
            {
                "assignment_id": str(assignment.id),
                "work_code": work_code(work.id),
                "round_no": round_obj.round_no if round_obj else None,
                "artifact_title": artifact.title if artifact else None,
                "artifact_era": artifact.era if artifact else "",
                "artifact_type": artifact.artifact_type if artifact else "",
                "artifact_introduction": artifact.introduction if artifact else "",
                "product_name": work.product_name,
                "product_category": work.product_category,
                "design_concept": work.design_concept,
                "rationale_fields": work.rationale_fields or {},
                "structured_fields": work.structured_fields or {},
                "open_statement": work.open_statement,
                "image_url": image_url,
                "image_available": bool(image_url),
                "status": assignment.status,
                "scores": ratings.get(assignment.id).scores_json
                if ratings.get(assignment.id)
                else {},
                "comment": ratings.get(assignment.id).comment
                if ratings.get(assignment.id)
                else "",
            }
        )
    submitted = sum(1 for item in assignments if item.status == "submitted")
    scale = peer_scale_for_batch(batch)
    return {
        "waiting": False,
        "deployment_mode": "beta" if beta else "study",
        "gate": {
            "status": gate.status,
            "entered": counts["entered"],
            "t2_ended": counts["t2_ended"],
            "valid_work_count": counts["valid_work_count"],
            "t1_work_count": counts.get("t1_work_count", 0),
            "t2_work_count": counts.get("t2_work_count", 0),
            "can_open": True,
            "message": "班级0为陆续体验模式，互评任务按个人首次进入时的作品快照。" if beta else "全班已完成 T2，T1 和 T2 作品一起进入互评。",
        },
        "batch": {
            "id": str(batch.id),
            "algorithm_version": batch.algorithm_version,
            "scale_version": batch.scale_version,
            "review_version": scale.get("version", batch.scale_version),
            "eligible_work_count": batch.eligible_work_count,
            "work_target": (batch.config_json or {}).get("work_target"),
            "reviewer_target": (batch.config_json or {}).get("reviewer_target"),
        },
        "review": scale,
        "assignments": payload,
        "completed": len(payload) == 0 or submitted >= len(payload),
        "submitted": submitted,
        "total": len(payload),
    }


async def submit_peer_rating(
    session: AsyncSession,
    run: Run,
    assignment_id: str,
    payload: PeerRatingRequest,
) -> PeerRating:
    try:
        assignment_uuid = uuid.UUID(assignment_id)
    except ValueError:
        raise AppError(404, "peer_assignment_not_found", "Peer assignment not found.")
    result = await session.execute(
        select(PeerAssignment).where(
            PeerAssignment.id == assignment_uuid,
            PeerAssignment.reviewer_run_id == run.id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise AppError(404, "peer_assignment_not_found", "Peer assignment not found.")

    batch = await session.get(PeerBatch, assignment.batch_id)
    scale = peer_scale_for_batch(batch) if batch is not None else peer_scale(None)
    score_keys = score_keys_for_scale(scale)
    scores = {}
    for key in score_keys:
        value = payload.scores.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            raise AppError(
                422,
                "invalid_peer_scores",
                "Each peer rating must be an integer from 1 to 5.",
                {"missing_or_invalid": key},
            )
        scores[key] = value

    rating_result = await session.execute(
        select(PeerRating).where(PeerRating.assignment_id == assignment.id)
    )
    rating = rating_result.scalar_one_or_none()
    if rating is None:
        rating = PeerRating(
            assignment_id=assignment.id,
            scores_json=scores,
            comment=(payload.comment or "").strip(),
            submitted_at=_now(),
            updated_at=_now(),
        )
        session.add(rating)
    else:
        rating.scores_json = scores
        rating.comment = (payload.comment or "").strip()
        rating.updated_at = _now()
    assignment.status = "submitted"
    await session.flush()
    return rating


async def record_peer_impression(
    session: AsyncSession, run: Run, assignment_id: str, viewed_ms: int
) -> PeerImpression:
    try:
        assignment_uuid = uuid.UUID(assignment_id)
    except ValueError:
        raise AppError(404, "peer_assignment_not_found", "Peer assignment not found.")
    assignment = (
        await session.execute(
            select(PeerAssignment).where(
                PeerAssignment.id == assignment_uuid,
                PeerAssignment.reviewer_run_id == run.id,
            )
        )
    ).scalar_one_or_none()
    if not assignment:
        raise AppError(404, "peer_assignment_not_found", "Peer assignment not found.")
    existing = (
        await session.execute(
            select(PeerImpression).where(
                PeerImpression.assignment_id == assignment.id
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = PeerImpression(
            assignment_id=assignment.id,
            batch_id=assignment.batch_id,
            reviewer_run_id=run.id,
            work_id=assignment.work_id,
            position=assignment.position,
            shown_at=_now(),
            viewed_ms=max(0, viewed_ms),
            updated_at=_now(),
        )
        session.add(existing)
    else:
        existing.viewed_ms = max(existing.viewed_ms, max(0, viewed_ms))
        existing.updated_at = _now()
    await session.flush()
    return existing


async def peer_progress(session: AsyncSession, run: Run) -> tuple[int, int]:
    result = await session.execute(
        select(PeerAssignment).where(PeerAssignment.reviewer_run_id == run.id)
    )
    assignments = list(result.scalars().all())
    submitted = sum(1 for item in assignments if item.status == "submitted")
    return submitted, len(assignments)


async def peer_work_scores(
    session: AsyncSession,
    class_id: int,
    *,
    batch_id: Optional[uuid.UUID] = None,
    run_id: Optional[uuid.UUID] = None,
) -> List[Dict[str, Any]]:
    """Aggregate peer ratings for T1/T2 works in one frozen class batch.

    The peer score is descriptive: rating_count and the three dimension means
    for the batch's own scale version.  It is not the D1–D4 research rubric,
    never mixes V2 and V2.1 dimensions, and is never shown to students.
    """
    if batch_id is None:
        batch = await _batch_for_class(session, class_id)
        if batch is None:
            return []
        batch_id = batch.id
    else:
        batch = await session.get(PeerBatch, batch_id)
        if batch is None:
            return []
    scale = peer_scale_for_batch(batch)
    score_keys = score_keys_for_scale(scale)
    query = (
        select(PeerAssignment, PeerRating, WorkRevision, Round, Run)
        .join(WorkRevision, WorkRevision.id == PeerAssignment.work_id)
        .join(Round, Round.id == WorkRevision.round_id)
        .join(Run, Run.id == Round.run_id)
        .outerjoin(PeerRating, PeerRating.assignment_id == PeerAssignment.id)
        .where(
            PeerAssignment.batch_id == batch_id,
            Run.participant_id.is_not(None),
        )
        .order_by(Round.round_no, WorkRevision.id)
    )
    if run_id is not None:
        query = query.where(Run.id == run_id)
    rows = list((await session.execute(query)).all())
    by_work: Dict[int, Dict[str, Any]] = {}
    image_cache: Dict[int, Optional[str]] = {}
    for assignment, rating, work, round_obj, owner_run in rows:
        entry = by_work.setdefault(
            int(work.id),
            {
                "batch_id": str(batch_id),
                "class_id": class_id,
                "participant_id": str(owner_run.participant_id),
                "run_id": str(owner_run.id),
                "round_no": round_obj.round_no,
                "work_id": int(work.id),
                "work_code": work_code(int(work.id)),
                "artifact_slot": None,
                "ai_condition": round_obj.condition,
                "review_version": scale.get("version", batch.scale_version),
                "image_available": False,
                "rating_count": 0,
                "dimension_scores": {key: [] for key in score_keys},
            },
        )
        if rating is not None:
            entry["rating_count"] += 1
            for key in score_keys:
                value = (rating.scores_json or {}).get(key)
                if isinstance(value, int) and not isinstance(value, bool):
                    entry["dimension_scores"][key].append(value)
        if round_obj.id not in image_cache:
            image_cache[round_obj.id] = await _selected_image_url(session, round_obj)
        entry["image_available"] = bool(image_cache[round_obj.id])
        if entry["artifact_slot"] is None:
            artifact = await session.get(ArtifactVersion, round_obj.artifact_version_id)
            entry["artifact_slot"] = artifact.slot if artifact else None
    results = []
    for entry in by_work.values():
        dimension_scores = entry.pop("dimension_scores")
        for key in score_keys:
            values = dimension_scores.get(key, [])
            entry[f"{key}_mean"] = (
                round(sum(values) / len(values), 3) if values else None
            )
        results.append(entry)
    results.sort(key=lambda item: (item["round_no"], item["work_id"]))
    return results


async def peer_scores_received(
    session: AsyncSession, run_id: uuid.UUID, class_id: int
) -> List[Dict[str, Any]]:
    return await peer_work_scores(session, class_id, run_id=run_id)


async def rebuild_peer_batch(
    session: AsyncSession, class_id: int, *, force: bool = False
) -> PeerBatch:
    """Explicitly supersede and recreate one class's peer batch.

    Intended for pilot/test classes after an algorithm change.  Old assignments
    and ratings are retained (the old batch becomes ``superseded``), but they do
    not contribute to the new current batch's received scores.
    """
    gate = await get_or_create_gate(session, class_id)
    if gate.status != "open":
        raise AppError(
            409,
            "peer_gate_not_open",
            "The class peer gate must be open before rebuilding its batch.",
        )
    old = await _batch_for_class(session, class_id)
    if old is not None:
        submitted = (
            await session.execute(
                select(func.count())
                .select_from(PeerRating)
                .join(PeerAssignment, PeerAssignment.id == PeerRating.assignment_id)
                .where(PeerAssignment.batch_id == old.id)
            )
        ).scalar_one()
        if submitted and not force:
            raise AppError(
                409,
                "peer_ratings_exist",
                "This batch already has submitted peer ratings. Re-run with force to supersede it.",
                {"submitted_ratings": int(submitted)},
            )
        old.status = "superseded"
        await session.flush()

    works = await eligible_works(session, class_id, (1, 2))
    reviewers = await eligible_reviewers(session, class_id)
    batch = await _create_batch(session, class_id, works, reviewers)
    gate.batch_id = batch.id
    gate.valid_work_count_at_open = len(works)
    gate.updated_at = _now()
    await session.flush()
    return batch
