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
    Run,
    WorkRevision,
)
from ..schemas import PeerRatingRequest
from .works import latest_work, work_completion_issues

PEER_ALGORITHM_VERSION = "peer-v2-balanced"
PEER_TARGET = 6
PEER_SCORE_KEYS = ("clarity", "evidence_link", "attraction")


def is_beta_class(session: AsyncSession, class_id: int) -> bool:
    return class_id == 0 and session.info.get("deployment_mode") == "beta"


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


async def eligible_works(session: AsyncSession, class_id: int) -> List[Dict[str, Any]]:
    """Latest *valid* submitted T2 work per participant in one class."""

    result = await session.execute(
        select(WorkRevision, Round, Run, Participant)
        .join(Round, Round.id == WorkRevision.round_id)
        .join(Run, Run.id == Round.run_id)
        .join(Participant, Participant.id == Run.participant_id)
        .where(
            Participant.class_id == class_id,
            Round.round_no == 2,
            Round.finished_at.is_not(None),
            WorkRevision.revision_no == Round.current_work_revision,
        )
        .order_by(WorkRevision.id)
    )
    works = []
    for work, round_obj, run, participant in result.all():
        if work_completion_issues(
            2, round_obj.condition, work, run.design_version
        ):
            continue
        works.append(
            {
                "work": work,
                "round": round_obj,
                "run": run,
                "participant": participant,
                "image_url": await _selected_image_url(session, round_obj),
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
    works = await eligible_works(session, class_id)
    return {
        "gate": gate,
        "entered": int(entered),
        "t2_ended": int(t2_ended),
        "valid_work_count": len(works),
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


def _balanced_degrees(caps: List[int], total: int) -> List[int]:
    """Give every unit of capacity to the currently least-loaded eligible slot."""
    degrees = [0] * len(caps)
    remaining = max(0, min(total, sum(caps)))
    while remaining:
        eligible = [index for index, cap in enumerate(caps) if degrees[index] < cap]
        if not eligible:
            break
        smallest = min(degrees[index] for index in eligible)
        for index in eligible:
            if remaining == 0:
                break
            if degrees[index] == smallest and degrees[index] < caps[index]:
                degrees[index] += 1
                remaining -= 1
    return degrees


def _quota_for_a(
    targets: List[int], a_caps: List[int], b_caps: List[int], a_total: int
) -> Optional[List[int]]:
    """Choose reviewer A counts between feasible bounds, summing to a_total."""
    lows = [max(0, target - b_cap) for target, b_cap in zip(targets, b_caps)]
    highs = [min(target, a_cap) for target, a_cap in zip(targets, a_caps)]
    if sum(lows) > a_total or sum(highs) < a_total:
        return None
    quotas = list(lows)
    remaining = a_total - sum(quotas)
    while remaining:
        eligible = [index for index in range(len(quotas)) if quotas[index] < highs[index]]
        if not eligible:
            return None
        # Prefer the least allocated reviewer; ties are deterministic by index.
        smallest = min(quotas[index] for index in eligible)
        for index in eligible:
            if remaining == 0:
                break
            if quotas[index] == smallest and quotas[index] < highs[index]:
                quotas[index] += 1
                remaining -= 1
    return quotas


def _flow_assign(
    *,
    reviewer_ids: List[Any],
    work_ids: List[int],
    reviewer_targets: Dict[Any, int],
    work_targets: Dict[int, int],
    own_work: Dict[Any, Optional[int]],
) -> Optional[List[tuple[Any, int]]]:
    if not reviewer_ids or not work_ids:
        return [] if sum(reviewer_targets.values()) == 0 else None
    total = sum(reviewer_targets.values())
    if total == 0:
        return []
    if total != sum(work_targets.values()):
        return None
    source = 0
    reviewer_offset = 1
    work_offset = reviewer_offset + len(reviewer_ids)
    sink = work_offset + len(work_ids)
    flow = _Dinic(sink + 1)
    for index, run_id in enumerate(reviewer_ids):
        target = reviewer_targets.get(run_id, 0)
        if target:
            flow.add_edge(source, reviewer_offset + index, target)
    for index, work_id in enumerate(work_ids):
        target = work_targets.get(work_id, 0)
        if target:
            flow.add_edge(work_offset + index, sink, target)
    references: Dict[tuple[int, int], tuple[int, int]] = {}
    for reviewer_index, run_id in enumerate(reviewer_ids):
        for work_index, work_id in enumerate(work_ids):
            if own_work.get(run_id) == work_id:
                continue
            references[(reviewer_index, work_index)] = flow.add_edge(
                reviewer_offset + reviewer_index,
                work_offset + work_index,
                1,
            )
    if flow.max_flow(source, sink) != total:
        return None
    assignments: List[tuple[Any, int]] = []
    for (reviewer_index, work_index), (node, edge_index) in references.items():
        if flow.graph[node][edge_index][2] == 0:
            assignments.append((reviewer_ids[reviewer_index], work_ids[work_index]))
    if len(assignments) != total:
        return None
    return assignments


def _greedy_assign(
    reviewer_ids: List[Any],
    works: List[Dict[str, Any]],
    reviewer_targets: Dict[Any, int],
    work_targets: Dict[int, int],
    own_work: Dict[Any, Optional[int]],
) -> List[tuple[Any, int]]:
    counts = {int(item["work"].id): 0 for item in works}
    result: List[tuple[Any, int]] = []
    for run_id in reviewer_ids:
        target = reviewer_targets.get(run_id, 0)
        if target <= 0:
            continue
        candidates = [
            item
            for item in works
            if item["work"].id != own_work.get(run_id)
            and counts[int(item["work"].id)] < work_targets.get(int(item["work"].id), 0)
        ]
        candidates.sort(
            key=lambda item: (
                counts[int(item["work"].id)],
                _order_key(run_id, int(item["work"].id)),
            )
        )
        for item in candidates[:target]:
            result.append((run_id, int(item["work"].id)))
            counts[int(item["work"].id)] += 1
    return result


def _balanced_peer_assignments(
    works: List[Dict[str, Any]], reviewers: List[Dict[str, Any]]
) -> tuple[List[tuple[Any, int]], Dict[str, Any]]:
    """Assign peer reviews for any class size, including absences.

    For N reviewers/work owners:
      - every reviewer reviews at most 6 works;
      - every work receives at most 6 ratings;
      - N=1 -> no assignments; N=2..6 -> everyone reviews every other work;
      - N>=7 -> 6 per reviewer/work when enough works exist;
      - works are capped at 6; missing/incomplete works are never invented;
      - A/B pools are balanced where feasible, then filled from the other pool.
    """
    reviewer_runs = [item["run"] for item in reviewers]
    work_items = {int(item["work"].id): item for item in works}
    reviewer_ids = [run.id for run in reviewer_runs]
    work_ids = list(work_items.keys())
    own_work = {
        run.id: next(
            (
                int(item["work"].id)
                for item in works
                if item["run"].id == run.id
            ),
            None,
        )
        for run in reviewer_runs
    }
    n_reviewers = len(reviewer_ids)
    n_works = len(work_ids)
    if n_reviewers <= 1 or n_works == 0:
        return [], {
            "algorithm": PEER_ALGORITHM_VERSION,
            "reviewer_count": n_reviewers,
            "work_count": n_works,
            "target_total": 0,
            "reviewer_targets": {},
            "work_targets": {},
        }

    reviewer_caps = [
        min(PEER_TARGET, n_works - (1 if own_work[run_id] is not None else 0))
        for run_id in reviewer_ids
    ]
    work_caps = {work_id: min(PEER_TARGET, n_reviewers - 1) for work_id in work_ids}
    total = min(sum(reviewer_caps), sum(work_caps.values()))
    reviewer_targets_list = _balanced_degrees(reviewer_caps, total)
    work_targets_list = _balanced_degrees(
        [work_caps[work_id] for work_id in work_ids], total
    )
    reviewer_targets = dict(zip(reviewer_ids, reviewer_targets_list))
    work_targets = dict(zip(work_ids, work_targets_list))

    a_works = [item for item in works if item["run"].t1_condition == "A"]
    b_works = [item for item in works if item["run"].t1_condition == "B"]
    a_ids = [int(item["work"].id) for item in a_works]
    b_ids = [int(item["work"].id) for item in b_works]
    a_total = sum(work_targets[work_id] for work_id in a_ids)
    b_total = sum(work_targets[work_id] for work_id in b_ids)

    a_caps = []
    b_caps = []
    for run_id in reviewer_ids:
        target = reviewer_targets[run_id]
        own = own_work.get(run_id)
        a_caps.append(min(target, max(0, len(a_ids) - (1 if own in a_ids else 0))))
        b_caps.append(min(target, max(0, len(b_ids) - (1 if own in b_ids else 0))))
    a_quotas = _quota_for_a(reviewer_targets_list, a_caps, b_caps, a_total)
    assignments: Optional[List[tuple[Any, int]]] = None
    if a_quotas is not None:
        b_quotas = [
            target - a_quota
            for target, a_quota in zip(reviewer_targets_list, a_quotas)
        ]
        a_assign = _flow_assign(
            reviewer_ids=reviewer_ids,
            work_ids=a_ids,
            reviewer_targets=dict(zip(reviewer_ids, a_quotas)),
            work_targets={work_id: work_targets[work_id] for work_id in a_ids},
            own_work=own_work,
        )
        b_assign = _flow_assign(
            reviewer_ids=reviewer_ids,
            work_ids=b_ids,
            reviewer_targets=dict(zip(reviewer_ids, b_quotas)),
            work_targets={work_id: work_targets[work_id] for work_id in b_ids},
            own_work=own_work,
        )
        if a_assign is not None and b_assign is not None:
            assignments = a_assign + b_assign
    if assignments is None:
        # A/B quota flow can be infeasible for very small or very imbalanced
        # classes; fall back to the all-work flow while retaining exact degrees.
        assignments = _flow_assign(
            reviewer_ids=reviewer_ids,
            work_ids=work_ids,
            reviewer_targets=reviewer_targets,
            work_targets=work_targets,
            own_work=own_work,
        )
    if assignments is None:
        assignments = _greedy_assign(
            reviewer_ids, works, reviewer_targets, work_targets, own_work
        )
    return assignments, {
        "algorithm": PEER_ALGORITHM_VERSION,
        "reviewer_count": n_reviewers,
        "work_count": n_works,
        "target_total": total,
        "reviewer_targets": {str(key): value for key, value in reviewer_targets.items()},
        "work_targets": {str(key): value for key, value in work_targets.items()},
        "a_work_count": len(a_ids),
        "b_work_count": len(b_ids),
        "a_target_total": a_total,
        "b_target_total": b_total,
    }


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
        scale_version="peer-scale-v2",
        eligible_work_count=len(works),
        config_json={},
        created_at=_now(),
        frozen_at=_now(),
    )
    session.add(batch)
    await session.flush()

    assignments, config = _balanced_peer_assignments(works, reviewers)
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
    candidates = [item for item in await eligible_works(session, 0) if item["run"].id != run.id]
    candidates.sort(key=lambda item: _order_key(run.id, item["work"].id))
    chosen = []
    for condition in ("A", "B"):
        chosen.extend([item for item in candidates if item["run"].t1_condition == condition][:3])
    selected_ids = {item["work"].id for item in chosen}
    chosen.extend([item for item in candidates if item["work"].id not in selected_ids][:PEER_TARGET - len(chosen)])
    chosen.sort(key=lambda item: _order_key(run.id, item["work"].id))
    batch = PeerBatch(
        class_id=0, status="frozen", algorithm_version="beta-continuous-v1",
        scale_version="peer-scale-v2", eligible_work_count=len(candidates),
        config_json={"deployment_mode": "beta", "reviewer_run_id": str(run.id),
                     "snapshot_work_ids": [item["work"].id for item in chosen]},
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
                "can_open": counts["can_open"],
                "message": "请等待全班完成 T2。系统会在全班结束后自动开放互评。",
            },
            "batch": None,
            "assignments": [],
            "completed": False,
            "submitted": 0,
            "total": 0,
        }
    if batch is None:
        batch = await _batch_for_class(session, participant.class_id)
    if batch is None:
        works = await eligible_works(session, participant.class_id)
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
        payload.append(
            {
                "assignment_id": str(assignment.id),
                "work_code": work_code(work.id),
                "product_name": work.product_name,
                "product_category": work.product_category,
                "design_concept": work.design_concept,
                "rationale_fields": work.rationale_fields or {},
                "open_statement": work.open_statement,
                "image_url": await _selected_image_url(session, round_obj)
                if round_obj
                else None,
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
    return {
        "waiting": False,
        "deployment_mode": "beta" if beta else "study",
        "gate": {
            "status": gate.status,
            "entered": counts["entered"],
            "t2_ended": counts["t2_ended"],
            "valid_work_count": counts["valid_work_count"],
            "can_open": True,
            "message": "班级0为陆续体验模式，互评任务按个人首次进入时的作品冻结。" if beta else "全班已完成 T2，互评已开放。",
        },
        "batch": {
            "id": str(batch.id),
            "algorithm_version": batch.algorithm_version,
            "scale_version": batch.scale_version,
            "eligible_work_count": batch.eligible_work_count,
        },
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

    scores = {}
    for key in PEER_SCORE_KEYS:
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
