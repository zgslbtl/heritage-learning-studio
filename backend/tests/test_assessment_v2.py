from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db import Base, Database
from app.models import (
    ArtifactVersion,
    AssessmentItemKey,
    AssessmentResponse,
    InstrumentVersion,
    Participant,
    ProtocolAssessmentForm,
    ProtocolVersion,
    Round,
    Run,
)
from app.schemas import WorkUpdate
from app.services.assessments import assessment_payload, submit_assessment
from app.services.export import build_export
from app.services.formal_content import import_formal_content, import_formal_v2
from app.services.image_queue import build_product_prompt
from app.services.run_state import (
    complete_tutorial,
    create_or_resume_run,
    protocol_instrument,
    start_round,
)
from app.prompts.hlsf import phase_prompt
from app.services.hlsf import advance_guide, load_state, guide_payload
from app.services.works import (
    save_work,
    work_ai_context,
    work_completion_issues,
    work_form_for,
    work_payload,
)


@pytest.mark.asyncio
async def test_v2_import_and_stage_counts(settings):
    db = Database(settings.database_url)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with db.session_factory() as session:
            result = await import_formal_v2(session, settings, activate=True)
            assert result["instruments"] == 17
            protocol = (
                await session.execute(
                    select(ProtocolVersion).where(ProtocolVersion.is_active.is_(True))
                )
            ).scalar_one()
            assert protocol.assessment_version == "assessment_v2.0_pilot"
            forms = (
                await session.execute(
                    select(ProtocolAssessmentForm).where(
                        ProtocolAssessmentForm.protocol_version_id == protocol.id
                    )
                )
            ).scalars().all()
            assert len(forms) == 16
            instruments = (
                await session.execute(select(InstrumentVersion))
            ).scalars().all()
            counts = {}
            for instrument in instruments:
                if instrument.object_code:
                    counts.setdefault(instrument.kind, []).append(
                        len((instrument.schema_json or {}).get("questions", []))
                    )
            assert sorted(counts["k0"]) == [9, 9, 9, 9]
            assert sorted(counts["k1"]) == [7, 7, 7, 7]
            assert sorted(counts["k2"]) == [6, 6, 6, 6]
            assert sorted(counts["k3"]) == [7, 7, 7, 7]
            keys = (await session.execute(select(AssessmentItemKey))).scalars().all()
            assert len(keys) == 104
            short_keys = [key for key in keys if key.dimension == "short_answer"]
            assert len(short_keys) == 8
            assert all(key.max_score == 2 for key in short_keys)
            survey = next(inst for inst in instruments if inst.kind == "survey")
            assert len((survey.schema_json or {}).get("questions", [])) == 7
            from app.services.readiness import build_readiness
            settings.auth_mode = "email"
            ready = await build_readiness(session, settings)
            assert ready["ready_for_students"] is True
            assert ready["active_protocol"]["assessment_version"] == "assessment_v2.0_pilot"
    finally:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await db.dispose()


@pytest.mark.asyncio
async def test_v2_import_does_not_change_existing_v1_run(settings):
    db = Database(settings.database_url)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with db.session_factory() as session:
            await import_formal_content(session, settings)
            p1 = Participant(class_id=1, group_name="G1", email="v1@polyu.edu.hk")
            session.add(p1)
            await session.flush()
            run1 = await create_or_resume_run(session, participant=p1, settings=settings)
            assert run1.design_version == "crossover-v1.0-pilot"
            v1_protocol_id = run1.protocol_version_id
            k0_v1 = await protocol_instrument(session, run1, "k0")
            assert len((k0_v1.schema_json or {}).get("questions", [])) == 15

            await import_formal_v2(session, settings, activate=True)
            await session.refresh(run1)
            assert run1.protocol_version_id == v1_protocol_id
            k0_v1_again = await protocol_instrument(session, run1, "k0")
            assert len((k0_v1_again.schema_json or {}).get("questions", [])) == 15

            p2 = Participant(class_id=1, group_name="G1", email="v2@polyu.edu.hk")
            session.add(p2)
            await session.flush()
            run2 = await create_or_resume_run(session, participant=p2, settings=settings)
            assert run2.design_version == "crossover-v1.1-assessment-v2-pilot"
            k0_v2 = await protocol_instrument(session, run2, "k0")
            assert len((k0_v2.schema_json or {}).get("questions", [])) == 9
    finally:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await db.dispose()


