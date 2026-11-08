"""Version-specific researcher calculations; raw responses are never recoded."""
from __future__ import annotations

from typing import Any

SURVEY_V3 = "survey-v3.0-review"
REVERSE_ITEMS = ("S7", "S8", "S16", "S17")
V3_SCORE_FIELDS = (
    *(f"v3_{qid.lower()}_reversed" for qid in REVERSE_ITEMS),
    *(f"v3_{construct}_r{round_no}" for round_no in (1, 2)
      for construct in ("exploration_mean", "expressiveness_mean", "perceived_choice_mean", "mental_effort")),
)


def survey_v3_scores(version: str, answers: dict[str, Any]) -> dict[str, Any]:
    if version != SURVEY_V3:
        return {}

    def valid(qid: str, low: int, high: int):
        value = answers.get(qid)
        return value if type(value) is int and low <= value <= high else None

    result = {}
    for qid in REVERSE_ITEMS:
        value = valid(qid, 1, 7)
        if value is not None:
            result[f"v3_{qid.lower()}_reversed"] = 8 - value
    for round_no, offset in ((1, 0), (2, 9)):
        for construct, indices, low, high in (
            ("exploration_mean", (1, 2), 0, 10),
            ("expressiveness_mean", (3, 4), 0, 10),
            ("perceived_choice_mean", (5, 6, 7, 8), 1, 7),
            ("mental_effort", (9,), 1, 9),
        ):
            values = []
            for index in indices:
                qid = f"S{index + offset}"
                value = valid(qid, low, high)
                if value is None:
                    break
                values.append(8 - value if qid in REVERSE_ITEMS else value)
            else:
                result[f"v3_{construct}_r{round_no}"] = sum(values) / len(values)
    return result
