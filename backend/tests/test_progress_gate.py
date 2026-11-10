from __future__ import annotations

import asyncio
import csv
import io
import uuid
import zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, func

from app.models import (AssessmentResponse, ClassPeerGate, ClassPeerGateEvent, PeerAssignment,
                        PeerBatch, PeerRating, Round, Run, WorkRevision)
from app.services import peer
from tests.conftest import reach_t2_active, save_t2_work, submit_assessment, complete_k0, enter_t1


async def students(app, count):
    result = []
    for i in range(count):
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver')
        response = await c.post('/api/auth/enter', json={'class_id': 1, 'email': f'progress.{i}@polyu.edu.hk'})
        assert response.status_code == 200, response.text
        result.append((c, uuid.UUID(response.json()['state']['run_id']), uuid.UUID(response.json()['state']['participant']['id'])))
    return result


async def seed_cohort(app, clients, ready_count, started_count=None):
    first = clients[0][0]
    await reach_t2_active(first)
    await save_t2_work(first)
    assert (await first.post('/api/student/rounds/2/finish')).status_code == 200
    await submit_assessment(first, 'k3', {'k3_text': 'Answer'})
    await submit_assessment(first, 'survey', {'survey': 4})
    start = datetime.now(timezone.utc) - timedelta(minutes=2)
    async with app.state.db.session_factory() as s:
        source_rounds = list((await s.execute(select(Round).where(Round.run_id == clients[0][1]).order_by(Round.round_no))).scalars())
        source_work = {r.id: (await s.execute(select(WorkRevision).where(WorkRevision.round_id == r.id))).scalars().first() for r in source_rounds}
        source_assessments = list((await s.execute(select(AssessmentResponse).where(AssessmentResponse.run_id == clients[0][1], AssessmentResponse.kind.in_(('k3', 'survey'))))).scalars())
        source_rounds[0].started_at = start
        for index, (_, rid, _) in enumerate(clients[1:], 1):
            run = await s.get(Run, rid)
            run.stage = 'peer_assessment' if index < ready_count else 'k3'
            if index >= (started_count if started_count is not None else len(clients)):
                continue
            for original in source_rounds:
                r = Round(run_id=rid, round_no=original.round_no, artifact_version_id=original.artifact_version_id,
                          condition=original.condition, started_at=start + timedelta(seconds=index),
                          deadline_at=start + timedelta(minutes=30), finished_at=start + timedelta(minutes=1), current_work_revision=1)
                s.add(r); await s.flush()
                w = source_work[original.id]
                fields = {c.name: getattr(w, c.name) for c in WorkRevision.__table__.columns if c.name not in ('id', 'round_id')}
                s.add(WorkRevision(round_id=r.id, **fields))
            if index < ready_count:
                for a in source_assessments:
                    s.add(AssessmentResponse(run_id=rid, kind=a.kind, instrument_version_id=a.instrument_version_id,
                                             status='submitted', answers_json=a.answers_json, submitted_at=start))
        await s.commit()
    return start + timedelta(seconds=9)


async def mark_ready(app, rid):
    async with app.state.db.session_factory() as s:
        template = (await s.execute(select(AssessmentResponse).where(AssessmentResponse.kind == 'survey', AssessmentResponse.status == 'submitted'))).scalars().first()
        source = list((await s.execute(select(AssessmentResponse).where(AssessmentResponse.run_id == template.run_id, AssessmentResponse.kind.in_(('k3', 'survey'))))).scalars())
        for a in source:
            s.add(AssessmentResponse(run_id=rid, kind=a.kind, instrument_version_id=a.instrument_version_id,
                                     answers_json=a.answers_json, status='submitted'))
        (await s.get(Run, rid)).stage = 'peer_assessment'
        await s.commit()


