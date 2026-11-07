#!/usr/bin/env python3
"""Local-only runtime for browser smoke testing.

Starts an ephemeral PostgreSQL database, an explicitly labelled OpenAI-compatible test
stub, seeds demo content, and runs Uvicorn on 127.0.0.1:8000. This is NOT a production
server and must never be used to claim real model validation.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
RUNTIME = ROOT / ".local-runtime"
PGDATA = RUNTIME / "pgdata"
DATA_DIR = RUNTIME / "data"
DB_NAME = "heritage_dev"
ADMIN_PASSWORD = "local-dev-admin-password-123"
PEPPER = "local-dev-code-pepper-0123456789"


def start_ai_stub() -> tuple[ThreadingHTTPServer, str]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send(self, status: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            if self.path.endswith("/chat/completions"):
                messages = payload.get("messages", [])
                user = next(
                    (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
                    "",
                )
                self._send(
                    200,
                    {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": (
                                        "[LOCAL TEST STUB — NOT A REAL MODEL] "
                                        + str(user)[:200]
                                    ),
                                }
                            }
                        ]
                    },
                )
                return
            if self.path.endswith("/images/generations"):
                from PIL import Image

                image = Image.new("RGB", (1280, 720), (74, 102, 124))
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                self._send(
                    200,
                    {"data": [{"b64_json": base64.b64encode(buffer.getvalue()).decode()}]},
                )
                return
            self._send(404, {"error": {"message": "not found"}})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/v1"


def create_database(host: str, preserve: bool) -> str:
    import asyncpg

    async def go() -> None:
        conn = await asyncpg.connect(user="postgres", database="postgres", host=host)
        try:
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", DB_NAME
            )
            if preserve and exists:
                return
            await conn.execute(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE)")
            await conn.execute(f"CREATE DATABASE {DB_NAME}")
        finally:
            await conn.close()

    asyncio.run(go())
    return f"postgresql+asyncpg://postgres@/{DB_NAME}?host={host}"


def _validate_real_ai_env() -> list[str]:
    from dotenv import dotenv_values

    env_path = ROOT / ".env"
    dotenv = dotenv_values(env_path) if env_path.exists() else {}
    required = (
        "TEXT_MODEL_BASE_URL",
        "TEXT_MODEL_NAME",
        "TEXT_MODEL_API_KEY",
        "IMAGE_MODEL_BASE_URL",
        "IMAGE_MODEL_NAME",
        "IMAGE_MODEL_API_KEY",
    )
    return [
        key
        for key in required
        if not (os.environ.get(key) or dotenv.get(key))
    ]


def main() -> int:
    preserve = os.environ.get("HLS_PRESERVE", "0") == "1"
    real_ai = os.environ.get("HLS_USE_REAL_AI", "0") == "1"
    formal = os.environ.get("HLS_FORMAL", "0") == "1"
    api_port = int(os.environ.get("HLS_API_PORT", "8000"))
    web_port = int(os.environ.get("HLS_WEB_PORT", "5173"))
    if real_ai:
        missing = _validate_real_ai_env()
        if missing:
            print(
                "HLS_USE_REAL_AI=1 requires the following in .env or the environment: "
                + ", ".join(missing),
                file=sys.stderr,
            )
            print(
                "DeepSeek official API supplies text only; configure an independent "
                "OpenAI-compatible image endpoint for keyframes.",
                file=sys.stderr,
            )
            return 2
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if not preserve:
        shutil.rmtree(DATA_DIR, ignore_errors=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    import fasteners
    import pgserver
    from pgserver.postgres_server import PostgresServer

    runtime_socket_root = Path(tempfile.gettempdir()) / "hls-dev-runtime"
    runtime_socket_root.mkdir(parents=True, exist_ok=True)
    PostgresServer.runtime_path = runtime_socket_root
    PostgresServer.lock_path = runtime_socket_root / ".lockfile"
    PostgresServer._lock = fasteners.InterProcessLock(PostgresServer.lock_path)

    if not (PGDATA / "PG_VERSION").exists():
        shutil.rmtree(PGDATA, ignore_errors=True)
        PGDATA.mkdir(parents=True, exist_ok=True)
    server = pgserver.get_server(PGDATA, cleanup_mode="stop")
    host = parse_qs(urlparse(server.get_uri()).query)["host"][0]
    db_url = create_database(host, preserve)

    ai_server = None
    env = os.environ.copy()
    env.update(
        {
            "ENVIRONMENT": "development",
            "DATABASE_URL": db_url,
            "ADMIN_PASSWORD": ADMIN_PASSWORD,
            "ANON_CODE_PEPPER": PEPPER,
            "DATA_DIR": str(DATA_DIR),
            "COOKIE_SECURE": "false",
            "PUBLIC_ORIGIN": f"http://127.0.0.1:{web_port}",
            "AUTO_BOOTSTRAP": "true",
            "AUTH_MODE": "email",
            "IMAGE_WORKER_ENABLED": "true",
            "PYTHONPYCACHEPREFIX": str(ROOT / ".pycache"),
        }
    )
    if not real_ai:
        ai_server, ai_base = start_ai_stub()
        env.update(
            {
                "TEXT_MODEL_BASE_URL": ai_base,
                "TEXT_MODEL_NAME": "local-test-text",
                "TEXT_MODEL_API_KEY": "local-test-key",
                "IMAGE_MODEL_BASE_URL": ai_base,
                "IMAGE_MODEL_NAME": "local-test-image",
                "IMAGE_MODEL_API_KEY": "local-test-key",
                "IMAGE_MODEL_TIMEOUT_SECONDS": "30",
                "TEXT_MODEL_TIMEOUT_SECONDS": "30",
            }
        )
    python = str(BACKEND / ".venv" / "bin" / "python")
    subprocess.run([python, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True)
    if formal:
        if not preserve:
            subprocess.run([python, "-m", "app.cli", "import-formal"], cwd=BACKEND, env=env, check=True)
    elif not preserve:
        subprocess.run([python, "-m", "app.cli", "seed-demo"], cwd=BACKEND, env=env, check=True)

    api = subprocess.Popen(
        [
            str(BACKEND / ".venv" / "bin" / "uvicorn"),
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
            "--no-access-log",
        ],
        cwd=BACKEND,
        env=env,
    )

    def shutdown(*_: Any) -> None:
        try:
            api.terminate()
            api.wait(timeout=10)
        except Exception:
            try:
                api.kill()
            except Exception:
                pass
        if ai_server is not None:
            ai_server.shutdown()
        try:
            server.cleanup()
        except Exception:
            pass
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    for _ in range(80):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{api_port}/api/health/live", timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.25)
    else:
        print("API did not start", file=sys.stderr)
        api.terminate()
        return 1
    print(f"RUNTIME_READY api=http://127.0.0.1:{api_port} web=http://127.0.0.1:{web_port}")
    print("STUDENT_LOGIN=PolyU email (internal tests: class 0)")
    print("CONTENT=" + ("FORMAL_V1" if formal else "DEMO"))
    print(f"ADMIN_PASSWORD={ADMIN_PASSWORD}")
    if real_ai:
        print("AI=REAL PROVIDERS FROM .env (text=DeepSeek-compatible, image=configured endpoint)", flush=True)
    else:
        print("AI=LOCAL TEST STUB (not a real provider)", flush=True)
    return api.wait()


if __name__ == "__main__":
    raise SystemExit(main())
