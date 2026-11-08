from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import shutil
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urlparse

import asyncpg
import fasteners
import httpx
import pgserver
import pytest
import pytest_asyncio
from PIL import Image
from pgserver.postgres_server import PostgresServer

from app.bootstrap import bootstrap_cohort
from app.config import Settings
from app.db import Database, Base
from app.main import create_app
from app.schemas import InstrumentPayload
from app.services.artifacts import create_artifact_version
from app.services.instruments import create_instrument_version
from app.services.readiness import activate_protocol

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = PROJECT_ROOT / ".test-tmp"
DATABASE_NAME = "hls_test"


def _short_runtime_dir() -> Path:
    path = Path(tempfile.gettempdir()) / "hls-pg-runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="session")
def pg_server() -> Iterator[pgserver.PostgresServer]:
    pg_logger = logging.getLogger("pgserver")
    pg_logger.handlers = [logging.NullHandler()]
    pg_logger.propagate = False
    runtime = _short_runtime_dir()
    PostgresServer.runtime_path = runtime
    PostgresServer.lock_path = runtime / ".lockfile"
    PostgresServer._lock = fasteners.InterProcessLock(PostgresServer.lock_path)
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    pgdata = Path(tempfile.mkdtemp(prefix="pgdata-", dir=str(TEST_ROOT)))
    server = pgserver.get_server(pgdata, cleanup_mode="stop")
    uri = server.get_uri()
    parsed = urlparse(uri)
    from urllib.parse import parse_qs

    socket_dir = parse_qs(parsed.query)["host"][0]

    async def create_database() -> None:
        conn = await asyncpg.connect(user="postgres", database="postgres", host=socket_dir)
        try:
            await conn.execute(f'DROP DATABASE IF EXISTS {DATABASE_NAME} WITH (FORCE)')
            await conn.execute(f"CREATE DATABASE {DATABASE_NAME}")
        finally:
            await conn.close()

    asyncio.run(create_database())
    yield server
    server.cleanup()
    shutil.rmtree(TEST_ROOT / pgdata.name, ignore_errors=True)


@pytest.fixture(scope="session")
def pg_socket_dir(pg_server) -> str:
    from urllib.parse import parse_qs

    return parse_qs(urlparse(pg_server.get_uri()).query)["host"][0]


@pytest.fixture()
def database_url(pg_socket_dir) -> str:
    return f"postgresql+asyncpg://postgres@/{DATABASE_NAME}?host={pg_socket_dir}"


class FakeAIState:
    def __init__(self) -> None:
        self.fail_text = False
        self.fail_image = False
        self.text_calls = 0
        self.image_calls = 0
        self.last_chat_payload: Optional[Dict[str, Any]] = None
        self.last_image_payload: Optional[Dict[str, Any]] = None
        self.image_delay = 0.0
        self.image_inflight = 0
        self.max_image_inflight = 0
        self._image_lock = threading.Lock()


class _FakeAIHandler(BaseHTTPRequestHandler):
    state: FakeAIState

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"error": {"message": "bad json"}})
            return
        if self.path.endswith("/chat/completions"):
            self.state.text_calls += 1
            self.state.last_chat_payload = payload
            if self.state.fail_text:
                self._send(500, {"error": {"message": "fake text failure"}})
                return
            messages = payload.get("messages", [])
            last_user = next(
                (item.get("content", "") for item in reversed(messages) if item.get("role") == "user"),
                "",
            )
            text = f"[TEST STUB] Reply to: {last_user[:80]}"
            self._send(
                200,
                {
                    "id": "chatcmpl-test",
                    "choices": [{"message": {"role": "assistant", "content": text}}],
                },
            )
            return
        if self.path.endswith("/images/generations"):
            self.state.image_calls += 1
            self.state.last_image_payload = payload
            with self.state._image_lock:
                self.state.image_inflight += 1
                self.state.max_image_inflight = max(
                    self.state.max_image_inflight, self.state.image_inflight
                )
            try:
                if self.state.image_delay:
                    time.sleep(self.state.image_delay)
                if self.state.fail_image:
                    self._send(503, {"error": {"message": "fake image outage"}})
                    return
                image = Image.new("RGB", (96, 54), (70, 100, 130))
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                import base64

                encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
                self._send(200, {"data": [{"b64_json": encoded}]})
            finally:
                with self.state._image_lock:
                    self.state.image_inflight -= 1
            return
        self._send(404, {"error": {"message": "not found"}})


@pytest.fixture()
def fake_ai() -> Iterator[FakeAIState]:
    state = FakeAIState()
    handler = type("FakeHandler", (_FakeAIHandler,), {"state": state})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"  # type: ignore[attr-defined]
    yield state
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


