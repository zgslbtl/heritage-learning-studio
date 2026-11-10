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
    ClassGroup,
    ClassPeerGateEvent,
    AssessmentResponse,
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
GATE_POLICY = "progress-10-60-90-v1"


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
    await session.execute(select(ClassGroup).where(ClassGroup.id == class_id).with_for_update())
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


async def gate_counts(session: AsyncSession, class_id: int) -> Dict[str, Any]:
    gate = await get_or_create_gate(session, class_id)
    runs = list((await session.execute(select(Run).join(Participant).where(
        Participant.class_id == class_id).order_by(Run.id))).scalars())
    active = [run for run in runs if not run.stopped_at]
    active_ids = {run.id for run in active}
    works = await eligible_works(session, class_id, (1, 2))
    paired = {item["run"].id for item in works if item["round_no"] == 1} & {
        item["run"].id for item in works if item["round_no"] == 2}
    submitted = list((await session.execute(select(AssessmentResponse.run_id, AssessmentResponse.kind).join(
        Run, Run.id == AssessmentResponse.run_id).join(Participant).where(
        Participant.class_id == class_id, AssessmentResponse.kind.in_(("k3", "survey")),
        AssessmentResponse.status == "submitted"))).all())
    ready_ids = paired & active_ids & {rid for rid, kind in submitted if kind == "k3"} & {
        rid for rid, kind in submitted if kind == "survey"}
    # Derive the exact tenth distinct T1 start, including starts before deployment.
    # A stopped participant's historical start is retained; the clock never resets.
    starts = list((await session.execute(select(Round.started_at).join(Run).join(Participant).where(
        Participant.class_id == class_id, Round.round_no == 1).order_by(
        Round.started_at, Round.id))).scalars())
    if class_id != 0 and gate.status != "open":
        gate.policy_version = GATE_POLICY
        if gate.timer_started_at is None and len(starts) >= 10:
            gate.timer_started_at = starts[9]
            session.add(ClassPeerGateEvent(class_id=class_id, event_type="timer_started",
                counts_json={"t1_started": len(starts), "timer_started_at": starts[9].isoformat()}))
    elapsed = max(0, int((_now() - _aware(gate.timer_started_at)).total_seconds())) if gate.timer_started_at else 0
    all_ready = len(active) > 0 and len(ready_ids) == len(active)
    threshold_ready = len(active) > 0 and len(ready_ids) * 10 >= len(active) * 9
    can_open = all_ready or (gate.timer_started_at is not None and elapsed >= 3600 and threshold_ready)
    t2_ended = (await session.execute(select(func.count()).select_from(Round).join(Run).join(Participant).where(
        Participant.class_id == class_id, Round.round_no == 2, Round.finished_at.is_not(None)))).scalar_one()
    return {"gate": gate, "entered": len(runs), "active_count": len(active),
        "stopped_count": len(runs) - len(active), "ready_count": len(ready_ids),
        "completion_percent": round(100 * len(ready_ids) / len(active), 1) if active else 0,
        "timer_started_at": gate.timer_started_at.isoformat() if gate.timer_started_at else None,
        "t1_started_count": len(starts), "elapsed_seconds": elapsed,
        "remaining_seconds": max(0, 3600 - elapsed) if gate.timer_started_at else None,
        "opening_reason": "all_ready" if all_ready else "time_and_90_percent" if can_open else None,
        "ready_ids": ready_ids, "active_ids": active_ids,
        "t2_ended": int(t2_ended), "valid_work_count": len(works),
        "t1_work_count": sum(item["round_no"] == 1 for item in works),
        "t2_work_count": sum(item["round_no"] == 2 for item in works),
        "works": works, "can_open": can_open}


def gate_progress_payload(counts: Dict[str, Any]) -> Dict[str, Any]:
    gate = counts["gate"]
    keys = ("entered", "active_count", "stopped_count", "ready_count", "completion_percent",
            "timer_started_at", "t1_started_count", "elapsed_seconds", "remaining_seconds",
            "t2_ended", "valid_work_count", "t1_work_count", "t2_work_count", "can_open")
    return {**{key: counts[key] for key in keys}, "status": gate.status,
            "policy_version": gate.policy_version, "opening_reason": gate.opening_reason,
            "message": "全员完成即开放；否则第10人开始第一轮后满60分钟，且完成率达到90%时开放。",
            "message_en": "Opens when everyone is ready, or 60 minutes after the tenth student starts round 1 with at least 90% ready."}


