from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image, ImageChops, ImageOps
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..domain import ASSESSMENT_V1_VERSION, ASSESSMENT_V2_VERSION
from ..errors import AppError
from ..models import (
    ArtifactVersion,
    AssessmentItemKey,
    ClassGroup,
    InstrumentVersion,
    ProtocolAssessmentForm,
    ProtocolVersion,
    Run,
)
from ..schemas import InstrumentPayload
from .artifacts import create_artifact_version
from .instruments import create_instrument_version
from .storage import Storage

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content" / "formal_v1"
CONTENT_V2_DIR = Path(__file__).resolve().parent.parent / "content" / "formal_v2"
KIND_TITLES = {
    "k0": "开始前的小问题",
    "k1": "刚才的学习回顾",
    "k2": "下一件文物之前",
    "k3": "最后的学习回顾",
    "survey": "最后几个问题",
}
KIND_INSTRUCTIONS = {
    "k0": "开始前，想先了解你现在的想法。请按自己的理解填写，不需要使用 AI 或查找资料。",
    "k1": "刚才的学习之后，想再听听你的想法。请按自己的理解填写，不需要使用 AI 或查找资料。",
    "k2": "在认识下一件文物之前，先说说你现在的想法。请按自己的理解填写。",
    "k3": "最后，想再听听你的想法。请按自己的理解填写。",
    "survey": "下面的问题想了解你在两轮创作中的真实体验。两轮使用的文物和 AI 互动方式可能不同，请分别回想每一轮的情况。没有正确或错误答案。",
}
# English reading aid only; the Chinese instructions remain the instrument text.
KIND_TITLES_EN = {
    "k0": "Before we begin",
    "k1": "A quick look back",
    "k2": "Before the next artifact",
    "k3": "One last look",
    "survey": "A few last questions",
}
KIND_INSTRUCTIONS_EN = {
    "k0": "Before we begin, a few questions about your current thinking. Please answer from your own understanding; you do not need AI or to look anything up.",
    "k1": "After the learning you just did, we would like to hear your thinking again. Please answer from your own understanding; you do not need AI or to look anything up.",
    "k2": "Before you meet the next artifact, tell us what you think now. Please answer from your own understanding.",
    "k3": "Finally, we would like to hear your thinking once more. Please answer from your own understanding.",
    "survey": "These questions ask about your real experience in the two rounds. The artifact and the way the AI interacted may have differed between rounds; please recall each round separately. There are no right or wrong answers.",
}
DYNAMIC_PREFIX = {0: "M", 1: "T"}


def _read_json(name: str, content_dir: Path = CONTENT_DIR) -> Dict[str, Any]:
    path = content_dir / name
    if not path.exists():
        raise AppError(503, "formal_content_missing", f"Formal content file missing: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _prepare_media(
    settings: Settings,
    source_dir: Path = CONTENT_DIR,
    target_name: str = "formal_v1",
) -> Dict[str, Dict[str, Any]]:
    settings.ensure_directories()
    artifacts_dir = settings.data_dir / "artifacts" / target_name
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    result: Dict[str, Dict[str, Any]] = {}
    media_defs = []
    artifacts = _read_json("artifacts.json", source_dir)
    for obj in artifacts.values():
        media_defs.extend(obj.get("media") or [])
    for item in media_defs:
        key = item["key"]
        source = source_dir / "media" / item["file"]
        if not source.exists():
            raise AppError(503, "formal_media_missing", f"Missing media file: {item['file']}")
        source_digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
        prefix = f"{key}-{source_digest}" if settings.storage_backend == "blob" else key
        original_name = f"{prefix}-original.png"
        display_name = f"{prefix}-display.jpg"
        original_path = artifacts_dir / original_name
        display_path = artifacts_dir / display_name
        original_path.write_bytes(source.read_bytes())
        with Image.open(io.BytesIO(source.read_bytes())) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            if image.mode == "L":
                image = image.convert("RGB")
            width, height = image.size
            # The T registration image has large white margins.  Keep the
            # original file, but trim the display variant so the artwork fills
            # the reading panel and the assessment image.
            white = Image.new("RGB", image.size, (255, 255, 255))
            difference = ImageChops.difference(image, white).convert("L")
            mask = difference.point(lambda value: 255 if value > 12 else 0)
            bbox = mask.getbbox()
            if bbox:
                left, top, right, bottom = bbox
                if (right - left) >= 200 and (bottom - top) >= 200:
                    image = image.crop(bbox)
            image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
            image.save(display_path, format="JPEG", quality=88, optimize=True)
        if settings.storage_backend == "blob":
            storage = Storage(settings)
            for path, mime in ((original_path, "image/png"), (display_path, "image/jpeg")):
                storage.put_file(str(path.relative_to(settings.data_dir)), path, mime, overwrite=True)
        result[key] = {
            **item,
            "display_path": str(Path("artifacts") / target_name / display_name),
            "original_path": str(Path("artifacts") / target_name / original_name),
            "mime": "image/jpeg",
            "original_mime": "image/png",
            "sha256": hashlib.sha256(original_path.read_bytes()).hexdigest(),
            "width": width,
            "height": height,
        }
    return result


