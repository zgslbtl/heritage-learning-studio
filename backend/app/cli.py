from __future__ import annotations

import argparse
import asyncio
import io
import sys
from typing import List

from PIL import Image, ImageDraw

from .bootstrap import bootstrap_cohort
from .config import Settings
from .db import Database
from .models import ArtifactVersion, Run
from .schemas import InstrumentPayload
from .services.artifacts import create_artifact_version
from .services.instruments import create_instrument_version
from .services.formal_content import import_formal_content, import_formal_v2, release_survey_v3
from .services.readiness import activate_protocol, build_readiness
from .services.peer import rebuild_peer_batch

DEMO_QUESTIONS = {
    "k0": {
        "title": "K0 知识前测占位 / Knowledge Pre-test placeholder",
        "instructions": "DEMO PLACEHOLDER — not reviewed research content. 本环节不提供 AI 与资料访问。",
        "questions": [
            {
                "id": "demo_k0",
                "type": "single_choice",
                "prompt": "这是一个占位 K0 题目。请选择一个选项以测试流程。"
                " / Placeholder K0 item for flow testing.",
                "required": True,
                "options": [
                    {"value": "a", "label": "选项 A / Option A"},
                    {"value": "b", "label": "选项 B / Option B"},
                ],
            }
        ],
    },
    "k1": {
        "title": "K1 知识后测占位 / T1 Knowledge Post-test placeholder",
        "instructions": "DEMO PLACEHOLDER — no substantive assessment.",
        "questions": [
            {
                "id": "demo_k1",
                "type": "short_text",
                "prompt": "请写一句占位回答以测试 K1 页面。 / Enter a placeholder K1 sentence.",
                "required": True,
                "max_length": 200,
            }
        ],
    },
    "k2": {
        "title": "K2 知识前测占位 / T2 Knowledge Pre-test placeholder",
        "instructions": "DEMO PLACEHOLDER — no substantive assessment.",
        "questions": [
            {
                "id": "demo_k2",
                "type": "multi_choice",
                "prompt": "这是一个占位 K2 多选题。 / Placeholder K2 multiple-choice item.",
                "required": True,
                "options": [
                    {"value": "x", "label": "选项 X / Option X"},
                    {"value": "y", "label": "选项 Y / Option Y"},
                ],
            }
        ],
    },
    "k3": {
        "title": "K3 知识后测占位 / T2 Knowledge Post-test placeholder",
        "instructions": "DEMO PLACEHOLDER — no substantive assessment.",
        "questions": [
            {
                "id": "demo_k3",
                "type": "short_text",
                "prompt": "请写一句占位回答以测试 K3 页面。 / Enter a placeholder K3 sentence.",
                "required": True,
                "max_length": 300,
            }
        ],
    },
    "survey": {
        "title": "体验问卷占位 / Experience Survey placeholder",
        "instructions": "DEMO PLACEHOLDER — not a research instrument.",
        "questions": [
            {
                "id": "demo_survey",
                "type": "likert",
                "prompt": "请选择一个占位评分。 / Choose a placeholder rating.",
                "required": True,
                "scale_min": 1,
                "scale_max": 5,
                "scale_labels": ["低 / Low", "", "中 / Mid", "", "高 / High"],
            }
        ],
    },
}