@pytest.mark.asyncio
async def test_v2_k0_scoring_and_work_rationale(settings):
    db = Database(settings.database_url)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with db.session_factory() as session:
            await import_formal_v2(session, settings, activate=True)
            p = Participant(class_id=1, group_name="G1", email="v2work@polyu.edu.hk")
            session.add(p)
            await session.flush()
            run = await create_or_resume_run(session, participant=p, settings=settings)
            payload = await assessment_payload(session, run, "k0")
            questions = payload["instrument"]["questions"]
            assert len(questions) == 9
            assert not any(q["type"] == "short_text" for q in questions)

            instrument = await protocol_instrument(session, run, "k0")
            keys = (
                await session.execute(
                    select(AssessmentItemKey).where(
                        AssessmentItemKey.instrument_version_id == instrument.id
                    )
                )
            ).scalars().all()
            key_map = {key.question_id: key.correct_value for key in keys}
            answers = {}
            for q in questions:
                if q["type"] == "single_choice":
                    answers[q["id"]] = key_map.get(q["id"], q["options"][0]["value"])
            response = await submit_assessment(session, run, "k0", answers)
            assert response.score_total == 6
            assert response.scoring_version == "k-v2.0"

            protocol = await session.get(ProtocolVersion, run.protocol_version_id)
            artifact = await session.get(ArtifactVersion, protocol.artifact_x_version_id)
            now = datetime.now(timezone.utc)
            round_obj = Round(
                run_id=run.id,
                round_no=1,
                artifact_version_id=artifact.id,
                condition="A",
                started_at=now,
                deadline_at=now + timedelta(minutes=20),
                current_work_revision=0,
            )
            session.add(round_obj)
            await session.flush()
            update = WorkUpdate(
                product_name="测试产品",
                product_category="徽章",
                target_audience="青年观众",
                rationale_fields={
                    "heritage_knowledge": "鹭鸶与六品文官身份有关（M03）。",
                    "cultural_translation": "保留鹭鸶与莲塘的组合，转成徽章主图。",
                    "design_reason": "面向青年观众，便于日常佩戴。",
                },
            )
            revision, created = await save_work(
                session, round_obj, update, design_version=run.design_version
            )
            assert created
            assert work_form_for(1, "A", run.design_version) == "rationale"
            assert work_completion_issues(1, "A", revision, run.design_version) == []
            saved = work_payload(revision)
            assert saved["rationale_fields"]["heritage_knowledge"].startswith("鹭鸶")
            context = work_ai_context(revision, run.design_version)
            assert "你从文物中学到了什么" in context
            prompt = build_product_prompt(artifact, revision)
            assert "Three-part rationale" in prompt
            assert "鹭鸶" in prompt

            path, _ = await build_export(session, settings)
            try:
                with zipfile.ZipFile(path) as archive:
                    work_rows = list(csv.DictReader(io.StringIO(archive.read("work_revisions.csv").decode("utf-8-sig"))))
                    assert work_rows
                    assert work_rows[0]["rationale_fields_json"]
                    assert work_rows[0]["rationale_schema_version"] == "rationale_v2.0"
                    assert work_rows[0]["image_prompt"] == ""
                    analysis_rows = list(csv.DictReader(io.StringIO(archive.read("analysis.csv").decode("utf-8-sig"))))
                    assert analysis_rows
                    assert analysis_rows[0]["mc_max"] == "6"
                    assert analysis_rows[0]["assessment_version"] == "assessment_v2.0_pilot"
            finally:
                path.unlink(missing_ok=True)
    finally:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await db.dispose()


