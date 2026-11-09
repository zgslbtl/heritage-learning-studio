from __future__ import annotations

import copy
import json
import uuid

import pytest
from sqlalchemy import func, select

from app.db import Base, Database
from app.models import AssessmentItemKey, InstrumentVersion, Participant, ProtocolAssessmentForm, ProtocolVersion
from app.services.content_release import current_definitions, release_current_content
from app.services.formal_content import import_formal_v2
from app.services.peer_scales import DEFAULT_PEER_SCALE_VERSION, PEER_SCALE_V21, PEER_SCALE_V22, peer_scale
from app.services.run_state import create_or_resume_run, protocol_instrument


def test_all_current_items_and_peer_anchors_have_english():
    meta, definitions = current_definitions()
    assert meta['content_version'] == 'v2.4-bilingual'
    for (kind, obj, form), (payload, keys) in definitions.items():
        assert payload.title_en and payload.instructions_en
        assert len(payload.questions) == {'k0': 11, 'k1': 7, 'k2': 6, 'k3': 7, 'survey': 19}[kind]
        for q in payload.questions:
            assert q.prompt_en
            assert all(o.label_en for o in q.options)
            if q.section:
                assert q.section_en
            if q.type == 'likert':
                assert set(q.scale_anchors) == set(q.scale_anchors_en)
        if kind == 'k0':
            assert [q.id for q in payload.questions[:5]] == [f'B-0{i}' for i in range(1, 6)]
            assert all(payload.questions[i].options[-1].label == '不愿透露' for i in (3, 4))
    assert DEFAULT_PEER_SCALE_VERSION == PEER_SCALE_V22
    v21, v22 = peer_scale(PEER_SCALE_V21), peer_scale(PEER_SCALE_V22)
    chinese = copy.deepcopy(v22)
    for key in list(chinese):
        if key.endswith('_en'): del chinese[key]
    for dimension in chinese['dimensions']:
        for key in list(dimension):
            if key.endswith('_en'): del dimension[key]
    chinese['version'] = PEER_SCALE_V21
    assert chinese == v21
    assert v22['title_en'] and v22['instructions_en'] and v22['comment_prompt_en']
    assert len(v22['principles_en']) == len(v22['principles'])
    for dimension in v22['dimensions']:
        assert dimension['label_en'] and dimension['prompt_en']
        assert len(dimension['anchors_en']) == 5


@pytest.mark.asyncio
async def test_release_dry_run_idempotence_scoring_and_frozen_runs(settings):
    db = Database(settings.database_url)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with db.session_factory() as session:
            await import_formal_v2(session, settings, activate=True)
            old_protocol = (await session.execute(select(ProtocolVersion).where(ProtocolVersion.is_active.is_(True)))).scalar_one()
            old_id = old_protocol.id
            old_survey_id = old_protocol.instrument_versions['survey']
            instruments = (await session.execute(select(InstrumentVersion).where(InstrumentVersion.kind != 'survey'))).scalars().all()
            for instrument in instruments:
                schema = copy.deepcopy(instrument.schema_json)
                schema.pop('title_en', None); schema.pop('instructions_en', None)
                schema['questions'] = [q for q in schema['questions'] if q['id'] not in ('B-04', 'B-05')]
                for question in schema['questions']:
                    question.pop('prompt_en', None); question.pop('section_en', None)
                    for option in question.get('options', []): option.pop('label_en', None)
                instrument.schema_json = schema
            participant = Participant(class_id=1, group_name='G1', email='frozen-content@polyu.edu.hk')
            session.add(participant); await session.flush()
            run = await create_or_resume_run(session, participant=participant, settings=settings)
            run_id = run.id
            await session.commit()
            original = {i.id: copy.deepcopy(i.schema_json) for i in instruments}
            count = (await session.execute(select(func.count()).select_from(InstrumentVersion))).scalar_one()
            preview = await release_current_content(session)
            assert preview['dry_run'] and preview['created_instruments'] == 16 and preview['reused_instruments'] == 1
            assert (await session.execute(select(func.count()).select_from(InstrumentVersion))).scalar_one() == count
            assert old_protocol.is_active
            await session.rollback()
            result = await release_current_content(session, activate=True)
            assert result['activated'] and result['created_instruments'] == 16
            await session.commit()
            session.expire_all()
            from app.models import Run
            frozen_run = await session.get(Run, run_id)
            assert frozen_run.protocol_version_id == old_id
            assert len((await protocol_instrument(session, frozen_run, 'k0')).schema_json['questions']) == 9
            new_protocol = await session.get(ProtocolVersion, uuid.UUID(result['protocol_id']))
            assert new_protocol.instrument_versions['survey'] == old_survey_id
            assert len((await session.execute(select(ProtocolAssessmentForm).where(ProtocolAssessmentForm.protocol_version_id == new_protocol.id))).scalars().all()) == 16
            for iid, schema in original.items(): assert (await session.get(InstrumentVersion, iid)).schema_json == schema
            again = await release_current_content(session, activate=True)
            assert again['changed'] is False and again['created_instruments'] == 0
            assert (await session.execute(select(func.count()).select_from(InstrumentVersion))).scalar_one() == count + 16
            # A scoring-key-only change must also get a new immutable instrument.
            active_key = (await session.execute(select(AssessmentItemKey).where(AssessmentItemKey.instrument_version_id == uuid.UUID(new_protocol.instrument_versions['k0'])))).scalars().first()
            active_key.correct_value = 'not-the-current-key'
            await session.flush()
            correction = await release_current_content(session, activate=True)
            assert correction['changed'] and correction['created_instruments'] == 1
            await session.commit()
    finally:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await db.dispose()
