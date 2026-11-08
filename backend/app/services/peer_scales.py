from __future__ import annotations

from typing import Any, Dict, List, Optional

# Peer-review content versions.  A batch freezes the version it was created
# with; the resolved definition is also snapshotted into PeerBatch.config_json
# so historical batches keep their original wording even if this file changes.
PEER_SCALE_V2 = "peer-scale-v2"
PEER_SCALE_V21 = "peer-review-v2.1-pilot"
DEFAULT_PEER_SCALE_VERSION = PEER_SCALE_V21

LEGACY_PEER_SCORE_KEYS = ("clarity", "evidence_link", "attraction")
PEER_V21_SCORE_KEYS = (
    "cultural_clarity",
    "cultural_translation",
    "design_originality",
)

# The legacy scale is kept only so already-frozen batches remain readable.
# It has no per-point anchors because the original UI only showed 1-5 numbers.
PEER_SCALE_V2_DEFINITION: Dict[str, Any] = {
    "version": PEER_SCALE_V2,
    "title": "请评价分配给你的匿名作品",
    "instructions": (
        "你将看到若干件同班同学的创作作品。作品以匿名编号显示，不显示作者或他人评分。"
        "每件作品请按三个维度独立评分；你的评分不会显示给作品作者。"
    ),
    "principles": [],
    "comment_prompt": "可以写一条具体、尊重作者的建议…",
    "score_min": 1,
    "score_max": 5,
    "dimensions": [
        {
            "key": "clarity",
            "short": "",
            "label": "文化信息表达是否清楚？",
            "prompt": "",
            "anchors": [],
        },
        {
            "key": "evidence_link",
            "short": "",
            "label": "文物知识与设计选择的联系是否容易理解？",
            "prompt": "",
            "anchors": [],
        },
        {
            "key": "attraction",
            "short": "",
            "label": "作品整体设计吸引力如何？",
            "prompt": "",
            "anchors": [],
        },
    ],
}

PEER_SCALE_V21_DEFINITION: Dict[str, Any] = {
    "version": PEER_SCALE_V21,
    "title": "看看其他同学的设计",
    "instructions": (
        "请根据作品图片和作品说明评价。重点是你能否看懂作品想表达的文化内容，"
        "以及设计怎样从文物中获得启发。\n\n"
        "不要求你判断历史资料是否绝对正确。请按照自己的理解评价。"
    ),
    "principles": [
        "设计有创意不等于一定要完全改变文物图案。",
        "保留、简化、重新组合、改变用途、转变媒介，都可能体现创造性。",
        "与文物外观差异大，不代表一定具有更高创造性。",
        "作品图片美观，不代表文化理解一定准确。",
        "学生评价的是作品表达和设计转译的可理解程度，而不是承担专业历史考证责任。",
    ],
    "comment_prompt": "你觉得这件作品最有意思的地方是什么？或者还有哪里可以改进？",
    "score_min": 1,
    "score_max": 5,
    "dimensions": [
        {
            "key": "cultural_clarity",
            "short": "P1",
            "label": "文化表达清晰度",
            "prompt": "这件作品想表达的文物知识或文化意义是否清楚？",
            "anchors": [
                "几乎无法理解。",
                "表达不太清楚。",
                "能够理解一部分。",
                "表达比较清楚。",
                "表达非常清楚。",
            ],
        },
        {
            "key": "cultural_translation",
            "short": "P2",
            "label": "文化转译清晰度",
            "prompt": (
                "你能否看出这件作品如何将文物的特征、结构、功能或文化意义"
                "转化为新的设计？"
            ),
            "anchors": [
                "看不出明确联系。",
                "联系比较模糊。",
                "能够看出一定联系。",
                "联系清楚。",
                "联系清楚且有说服力。",
            ],
        },
        {
            "key": "design_originality",
            "short": "P3",
            "label": "设计创意",
            "prompt": "你认为这件作品对文物内容的设计转化有多少新意？",
            "anchors": [
                "缺少明显的新构思。",
                "新意较少。",
                "有一定新想法。",
                "构思比较新颖。",
                "构思有明显的新意。",
            ],
        },
    ],
}

PEER_SCALES: Dict[str, Dict[str, Any]] = {
    PEER_SCALE_V2: PEER_SCALE_V2_DEFINITION,
    PEER_SCALE_V21: PEER_SCALE_V21_DEFINITION,
}


def peer_scale(version: Optional[str]) -> Dict[str, Any]:
    """Return a scale definition, falling back to the legacy scale."""

    return PEER_SCALES.get(str(version or ""), PEER_SCALE_V2_DEFINITION)


def peer_scale_for_batch(batch: Any) -> Dict[str, Any]:
    """Resolve the frozen scale for one PeerBatch.

    New batches carry a full definition snapshot in ``config_json["scale"]``.
    Old batches predate the snapshot and fall back to the legacy version.
    """

    config = getattr(batch, "config_json", None) or {}
    snapshot = config.get("scale")
    if isinstance(snapshot, dict) and snapshot.get("dimensions"):
        return snapshot
    return peer_scale(getattr(batch, "scale_version", None))


def score_keys_for_scale(scale: Dict[str, Any]) -> List[str]:
    return [
        str(dimension.get("key"))
        for dimension in (scale.get("dimensions") or [])
        if dimension.get("key")
    ]
