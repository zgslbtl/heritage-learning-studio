from __future__ import annotations

from uuid import uuid4

import httpx

from types import SimpleNamespace

from app.prompts.hlsf import DESIGN_COACH_B, HLSF_VERSION, PHASE_HINTS, PHASE_PROMPTS
from app.services.ai_text import _artifact_section_index, _learning_anchor_context
from app.services.works import work_completion_issues
from tests.conftest import (
    code_rows,
    complete_k0,
    enter_t1,
    enter_t1,
    reach_t2_active,
    save_t1_work,
    save_t2_work,
    submit_assessment,
)


def _system(payload):
    return next(
        message["content"]
        for message in payload["messages"]
        if message["role"] == "system"
    )


async def _login_row(client, settings, groups, email_mode=False):
    rows = code_rows(settings)
    row = next(item for item in rows if item["group"] in groups)
    entered = await client.post(
        "/api/auth/enter",
        json={"code": row["access_code"], "class_id": int(row["class_id"])},
    )
    assert entered.status_code == 200, entered.text
    return entered.json()["state"]["participant"]["id"]


def test_hlsf_v16_product_design_templates_and_hints_are_versioned():
    assert HLSF_VERSION == "hlsf-v1.7.1-crossover-pilot"
    assert set(PHASE_PROMPTS) == {"observe", "explain", "create", "reflect"}
    assert set(PHASE_HINTS) == {"observe", "explain", "create", "reflect"}
    assert "最值得深入了解" in PHASE_PROMPTS["observe"]
    assert "我还不知道" in PHASE_PROMPTS["observe"]
    assert "用自己的话解释" in PHASE_PROMPTS["explain"]
    assert "由你来决定创作方向" in PHASE_PROMPTS["create"]
    assert "最值得修订的一处" in PHASE_PROMPTS["reflect"]
    assert "每次只提出一个最重要的问题" in DESIGN_COACH_B
    assert "不主动列举、建议或暗示具体产品类型" in DESIGN_COACH_B
    assert "2–4句" in DESIGN_COACH_B
    assert "Mxx/Txx" in DESIGN_COACH_B
    assert "不知道" in DESIGN_COACH_B
    for text in PHASE_HINTS.values():
        assert text.strip()


def test_submission_form_is_condition_driven():
    base = {
        "product_name": "Product",
        "product_category": "T-shirt",
        "target_audience": "Visitors",
        "design_concept": "Concept",
        "structured_fields": {
            "cultural_features": "a",
            "historical_function": "b",
            "sources_evidence": "c",
            "cultural_continuity": "d",
            "cultural_translation": "e",
            "innovation_rationale": "f",
        },
        "open_statement": "Open statement",
    }
    a_only_open = SimpleNamespace(**{**base, "structured_fields": {}})
    b_only_structured = SimpleNamespace(**{**base, "open_statement": ""})
    version = "crossover-v1.0-pilot"
    assert work_completion_issues(1, "A", a_only_open, version) == []
    assert work_completion_issues(2, "A", b_only_structured, version) == ["open_statement"]
    assert work_completion_issues(1, "B", b_only_structured, version) == []
    assert work_completion_issues(2, "B", a_only_open, version) != []
    # Legacy v1.5 runs retain T1 structured / T2 open.
    assert work_completion_issues(1, "A", a_only_open) != []
    assert work_completion_issues(2, "B", a_only_open) == []


def test_v16_section_index_and_learning_anchors_are_test_free():
    artifact = SimpleNamespace(
        object_code="M",
        sections_json=[
            {
                "key": "M01",
                "title": "M01 · 物件与可观察图像",
                "body": "证据层次：馆藏登记｜图像观察 | 参考：[HKPM-P]\n\n登记信息……",
                "source_ids": ["HKPM-P"],
            },
            {
                "key": "M03",
                "title": "M03 · 明代官服制度中的意义",
                "body": "证据层次：古籍制度｜历史解释\n\n制度说明……",
                "source_ids": ["MING-01"],
            },
        ],
    )
    index = _artifact_section_index(artifact)
    anchors = _learning_anchor_context(artifact)
    assert "M01" in index and "馆藏登记｜图像观察" in index
    assert "sources: HKPM-P" in index
    assert "M03" in anchors and "身份识别" in anchors
    assert "M-A-01" not in index + anchors
    assert "正确答案" not in index + anchors
    assert "K0" not in index + anchors