@pytest.mark.asyncio
async def test_v2_survey_export_links_round_conditions(settings):
    db = Database(settings.database_url)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with db.session_factory() as session:
            await import_formal_v2(session, settings, activate=True)
            p = Participant(class_id=1, group_name="G1", email="v2survey@polyu.edu.hk")
            session.add(p)
            await session.flush()
            run = await create_or_resume_run(session, participant=p, settings=settings)
            protocol = await session.get(ProtocolVersion, run.protocol_version_id)
            now = datetime.now(timezone.utc)
            for no, slot, condition in ((1, protocol.artifact_x_version_id, "A"), (2, protocol.artifact_y_version_id, "B")):
                session.add(Round(
                    run_id=run.id,
                    round_no=no,
                    artifact_version_id=slot,
                    condition=condition,
                    started_at=now,
                    deadline_at=now + timedelta(minutes=20),
                    current_work_revision=0,
                ))
            session.add(AssessmentResponse(
                run_id=run.id,
                kind="survey",
                instrument_version_id=(await session.execute(select(InstrumentVersion).where(InstrumentVersion.kind == "survey"))).scalar_one().id,
                answers_json={"S1": 4, "S2": 5, "S3": 6, "S4": 5, "S5": 6, "S6": 7, "S7": "second"},
                status="submitted",
                submitted_at=now,
            ))
            await session.flush()
            path, _ = await build_export(session, settings)
            try:
                with zipfile.ZipFile(path) as archive:
                    rows = list(csv.DictReader(io.StringIO(archive.read("survey.csv").decode("utf-8-sig"))))
                    assert len(rows) == 1
                    assert rows[0]["round1_ai_condition"] == "A"
                    assert rows[0]["round2_ai_condition"] == "B"
                    assert rows[0]["S7"] == "second"
                    assert rows[0]["S7_label"] == "第二轮"
            finally:
                path.unlink(missing_ok=True)
    finally:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await db.dispose()


@pytest.mark.asyncio
async def test_v2_hlsf_reflect_uses_three_part_statement(settings):
    db = Database(settings.database_url)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with db.session_factory() as session:
            await import_formal_v2(session, settings, activate=True)
            p = Participant(class_id=1, group_name="G3", email="v2hlsf@polyu.edu.hk")
            session.add(p)
            await session.flush()
            run = await create_or_resume_run(session, participant=p, settings=settings)
            payload = await assessment_payload(session, run, "k0")
            instrument = await protocol_instrument(session, run, "k0")
            keys = (
                await session.execute(
                    select(AssessmentItemKey).where(
                        AssessmentItemKey.instrument_version_id == instrument.id
                    )
                )
            ).scalars().all()
            key_map = {key.question_id: key.correct_value for key in keys}
            answers = {}
            for q in payload["instrument"]["questions"]:
                if q["type"] == "single_choice":
                    answers[q["id"]] = key_map.get(q["id"], q["options"][0]["value"])
            await submit_assessment(session, run, "k0", answers)
            await complete_tutorial(session, run)
            round_obj = await start_round(session, run, 1, settings)
            assert round_obj.condition == "B"
            state = await load_state(session, round_obj.id)
            assert state is not None
            guide = guide_payload(state, round_obj, run.design_version)
            assert guide and guide["version"] == "hlsf-v1.8-assessment-v2-pilot"

            v2_reflect = phase_prompt(2, "reflect", run.design_version)
            v1_reflect = phase_prompt(2, "reflect", "crossover-v1.0-pilot")
            assert "三段作品说明" in v2_reflect
            assert "开放作品说明" not in v2_reflect
            assert "开放作品说明" in v1_reflect
    finally:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await db.dispose()