async def test_27_of_30_freeze_and_three_late_reviewers(app_client, monkeypatch):
    admin, app, settings = app_client
    cs = await students(app, 30)
    try:
        tenth = await seed_cohort(app, cs, 26)
        async with app.state.db.session_factory() as s:
            counts = await peer.gate_counts(s, 1)
            assert counts['ready_count'] == 26 and counts['active_count'] == 30
            assert counts['gate'].timer_started_at == tenth
            await s.commit()
        monkeypatch.setattr(peer, '_now', lambda: tenth + timedelta(minutes=60))
        assert (await cs[0][0].get('/api/student/peer-assessment')).json()['waiting'] is True
        await mark_ready(app, cs[26][1])
        monkeypatch.setattr(peer, '_now', lambda: tenth + timedelta(minutes=59, seconds=59))
        assert (await cs[0][0].get('/api/student/peer-assessment')).json()['waiting'] is True
        monkeypatch.setattr(peer, '_now', lambda: tenth + timedelta(minutes=60))
        opened = await asyncio.gather(*(c.get('/api/student/peer-assessment') for c, _, _ in cs[:3]))
        assert all(r.status_code == 200 and not r.json()['waiting'] for r in opened)
        assert len({r.json()['batch']['id'] for r in opened}) == 1
        assert opened[0].json()['gate']['completion_percent'] == 90
        original = {a['assignment_id'] for a in opened[0].json()['assignments']}
        assert len(original) == 12
        async with app.state.db.session_factory() as s:
            main = list((await s.execute(select(PeerAssignment))).scalars())
            assert len(main) == 27 * 12
            assert set(Counter(a.work_id for a in main).values()) == {6}
            assert (await s.execute(select(func.count()).select_from(PeerBatch))).scalar_one() == 1
        # A direct completion request must allocate late tasks, never bypass them.
        for c, rid, _ in cs[27:]:
            await mark_ready(app, rid)
            premature = await c.post('/api/student/peer-assessment/complete')
            assert premature.status_code == 409 and premature.json()['error']['code'] == 'peer_incomplete'
            payload = (await c.get('/api/student/peer-assessment')).json()
            assert payload['total'] == 12 and all(a['allocation_kind'] == 'supplemental' for a in payload['assignments'])
            assert Counter(a['round_no'] for a in payload['assignments']) == {1: 6, 2: 6}
            again = (await c.get('/api/student/peer-assessment')).json()
            assert [a['assignment_id'] for a in again['assignments']] == [a['assignment_id'] for a in payload['assignments']]
            for a in payload['assignments']:
                scores = {d['key']: 4 for d in payload['review']['dimensions']}
                assert (await c.post('/api/student/peer-assessment/' + a['assignment_id'], json={'scores': scores})).status_code == 200
            assert (await c.post('/api/student/peer-assessment/complete')).status_code == 200
            feed = (await c.get('/api/student/social-feed')).json()
            assert feed['count'] == 60 and Counter(w['round_no'] for w in feed['works']) == {1: 30, 2: 30}
        unchanged = (await cs[0][0].get('/api/student/peer-assessment')).json()
        assert {a['assignment_id'] for a in unchanged['assignments']} == original
        await admin.post('/api/admin/login', json={'password': settings.admin_password})
        export = await admin.get('/api/admin/export')
        assert export.status_code == 200, export.text[:100]
        with zipfile.ZipFile(io.BytesIO(export.content)) as z:
            rows = lambda name: list(csv.DictReader(io.StringIO(z.read(name).decode('utf-8-sig'))))
            assert set(r['rating_count'] for r in rows('peer_work_scores.csv')) == {'0'}
            assert sum(int(r['rating_count']) for r in rows('peer_supplemental_work_scores.csv')) == 36
            assert set(r['allocation_kind'] for r in rows('peer_ratings.csv')) == {'supplemental'}
        late = await admin.post('/api/auth/enter', json={'class_id': 1, 'email': 'too.late@polyu.edu.hk'})
        assert late.status_code == 409 and late.json()['error']['code'] == 'class_closed'
    finally:
        for c, _, _ in cs: await c.aclose()


async def test_tenth_start_persistent_and_small_class_all_ready(app_client, monkeypatch):
    _, app, _ = app_client
    cs = await students(app, 10)
    try:
        tenth = await seed_cohort(app, cs, 1, started_count=9)
        async with app.state.db.session_factory() as s:
            assert (await peer.gate_counts(s, 1))['timer_started_at'] is None
            template = (await s.execute(select(Round).where(Round.round_no == 1))).scalars().first()
            s.add(Round(run_id=cs[9][1], round_no=1, artifact_version_id=template.artifact_version_id,
                        condition='A', started_at=tenth, deadline_at=tenth + timedelta(minutes=24)))
            await s.flush()
            assert (await peer.gate_counts(s, 1))['gate'].timer_started_at == tenth
            await s.commit()
        async with app.state.db.session_factory() as s:
            await peer.stop_participant(s, cs[9][2], 'Left the classroom', actor_id='test-admin')
            assert (await peer.gate_counts(s, 1))['gate'].timer_started_at == tenth
            await s.commit()
    finally:
        for c, _, _ in cs: await c.aclose()