async def test_b_design_context_phase_guidance_and_work_record(app_client):
    client, app, settings = app_client
    fake = app.state.fake_ai_state
    participant_id = await _login_row(client, settings, {"G3", "G4"})
    await complete_k0(client)
    await enter_t1(client)

    messages = await client.get("/api/student/rounds/1/messages")
    assert messages.status_code == 200, messages.text
    body = messages.json()
    assert body["guide"]["version"] == "hlsf-v1.7.1-crossover-pilot"
    assert body["messages"][0]["source"] == "hlsf_prompt"
    assert "最值得深入了解" in body["messages"][0]["content"]

    await save_t1_work(client, "CRANE-LOTUS-PRODUCT")
    seed = "I want to keep the crane and lotus motif in a contemporary design."
    observe = await client.post(
        "/api/student/rounds/1/messages",
        json={"content": seed, "client_message_id": str(uuid4())},
    )
    assert observe.status_code == 200, observe.text
    observe_system = _system(fake.last_chat_payload)
    assert "文化遗产知识与文创设计的学习教练" in observe_system
    assert "Current coaching phase: observe" in observe_system
    assert "CRANE-LOTUS-PRODUCT" in observe_system
    assert "Student's current product-design record" in observe_system
    assert "story seed" not in observe_system.lower()
    assert "2–4句" in observe_system

    calls_after_observe = fake.text_calls
    advanced = await client.post(
        "/api/student/rounds/1/hlsf/advance",
        json={"from_phase": "observe", "skip": False},
    )
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["guide"]["version"] == "hlsf-v1.7.1-crossover-pilot"
    assert fake.text_calls == calls_after_observe  # fixed scaffold adds no model call

    explain = await client.post(
        "/api/student/rounds/1/messages",
        json={"content": "Which evidence should I use?", "client_message_id": str(uuid4())},
    )
    assert explain.status_code == 200, explain.text
    explain_system = _system(fake.last_chat_payload)
    assert "Current coaching phase: explain" in explain_system
    assert "CRANE-LOTUS-PRODUCT" in explain_system
    assert "百科式讲授" in explain_system

    await client.post(
        "/api/student/rounds/1/hlsf/advance",
        json={"from_phase": "explain", "skip": False},
    )
    create = await client.post(
        "/api/student/rounds/1/messages",
        json={
            "content": "I want to design a T-shirt with my own approach.",
            "client_message_id": str(uuid4()),
        },
    )
    assert create.status_code == 200, create.text
    create_system = _system(fake.last_chat_payload)
    assert "Current coaching phase: create" in create_system
    assert "CRANE-LOTUS-PRODUCT" in create_system
    assert "product" in create_system.lower()

    await client.post(
        "/api/student/rounds/1/hlsf/advance",
        json={"from_phase": "create", "skip": False},
    )
    reflect = await client.post(
        "/api/student/rounds/1/messages",
        json={
            "content": "Please review the design I saved and name one change.",
            "client_message_id": str(uuid4()),
        },
    )
    assert reflect.status_code == 200, reflect.text
    reflect_system = _system(fake.last_chat_payload)
    assert "Current coaching phase: reflect" in reflect_system
    assert "CRANE-LOTUS-PRODUCT" in reflect_system
    assert "最值得重新考虑" in reflect_system

    refreshed = await client.get("/api/student/rounds/1/messages")
    assert refreshed.status_code == 200
    assert refreshed.json()["guide"]["phase"] == "reflect"

    admin = await client.post("/api/admin/login", json={"password": settings.admin_password})
    assert admin.status_code == 200, admin.text
    detail = await client.get(f"/api/admin/participants/{participant_id}")
    assert detail.status_code == 200, detail.text
    detail_body = detail.json()
    assert any(
        event["meta"].get("prompt_version") == "hlsf-v1.7.1-crossover-pilot"
        for event in detail_body["hlsf_events"]
    )
    assert any(
        call["prompt_version"] == "chat-v2+hlsf-v1.7.1-crossover-pilot"
        for call in detail_body["ai_calls"]
    )


async def test_b_reflect_without_work_does_not_invent_review(app_client):
    client, app, settings = app_client
    fake = app.state.fake_ai_state
    await _login_row(client, settings, {"G3", "G4"})
    await complete_k0(client)
    await enter_t1(client)
    for phase in ("observe", "explain", "create"):
        advanced = await client.post(
            "/api/student/rounds/1/hlsf/advance",
            json={"from_phase": phase, "skip": True},
        )
        assert advanced.status_code == 200, advanced.text
    reflect = await client.post(
        "/api/student/rounds/1/messages",
        json={"content": "Can you review my design?", "client_message_id": str(uuid4())},
    )
    assert reflect.status_code == 200, reflect.text
    system = _system(fake.last_chat_payload)
    assert "No student product design has been saved" in system


