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
from app.services.formal_content import import_formal_content, import_formal_v2


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
    from app.services.run_state import create_or_resume_run, protocol_instrument, protocol_instrument

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


@pytest.mark.asyncio
async def test_artifact_payload_carries_english_reading_aid(settings):
    from app.services.artifacts import student_artifact
    from app.services.formal_content import import_formal_v2
    from app.models import ArtifactVersion
    from sqlalchemy import select

    db = Database(settings.database_url)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with db.session_factory() as session:
            await import_formal_v2(session, settings, activate=True)
            artifact = (
                await session.execute(
                    select(ArtifactVersion).where(ArtifactVersion.object_code == "M")
                )
            ).scalars().first()
            payload = student_artifact(artifact)
            assert payload["title_en"].startswith("Square Rank Badge")
            sections = {section["key"]: section for section in payload["sections"]}
            assert sections["M03"]["title_en"].startswith("M03")
            assert "Evidence level" in sections["M03"]["body_en"]
            # The Chinese body is untouched and stays the reference text.
            assert "证据层次" in sections["M03"]["body"]
    finally:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await db.dispose()


async def test_formal_v2_k0_includes_demographics(settings):
    """K0 asks age and gender once, and only new runs see the new question set."""
    from app.errors import AppError
    from app.models import Participant
    from app.services.assessments import assessment_payload, submit_assessment
    from app.services.run_state import create_or_resume_run, protocol_instrument

    db = Database(settings.database_url)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with db.session_factory() as session:
            await import_formal_v2(session, settings, activate=True)
            participant = Participant(
                class_id=1, group_name="G1", email="demographics@polyu.edu.hk"
            )
            session.add(participant)
            await session.flush()
            run = await create_or_resume_run(session, participant=participant, settings=settings)
            k0 = await assessment_payload(session, run, "k0")
            questions = k0["instrument"]["questions"]
            by_id = {question["id"]: question for question in questions}
            assert [question["id"] for question in questions[:5]] == [
                "B-01",
                "B-02",
                "B-03",
                "B-04",
                "B-05",
            ]
            assert by_id["B-04"]["type"] == "single_choice"
            assert by_id["B-04"]["prompt"] == "你的年龄段是？"
            assert [option["value"] for option in by_id["B-04"]["options"]] == [
                "a",
                "b",
                "c",
                "d",
                "e",
                "f",
            ]
            assert by_id["B-05"]["prompt"] == "你的性别是？"
            assert by_id["B-05"]["options"][2]["label"] == "非二元／其他"
            assert by_id["B-05"]["options"][3]["label"] == "不愿透露"
            # English is a comprehension aid only: prompts and labels carry it,
            # values and required flags stay exactly as before.
            assert by_id["B-04"]["prompt_en"] == "What is your age group?"
            assert by_id["B-04"]["options"][0]["label_en"] == "18–20"
            assert by_id["B-04"]["options"][0]["value"] == "a"
            assert by_id["B-05"]["prompt_en"] == "What is your gender?"
            assert by_id["B-05"]["required"] is True

            k1_instrument = await protocol_instrument(session, run, "k1")
            assert not any(
                str(question.get("id", "")).startswith("B-")
                for question in (k1_instrument.schema_json or {}).get("questions", [])
            )

            answers = {
                question["id"]: question["options"][0]["value"]
                for question in questions
                if question["type"] == "single_choice"
            }
            missing = dict(answers)
            missing.pop("B-04")
            missing.pop("B-05")
            with pytest.raises(AppError) as missing_error:
                await submit_assessment(session, run, "k0", missing)
            assert missing_error.value.code == "answers_incomplete"
            assert set(missing_error.value.details["missing"]) == {"B-04", "B-05"}

            answers["B-04"] = "b"
            answers["B-05"] = "d"
            response = await submit_assessment(session, run, "k0", answers)
            assert response.answers_json["B-04"] == "b"
            assert response.answers_json["B-05"] == "d"
    finally:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await db.dispose()