@pytest.mark.asyncio
async def test_v2_student_flow_k0_to_survey(settings):
    import httpx
    from app.main import create_app

    settings.auth_mode = "email"
    settings.auto_bootstrap = False
    db = Database(settings.database_url)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with db.session_factory() as session:
            await import_formal_v2(session, settings, activate=True)
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                entered = await client.post(
                    "/api/auth/enter",
                    json={"email": "v2flow@polyu.edu.hk", "class_id": 1},
                )
                assert entered.status_code == 200, entered.text

                def answers_for(questions):
                    out = {}
                    for q in questions:
                        if q["type"] == "single_choice":
                            out[q["id"]] = (q.get("options") or [{"value": "a"}])[0]["value"]
                        elif q["type"] == "short_text":
                            out[q["id"]] = "这是一句用于流程测试的短答。"
                    return out

                k0 = await client.get("/api/student/instruments/k0")
                assert k0.status_code == 200, k0.text
                k0q = k0.json()["instrument"]["questions"]
                assert len(k0q) == 9
                assert not any(q["type"] == "short_text" for q in k0q)
                sub = await client.post("/api/student/instruments/k0/submit", json={"answers": answers_for(k0q)})
                assert sub.status_code == 200, sub.text
                assert (await client.post("/api/student/tutorial/complete")).status_code == 200
                assert (await client.post("/api/student/rounds/1/start")).status_code == 200
                round1 = (await client.get("/api/student/rounds/1")).json()
                assert round1["work_form"] == "rationale"
                work = await client.put(
                    "/api/student/rounds/1/work",
                    json={
                        "product_name": "测试徽章",
                        "product_category": "徽章",
                        "target_audience": "青年观众",
                        "rationale_fields": {
                            "heritage_knowledge": "鹭鸶与六品文官身份有关（M03）。",
                            "cultural_translation": "保留鹭鸶与莲塘组合，转成徽章主图。",
                            "design_reason": "便于日常佩戴和识别。",
                        },
                    },
                )
                assert work.status_code == 200, work.text
                assert work.json()["work"]["rationale_fields"]["heritage_knowledge"]
                assert (await client.post("/api/student/rounds/1/finish")).status_code == 200

                k1 = await client.get("/api/student/instruments/k1")
                assert k1.status_code == 200, k1.text
                k1q = k1.json()["instrument"]["questions"]
                assert len(k1q) == 7
                assert sum(q["type"] == "short_text" for q in k1q) == 1
                assert (await client.post("/api/student/instruments/k1/submit", json={"answers": answers_for(k1q)})).status_code == 200

                k2 = await client.get("/api/student/instruments/k2")
                assert k2.status_code == 200, k2.text
                k2q = k2.json()["instrument"]["questions"]
                assert len(k2q) == 6
                assert not any(q["type"] == "short_text" for q in k2q)
                assert (await client.post("/api/student/instruments/k2/submit", json={"answers": answers_for(k2q)})).status_code == 200

                assert (await client.post("/api/student/rounds/2/start")).status_code == 200
                round2 = (await client.get("/api/student/rounds/2")).json()
                assert round2["work_form"] == "rationale"
                work2 = await client.put(
                    "/api/student/rounds/2/work",
                    json={
                        "product_name": "测试织带",
                        "product_category": "织带",
                        "target_audience": "博物馆观众",
                        "rationale_fields": {
                            "heritage_knowledge": "联珠团窠内是相向格里芬（T02）。",
                            "cultural_translation": "保留珠点圆环与相向神兽的重复单元。",
                            "design_reason": "让图案在织带上保持可识别。",
                        },
                    },
                )
                assert work2.status_code == 200, work2.text
                assert (await client.post("/api/student/rounds/2/finish", json={"consent_future_research": True})).status_code == 200

                k3 = await client.get("/api/student/instruments/k3")
                assert k3.status_code == 200, k3.text
                k3q = k3.json()["instrument"]["questions"]
                assert len(k3q) == 7
                assert sum(q["type"] == "short_text" for q in k3q) == 1
                assert (await client.post("/api/student/instruments/k3/submit", json={"answers": answers_for(k3q)})).status_code == 200

                survey = await client.get("/api/student/instruments/survey")
                assert survey.status_code == 200, survey.text
                sq = survey.json()["instrument"]["questions"]
                assert len(sq) == 7
                survey_answers = {}
                for q in sq:
                    if q["id"] == "S7":
                        survey_answers[q["id"]] = "second"
                    elif q["id"] in ("S3", "S6"):
                        survey_answers[q["id"]] = 5
                    else:
                        survey_answers[q["id"]] = 4
                assert (await client.post("/api/student/instruments/survey/submit", json={"answers": survey_answers})).status_code == 200
                state = (await client.get("/api/student/state")).json()
                assert state["stage"] == "peer_assessment"
    finally:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await db.dispose()
