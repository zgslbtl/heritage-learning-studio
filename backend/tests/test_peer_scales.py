from __future__ import annotations

from types import SimpleNamespace

from app.services.peer_scales import (
    PEER_SCALE_V2,
    PEER_SCALE_V21,
    peer_scale,
    peer_scale_for_batch,
    score_keys_for_scale,
)


def test_v21_and_legacy_score_keys_are_kept_separate():
    v21 = peer_scale(PEER_SCALE_V21)
    legacy = peer_scale(PEER_SCALE_V2)
    assert v21["version"] == "peer-review-v2.1-pilot"
    assert score_keys_for_scale(v21) == [
        "cultural_clarity",
        "cultural_translation",
        "design_originality",
    ]
    assert legacy["version"] == "peer-scale-v2"
    assert score_keys_for_scale(legacy) == [
        "clarity",
        "evidence_link",
        "attraction",
    ]


def test_batch_uses_frozen_scale_snapshot_or_legacy_fallback():
    v21 = peer_scale(PEER_SCALE_V21)
    snapshot_batch = SimpleNamespace(
        scale_version="peer-review-v2.1-pilot",
        config_json={"scale": v21},
    )
    assert peer_scale_for_batch(snapshot_batch)["version"] == "peer-review-v2.1-pilot"

    old_batch = SimpleNamespace(scale_version="peer-scale-v2", config_json={})
    assert score_keys_for_scale(peer_scale_for_batch(old_batch)) == [
        "clarity",
        "evidence_link",
        "attraction",
    ]

    # An unknown future version without a snapshot falls back to the legacy
    # definition rather than inventing new dimensions.
    unknown = SimpleNamespace(scale_version="peer-scale-v99", config_json={})
    assert peer_scale_for_batch(unknown)["version"] == "peer-scale-v2"
