from __future__ import annotations

import asyncio

import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..domain import ASSESSMENT_KINDS, ASSESSMENT_V1_VERSION, ASSESSMENT_V2_VERSION, SLOTS
from ..errors import AppError
from ..models import (
    ArtifactVersion,
    ClassGroup,
    InstrumentVersion,
    Participant,
    ProtocolAssessmentForm,
    ProtocolVersion,
    Run,
)
from ..schemas import InstrumentPayload
from .storage import Storage


async def latest_artifact(
    session: AsyncSession, slot: str
) -> Optional[ArtifactVersion]:
    result = await session.execute(
        select(ArtifactVersion)
        .where(ArtifactVersion.slot == slot)
        .order_by(ArtifactVersion.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def latest_instrument(
    session: AsyncSession, kind: str
) -> Optional[InstrumentVersion]:
    result = await session.execute(
        select(InstrumentVersion)
        .where(InstrumentVersion.kind == kind)
        .order_by(InstrumentVersion.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def latest_form_instruments(
    session: AsyncSession,
) -> Dict[Tuple[str, str, str], InstrumentVersion]:
    """Latest version for each kind × object × form (formal content)."""
    rows = (
        await session.execute(
            select(InstrumentVersion)
            .where(
                InstrumentVersion.object_code.is_not(None),
                InstrumentVersion.form_code.is_not(None),
            )
            .order_by(
                InstrumentVersion.kind,
                InstrumentVersion.object_code,
                InstrumentVersion.form_code,
                InstrumentVersion.version.desc(),
            )
        )
    ).scalars().all()
    result: Dict[Tuple[str, str, str], InstrumentVersion] = {}
    for version in rows:
        key = (version.kind, version.object_code or "", version.form_code or "")
        result.setdefault(key, version)
    return result


async def latest_content(session: AsyncSession) -> Dict[str, Any]:
    artifacts: Dict[str, ArtifactVersion] = {}
    for slot in SLOTS:
        artifact = await latest_artifact(session, slot)
        if artifact:
            artifacts[slot] = artifact
    instruments: Dict[str, InstrumentVersion] = {}
    for kind in ASSESSMENT_KINDS:
        instrument = await latest_instrument(session, kind)
        if instrument:
            instruments[kind] = instrument
    return {"artifacts": artifacts, "instruments": instruments}


async def active_protocol(session: AsyncSession) -> Optional[ProtocolVersion]:
    result = await session.execute(
        select(ProtocolVersion).where(ProtocolVersion.is_active.is_(True))
    )
    return result.scalar_one_or_none()


def _data_dir_writable(settings: Settings) -> bool:
    try:
        settings.ensure_directories()
        with tempfile.NamedTemporaryFile(dir=str(settings.data_dir), delete=True):
            pass
        return True
    except OSError:
        return False


async def build_readiness(session: AsyncSession, settings: Settings) -> Dict[str, Any]:
    latest = await latest_content(session)
    form_instruments = await latest_form_instruments(session)
    formal_forms_present = bool(form_instruments)
    active = await active_protocol(session)
    participant_count = (
        await session.execute(select(func.count()).select_from(Participant))
    ).scalar_one()
    run_count = (
        await session.execute(select(func.count()).select_from(Run))
    ).scalar_one()
    expected = settings.class_count * settings.participants_per_class

    checks: List[Dict[str, Any]] = []

    def add(key: str, label: str, ok: bool, detail: str) -> None:
        checks.append({"key": key, "label": label, "ok": bool(ok), "detail": detail})

    add(
        "admin_password",
        "Admin password configured",
        len(settings.admin_password) >= 16,
        "Set a 16+ character ADMIN_PASSWORD.",
    )
    add(
        "code_pepper",
        "Allocation pepper configured",
        len(settings.anon_code_pepper) >= 16,
        "Set ANON_CODE_PEPPER and never change it after participants are allocated.",
    )
    if settings.auth_mode == "email":
        add(
            "login_mode",
            "PolyU email login enabled",
            True,
            "Students enter with a PolyU email; class 0 is reserved for internal testing.",
        )
        class_ids = set(
            (
                await session.execute(
                    select(ClassGroup.id).where(
                        ClassGroup.id.in_(settings.enabled_class_ids)
                    )
                )
            ).scalars().all()
        )
        add(
            "classes",
            "Formal classes configured",
            class_ids == set(settings.enabled_class_ids),
            f"Class IDs found: {sorted(class_ids)}.",
        )
    else:
        add(
            "codes",
            "Cohort codes generated",
            participant_count == expected,
            f"{participant_count} participant records; expected {expected}.",
        )
        add(
            "codes_csv",
            "Protected cohort CSV present",
            settings.codes_csv_path.exists(),
            str(settings.codes_csv_path),
        )
    x_ok = bool(
        latest["artifacts"].get("X")
        and latest["artifacts"]["X"].title
        and latest["artifacts"]["X"].image_path
    )
    y_ok = bool(
        latest["artifacts"].get("Y")
        and latest["artifacts"]["Y"].title
        and latest["artifacts"]["Y"].image_path
    )
    add("artifact_x", "Artifact X evidence pack ready", x_ok, "Title, evidence and image required.")
    add("artifact_y", "Artifact Y evidence pack ready", y_ok, "Title, evidence and image required.")
    missing = [
        kind for kind in ASSESSMENT_KINDS if not latest["instruments"].get(kind)
    ]
    missing_forms = []
    if formal_forms_present:
        for kind in ("k0", "k1", "k2", "k3"):
            for object_code in ("M", "T"):
                for form_code in ("A", "B"):
                    if (kind, object_code, form_code) not in form_instruments:
                        missing_forms.append(f"{kind}-{object_code}-{form_code}")
    add(
        "instruments",
        "K0-K3 + survey instruments configured",
        not missing and not missing_forms,
        "Missing: " + ", ".join(missing + missing_forms)
        if (missing or missing_forms)
        else "All present.",
    )
    sections_ok = True if not formal_forms_present else all(
        latest["artifacts"].get(slot)
        and bool(latest["artifacts"][slot].sections_json)
        and bool(latest["artifacts"][slot].media_json)
        for slot in SLOTS
    )
    add(
        "artifact_sections",
        "Formal artifact sections and media configured",
        sections_ok,
        "Both artifacts need clickable sections and protected media.",
    )
    add(
        "text_model",
        "Text model configured",
        settings.text_configured,
        "TEXT_MODEL_BASE_URL, TEXT_MODEL_NAME and TEXT_MODEL_API_KEY are required.",
    )
    add(
        "image_model",
        "Image model configured",
        settings.image_configured,
        "IMAGE_MODEL_BASE_URL, IMAGE_MODEL_NAME and IMAGE_MODEL_API_KEY are required.",
    )
    add(
        "storage",
        "Persistent storage available",
        await asyncio.to_thread(Storage(settings).ready) if Storage(settings).cloud else _data_dir_writable(settings),
        ("Private JD Cloud OSS probe" if settings.storage_backend == "jdcloud_oss" else "Private Vercel Blob probe") if Storage(settings).cloud else str(settings.data_dir),
    )
    protocol_keys = set((active.instrument_versions or {}).keys()) if active else set()
    active_forms = 0
    if active:
        active_forms = (
            await session.execute(
                select(func.count())
                .select_from(ProtocolAssessmentForm)
                .where(ProtocolAssessmentForm.protocol_version_id == active.id)
            )
        ).scalar_one()
    protocol_ok = active is not None and set(ASSESSMENT_KINDS).issubset(protocol_keys)
    if formal_forms_present:
        protocol_ok = protocol_ok and active_forms == 16
    add(
        "protocol",
        "Active frozen assessment protocol",
        protocol_ok,
        "Activate a protocol containing K0-K3 and survey before students enter.",
    )
    demo_present = any(
        version.is_demo for version in latest["artifacts"].values()
    ) or any(version.is_demo for version in latest["instruments"].values())
    add(
        "production_content",
        "No demo content in production",
        not (settings.is_production and demo_present),
        "Demo content must not be used for formal data collection."
        if settings.is_production
        else "Demo content allowed outside production.",
    )
    add(
        "protocol_lock",
        "Protocol editable",
        run_count == 0,
        f"{run_count} run(s) exist; protocol changes are locked."
        if run_count
        else "No runs yet.",
    )

    required_keys = {
        "admin_password",
        "code_pepper",
        "artifact_x",
        "artifact_y",
        "instruments",
        "text_model",
        "image_model",
        "storage",
        "production_content",
        "protocol_lock",
    }
    if formal_forms_present:
        required_keys.add("artifact_sections")
    if settings.auth_mode == "email":
        required_keys.update({"login_mode", "classes"})
    else:
        required_keys.update({"codes", "codes_csv"})
    required_for_activation = [
        check for check in checks if check["key"] in required_keys
    ]
    return {
        "deployment_mode": settings.deployment_mode,
        "ready_to_activate": all(check["ok"] for check in required_for_activation),
        "ready_for_students": protocol_ok
        and all(
            check["ok"]
            for check in checks
            if check["key"] not in ("protocol", "protocol_lock")
        )
        and (not settings.is_production or not demo_present),
        "checks": checks,
        "active_protocol": protocol_summary(active) if active else None,
        "latest": {
            "artifacts": {
                slot: artifact_summary(version)
                for slot, version in latest["artifacts"].items()
            },
            "instruments": {
                kind: instrument_summary(version)
                for kind, version in latest["instruments"].items()
            },
        },
        "participant_count": participant_count,
        "run_count": run_count,
        "demo_present": demo_present,
    }


async def activate_protocol(
    session: AsyncSession, settings: Settings, allow_demo: bool = False
) -> ProtocolVersion:
    readiness = await build_readiness(session, settings)
    if not readiness["ready_to_activate"]:
        failed = [
            check["key"] for check in readiness["checks"] if not check["ok"]
        ]
        raise AppError(
            409,
            "protocol_not_ready",
            "The study protocol is not ready to activate.",
            {"failed_checks": failed},
        )
    latest = await latest_content(session)
    form_instruments = await latest_form_instruments(session)
    demo = any(version.is_demo for version in latest["artifacts"].values()) or any(
        version.is_demo for version in latest["instruments"].values()
    )
    if demo and (settings.is_production or not allow_demo):
        raise AppError(
            409,
            "demo_content_blocked",
            "Demo content cannot be activated for this environment.",
        )
    current = await active_protocol(session)
    if current is not None:
        current.is_active = False
        await session.flush()
    latest_k0_schema = (latest["instruments"].get("k0").schema_json or {}) if latest["instruments"].get("k0") else {}
    assessment_version = (
        ASSESSMENT_V2_VERSION
        if latest_k0_schema.get("scoring_version") == "k-v2.0"
        else ASSESSMENT_V1_VERSION
    )
    protocol = ProtocolVersion(
        artifact_x_version_id=latest["artifacts"]["X"].id,
        artifact_y_version_id=latest["artifacts"]["Y"].id,
        instrument_versions={
            kind: str(version.id) for kind, version in latest["instruments"].items()
        },
        research_rubric_json={},
        assessment_version=assessment_version,
        is_demo=demo,
        is_active=True,
        activated_at=datetime.now(timezone.utc),
    )
    session.add(protocol)
    await session.flush()
    if form_instruments:
        for (kind, object_code, form_code), version in form_instruments.items():
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
    return protocol


def artifact_summary(version: ArtifactVersion) -> Dict[str, Any]:
    return {
        "id": str(version.id),
        "slot": version.slot,
        "object_code": version.object_code,
        "version": version.version,
        "title": version.title,
        "era": version.era,
        "type": version.artifact_type,
        "has_image": bool(version.image_path),
        "has_sections": bool(version.sections_json),
        "is_demo": version.is_demo,
        "created_at": version.created_at.isoformat(),
        "image_url": f"/api/files/artifacts/{version.id}/image"
        if version.image_path
        else None,
    }


def instrument_summary(version: InstrumentVersion) -> Dict[str, Any]:
    return {
        "id": str(version.id),
        "kind": version.kind,
        "object_code": version.object_code,
        "form_code": version.form_code,
        "version": version.version,
        "title": version.title,
        "is_demo": version.is_demo,
        "created_at": version.created_at.isoformat(),
    }


def protocol_summary(protocol: ProtocolVersion) -> Dict[str, Any]:
    return {
        "id": str(protocol.id),
        "artifact_x_version_id": str(protocol.artifact_x_version_id),
        "artifact_y_version_id": str(protocol.artifact_y_version_id),
        "instrument_versions": protocol.instrument_versions,
        "assessment_version": protocol.assessment_version or ASSESSMENT_V1_VERSION,
        "is_demo": protocol.is_demo,
        "activated_at": protocol.activated_at.isoformat()
        if protocol.activated_at
        else None,
    }