async def maybe_auto_open_gate(session: AsyncSession, class_id: int) -> Optional[PeerBatch]:
    gate = await get_or_create_gate(session, class_id)
    if is_beta_class(session, class_id):
        gate.status = "open"
        gate.peer_opened_at = gate.peer_opened_at or _now()
        gate.updated_at = _now()
        await session.flush()
        return None
    if gate.status == "open":
        return await _batch_for_class(session, class_id)
    # Readiness requires actual post-test and survey submissions; a timeout
    # alone never counts as completion and must not manufacture a response.
    counts = await gate_counts(session, class_id)
    if not counts["can_open"]:
        gate.updated_at = _now()
        await session.flush()
        return None
    ready_ids = counts["ready_ids"]
    works = [item for item in counts["works"] if item["run"].id in ready_ids]
    reviewers = [item for item in await eligible_reviewers(session, class_id) if item["run"].id in ready_ids]
    batch = await _create_batch(session, class_id, works, reviewers)
    gate.status = "open"
    gate.membership_frozen_at = gate.peer_opened_at = _now()
    gate.entered_count_at_open = counts["entered"]
    gate.t2_ended_count_at_open = counts["t2_ended"]
    gate.valid_work_count_at_open = len(works)
    gate.batch_id = batch.id
    gate.opening_reason = counts["opening_reason"]
    gate.snapshot_json = {"member_run_ids": [str(x) for x in sorted(counts["active_ids"])],
        "main_reviewer_run_ids": [str(x) for x in sorted(ready_ids)],
        "work_ids": [item["work"].id for item in works],
        "active_count": counts["active_count"], "ready_count": counts["ready_count"],
        "stopped_count": counts["stopped_count"], "policy_version": GATE_POLICY}
    batch.config_json = {**batch.config_json, **gate.snapshot_json,
                         "zero_assignment_reason": "no_other_author" if len(ready_ids) <= 1 else None}
    gate.updated_at = _now()
    session.add(ClassPeerGateEvent(class_id=class_id, event_type="auto_open",
        counts_json={**gate.snapshot_json, "opening_reason": gate.opening_reason}, peer_batch_id=batch.id))
    await session.flush()
    return batch