def _media_payload(
    media: Dict[str, Dict[str, Any]], keys: list[str]
) -> list[Dict[str, Any]]:
    return [media[key] for key in keys if key in media]


def _instrument_payload(
    *,
    kind: str,
    object_code: str,
    form_code: str,
    questions: list[dict],
    scoring_version: str,
) -> InstrumentPayload:
    return InstrumentPayload(
        title=KIND_TITLES[kind],
        title_en=KIND_TITLES_EN.get(kind),
        instructions=KIND_INSTRUCTIONS[kind],
        instructions_en=KIND_INSTRUCTIONS_EN.get(kind),
        scoring_version=scoring_version,
        questions=questions,
    )


def _stage_questions(
    forms_data: Dict[str, Any],
    kind: str,
    object_code: str,
    form_code: str,
) -> list[dict]:
    """Return the questions shown at one K stage.

    v1 has no ``stage_rules``: K0 prepends baseline and all forms keep the short
    answer.  v2 supplies stage rules and omits the short answer at K0/K2.
    """
    baseline = forms_data.get("baseline") or []
    form_questions = forms_data["forms"][object_code][form_code]
    stage_rules = forms_data.get("stage_rules") or (forms_data.get("meta") or {}).get("stage_rules") or {}
    rules = stage_rules.get(kind)
    if rules is None:
        include_baseline = kind == "k0"
        include_short = True
    else:
        include_baseline = bool(rules.get("baseline"))
        include_short = bool(rules.get("include_short", True))

    questions: list[dict] = []
    if include_baseline:
        questions.extend(
            {**question, "section": "开始前"} for question in baseline
        )
    for question in form_questions:
        if question.get("type") == "short_text" and not include_short:
            continue
        if kind == "k0":
            questions.append({**question, "section": "关于这件文物"})
        else:
            questions.append(question)
    return questions


