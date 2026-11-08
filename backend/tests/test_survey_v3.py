from __future__ import annotations

import csv
import io
import json
import zipfile
import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.db import Base, Database
from app.errors import AppError
from app.models import AssessmentResponse, InstrumentVersion, Participant, ProtocolAssessmentForm, ProtocolVersion
from app.schemas import InstrumentPayload
from app.services.assessments import assessment_payload, submit_assessment
from app.services.export import build_export
from app.services.formal_content import CONTENT_V2_DIR, import_formal_v2, release_survey_v3
from app.services.instruments import instrument_payload, validate_answers
from app.services.run_state import create_or_resume_run, protocol_instrument
from app.services.survey import SURVEY_V3, survey_v3_scores


def schema():
    return json.loads((CONTENT_V2_DIR / 'instruments.json').read_text())['survey']


def answers():
    return {**{f'S{i}': 0 for i in (1, 2, 3, 4, 10, 11, 12, 13)},
            **{f'S{i}': 7 for i in (5, 6, 14, 15)},
            **{f'S{i}': 1 for i in (7, 8, 16, 17)}, 'S9': 5, 'S18': 9, 'S19': 'same'}


def test_v3_ranges_zero_reverse_and_separate_constructs():
    frontend_fixture = Path(__file__).parents[2] / "frontend/src/tests/fixtures/survey_v3.json"
    if frontend_fixture.exists():
        assert json.loads(frontend_fixture.read_text()) == schema()
    payload = InstrumentPayload(**schema()).model_dump()
    raw = answers()
    assert validate_answers(payload, raw, True)[0] == raw
    for qid, bad in [('S1', -1), ('S1', 11), ('S5', 0), ('S9', 10), ('S18', True), ('S19', 1)]:
        with pytest.raises(AppError):
            validate_answers(payload, {**raw, qid: bad}, True)
    with pytest.raises(AppError):
        validate_answers(payload, {k: v for k, v in raw.items() if k != 'S18'}, True)
    scores = survey_v3_scores(SURVEY_V3, raw)
    assert scores['v3_exploration_mean_r1'] == 0
    assert scores['v3_expressiveness_mean_r2'] == 0
    assert scores['v3_perceived_choice_mean_r1'] == 7
    assert scores['v3_perceived_choice_mean_r2'] == 7
    assert scores['v3_s7_reversed'] == scores['v3_s8_reversed'] == 7
    assert scores['v3_s16_reversed'] == scores['v3_s17_reversed'] == 7
    assert scores['v3_mental_effort_r1'] == 5
    assert scores['v3_mental_effort_r2'] == 9
    assert raw['S7'] == 1
    assert 'total' not in scores
    assert survey_v3_scores('survey-v2.1-pilot', raw) == {}
    assert 'v3_perceived_choice_mean_r1' not in survey_v3_scores(SURVEY_V3, {**raw, 'S7': None})
    assert 'v3_exploration_mean_r1' not in survey_v3_scores(SURVEY_V3, {**raw, 'S1': True})
    assert survey_v3_scores(SURVEY_V3, {**raw, 'S7': 7})['v3_s7_reversed'] == 1


@pytest.mark.asyncio
async def test_v3_release_preserves_frozen_runs_and_exports(settings):
    db = Database(settings.database_url)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with db.session_factory() as session:
            await import_formal_v2(session, settings, activate=True)
            active = (await session.execute(select(ProtocolVersion).where(ProtocolVersion.is_active.is_(True)))).scalar_one()
            old_survey = await session.get(InstrumentVersion, uuid.UUID(active.instrument_versions['survey']))
            # Explicit frozen V2.1 fixture; historical item IDs have different meanings.
            old_survey.schema_json = json.loads((Path(__file__).parent / 'fixtures/survey_v21.json').read_text())
            await session.flush()
            p = Participant(class_id=1, group_name='G1', email='frozen-v21@polyu.edu.hk')
            session.add(p)
            await session.flush()
            old_run = await create_or_resume_run(session, participant=p, settings=settings)
            result = await release_survey_v3(session)
            assert result['changed'] is True
            assert result['reused_knowledge_forms'] == 16
            assert old_run.protocol_version_id == active.id
            assert (await protocol_instrument(session, old_run, 'survey')).id == old_survey.id
            new_protocol = await session.get(ProtocolVersion, uuid.UUID(result['protocol_id']))
            assert new_protocol.artifact_x_version_id == active.artifact_x_version_id
            assert new_protocol.artifact_y_version_id == active.artifact_y_version_id
            assert {k: v for k, v in new_protocol.instrument_versions.items() if k != 'survey'} == {k: v for k, v in active.instrument_versions.items() if k != 'survey'}
            p2 = Participant(class_id=1, group_name='G3', email='new-v3@polyu.edu.hk')
            session.add(p2)
            await session.flush()
            run = await create_or_resume_run(session, participant=p2, settings=settings)
            assert run.protocol_version_id == new_protocol.id
            with pytest.raises(AppError):
                await assessment_payload(session, run, 'survey')
            run.stage = 'survey'  # Engineering fixture after T2/K3; no external model call.
            public = await assessment_payload(session, run, 'survey')
            assert len(public['instrument']['questions']) == 19
            assert 'research_notes' not in public['instrument']
            assert 'reverse' not in json.dumps(public['instrument'])
            response = await submit_assessment(session, run, 'survey', answers())
            assert response.score_total is None
            assert response.scoring_version == SURVEY_V3
            assert response.score_json['v3_perceived_choice_mean_r1'] == 7
            assert run.stage == 'peer_assessment'
            path, _ = await build_export(session, settings)
            try:
                with zipfile.ZipFile(path) as archive:
                    row = list(csv.DictReader(io.StringIO(archive.read('survey.csv').decode('utf-8-sig'))))[0]
                assert row['S1'] == '0'
                assert row['S7'] == '1'
                assert row['S19'] == 'same'
                assert row['survey_version'] == SURVEY_V3
                assert row['v3_s7_reversed'] == '7'
                assert float(row['v3_perceived_choice_mean_r2']) == 7
                assert row['s19_preferred_ai_condition'] == 'Similar'
                assert row['s7_preferred_round'] == row['s1_exploration_r1'] == ''
            finally:
                path.unlink(missing_ok=True)
            await session.commit()
            # Reload JSONB/JSON dictionaries as production would before repeating release.
            session.expire_all()
            again = await release_survey_v3(session)
            assert again['changed'] is False
            assert (await session.execute(select(func.count()).select_from(InstrumentVersion))).scalar_one() == 18
            assert (await session.execute(select(func.count()).select_from(ProtocolAssessmentForm))).scalar_one() == 32
    finally:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await db.dispose()
