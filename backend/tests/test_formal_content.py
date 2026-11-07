from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.db import Base, Database
from app.models import (
    ArtifactVersion,
    AssessmentItemKey,
    ClassGroup,
    InstrumentVersion,
    ProtocolAssessmentForm,
    ProtocolVersion,
)
from app.services.formal_content import import_formal_content


@pytest.mark.asyncio
async def test_formal_content_import(settings):
    db = Database(settings.database_url)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with db.session_factory() as session:
            result = await import_formal_content(session, settings)
            assert result["instruments"] == 17
            protocol = (
                await session.execute(
                    select(ProtocolVersion).where(ProtocolVersion.is_active.is_(True))
                )
            ).scalar_one()
            assert protocol.is_demo is False
            forms = (
                await session.execute(
                    select(ProtocolAssessmentForm).where(
                        ProtocolAssessmentForm.protocol_version_id == protocol.id
                    )
                )
            ).scalars().all()
            assert len(forms) == 16
            artifacts = (
                await session.execute(select(ArtifactVersion))
            ).scalars().all()
            assert {artifact.object_code for artifact in artifacts} == {"M", "T"}
            for artifact in artifacts:
                assert artifact.sections_json
                assert artifact.media_json
                text = " ".join(section["body"] for section in artifact.sections_json)
                assert "现代设计" not in text
                assert "文创" not in text
                assert "可以用于今天" not in text
            instruments = (
                await session.execute(select(InstrumentVersion))
            ).scalars().all()
            assert len(instruments) == 17
            keys = (
                await session.execute(select(AssessmentItemKey))
            ).scalars().all()
            assert keys
            import re
            assert all(
                not re.search(r"总分|分值|得分|\d+\s*分", q.get("prompt", ""))
                for inst in instruments
                for q in (inst.schema_json or {}).get("questions", [])
            )
            assert (
                await session.execute(select(ClassGroup.id))
            ).scalars().all() == [1, 2, 3, 4]
            settings.auth_mode = "email"
            from app.services.readiness import build_readiness
            readiness = await build_readiness(session, settings)
            assert readiness["ready_for_students"] is True
            assert readiness["ready_to_activate"] is True
            assert any(
                check["key"] == "artifact_sections" and check["ok"]
                for check in readiness["checks"]
            )
    finally:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await db.dispose()


@pytest.mark.asyncio
async def test_formal_form_balance_and_assessment_image(settings):
    from app.models import Participant
    from app.services.assessments import assessment_payload
    from app.services.run_state import create_or_resume_run, protocol_instrument

    db = Database(settings.database_url)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with db.session_factory() as session:
            await import_formal_content(session, settings)
            p1 = Participant(class_id=1, group_name="G1", email="m1@polyu.edu.hk")
            p2 = Participant(class_id=1, group_name="G1", email="m2@polyu.edu.hk")
            session.add_all([p1, p2])
            await session.flush()
            run1 = await create_or_resume_run(session, participant=p1, settings=settings)
            run2 = await create_or_resume_run(session, participant=p2, settings=settings)
            assert run1.object_order == "MT"
            assert {run1.test_form_order, run2.test_form_order} == {"AB", "BA"}
            k0_1 = await protocol_instrument(session, run1, "k0")
            k1_1 = await protocol_instrument(session, run1, "k1")
            k2_1 = await protocol_instrument(session, run1, "k2")
            assert (k0_1.object_code, k0_1.form_code) == ("M", "A")
            assert (k1_1.object_code, k1_1.form_code) == ("M", "B")
            assert (k2_1.object_code, k2_1.form_code) == ("T", "A")
            payload = await assessment_payload(session, run1, "k0")
            assert payload["artifact_image_url"]
            assert "title" not in payload  # no artifact metadata beside image
            assert "score" not in json.dumps(payload).lower()
            questions = payload["instrument"]["questions"]
            assert questions[0]["section"] == "开始前"
            assert all("总分" not in q["prompt"] and "分值" not in q["prompt"] for q in questions)
    finally:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await db.dispose()


@pytest.mark.asyncio
async def test_formal_student_flow_uses_image_only_and_media(settings):
    import httpx
    from app.main import create_app

    settings.auth_mode = "email"
    settings.auto_bootstrap = False
    db = Database(settings.database_url)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with db.session_factory() as session:
            await import_formal_content(session, settings)
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                entered = await client.post(
                    "/api/auth/enter", json={"email": "formal@polyu.edu.hk", "class_id": 1}
                )
                assert entered.status_code == 200, entered.text
                payload = await client.get("/api/student/instruments/k0")
                assert payload.status_code == 200, payload.text
                data = payload.json()
                assert data["artifact_image_url"]
                assert "title" not in data
                assert all("总分" not in q["prompt"] for q in data["instrument"]["questions"])
                image = await client.get(data["artifact_image_url"])
                assert image.status_code == 200
                answers = {}
                for question in data["instrument"]["questions"]:
                    if question["type"] == "single_choice":
                        answers[question["id"]] = question["options"][0]["value"]
                    elif question["type"] == "short_text":
                        answers[question["id"]] = "这是用于流程测试的简短回答。"
                b01 = next(
                    question for question in data["instrument"]["questions"]
                    if question["id"] == "B-01"
                )
                other = next(
                    option for option in b01["options"] if option.get("allow_text")
                )
                answers["B-01"] = {"value": other["value"], "text": "建筑学" }
                submitted = await client.post(
                    "/api/student/instruments/k0/submit", json={"answers": answers}
                )
                assert submitted.status_code == 200, submitted.text
                tutorial = await client.post("/api/student/tutorial/complete")
                assert tutorial.status_code == 200, tutorial.text
                started = await client.post("/api/student/rounds/1/start")
                assert started.status_code == 200, started.text
                round_payload = await client.get("/api/student/rounds/1")
                assert round_payload.status_code == 200, round_payload.text
                artifact = round_payload.json()["artifact"]
                assert artifact["sections"]
                media_url = artifact["media"][1]["url"]
                media = await client.get(media_url)
                assert media.status_code == 200
                logged = await client.post(
                    "/api/student/rounds/1/evidence-events",
                    json={
                        "section": "M01",
                        "event_type": "section_open",
                        "meta": {"media_key": "M-full"},
                    },
                )
                assert logged.status_code == 200, logged.text
        async with db.session_factory() as session:
            from app.models import EvidenceEvent
            event = (
                await session.execute(select(EvidenceEvent).order_by(EvidenceEvent.id.desc()).limit(1))
            ).scalar_one()
            assert event.meta_json["media_key"] == "M-full"
    finally:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await db.dispose()
