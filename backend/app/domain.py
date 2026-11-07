from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Tuple


class Group(str, Enum):
    G1 = "G1"
    G2 = "G2"
    G3 = "G3"
    G4 = "G4"


GROUPS: List[str] = [Group.G1.value, Group.G2.value, Group.G3.value, Group.G4.value]


class Condition(str, Enum):
    A = "A"
    B = "B"


class ArtifactSlot(str, Enum):
    X = "X"
    Y = "Y"


SLOTS: List[str] = [ArtifactSlot.X.value, ArtifactSlot.Y.value]


class Stage(str, Enum):
    """Current v1.5 study flow.

    Legacy stage names remain in ``LEGACY_STAGE_LABELS`` so older rows can
    still be displayed in the researcher console and exported unchanged.
    """

    K0 = "k0"
    TUTORIAL = "tutorial"
    T1_READY = "t1_ready"
    T1_ACTIVE = "t1_active"
    K1 = "k1"
    K2 = "k2"
    T2_READY = "t2_ready"
    T2_ACTIVE = "t2_active"
    K3 = "k3"
    SURVEY = "survey"
    PEER_ASSESSMENT = "peer_assessment"
    SOCIAL_FEED = "social_feed"
    COMPLETE = "complete"


STAGE_ORDER: List[str] = [stage.value for stage in Stage]

# Old v1.0 stages are retained only for reading historical rows.
LEGACY_STAGES: List[str] = [
    "pre_test",
    "round1_ready",
    "round1_active",
    "r1_test",
    "round2_ready",
    "round2_active",
    "post_test",
    "transfer",
    "questionnaire",
]

ASSESSMENT_STAGE_KIND: Dict[str, str] = {
    Stage.K0.value: "k0",
    Stage.K1.value: "k1",
    Stage.K2.value: "k2",
    Stage.K3.value: "k3",
    Stage.SURVEY.value: "survey",
}

KIND_TO_STAGE: Dict[str, str] = {kind: stage for stage, kind in ASSESSMENT_STAGE_KIND.items()}

ASSESSMENT_KINDS = ["k0", "k1", "k2", "k3", "survey"]
LEGACY_ASSESSMENT_KINDS = ["pre_test", "r1_test", "post_test", "transfer", "questionnaire"]

KIND_LABELS = {
    "k0": "K0 · 文物知识前测 / Knowledge Pre-test",
    "k1": "K1 · T1 知识后测 / T1 Knowledge Post-test",
    "k2": "K2 · T2 文物知识前测 / T2 Knowledge Pre-test",
    "k3": "K3 · T2 知识后测 / T2 Knowledge Post-test",
    "survey": "体验问卷 / Experience Survey",
    # legacy labels for researcher detail/export
    "pre_test": "旧版前测 / Legacy Pre-test",
    "r1_test": "旧版 R1 测试 / Legacy R1 Assessment",
    "post_test": "旧版后测 / Legacy Post-test",
    "transfer": "旧版迁移题 / Legacy Transfer",
    "questionnaire": "旧版问卷 / Legacy Questionnaire",
}

NEXT_AFTER_ASSESSMENT = {
    "k0": Stage.TUTORIAL.value,
    "k1": Stage.K2.value,
    "k2": Stage.T2_READY.value,
    "k3": Stage.SURVEY.value,
    "survey": Stage.PEER_ASSESSMENT.value,
}

TASK_LABELS = {
    1: "T1 · 文物理解与文创共创",
    2: "T2 · 新文物迁移共创",
}


class HLSFPhase(str, Enum):
    OBSERVE = "observe"
    EXPLAIN = "explain"
    CREATE = "create"
    REFLECT = "reflect"
    COMPLETE = "complete"


HLSF_ORDER = [
    HLSFPhase.OBSERVE.value,
    HLSFPhase.EXPLAIN.value,
    HLSFPhase.CREATE.value,
    HLSFPhase.REFLECT.value,
]


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SessionRole(str, Enum):
    STUDENT = "student"
    ADMIN = "admin"


# Crossover pilot versions: every participant receives one Standard AI round
# and one HLSF round, with different artifacts.  v1.1 adds the assessment v2
# pilot (6 MC per form, post-only short answers, unified three-part rationale).
CROSSOVER_V1_DESIGN_VERSION = "crossover-v1.0-pilot"
CROSSOVER_V2_DESIGN_VERSION = "crossover-v1.1-assessment-v2-pilot"
CROSSOVER_DESIGN_VERSION = CROSSOVER_V1_DESIGN_VERSION
CROSSOVER_DESIGN_VERSIONS = {
    CROSSOVER_V1_DESIGN_VERSION,
    CROSSOVER_V2_DESIGN_VERSION,
}

ASSESSMENT_V1_VERSION = "assessment_v1"
ASSESSMENT_V2_VERSION = "assessment_v2.0_pilot"
RATIONALE_V2_VERSION = "rationale_v2.0"


def design_version_for_assessment(assessment_version: Optional[str]) -> str:
    """Map a frozen protocol's assessment version to its run design version."""
    if assessment_version == ASSESSMENT_V2_VERSION:
        return CROSSOVER_V2_DESIGN_VERSION
    return CROSSOVER_V1_DESIGN_VERSION


