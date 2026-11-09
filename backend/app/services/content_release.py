"""Release the checked-in instruments without rewriting historical study records."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain import ASSESSMENT_V2_VERSION
from ..errors import AppError
from ..models import AssessmentItemKey, InstrumentVersion, ProtocolAssessmentForm, ProtocolVersion
from ..schemas import InstrumentPayload
from .formal_content import CONTENT_V2_DIR, _instrument_payload, _read_json, _stage_questions
from .instruments import create_instrument_version
from .peer_scales import DEFAULT_PEER_SCALE_VERSION, peer_scale

KEY_FIELDS = ('question_id', 'correct_value', 'max_score', 'construct', 'dimension', 'notes')


def content_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _fingerprint(schema: dict, keys: list[dict]) -> str:
    # Pydantic fills old omitted defaults, and JSON mode normalizes anchor keys.
    return content_hash({'schema': InstrumentPayload.model_validate(schema).model_dump(mode='json'),
                         'keys': sorted(keys, key=lambda row: row['question_id'])})


def current_definitions() -> tuple[dict, dict]:
    source = _read_json('instruments.json', CONTENT_V2_DIR)
    keys_source = _read_json('assessment_keys.json', CONTENT_V2_DIR)
    meta = source['meta']
    definitions = {}
    for kind in ('k0', 'k1', 'k2', 'k3'):
        for obj in ('M', 'T'):
            for form in ('A', 'B'):
                questions = _stage_questions(source, kind, obj, form)
                payload = _instrument_payload(kind=kind, object_code=obj, form_code=form,
                                              questions=questions, scoring_version=meta['scoring_version'])
                keys = []
                for question in questions:
                    qid = question['id']
                    if question['type'] == 'short_text':
                        keys.append(dict(question_id=qid, correct_value=None,
                                         max_score=meta['short_answer_max_score'], construct='fact+relation',
                                         dimension='short_answer', notes=keys_source['short_answer'].get(qid, '')))
                    elif qid in keys_source['keys'][obj][form]:
                        keys.append(dict(question_id=qid, correct_value=keys_source['keys'][obj][form][qid],
                                         max_score=1, construct='knowledge', dimension='mcq', notes=''))
                definitions[(kind, obj, form)] = (payload, keys)
    definitions[('survey', None, None)] = (InstrumentPayload(**source['survey']), [])
    return meta, definitions


async def release_current_content(session: AsyncSession, *, activate: bool = False) -> dict:
    # Shared with release-survey-v3; hold until caller commits/rolls back.
    await session.execute(text('SELECT pg_advisory_xact_lock(711903003)'))
    active = (await session.execute(select(ProtocolVersion).where(
        ProtocolVersion.is_active.is_(True)).with_for_update())).scalar_one_or_none()
    if active is None or active.is_demo or active.assessment_version != ASSESSMENT_V2_VERSION:
        raise AppError(409, 'content_release_requires_v2', 'An active formal assessment V2 protocol is required.')
    meta, definitions = current_definitions()
    rows = (await session.execute(select(InstrumentVersion).where(
        InstrumentVersion.is_demo.is_(False)).order_by(InstrumentVersion.version.desc()))).scalars().all()
    key_rows = (await session.execute(select(AssessmentItemKey))).scalars().all()
    keys_by_id: dict = {}
    for row in key_rows:
        keys_by_id.setdefault(row.instrument_version_id, []).append({k: getattr(row, k) for k in KEY_FIELDS})
    by_id = {row.id: row for row in rows}
    fingerprints = {row.id: _fingerprint(row.schema_json, keys_by_id.get(row.id, [])) for row in rows}
    forms = (await session.execute(select(ProtocolAssessmentForm).where(
        ProtocolAssessmentForm.protocol_version_id == active.id))).scalars().all()
    active_forms = {(f.kind, f.object_code, f.form_code): f.instrument_version_id for f in forms}
    active_forms[('survey', None, None)] = uuid.UUID(active.instrument_versions['survey'])
    desired_hashes = {key: _fingerprint(payload.model_dump(mode='json'), keys)
                      for key, (payload, keys) in definitions.items()}
    peer = peer_scale(DEFAULT_PEER_SCALE_VERSION)
    release_hash = content_hash({'instruments': {'/'.join(x or '-' for x in key): value for key, value in desired_hashes.items()},
                                 'content_version': meta['content_version'], 'peer_scale': peer})
    changed = [key for key, digest in desired_hashes.items() if fingerprints.get(active_forms.get(key)) != digest]
    matches = not changed and active.research_rubric_json.get('content_release_hash') == release_hash
    report = {'changed': not matches, 'activated': False, 'dry_run': not activate,
              'previous_protocol_id': str(active.id), 'protocol_id': str(active.id),
              'content_version': meta['content_version'], 'survey_version': definitions[('survey', None, None)][0].survey_version,
              'peer_review_version': DEFAULT_PEER_SCALE_VERSION, 'content_release_hash': release_hash,
              'changed_instruments': ['/'.join(x or '-' for x in key) for key in changed],
              'created_instruments': 0, 'reused_instruments': 0}
    selected = {}
    for key, (payload, keys) in definitions.items():
        # Prefer the frozen active instrument, then an identical prior version.
        existing = by_id.get(active_forms.get(key))
        if existing is None or fingerprints.get(existing.id) != desired_hashes[key]:
            existing = next((row for row in rows if (row.kind, row.object_code, row.form_code) == key
                             and fingerprints[row.id] == desired_hashes[key]), None)
        if existing is None:
            report['created_instruments'] += 1
            if activate and not matches:
                existing = await create_instrument_version(session, kind=key[0], payload=payload,
                                                           object_code=key[1], form_code=key[2])
                for item in keys:
                    session.add(AssessmentItemKey(instrument_version_id=existing.id, **item))
        else:
            report['reused_instruments'] += 1
        if existing is not None:
            selected[key] = existing
    if not activate or matches:
        return report
    active.is_active = False
    await session.flush()
    rubric = {**active.research_rubric_json, 'content_version': meta['content_version'],
              'content_release_hash': release_hash, 'survey_version': report['survey_version'],
              'peer_review_version': DEFAULT_PEER_SCALE_VERSION}
    protocol = ProtocolVersion(artifact_x_version_id=active.artifact_x_version_id,
        artifact_y_version_id=active.artifact_y_version_id,
        instrument_versions={kind: str(selected[(kind, 'M', 'A')].id) for kind in ('k0', 'k1', 'k2', 'k3')}
                            | {'survey': str(selected[('survey', None, None)].id)},
        research_rubric_json=rubric, assessment_version=active.assessment_version,
        is_demo=False, is_active=True, activated_at=datetime.now(timezone.utc))
    session.add(protocol)
    await session.flush()
    for (kind, obj, form), version in selected.items():
        if kind != 'survey':
            session.add(ProtocolAssessmentForm(protocol_version_id=protocol.id, kind=kind,
                                               object_code=obj, form_code=form, instrument_version_id=version.id))
    await session.flush()
    report.update(activated=True, protocol_id=str(protocol.id))
    return report