async def _latest_formal_artifact(
    session: AsyncSession, object_code: str
) -> Optional[ArtifactVersion]:
    result = await session.execute(
        select(ArtifactVersion)
        .where(
            ArtifactVersion.object_code == object_code,
            ArtifactVersion.is_demo.is_(False),
        )
        .order_by(ArtifactVersion.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _ensure_artifacts(
    session: AsyncSession,
    settings: Settings,
    *,
    artifact_dir: Path,
    reuse_artifacts: bool,
    target_name: str,
) -> tuple[Dict[str, ArtifactVersion], int]:
    artifacts_data = _read_json("artifacts.json", artifact_dir)
    artifacts: Dict[str, ArtifactVersion] = {}
    missing: list[str] = []

    if reuse_artifacts:
        for object_code in ("M", "T"):
            existing = await _latest_formal_artifact(session, object_code)
            if existing is not None:
                artifacts[object_code] = existing
            else:
                missing.append(object_code)
    else:
        missing = ["M", "T"]

    media: Dict[str, Dict[str, Any]] = {}
    if missing:
        media = _prepare_media(settings, artifact_dir, target_name)
        for object_code in missing:
            obj = artifacts_data[object_code]
            primary_bytes = (artifact_dir / "media" / next(
                item["file"] for item in obj["media"] if item["key"] == obj["image_key"]
            )).read_bytes()
            artifact_media = _media_payload(media, [item["key"] for item in obj["media"]])
            artifact = await create_artifact_version(
                session,
                settings,
                slot=obj["slot"],
                title=obj["title"],
                era=obj["era"],
                artifact_type=obj["type"],
                introduction=obj["introduction"],
                facts=[],
                evidence=[],
                uncertainty=[],
                image_bytes=primary_bytes,
                image_filename=f"{object_code}-primary.png",
                is_demo=False,
                object_code=object_code,
                sections=obj["sections"],
                media=artifact_media,
                rights_status=obj.get("rights_status", "internal-research"),
            )
            artifacts[object_code] = artifact
    return artifacts, len(media)


async def _import_content_pack(
    session: AsyncSession,
    settings: Settings,
    *,
    content_dir: Path,
    artifact_dir: Path,
    allow_existing_runs: bool,
    reuse_artifacts: bool,
    activate: bool,
    assessment_version: str,
    target_name: str,
    dry_run: bool = False,
    force_new_version: bool = False,
) -> Dict[str, Any]:
    if dry_run and settings.storage_backend == "blob":
        # Validate/roll back against the DB without uploading to durable storage.
        settings = settings.model_copy(update={"storage_backend": "local", "data_dir": settings.data_dir / "dry-run"})
    forms_data = _read_json("instruments.json", content_dir)
    keys_data = _read_json("assessment_keys.json", content_dir)
    rubric = _read_json("rubric.json", content_dir)
    meta = forms_data.get("meta") or {}
    rubric = {
        **rubric,
        "assessment_version": assessment_version,
        "content_version": meta.get("content_version", ""),
        "rationale_schema_version": meta.get("rationale_schema_version"),
        "stage_rules": meta.get("stage_rules"),
        "short_answer_max_score": meta.get("short_answer_max_score", 4),
    }
    scoring_version = str(meta.get("scoring_version") or "k-v1.0")
    short_max = int(meta.get("short_answer_max_score") or 4)

    existing_runs = (
        await session.execute(select(Run.id).limit(1))
    ).scalar_one_or_none()
    if existing_runs and not dry_run and not allow_existing_runs:
        raise AppError(
            409,
            "formal_import_requires_fresh_db",
            "Formal content can only be imported before any participant run exists.",
        )

    if (
        assessment_version == ASSESSMENT_V2_VERSION
        and not dry_run
        and not force_new_version
    ):
        active_v2 = (
            await session.execute(
                select(ProtocolVersion).where(
                    ProtocolVersion.is_active.is_(True),
                    ProtocolVersion.assessment_version == ASSESSMENT_V2_VERSION,
                )
            )
        ).scalar_one_or_none()
        if active_v2 is not None:
            raise AppError(
                409,
                "assessment_v2_already_active",
                "An active assessment V2 protocol already exists. Use a new version or force a new protocol.",
            )

    # Create only this deployment's enabled classes; beta has no formal classes.
    existing_classes = set(
        (await session.execute(select(ClassGroup.id))).scalars().all()
    )
    for class_id in settings.enabled_class_ids:
        if class_id not in existing_classes:
            session.add(ClassGroup(id=class_id, name="班级 0 / 内部测试 / Internal testing" if class_id == 0 else f"班级 {class_id} / Class {class_id}"))
    await session.flush()

    artifacts, media_count = await _ensure_artifacts(
        session,
        settings,
        artifact_dir=artifact_dir,
        reuse_artifacts=reuse_artifacts,
        target_name=target_name,
    )

    form_versions: Dict[tuple[str, str, str], InstrumentVersion] = {}
    key_rows: list[AssessmentItemKey] = []
    for kind in ("k0", "k1", "k2", "k3"):
        for object_code in ("M", "T"):
            for form_code in ("A", "B"):
                questions = _stage_questions(forms_data, kind, object_code, form_code)
                payload = _instrument_payload(
                    kind=kind,
                    object_code=object_code,
                    form_code=form_code,
                    questions=questions,
                    scoring_version=scoring_version,
                )
                version = await create_instrument_version(
                    session,
                    kind=kind,
                    payload=payload,
                    is_demo=False,
                    object_code=object_code,
                    form_code=form_code,
                )
                form_versions[(kind, object_code, form_code)] = version
                keys_for_form = keys_data["keys"][object_code][form_code]
                for question in questions:
                    if question["type"] == "short_text":
                        key_rows.append(
                            AssessmentItemKey(
                                instrument_version_id=version.id,
                                question_id=question["id"],
                                correct_value=None,
                                max_score=short_max,
                                construct="fact+relation" if short_max == 2 else "R+E",
                                dimension="short_answer",
                                notes=keys_data["short_answer"].get(question["id"], ""),
                            )
                        )
                    elif question["id"] in keys_for_form:
                        key_rows.append(
                            AssessmentItemKey(
                                instrument_version_id=version.id,
                                question_id=question["id"],
                                correct_value=keys_for_form[question["id"]],
                                max_score=1,
                                construct="knowledge",
                                dimension="mcq",
                                notes="",
                            )
                        )
    survey_payload = InstrumentPayload(**forms_data["survey"])
    survey = await create_instrument_version(
        session, kind="survey", payload=survey_payload, is_demo=False
    )
    await session.flush()
    for row in key_rows:
        session.add(row)
    await session.flush()

    active = (
        await session.execute(
            select(ProtocolVersion).where(ProtocolVersion.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if active is not None and activate:
        active.is_active = False
        await session.flush()
    protocol = ProtocolVersion(
        artifact_x_version_id=artifacts["M"].id,
        artifact_y_version_id=artifacts["T"].id,
        instrument_versions={
            kind: str(form_versions[(kind, "M", "A")].id)
            for kind in ("k0", "k1", "k2", "k3")
        }
        | {"survey": str(survey.id)},
        research_rubric_json=rubric,
        assessment_version=assessment_version,
        is_demo=False,
        is_active=activate,
        activated_at=datetime.now(timezone.utc) if activate else None,
    )
    session.add(protocol)
    await session.flush()
    for (kind, object_code, form_code), version in form_versions.items():
        session.add(
            ProtocolAssessmentForm(
                protocol_version_id=protocol.id,
                kind=kind,
                object_code=object_code,
                form_code=form_code,
                instrument_version_id=version.id,
            )
        )
    await session.flush()
    if dry_run:
        await session.rollback()
        return {
            "dry_run": True,
            "protocol_id": None,
            "assessment_version": assessment_version,
            "instruments": len(form_versions) + 1,
        }
    await session.commit()
    return {
        "dry_run": False,
        "protocol_id": str(protocol.id),
        "assessment_version": assessment_version,
        "activated": activate,
        "artifacts": {key: str(value.id) for key, value in artifacts.items()},
        "instruments": len(form_versions) + 1,
        "media": media_count,
    }


async def import_formal_content(
    session: AsyncSession, settings: Settings, *, dry_run: bool = False
) -> Dict[str, Any]:
    return await _import_content_pack(
        session,
        settings,
        content_dir=CONTENT_DIR,
        artifact_dir=CONTENT_DIR,
        allow_existing_runs=False,
        reuse_artifacts=False,
        activate=True,
        assessment_version=ASSESSMENT_V1_VERSION,
        target_name="formal_v1",
        dry_run=dry_run,
    )


async def import_formal_v2(
    session: AsyncSession,
    settings: Settings,
    *,
    dry_run: bool = False,
    activate: bool = False,
    force_new_version: bool = False,
) -> Dict[str, Any]:
    meta = _read_json("instruments.json", CONTENT_V2_DIR).get("meta") or {}
    assessment_version = str(meta.get("assessment_version") or ASSESSMENT_V2_VERSION)
    return await _import_content_pack(
        session,
        settings,
        content_dir=CONTENT_V2_DIR,
        artifact_dir=CONTENT_DIR,
        allow_existing_runs=True,
        reuse_artifacts=True,
        activate=activate,
        assessment_version=assessment_version,
        target_name="formal_v2",
        dry_run=dry_run,
        force_new_version=force_new_version,
    )