def assessment_version_for_design(design_version: Optional[str]) -> str:
    if design_version == CROSSOVER_V2_DESIGN_VERSION:
        return ASSESSMENT_V2_VERSION
    if design_version == CROSSOVER_V1_DESIGN_VERSION:
        return ASSESSMENT_V1_VERSION
    return "legacy-v1.5"


def mc_max_for_design(design_version: Optional[str]) -> Optional[int]:
    if design_version == CROSSOVER_V2_DESIGN_VERSION:
        return 6
    if design_version == CROSSOVER_V1_DESIGN_VERSION:
        return 8
    return None


def rationale_schema_for_design(design_version: Optional[str]) -> str:
    if design_version == CROSSOVER_V2_DESIGN_VERSION:
        return RATIONALE_V2_VERSION
    return "legacy"

GROUP_ASSIGNMENTS: Dict[str, Dict[str, object]] = {
    Group.G1.value: {
        "t1_condition": Condition.A.value,
        "t2_condition": Condition.B.value,
        "order": (ArtifactSlot.X.value, ArtifactSlot.Y.value),
    },
    Group.G2.value: {
        "t1_condition": Condition.A.value,
        "t2_condition": Condition.B.value,
        "order": (ArtifactSlot.Y.value, ArtifactSlot.X.value),
    },
    Group.G3.value: {
        "t1_condition": Condition.B.value,
        "t2_condition": Condition.A.value,
        "order": (ArtifactSlot.X.value, ArtifactSlot.Y.value),
    },
    Group.G4.value: {
        "t1_condition": Condition.B.value,
        "t2_condition": Condition.A.value,
        "order": (ArtifactSlot.Y.value, ArtifactSlot.X.value),
    },
}

# Per-class target quotas.  Each class has 15 T1 Standard, 15 T1 HLSF,
# 15 X and 15 Y.  Total across the four classes is 30 per group.
CLASS_GROUP_QUOTAS: Dict[int, Dict[str, int]] = {
    1: {Group.G1.value: 8, Group.G2.value: 7, Group.G3.value: 7, Group.G4.value: 8},
    2: {Group.G1.value: 7, Group.G2.value: 8, Group.G3.value: 8, Group.G4.value: 7},
    3: {Group.G1.value: 8, Group.G2.value: 7, Group.G3.value: 7, Group.G4.value: 8},
    4: {Group.G1.value: 7, Group.G2.value: 8, Group.G3.value: 8, Group.G4.value: 7},
}


def class_group_quota(class_id: int, per_class: int = 30) -> Dict[str, int]:
    """Return target group counts for one class.

    The formal 30-person classes use the frozen 8/7/7/8 or 7/8/8/7 pattern.
    Other sizes (internal class 0, local tests) fall back to the old balanced
    base/remainder distribution without changing already-assigned students.
    """
    if per_class == 30 and class_id in CLASS_GROUP_QUOTAS:
        return dict(CLASS_GROUP_QUOTAS[class_id])
    base, remainder = divmod(per_class, len(GROUPS))
    extra = GROUPS[:remainder]
    return {group: base + (1 if group in extra else 0) for group in GROUPS}


def _assignment_for(group: str, design_version: Optional[str]) -> Dict[str, object]:
    if group not in GROUP_ASSIGNMENTS:
        raise ValueError(f"Unknown group: {group}")
    # Only explicit crossover runs receive the new T2 condition.  Historical
    # v1.5 runs have no design_version and must remain T2 = Standard AI.
    if design_version in CROSSOVER_DESIGN_VERSIONS:
        return GROUP_ASSIGNMENTS[group]
    legacy = GROUP_ASSIGNMENTS[group]
    return {
        "t1_condition": legacy["t1_condition"],
        "t2_condition": Condition.A.value,
        "order": legacy["order"],
    }


def group_t1_condition(group: str) -> str:
    if group not in GROUP_ASSIGNMENTS:
        raise ValueError(f"Unknown group: {group}")
    return str(GROUP_ASSIGNMENTS[group]["t1_condition"])


def group_t2_condition(group: str) -> str:
    if group not in GROUP_ASSIGNMENTS:
        raise ValueError(f"Unknown group: {group}")
    return str(GROUP_ASSIGNMENTS[group]["t2_condition"])


def group_artifact_order(group: str) -> Tuple[str, str]:
    if group not in GROUP_ASSIGNMENTS:
        raise ValueError(f"Unknown group: {group}")
    order = GROUP_ASSIGNMENTS[group]["order"]
    return tuple(order)  # type: ignore[return-value]


def group_condition_sequence(group: str) -> str:
    return group_t1_condition(group) + group_t2_condition(group)


def group_artifact_sequence(group: str) -> str:
    return "".join(group_artifact_order(group))


def round_assignment(
    group: str,
    round_no: int,
    design_version: Optional[str] = None,
) -> Tuple[str, str]:
    """Return ``(artifact_slot, condition)`` for a T1/T2 round.

    Crossover runs receive the group's T1/T2 conditions.  Historical runs
    (design_version is None or an older value) retain T2 = Standard AI.
    """
    if group not in GROUP_ASSIGNMENTS:
        raise ValueError(f"Unknown group: {group}")
    if round_no not in (1, 2):
        raise ValueError(f"Unknown round: {round_no}")
    assignment = _assignment_for(group, design_version)
    order = tuple(assignment["order"])  # type: ignore[arg-type]
    condition = assignment["t1_condition"] if round_no == 1 else assignment["t2_condition"]
    return order[round_no - 1], str(condition)