@pytest.fixture()
def settings(database_url, fake_ai) -> Settings:
    data_dir = TEST_ROOT / f"data-{uuid.uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=True)
    result = Settings(
        environment="test",
        public_origin=None,
        cookie_secure=False,
        database_url=database_url,
        admin_password="test-admin-password-123",
        anon_code_pepper="test-pepper-0123456789-abcdef",
        data_dir=data_dir,
        auto_bootstrap=True,
        auth_mode="code",
        image_worker_enabled=True,
        round_duration_seconds=840,
        t1_duration_seconds=840,
        t2_duration_seconds=840,
        text_model_base_url=fake_ai.base_url,
        text_model_name="test-text-model",
        text_model_api_key="test-text-key",
        image_model_base_url=fake_ai.base_url,
        image_model_name="test-image-model",
        image_model_api_key="test-image-key",
        image_model_timeout_seconds=10,
        text_model_timeout_seconds=10,
        image_job_limit_per_round=3,
        image_prompt_optimizer_enabled=False,
        image_max_concurrency=2,
    )
    yield result
    shutil.rmtree(data_dir, ignore_errors=True)


def demo_instrument(kind: str) -> InstrumentPayload:
    base = {
        "k0": {
            "title": "Demo K0",
            "questions": [
                {
                    "id": "k0_choice",
                    "type": "single_choice",
                    "prompt": "Demo K0 choice",
                    "required": True,
                    "options": [
                        {"value": "a", "label": "A"},
                        {"value": "b", "label": "B"},
                    ],
                }
            ],
        },
        "k1": {
            "title": "Demo K1",
            "questions": [
                {
                    "id": "k1_text",
                    "type": "short_text",
                    "prompt": "Demo K1 short answer",
                    "required": True,
                    "max_length": 200,
                }
            ],
        },
        "k2": {
            "title": "Demo K2",
            "questions": [
                {
                    "id": "k2_multi",
                    "type": "multi_choice",
                    "prompt": "Demo K2 multiple choice",
                    "required": True,
                    "options": [
                        {"value": "x", "label": "X"},
                        {"value": "y", "label": "Y"},
                    ],
                }
            ],
        },
        "k3": {
            "title": "Demo K3",
            "questions": [
                {
                    "id": "k3_text",
                    "type": "short_text",
                    "prompt": "Demo K3 short answer",
                    "required": True,
                    "max_length": 300,
                }
            ],
        },
        "survey": {
            "title": "Demo survey",
            "questions": [
                {
                    "id": "survey",
                    "type": "likert",
                    "prompt": "Demo survey rating",
                    "required": True,
                    "scale_min": 1,
                    "scale_max": 5,
                }
            ],
        },
    }[kind]
    return InstrumentPayload.model_validate(
        {"instructions": "DEMO PLACEHOLDER", **base}
    )

def demo_image() -> bytes:
    image = Image.new("RGB", (240, 150), (210, 220, 228))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def seed_demo_content(settings: Settings) -> None:
    db = Database(settings.database_url)
    try:
        async with db.session_factory() as session:
            await bootstrap_cohort(session, settings)
            for slot in ("X", "Y"):
                await create_artifact_version(
                    session,
                    settings,
                    slot=slot,
                    title=f"Demo Artifact {slot}",
                    era="Demo era",
                    artifact_type="Demo type",
                    introduction="DEMO PLACEHOLDER. Not real heritage content.",
                    facts=["Demo fact"],
                    evidence=["Demo source"],
                    uncertainty=["Demo uncertainty"],
                    image_bytes=demo_image(),
                    image_filename=f"{slot}.png",
                    is_demo=True,
                )
            for kind in ("k0", "k1", "k2", "k3", "survey"):
                await create_instrument_version(
                    session, kind=kind, payload=demo_instrument(kind), is_demo=True
                )
            await session.commit()
            await activate_protocol(session, settings, allow_demo=True)
            await session.commit()
    finally:
        await db.dispose()


@pytest_asyncio.fixture()
async def app_client(settings, fake_ai):
    db = Database(settings.database_url)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await db.dispose()
    await seed_demo_content(settings)
    app = create_app(settings)
    app.state.fake_ai_state = fake_ai
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver", timeout=20
        ) as client:
            yield client, app, settings
    cleanup_db = Database(settings.database_url)
    async with cleanup_db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await cleanup_db.dispose()


def code_rows(settings: Settings) -> List[Dict[str, str]]:
    with settings.codes_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


async def login_student(
    client: httpx.AsyncClient, settings: Settings, class_id: Optional[int] = None
) -> Dict[str, Any]:
    rows = code_rows(settings)
    row = next(
        (item for item in rows if class_id is None or int(item["class_id"]) == class_id),
        None,
    )
    assert row is not None
    response = await client.post(
        "/api/auth/enter",
        json={"code": row["access_code"], "class_id": int(row["class_id"])},
    )
    assert response.status_code == 200, response.text
    return {"row": row, "body": response.json()}


