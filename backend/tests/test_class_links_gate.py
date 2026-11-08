from __future__ import annotations

import httpx
from sqlalchemy import func, select

from app.models import PeerBatch
from tests.conftest import reach_t2_active, save_t2_work, submit_assessment


async def _email_student(app, email: str, class_token: str):
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver", timeout=20
    )
    entered = await client.post(
        "/api/auth/enter",
        json={"email": email, "class_id": 1, "class_token": class_token},
    )
    assert entered.status_code == 200, entered.text
    return client, entered


async def test_class_link_binding_and_dynamic_auto_gate(app_client):
    client, app, settings = app_client
    admin = await client.post("/api/admin/login", json={"password": settings.admin_password})
    assert admin.status_code == 200, admin.text
    created = await client.post("/api/admin/class-links", json={"class_id": 1, "label": "class 1"})
    assert created.status_code == 200, created.text
    token = created.json()["token"]
    assert created.json()["url"].endswith(token)

    resolved = await client.get(f"/api/auth/class-link?token={token}")
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["class_id"] == 1

    mismatch = await client.post(
        "/api/auth/enter",
        json={"email": "mismatch@polyu.edu.hk", "class_id": 2, "class_token": token},
    )
    assert mismatch.status_code == 401
    assert mismatch.json()["error"]["code"] == "invalid_class_link"

    first, first_enter = await _email_student(app, "gate.one@polyu.edu.hk", token)
    second, _ = await _email_student(app, "gate.two@polyu.edu.hk", token)
    try:
        await reach_t2_active(first)
        await save_t2_work(first)
        await reach_t2_active(second)
        await save_t2_work(second)

        first_finish = await first.post("/api/student/rounds/2/finish")
        assert first_finish.status_code == 200, first_finish.text
        await submit_assessment(first, "k3", {"k3_text": "K3 one"})
        await submit_assessment(first, "survey", {"survey": 4})
        waiting = await first.get("/api/student/peer-assessment")
        assert waiting.status_code == 200, waiting.text
        assert waiting.json()["waiting"] is True
        assert waiting.json()["total"] == 0
        async with app.state.db.session_factory() as session:
            count = (
                await session.execute(
                    select(func.count()).select_from(PeerBatch)
                )
            ).scalar_one()
            assert count == 0

        second_finish = await second.post("/api/student/rounds/2/finish")
        assert second_finish.status_code == 200, second_finish.text
        await submit_assessment(second, "k3", {"k3_text": "K3 two"})
        await submit_assessment(second, "survey", {"survey": 4})
        opened = await first.get("/api/student/peer-assessment")
        assert opened.status_code == 200, opened.text
        assert opened.json()["waiting"] is False
        assert opened.json()["gate"]["status"] == "open"
        assert opened.json()["total"] == 2
        assert opened.json()["gate"]["valid_work_count"] == 4
        second_opened = await second.get("/api/student/peer-assessment")
        assert second_opened.status_code == 200, second_opened.text
        assert second_opened.json()["total"] == 2

        # The class is closed to new email accounts once the batch is frozen.
        late = await client.post(
            "/api/auth/enter",
            json={"email": "late@polyu.edu.hk", "class_id": 1, "class_token": token},
        )
        assert late.status_code == 409
        assert late.json()["error"]["code"] == "class_closed"

        gates = await client.get("/api/admin/class-peer-gates")
        assert gates.status_code == 200, gates.text
        class_one = next(item for item in gates.json()["classes"] if item["class_id"] == 1)
        assert class_one["status"] == "open"
        assert class_one["entered"] >= 2
        assert class_one["batch_id"]
    finally:
        await first.aclose()
        await second.aclose()


async def test_class_link_revoke(app_client):
    client, app, settings = app_client
    admin = await client.post("/api/admin/login", json={"password": settings.admin_password})
    assert admin.status_code == 200
    created = await client.post("/api/admin/class-links", json={"class_id": 2})
    link_id = created.json()["link"]["id"]
    token = created.json()["token"]
    assert (await client.get(f"/api/auth/class-link?token={token}")).status_code == 200
    revoked = await client.post(f"/api/admin/class-links/{link_id}/revoke")
    assert revoked.status_code == 200, revoked.text
    assert (await client.get(f"/api/auth/class-link?token={token}")).status_code == 401


