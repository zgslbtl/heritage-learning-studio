from collections import Counter

from app.domain import CROSSOVER_DESIGN_VERSION, GROUPS, CLASS_GROUP_QUOTAS
from app.services.assignment import group_for_index, group_slots


def test_each_class_has_exact_quota_and_balanced_t1_conditions():
    pepper = "test-pepper-0123456789-abcdef"
    for class_id in (1, 2, 3, 4):
        slots = group_slots(pepper, class_id, 30)
        assert len(slots) == 30
        assert Counter(slots) == Counter(CLASS_GROUP_QUOTAS[class_id])
        assert slots == group_slots(pepper, class_id, 30)
        t1_a = sum(1 for group in slots if group in ("G1", "G2"))
        t1_x = sum(1 for group in slots if group in ("G1", "G3"))
        assert t1_a == 15
        assert t1_x == 15


def test_group_assignment_is_stable_and_quota_sequenced():
    pepper = "test-pepper-0123456789-abcdef"
    for class_id in (1, 2, 3, 4):
        slots = group_slots(pepper, class_id, 30)
        assert [group_for_index(pepper, class_id, index, 30) for index in range(30)] == slots
        assert group_for_index(pepper, class_id, 0, 30) == slots[0]
        assert group_for_index(pepper, class_id, 30, 30) == slots[0]


def test_crossover_mapping_has_one_a_and_one_b_round():
    from app.domain import round_assignment

    for group in GROUPS:
        t1 = round_assignment(group, 1, CROSSOVER_DESIGN_VERSION)
        t2 = round_assignment(group, 2, CROSSOVER_DESIGN_VERSION)
        assert t1[0] != t2[0]
        assert {t1[1], t2[1]} == {"A", "B"}
        legacy_t2 = round_assignment(group, 2)
        assert legacy_t2[1] == "A"
