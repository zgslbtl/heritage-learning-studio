from __future__ import annotations

import hashlib
import hmac
import random
from typing import List

from ..domain import CROSSOVER_DESIGN_VERSION, GROUPS, class_group_quota

BLOCK_SIZE = len(GROUPS)


def block_order(pepper: str, class_id: int, block_no: int) -> List[str]:
    """Return a reproducible, secret-seeded shuffle of G1..G4 for one block.

    The order is stable for all four positions in the block, but cannot be
    predicted without the server-side pepper.
    """
    digest = hmac.new(
        pepper.encode("utf-8"),
        f"hlsf-block:{class_id}:{block_no}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    seed = int.from_bytes(digest[:16], "big", signed=False)
    order = list(GROUPS)
    random.Random(seed).shuffle(order)
    return order


def group_slots(pepper: str, class_id: int, per_class: int = 30) -> List[str]:
    """Return the shuffled per-class quota slots.

    The multiset is fixed by the target quota; only its order is randomised.
    The order is reproducible from the server-side pepper and class, so the
    allocation can be audited without storing a guessable seed.
    """
    quota = class_group_quota(class_id, per_class)
    slots: List[str] = []
    for group in GROUPS:
        slots.extend([group] * int(quota.get(group, 0)))
    digest = hmac.new(
        pepper.encode("utf-8"),
        f"hlsf-class-quota:{CROSSOVER_DESIGN_VERSION}:{class_id}:{per_class}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    seed = int.from_bytes(digest[:16], "big", signed=False)
    random.Random(seed).shuffle(slots)
    return slots


def allocation_seed_hash(pepper: str, class_id: int, per_class: int = 30) -> str:
    """Return a one-way audit hash for the quota shuffle seed."""
    return hmac.new(
        pepper.encode("utf-8"),
        f"hlsf-class-quota:{CROSSOVER_DESIGN_VERSION}:{class_id}:{per_class}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def group_for_index(
    pepper: str,
    class_id: int,
    index: int,
    per_class: int = 30,
) -> str:
    """Return the group assigned to the next first-login participant.

    For the formal 30-person class this walks a shuffled 8/7/7/8 (or
    7/8/8/7) quota list.  Already-created participants keep their stored group.
    Internal class 0 / non-standard sizes wrap the same list to avoid breaking
    local testing; no formal class can exceed its capacity.
    """
    if index < 0:
        raise ValueError("index must be non-negative")
    slots = group_slots(pepper, class_id, per_class)
    if not slots:
        raise ValueError("empty group quota")
    return slots[index % len(slots)]