async def stop_participant(session: AsyncSession, participant_id: uuid.UUID, reason: str, *, restore: bool = False,
                           actor_id: str) -> Dict[str, Any]:
    participant = await session.get(Participant, participant_id)
    if not participant or participant.class_id == 0:
        raise AppError(404, "participant_not_found", "Formal-class participant not found.")
    gate = await get_or_create_gate(session, participant.class_id)
    run = (await session.execute(select(Run).where(Run.participant_id == participant_id)
        .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if gate.status == "open":
        raise AppError(409, "gate_already_open", "互评已开放，不能停止或恢复。 / Peer review is already open.")
    if not run:
        raise AppError(409, "run_not_found", "This participant has not entered the study.")
    reason = reason.strip()
    if not reason or len(reason) > 1000:
        raise AppError(422, "reason_required", "请填写原因（1–1000字）。 / Please provide a reason (1–1000 characters).")
    before = await gate_counts(session, participant.class_id)
    if restore:
        if not run.stopped_at:
            raise AppError(409, "not_stopped", "Participant is not stopped.")
        run.stopped_at = None
        run.stop_reason = None
    else:
        if run.stopped_at or run.id in before["ready_ids"] or run.stage == "complete":
            raise AppError(409, "cannot_stop", "Only unfinished, active participants can be stopped.")
        run.stopped_at = _now()
        run.stop_reason = reason
    await session.flush()
    after = await gate_counts(session, participant.class_id)
    session.add(ClassPeerGateEvent(class_id=participant.class_id,
        event_type="participant_restored" if restore else "participant_stopped",
        counts_json={"run_id": str(run.id), "participant_id": str(participant_id), "reason": reason,
                     "admin_session_id": actor_id, "stage": run.stage,
                     "before": {key: before[key] for key in ("active_count", "ready_count", "stopped_count")},
                     "after": {key: after[key] for key in ("active_count", "ready_count", "stopped_count")}}))
    await maybe_auto_open_gate(session, participant.class_id)
    return {"stopped": bool(run.stopped_at), "stage": run.stage, "gate": gate_progress_payload(after)}


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


async def ensure_supplemental_assignments(session: AsyncSession, run: Run, class_id: int,
                                         batch: PeerBatch, counts: Dict[str, Any]) -> None:
    gate = counts["gate"]
    if gate.policy_version != GATE_POLICY or str(run.id) in (gate.snapshot_json or {}).get("main_reviewer_run_ids", []):
        return  # Historical frozen batches and main allocations are immutable.
    if str(run.id) not in (gate.snapshot_json or {}).get("member_run_ids", []):
        raise AppError(409, "not_frozen_member", "Participant is not in the frozen class membership.")
    snapshots = dict((batch.config_json or {}).get("supplemental_reviewers", {}))
    snapshot = snapshots.get(str(run.id)) or {}
    # A researcher may explicitly authorize a frozen supplemental snapshot for
    # a participant with an incomplete work field. Preserve that missing data;
    # never repair research answers just to grant access to reviewing others.
    event_id = snapshot.get("manual_authorization_event_id")
    manual = False
    if isinstance(event_id, int):
        event = await session.get(ClassPeerGateEvent, event_id)
        submitted = set((await session.execute(select(AssessmentResponse.kind).where(
            AssessmentResponse.run_id == run.id, AssessmentResponse.kind.in_(("k3", "survey")),
            AssessmentResponse.status == "submitted"))).scalars())
        ended = set((await session.execute(select(Round.round_no).where(
            Round.run_id == run.id, Round.finished_at.is_not(None)))).scalars())
        manual = bool(event and event.class_id == class_id and event.peer_batch_id == batch.id
            and event.event_type == "manual_peer_assigned" and (event.counts_json or {}).get("run_id") == str(run.id)
            and set((event.counts_json or {}).get("work_ids", [])) == set(snapshot.get("work_ids", []))
            and set(snapshot.get("work_ids", [])).issubset(set((gate.snapshot_json or {}).get("work_ids", [])))
            and (event.counts_json or {}).get("reason") and run.stage == "peer_assessment"
            and submitted == {"k3", "survey"} and {1, 2}.issubset(ended))
    if run.stopped_at or (run.id not in counts["ready_ids"] and not manual):
        raise AppError(409, "peer_not_ready", "Complete both designs, the post-test and survey first.")
    if str(run.id) in snapshots:
        return
    frozen_ids = set((gate.snapshot_json or {}).get("work_ids", []))
    # Load frozen revisions, never replace them with a later revision.
    rows = (await session.execute(select(WorkRevision, Round, Run).join(Round,
        Round.id == WorkRevision.round_id).join(Run).join(Participant).where(
        WorkRevision.id.in_(frozen_ids), Participant.class_id == class_id, Run.id != run.id))).all()
    assigned_counts = dict((await session.execute(select(PeerAssignment.work_id, func.count()).where(
        PeerAssignment.batch_id == batch.id, PeerAssignment.allocation_kind == "supplemental").group_by(
        PeerAssignment.work_id))).all())
    chosen = []
    for round_no in (1, 2):
        pool = [(work, rnd) for work, rnd, owner in rows if rnd.round_no == round_no]
        condition_counts = {}
        for _ in range(min(PEER_WORK_TARGET, len(pool))):
            work, rnd = min(pool, key=lambda item: (assigned_counts.get(item[0].id, 0),
                condition_counts.get(item[1].condition, 0), _order_key(run.id, item[0].id)))
            chosen.append(work.id)
            condition_counts[rnd.condition] = condition_counts.get(rnd.condition, 0) + 1
            pool.remove((work, rnd))
    chosen.sort(key=lambda wid: _order_key(run.id, wid))
    for position, wid in enumerate(chosen):
        session.add(PeerAssignment(batch_id=batch.id, reviewer_run_id=run.id, work_id=wid,
                                  position=position, allocation_kind="supplemental"))
    snapshots[str(run.id)] = {"work_ids": chosen, "created_at": _now().isoformat(),
                            "zero_assignment_reason": "no_other_author" if not chosen else None}
    batch.config_json = {**batch.config_json, "supplemental_reviewers": snapshots}
    session.add(ClassPeerGateEvent(class_id=class_id, event_type="supplemental_assigned",
        peer_batch_id=batch.id, counts_json={"run_id": str(run.id), **snapshots[str(run.id)]}))
    await session.flush()


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
            "gate": gate_progress_payload(counts),
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

    if not beta:
        await ensure_supplemental_assignments(session, run, participant.class_id, batch, counts)

    result = await session.execute(
        select(PeerAssignment)
        .where(
            PeerAssignment.batch_id == batch.id,
            PeerAssignment.reviewer_run_id == run.id,
        )
        .order_by(PeerAssignment.position)
    )
    assignments = list(result.scalars().all())
    if not beta and gate.policy_version == GATE_POLICY and not assignments:
        frozen_ids = (gate.snapshot_json or {}).get("work_ids", [])
        others = (await session.execute(select(func.count()).select_from(WorkRevision).join(Round).where(
            WorkRevision.id.in_(frozen_ids), Round.run_id != run.id))).scalar_one()
        if others:
            raise AppError(409, "peer_allocation_missing", "互评任务尚未完整生成，请联系研究者。 / Peer allocation is incomplete. Please contact the researcher.")

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
                "allocation_kind": assignment.allocation_kind,
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
        "gate": gate_progress_payload(counts),
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
            PeerAssignment.allocation_kind == "main",
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