async def test_a_context_has_no_hlsf_guidance(app_client):
    client, app, settings = app_client
    fake = app.state.fake_ai_state
    rows = code_rows(settings)
    row = next(item for item in rows if item["group"] in {"G1", "G2"})
    entered = await client.post(
        "/api/auth/enter",
        json={"code": row["access_code"], "class_id": int(row["class_id"])},
    )
    assert entered.status_code == 200, entered.text
    await complete_k0(client)
    await enter_t1(client)
    started = await client.get("/api/student/rounds/1")
    assert started.status_code == 200
    assert started.json()["guide"] is None
    sent = await client.post(
        "/api/student/rounds/1/messages",
        json={
            "content": "Tell me a product idea about the crane.",
            "client_message_id": str(uuid4()),
        },
    )
    assert sent.status_code == 200, sent.text
    system = _system(fake.last_chat_payload)
    lowered = system.lower()
    assert "product-design coach" not in lowered
    assert "current coaching phase" not in lowered
    assert "student's current product-design record" not in lowered
    assert "hlsf-v1.7.1-crossover-pilot" not in system
    assert "Standard AI condition" in system
    assert "staged teaching framework" in system
    assert "you can start from" in system.lower()
    assert "普通 AI 条件" in system
    assert "不要主动给学生设计流程" in system


async def test_all_four_groups_complete_k0_t1_k1_k2_t2_k3(app_client):
    _client, app, settings = app_client
    rows = code_rows(settings)
    for group in ("G1", "G2", "G3", "G4"):
        row = next(item for item in rows if item["group"] == group)
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        )
        async with client:
            entered = await client.post(
                "/api/auth/enter",
                json={"code": row["access_code"], "class_id": int(row["class_id"])},
            )
            assert entered.status_code == 200, (group, entered.text)
            await complete_k0(client)
            await enter_t1(client)
            t1 = await client.get("/api/student/rounds/1")
            assert t1.status_code == 200
            if group in ("G3", "G4"):
                assert t1.json()["guide"] is not None
                assert t1.json()["work_form"] == "structured"
            else:
                assert t1.json()["guide"] is None
                assert t1.json()["work_form"] == "open"
            await save_t1_work(client, f"{group} T1 product")
            finished = await client.post("/api/student/rounds/1/finish")
            assert finished.status_code == 200, (group, finished.text)
            await submit_assessment(client, "k1", {"k1_text": "K1 answer"})
            await submit_assessment(client, "k2", {"k2_multi": ["x"]})
            start2 = await client.post("/api/student/rounds/2/start")
            assert start2.status_code == 200, (group, start2.text)
            t2 = await client.get("/api/student/rounds/2")
            assert t2.status_code == 200
            assert t1.json()["artifact"]["id"] != t2.json()["artifact"]["id"]
            if group in ("G1", "G2"):
                assert t2.json()["guide"] is not None
                assert t2.json()["work_form"] == "structured"
            else:
                assert t2.json()["guide"] is None
                assert t2.json()["work_form"] == "open"
            await save_t2_work(client, f"{group} T2 product")
            finish2 = await client.post(
                "/api/student/rounds/2/finish",
                json={"consent_future_research": True},
            )
            assert finish2.status_code == 200, (group, finish2.text)
            await submit_assessment(client, "k3", {"k3_text": "K3 answer"})
            state = await client.get("/api/student/state")
            assert state.json()["stage"] == "survey", (group, state.json())


async def test_g1_g2_standard_t1_then_hlsf_t2_flow(app_client):
    client, app, settings = app_client
    rows = code_rows(settings)
    row = next(item for item in rows if item["group"] in {"G1", "G2"})
    entered = await client.post(
        "/api/auth/enter",
        json={"code": row["access_code"], "class_id": int(row["class_id"])},
    )
    assert entered.status_code == 200, entered.text
    await complete_k0(client)
    await enter_t1(client)
    t1 = await client.get("/api/student/rounds/1")
    assert t1.status_code == 200
    assert t1.json()["guide"] is None
    await save_t1_work(client, "G1 G2 T1 product")
    finished = await client.post("/api/student/rounds/1/finish")
    assert finished.status_code == 200, finished.text
    await submit_assessment(client, "k1", {"k1_text": "K1 answer"})
    await submit_assessment(client, "k2", {"k2_multi": ["x"]})
    start2 = await client.post("/api/student/rounds/2/start")
    assert start2.status_code == 200, start2.text
    t2 = await client.get("/api/student/rounds/2")
    assert t2.status_code == 200
    assert t2.json()["guide"]["version"] == "hlsf-v1.7.1-crossover-pilot"
    assert t1.json()["artifact"]["id"] != t2.json()["artifact"]["id"]
    await save_t2_work(client, "G1 G2 T2 product")
    finish2 = await client.post(
        "/api/student/rounds/2/finish",
        json={"consent_future_research": True},
    )
    assert finish2.status_code == 200, finish2.text
    await submit_assessment(client, "k3", {"k3_text": "K3 answer"})
    await submit_assessment(client, "survey", {"survey": 4})
    assert (await client.get("/api/student/state")).json()["stage"] == "peer_assessment"