def _placeholder_png(slot: str) -> bytes:
    color = (214, 222, 228) if slot == "X" else (226, 218, 207)
    image = Image.new("RGB", (1400, 900), color)
    draw = ImageDraw.Draw(image)
    for x in range(0, 1400, 40):
        shade = (190 + (x // 40) % 20, 198, 204)
        draw.line((x, 0, x + 200, 900), fill=shade, width=2)
    draw.rectangle((70, 70, 1330, 830), outline=(90, 105, 118), width=3)
    draw.text((110, 360), f"DEMO PLACEHOLDER — ARTIFACT {slot}", fill=(50, 60, 68))
    draw.text((110, 400), "No real heritage content configured", fill=(70, 80, 88))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def seed_demo(settings: Settings) -> None:
    db = Database(settings.database_url, settings.db_pool_size, settings.db_max_overflow)
    try:
        async with db.session_factory() as session:
            await bootstrap_cohort(session, settings)
            any_run = (await session.execute(__import__("sqlalchemy").select(Run).limit(1))).first()
            if any_run:
                raise RuntimeError("Refusing to seed demo content after any run exists")
            latest_x = (
                await session.execute(
                    __import__("sqlalchemy").select(ArtifactVersion)
                    .where(ArtifactVersion.slot == "X")
                    .order_by(ArtifactVersion.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if latest_x is None:
                for slot in ("X", "Y"):
                    await create_artifact_version(
                        session,
                        settings,
                        slot=slot,
                        title=f"演示文物 {slot}（占位） / Demo Artifact {slot}",
                        era="未配置 / Not configured",
                        artifact_type="占位 / Placeholder",
                        introduction=(
                            "DEMO PLACEHOLDER. This is neutral test content, not a real "
                            "museum artifact. Configure approved Evidence Packs in the "
                            "researcher console before any formal study."
                        ),
                        facts=["占位事实条目 / Placeholder fact"],
                        evidence=["占位来源 / Placeholder source"],
                        uncertainty=["占位不确定说明 / Placeholder uncertainty"],
                        image_bytes=_placeholder_png(slot),
                        image_filename=f"demo-{slot}.png",
                        is_demo=True,
                    )
                for kind, payload_data in DEMO_QUESTIONS.items():
                    await create_instrument_version(
                        session,
                        kind=kind,
                        payload=InstrumentPayload.model_validate(payload_data),
                        is_demo=True,
                    )
                await session.commit()
            active = await activate_protocol(session, settings, allow_demo=True)
            await session.commit()
            readiness = await build_readiness(session, settings)
            print("Demo protocol activated:", active.id)
            print(
                "Readiness:",
                "ready" if readiness["ready_for_students"] else "not ready",
            )
            for check in readiness["checks"]:
                if not check["ok"]:
                    print(f"  FAIL {check['key']}: {check['detail']}")
            if settings.auth_mode == "email":
                print("Student login: PolyU email (use class 0 for internal testing)")
            else:
                print(f"Codes CSV: {settings.codes_csv_path}")
    finally:
        await db.dispose()


async def load_formal_content(settings: Settings, dry_run: bool = False) -> None:
    db = Database(settings.database_url, settings.db_pool_size, settings.db_max_overflow)
    try:
        async with db.session_factory() as session:
            result = await import_formal_content(session, settings, dry_run=dry_run)
            print("Formal content import:", result)
    finally:
        await db.dispose()


async def load_formal_v2(
    settings: Settings,
    *,
    dry_run: bool = False,
    activate: bool = False,
    force_new_version: bool = False,
) -> None:
    db = Database(settings.database_url, settings.db_pool_size, settings.db_max_overflow)
    try:
        async with db.session_factory() as session:
            result = await import_formal_v2(
                session,
                settings,
                dry_run=dry_run,
                activate=activate,
                force_new_version=force_new_version,
            )
            print("Formal V2 content import:", result)
    finally:
        await db.dispose()


async def print_readiness(settings: Settings) -> None:
    db = Database(settings.database_url)
    try:
        async with db.session_factory() as session:
            data = await build_readiness(session, settings)
            print("Ready to activate:", data["ready_to_activate"])
            print("Ready for students:", data["ready_for_students"])
            for check in data["checks"]:
                print(("[OK]  " if check["ok"] else "[FAIL]") + f" {check['key']}: {check['detail']}")
    finally:
        await db.dispose()


async def rebuild_peer_batch_cli(settings: Settings, class_id: int, *, force: bool) -> None:
    db = Database(settings.database_url, settings.db_pool_size, settings.db_max_overflow)
    try:
        async with db.session_factory() as session:
            batch = await rebuild_peer_batch(session, class_id, force=force)
            print(
                "Peer batch rebuilt:",
                {
                    "batch_id": str(batch.id),
                    "class_id": class_id,
                    "algorithm_version": batch.algorithm_version,
                    "eligible_work_count": batch.eligible_work_count,
                    "config": batch.config_json,
                },
            )
    finally:
        await db.dispose()


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Heritage Learning Studio operations")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed-demo", help="Create clearly marked neutral demo content (dev/test only)")
    sub.add_parser("readiness", help="Print protocol readiness checks")
    sub.add_parser("release-survey-v3", help="Activate the V3 review survey for future runs; retain frozen historical versions")
    formal = sub.add_parser("import-formal", help="Import the approved two-artifact formal content")
    formal.add_argument("--dry-run", action="store_true")
    formal_v2 = sub.add_parser(
        "import-formal-v2",
        help="Import the assessment V2 content pack without deleting legacy content",
    )
    formal_v2.add_argument("--dry-run", action="store_true")
    formal_v2.add_argument("--activate", action="store_true")
    formal_v2.add_argument("--force-new-version", action="store_true")
    rebuild_peer = sub.add_parser(
        "rebuild-peer-batch",
        help="Supersede and rebuild one class peer batch (pilot/test only)",
    )
    rebuild_peer.add_argument("--class-id", type=int, required=True)
    rebuild_peer.add_argument("--force", action="store_true")
    rebuild_peer.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    settings = Settings()
    if args.command == "release-survey-v3":
        async def release():
            db = Database(settings.database_url)
            try:
                async with db.session_factory() as session:
                    result = await release_survey_v3(session)
                    await session.commit()
                    print(result)
            finally:
                await db.dispose()
        asyncio.run(release())
        return 0
    if args.command == "import-formal":
        asyncio.run(load_formal_content(settings, dry_run=args.dry_run))
        return 0
    if args.command == "import-formal-v2":
        asyncio.run(
            load_formal_v2(
                settings,
                dry_run=args.dry_run,
                activate=args.activate,
                force_new_version=args.force_new_version,
            )
        )
        return 0
    if settings.is_production:
        print("Refusing development CLI in production environment.", file=sys.stderr)
        return 2
    if args.command == "seed-demo":
        asyncio.run(seed_demo(settings))
        return 0
    if args.command == "readiness":
        asyncio.run(print_readiness(settings))
        return 0
    if args.command == "rebuild-peer-batch":
        if not args.confirm:
            print("Refusing to rebuild without --confirm.", file=sys.stderr)
            return 2
        asyncio.run(rebuild_peer_batch_cli(settings, args.class_id, force=args.force))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