async def complete_k0(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/student/instruments/k0/submit", json={"answers": {"k0_choice": "a"}}
    )
    assert response.status_code == 200, response.text


async def enter_t1(client: httpx.AsyncClient) -> None:
    tutorial = await client.post("/api/student/tutorial/complete")
    assert tutorial.status_code == 200, tutorial.text
    started = await client.post("/api/student/rounds/1/start")
    assert started.status_code == 200, started.text


async def save_t1_work(client: httpx.AsyncClient, product: str = "Test product") -> None:
    response = await client.put(
        "/api/student/rounds/1/work",
        json={
            "product_name": product,
            "product_category": "T-shirt",
            "target_audience": "Young museum visitors",
            "design_concept": "A contemporary product based on the artifact.",
            "structured_fields": {
                "cultural_features": "Visible motif and form.",
                "historical_function": "Historical function explained from the evidence.",
                "sources_evidence": "Based on the reviewed evidence pack.",
                "cultural_continuity": "Retain the motif and its cultural meaning.",
                "cultural_translation": "Translate it into a modern product.",
                "innovation_rationale": "Explain the modern design choice.",
            },
            "open_statement": "A direct open statement for the free-form condition.",
            "image_prompt": "A studio product shot with warm side light and a neutral background.",
        },
    )
    assert response.status_code == 200, response.text


async def save_t2_work(client: httpx.AsyncClient, product: str = "Transfer product") -> None:
    response = await client.put(
        "/api/student/rounds/2/work",
        json={
            "product_name": product,
            "product_category": "Tote bag",
            "target_audience": "General museum audience",
            "design_concept": "A transfer design based on the new artifact.",
            "structured_fields": {
                "cultural_features": "A visible feature from the new artifact.",
                "historical_function": "A supported historical context.",
                "sources_evidence": "Evidence from the reviewed material.",
                "cultural_continuity": "A retained cultural relationship.",
                "cultural_translation": "A translation into the product.",
                "innovation_rationale": "A reason for the contemporary choice.",
            },
            "open_statement": "I retained one cultural idea and translated it into a modern product.",
        },
    )
    assert response.status_code == 200, response.text


async def submit_assessment(client: httpx.AsyncClient, kind: str, answers: dict) -> None:
    response = await client.post(
        f"/api/student/instruments/{kind}/submit", json={"answers": answers}
    )
    assert response.status_code == 200, response.text


async def reach_peer_assessment(client: httpx.AsyncClient) -> None:
    await complete_k0(client)
    await enter_t1(client)
    await save_t1_work(client)
    finish_t1 = await client.post("/api/student/rounds/1/finish")
    assert finish_t1.status_code == 200, finish_t1.text
    await submit_assessment(client, "k1", {"k1_text": "K1 answer"})
    await submit_assessment(client, "k2", {"k2_multi": ["x"]})
    start_t2 = await client.post("/api/student/rounds/2/start")
    assert start_t2.status_code == 200, start_t2.text
    await save_t2_work(client)
    finish_t2 = await client.post("/api/student/rounds/2/finish")
    assert finish_t2.status_code == 200, finish_t2.text
    await submit_assessment(client, "k3", {"k3_text": "K3 answer"})
    await submit_assessment(client, "survey", {"survey": 4})


async def finish_peer_and_social(client: httpx.AsyncClient) -> None:
    peer = await client.get("/api/student/peer-assessment")
    assert peer.status_code == 200, peer.text
    for assignment in peer.json().get("assignments", []):
        if assignment.get("status") == "submitted":
            continue
        response = await client.post(
            f"/api/student/peer-assessment/{assignment['assignment_id']}",
            json={
                "scores": {
                    "cultural_clarity": 4,
                    "cultural_translation": 4,
                    "design_originality": 4,
                },
                "comment": "Test peer review.",
            },
        )
        assert response.status_code == 200, response.text
    complete_peer = await client.post("/api/student/peer-assessment/complete")
    assert complete_peer.status_code == 200, complete_peer.text
    social = await client.get("/api/student/social-feed")
    assert social.status_code == 200, social.text
    complete_social = await client.post("/api/student/social/complete")
    assert complete_social.status_code == 200, complete_social.text


async def reach_t2_active(client: httpx.AsyncClient) -> None:
    await complete_k0(client)
    await enter_t1(client)
    await save_t1_work(client)
    finish_t1 = await client.post("/api/student/rounds/1/finish")
    assert finish_t1.status_code == 200, finish_t1.text
    await submit_assessment(client, "k1", {"k1_text": "K1 answer"})
    await submit_assessment(client, "k2", {"k2_multi": ["x"]})
    start_t2 = await client.post("/api/student/rounds/2/start")
    assert start_t2.status_code == 200, start_t2.text