async def test_saved_links_survive_another_class_and_a_new_admin_session(app_client):
    from app.main import create_app
    from app.models import ClassEntryLink
    from app.services.class_links import TOKEN_SCHEME, saved_class_link_url
    from app.security import token_hash

    client, app, settings = app_client
    await client.post('/api/admin/login', json={'password': settings.admin_password})
    saved = []
    for class_id in (1, 2):
        response = await client.post('/api/admin/class-links', json={'class_id': class_id, 'label': f'Class {class_id}'})
        assert response.status_code == 200
        saved.append(response.json())
    response = await client.get('/api/admin/class-links')
    assert response.headers['cache-control'] == 'private, no-store'
    listed = response.json()['links']
    assert {link['url'] for link in listed} == {link['url'] for link in saved}
    async with app.state.db.session_factory() as session:
        stored = await session.get(ClassEntryLink, saved[0]['link']['id'])
        assert stored.token_scheme == TOKEN_SCHEME
        assert stored.token_hash == token_hash(saved[0]['token'])
        assert stored.token_hash != saved[0]['token']
        changed_key = settings.model_copy(update={'anon_code_pepper': 'another-independent-test-key'})
        assert saved_class_link_url(changed_key, stored) is None
    await client.post('/api/admin/logout')
    assert (await client.get('/api/admin/class-links')).status_code == 401

    # A fresh application and authenticated session reconstruct the same URLs
    # from persisted records, independently of any frontend state.
    fresh = create_app(settings)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fresh), base_url='http://testserver') as admin:
            assert (await admin.get('/api/admin/class-links')).status_code == 401
            await admin.post('/api/admin/login', json={'password': settings.admin_password})
            listed = (await admin.get('/api/admin/class-links')).json()['links']
            assert {link['url'] for link in listed} == {link['url'] for link in saved}
            rotated = await admin.post(f"/api/admin/class-links/{saved[0]['link']['id']}/rotate")
            assert rotated.status_code == 200
            new_link = rotated.json()
            assert new_link['url'] != saved[0]['url']
            listed = {link['id']: link for link in (await admin.get('/api/admin/class-links')).json()['links']}
            assert listed[saved[0]['link']['id']]['url'] is None
            assert listed[saved[1]['link']['id']]['url'] == saved[1]['url']
            assert listed[new_link['link']['id']]['url'] == new_link['url']
            assert (await admin.get('/api/auth/class-link', params={'token': saved[0]['token']})).status_code == 401
            public = await admin.get('/api/auth/class-link', params={'token': new_link['token']})
            assert public.status_code == 200 and public.json()['class_id'] == 1
            assert 'url' not in public.json() and new_link['token'] not in public.text
            await admin.post(f"/api/admin/class-links/{new_link['link']['id']}/revoke")
            listed = (await admin.get('/api/admin/class-links')).json()['links']
            assert next(link for link in listed if link['id'] == new_link['link']['id'])['url'] is None
    finally:
        await fresh.state.db.dispose()


async def test_legacy_links_keep_working_and_can_be_regenerated(app_client):
    import secrets
    from app.models import ClassEntryLink
    from app.security import token_hash
    from tests.conftest import login_student

    client, app, settings = app_client
    old_token = secrets.token_urlsafe(24)
    async with app.state.db.session_factory() as session:
        legacy = ClassEntryLink(class_id=1, label='Older link', active=True, token_hash=token_hash(old_token))
        session.add(legacy)
        await session.commit()
        old_id = str(legacy.id)
    await client.post('/api/admin/login', json={'password': settings.admin_password})
    listed = (await client.get('/api/admin/class-links')).json()['links']
    assert listed[0]['url'] is None
    assert (await client.get('/api/auth/class-link', params={'token': old_token})).status_code == 200
    rotated = (await client.post(f'/api/admin/class-links/{old_id}/rotate')).json()
    listed = (await client.get('/api/admin/class-links')).json()['links']
    assert next(link for link in listed if link['id'] == rotated['link']['id'])['url'] == rotated['url']
    assert (await client.get('/api/auth/class-link', params={'token': old_token})).status_code == 401
    await client.post('/api/admin/logout')
    await login_student(client, settings)
    denied = await client.get('/api/admin/class-links')
    assert denied.status_code == 401 and rotated['token'] not in denied.text
