from __future__ import annotations

import csv
import io
import logging
import os
import secrets
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings
from .domain import GROUPS
from .models import ClassGroup, Participant
from .security import code_hmac, generate_code
from .services.assignment import group_slots

logger = logging.getLogger("hls.bootstrap")


async def ensure_classes(
    session: AsyncSession, class_count: int = 4, include_test_class: bool = False
) -> None:
    if include_test_class:
        existing = await session.get(ClassGroup, 0)
        if existing is None:
            session.add(ClassGroup(id=0, name="班级 0 / 内部测试 / Internal testing"))
    for class_id in range(1, class_count + 1):
        existing = await session.get(ClassGroup, class_id)
        if existing is None:
            session.add(
                ClassGroup(
                    id=class_id, name=f"班级 {class_id} / Class {class_id}"
                )
            )
    await session.flush()


def _balance_groups(per_class: int, rng: secrets.SystemRandom) -> List[str]:
    base = per_class // len(GROUPS)
    remainder = per_class % len(GROUPS)
    extra_groups = set(rng.sample(GROUPS, remainder))
    values: List[str] = []
    for group in GROUPS:
        values.extend([group] * (base + (1 if group in extra_groups else 0)))
    rng.shuffle(values)
    return values


def _write_codes_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="codes-", suffix=".csv", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "class_id",
                    "class_name",
                    "access_code",
                    "group",
                    "participant_id",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


async def bootstrap_cohort(
    session: AsyncSession, settings: Settings, force: bool = False
) -> Optional[Dict[str, object]]:
    """Seed classes and exactly one cohort of anonymous participants.

    Returns a summary if participants were generated, otherwise None.
    The plaintext codes are written only to the protected one-time CSV.
    """

    if not settings.anon_code_pepper:
        raise RuntimeError("ANON_CODE_PEPPER is required to create access codes")

    await ensure_classes(
        session,
        0 if settings.is_beta else settings.class_count,
        include_test_class=settings.is_beta or not settings.is_production,
    )
    await session.execute(text("SELECT pg_advisory_xact_lock(7819001)"))
    if settings.auth_mode == "email":
        await session.commit()
        logger.info(
            "Email login mode: classes ensured; no pre-generated participant codes"
        )
        return {
            "participants": 0,
            "classes": settings.class_count,
            "codes_csv": "",
        }
    count = (
        await session.execute(select(func.count()).select_from(Participant))
    ).scalar_one()
    if count and not force:
        await session.commit()
        return None
    if count and force:
        raise RuntimeError("Refusing to reissue codes while participants exist")

    expected = settings.class_count * settings.participants_per_class
    seen: set = set()
    csv_rows: List[Dict[str, str]] = []
    class_names = {
        class_id: f"班级 {class_id} / Class {class_id}"
        for class_id in range(1, settings.class_count + 1)
    }

    for class_id in range(1, settings.class_count + 1):
        groups = group_slots(
            settings.anon_code_pepper,
            class_id,
            settings.participants_per_class,
        )
        for group in groups:
            code = generate_code()
            while code in seen:
                code = generate_code()
            seen.add(code)
            participant = Participant(
                class_id=class_id,
                group_name=group,
                access_code_hmac=code_hmac(code, settings.anon_code_pepper),
                access_code_last4=code[-4:],
            )
            session.add(participant)
            await session.flush()
            csv_rows.append(
                {
                    "class_id": str(class_id),
                    "class_name": class_names[class_id],
                    "access_code": code,
                    "group": group,
                    "participant_id": str(participant.id),
                }
            )

    if len(csv_rows) != expected:
        raise RuntimeError("Cohort size did not match configuration")

    settings.ensure_directories()
    _write_codes_csv(settings.codes_csv_path, csv_rows)
    try:
        await session.commit()
    except Exception:
        settings.codes_csv_path.unlink(missing_ok=True)
        raise
    logger.info(
        "Generated %s anonymous participants; protected code CSV at %s",
        len(csv_rows),
        settings.codes_csv_path,
    )
    return {
        "participants": len(csv_rows),
        "classes": settings.class_count,
        "codes_csv": str(settings.codes_csv_path),
    }


def read_codes_csv(settings: Settings) -> Optional[str]:
    path = settings.codes_csv_path
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8-sig")