async def test_stop_restore_blocks_writes_preserves_stage_and_deadline(app_client):
    admin, app, settings = app_client
    cs = await students(app, 2)
    first, rid, pid = cs[0]
    second = cs[1][0]
    try:
        await complete_k0(first); await enter_t1(first)
        initial = (await first.get('/api/student/state')).json()
        await admin.post('/api/admin/login', json={'password': settings.admin_password})
        path = f'/api/admin/participants/{pid}'
        assert (await admin.post(path + '/stop', json={'reason': ' '})).status_code == 422
        stopped = await admin.post(path + '/stop', json={'reason': 'Participant left; confirmed in person'})
        assert stopped.status_code == 200, stopped.text
        after = (await first.get('/api/student/state')).json()
        assert after['stopped'] and after['stage'] == initial['stage']
        assert after['active_round']['deadline_at'] == initial['active_round']['deadline_at']
        for endpoint, body in [('/api/student/rounds/1/work', {'product_name': 'Blocked'}),
                               ('/api/student/instruments/k0/draft', {'answers': {}})]:
            r = await first.put(endpoint, json=body)
            assert r.status_code == 409 and r.json()['error']['code'] == 'participant_stopped'
        async with app.state.db.session_factory() as s:
            before_poll = (await s.get(Run, rid)).last_operation_at
        await first.get('/api/student/state'); await first.get('/api/student/state')
        async with app.state.db.session_factory() as s:
            assert (await s.get(Run, rid)).last_operation_at == before_poll
        assert (await admin.post(path + '/restore', json={'reason': 'Returned to class'})).status_code == 200
        restored = (await first.get('/api/student/state')).json()
        assert not restored['stopped'] and restored['active_round']['deadline_at'] == initial['active_round']['deadline_at']
        # Polling on an active account also leaves the operation timestamp alone.
        async with app.state.db.session_factory() as s:
            before_poll = (await s.get(Run, rid)).last_operation_at
        await first.get('/api/student/state')
        async with app.state.db.session_factory() as s:
            assert (await s.get(Run, rid)).last_operation_at == before_poll
    finally:
        for c, _, _ in cs: await c.aclose()


async def test_stopping_straggler_opens_small_class_and_cannot_restore_after_freeze(app_client):
    admin, app, settings = app_client
    cs = await students(app, 3)
    try:
        await seed_cohort(app, cs, 2)
        assert (await cs[0][0].get('/api/student/peer-assessment')).json()['waiting']
        await admin.post('/api/admin/login', json={'password': settings.admin_password})
        result = await admin.post(f'/api/admin/participants/{cs[2][2]}/stop', json={'reason': 'Confirmed withdrawal'})
        assert result.status_code == 200, result.text
        opened = (await cs[0][0].get('/api/student/peer-assessment')).json()
        assert not opened['waiting'] and opened['total'] == 2
        assert opened['gate']['active_count'] == 2 and opened['gate']['ready_count'] == 2
        assert opened['gate']['opening_reason'] == 'all_ready'
        restore = await admin.post(f'/api/admin/participants/{cs[2][2]}/restore', json={'reason': 'Return'})
        assert restore.status_code == 409 and restore.json()['error']['code'] == 'gate_already_open'
        overview = (await admin.get('/api/admin/overview')).json()
        assert not any(r['can_stop'] or r['can_restore'] for r in overview['participants'])
    finally:
        for c, _, _ in cs: await c.aclose()


async def test_actual_saves_refresh_operations_but_polling_does_not(app_client):
    _, app, _ = app_client
    cs = await students(app, 2)
    c, rid, _ = cs[0]
    try:
        await c.get('/api/student/instruments/k0')
        async with app.state.db.session_factory() as s:
            assert (await s.get(Run, rid)).last_operation_at is None
        r = await c.put('/api/student/instruments/k0/draft', json={'answers': {'k0_choice': 'a'}})
        assert r.status_code == 200
        async with app.state.db.session_factory() as s:
            written = (await s.get(Run, rid)).last_operation_at
            assert written is not None
        await c.get('/api/student/state'); await c.get('/api/student/instruments/k0')
        async with app.state.db.session_factory() as s:
            assert (await s.get(Run, rid)).last_operation_at == written
    finally:
        for c, _, _ in cs: await c.aclose()


async def test_concurrent_stop_open_is_atomic_and_legacy_batch_unchanged(app_client):
    admin, app, settings = app_client
    cs = await students(app, 3)
    try:
        await seed_cohort(app, cs, 2)
        await admin.post('/api/admin/login', json={'password': settings.admin_password})
        responses = await asyncio.gather(
            admin.post(f'/api/admin/participants/{cs[2][2]}/stop', json={'reason': 'Confirmed withdrawal'}),
            cs[0][0].get('/api/student/peer-assessment'), cs[1][0].get('/api/student/peer-assessment'))
        assert all(r.status_code == 200 for r in responses)
        async with app.state.db.session_factory() as s:
            batches = list((await s.execute(select(PeerBatch))).scalars())
            assert len(batches) == 1
            gate = await s.get(ClassPeerGate, 1)
            assert gate.status == 'open'
            assert gate.snapshot_json['active_count'] == gate.snapshot_json['ready_count'] == 2
            # Simulate a pre-upgrade frozen batch; its policy and assignments must stay unchanged.
            gate.policy_version = None; gate.snapshot_json = {}; gate.opening_reason = None
            before = [(a.id, a.work_id) for a in (await s.execute(select(PeerAssignment).order_by(PeerAssignment.id))).scalars()]
            await s.commit()
        for c, _, _ in cs[:2]: assert not (await c.get('/api/student/peer-assessment')).json()['waiting']
        async with app.state.db.session_factory() as s:
            gate = await s.get(ClassPeerGate, 1)
            assert gate.policy_version is None and gate.snapshot_json == {}
            assert before == [(a.id, a.work_id) for a in (await s.execute(select(PeerAssignment).order_by(PeerAssignment.id))).scalars()]
    finally:
        for c, _, _ in cs: await c.aclose()