async def test_g1_g2_t2_has_hlsf_and_uses_open_statement(app_client):
    client, app, settings = app_client
    fake = app.state.fake_ai_state
    rows = code_rows(settings)
    row = next(item for item in rows if item["group"] in {"G1", "G2"})
    entered = await client.post(
        "/api/auth/enter",
        json={"code": row["access_code"], "class_id": int(row["class_id"])},
    )
    assert entered.status_code == 200, entered.text
    await reach_t2_active(client)
    round_payload = await client.get("/api/student/rounds/2")
    assert round_payload.status_code == 200, round_payload.text
    assert round_payload.json()["guide"]["version"] == "hlsf-v1.7.1-crossover-pilot"
    assert round_payload.json()["work_form"] == "structured"
    messages = await client.get("/api/student/rounds/2/messages")
    assert messages.status_code == 200
    assert messages.json()["messages"][0]["source"] == "hlsf_prompt"
    assert "最值得深入了解" in messages.json()["messages"][0]["content"]

    await save_t2_work(client, "T2 HLSF product")
    sent = await client.post(
        "/api/student/rounds/2/messages",
        json={"content": "Please review my open statement.", "client_message_id": str(uuid4())},
    )
    assert sent.status_code == 200, sent.text
    system = _system(fake.last_chat_payload)
    assert "文化遗产知识与文创设计的学习教练" in system
    assert "This is T2" in system
    assert "open design statement" in system.lower()
    assert "T2 HLSF product" in system

    for phase in ("observe", "explain", "create"):
        advanced = await client.post(
            "/api/student/rounds/2/hlsf/advance",
            json={"from_phase": phase, "skip": False},
        )
        assert advanced.status_code == 200, advanced.text
    reflect_messages = await client.get("/api/student/rounds/2/messages")
    assert any(
        "开放作品说明" in message["content"]
        for message in reflect_messages.json()["messages"]
    )
    hint = await client.post(
        "/api/student/rounds/2/hlsf/hint", json={"phase": "reflect"}
    )
    assert hint.status_code == 200, hint.text
    assert "开放作品说明" in hint.json()["messages"][0]["content"]


async def test_t2_has_no_hlsf_and_standard_context(app_client):
    client, app, settings = app_client
    fake = app.state.fake_ai_state
    rows = code_rows(settings)
    row = next(item for item in rows if item["group"] in {"G3", "G4"})
    entered = await client.post(
        "/api/auth/enter",
        json={"code": row["access_code"], "class_id": int(row["class_id"])},
    )
    assert entered.status_code == 200, entered.text
    await reach_t2_active(client)
    round_payload = await client.get("/api/student/rounds/2")
    assert round_payload.status_code == 200, round_payload.text
    assert round_payload.json()["guide"] is None
    assert round_payload.json()["task"] == "T2"
    assert round_payload.json()["work_form"] == "open"
    messages = await client.get("/api/student/rounds/2/messages")
    assert messages.status_code == 200
    assert messages.json()["messages"] == []
    hlsf = await client.post(
        "/api/student/rounds/2/hlsf/advance",
        json={"from_phase": "observe", "skip": False},
    )
    assert hlsf.status_code == 404
    sent = await client.post(
        "/api/student/rounds/2/messages",
        json={
            "content": "Can you help with this new artifact?",
            "client_message_id": str(uuid4()),
        },
    )
    assert sent.status_code == 200, sent.text
    system = _system(fake.last_chat_payload)
    lowered = system.lower()
    assert "文化遗产知识与文创设计的学习教练" not in system
    assert "Current coaching phase" not in system
    assert "Artifact section index" not in system
    assert "Curated learning anchors" not in system
    assert "hlsf-v1.7.1-crossover-pilot" not in system
    assert "Standard AI condition" in system
    assert "staged teaching framework" in system
