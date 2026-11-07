#!/usr/bin/env python3
"""Optional real-provider smoke test. This spends provider quota.

Usage:
  backend/.venv/bin/python scripts/live_ai_smoke.py --text
  backend/.venv/bin/python scripts/live_ai_smoke.py --image
  backend/.venv/bin/python scripts/live_ai_smoke.py --text --image

Reads server-side model settings from the environment/.env. Never prints API keys.
The image test writes a file under .local-runtime/live-ai-smoke/.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image  # noqa: E402

from app.config import Settings  # noqa: E402
from app.errors import AppError  # noqa: E402
from app.services.ai_text import _call_provider  # noqa: E402
from app.services.image_queue import _call_image_provider  # noqa: E402

OUTPUT = ROOT / ".local-runtime" / "live-ai-smoke"


async def check_text(settings: Settings) -> bool:
    if not settings.text_configured:
        print("TEXT: NOT CONFIGURED (missing base URL/model/key)")
        return False
    messages = [
        {
            "role": "system",
            "content": "You are a concise cultural-heritage learning coach. Reply in one sentence.",
        },
        {
            "role": "user",
            "content": "用一句话说明：如果学生只描述了文物外观，你会怎样引导他发现一个故事问题？",
        },
    ]
    started = time.perf_counter()
    try:
        text, _raw, status = await _call_provider(settings, messages)
    except AppError as exc:
        print(f"TEXT: FAILED HTTP={exc.status_code} code={exc.code}: {exc.message}")
        return False
    elapsed = int((time.perf_counter() - started) * 1000)
    print(f"TEXT: OK status={status} model={settings.text_model_name} latency_ms={elapsed}")
    print("TEXT_SAMPLE:", text[:500])
    return True


async def check_image(settings: Settings) -> bool:
    if not settings.image_configured:
        print("IMAGE: NOT CONFIGURED (missing base URL/model/key)")
        return False
    prompt = (
        "A museum-education keyframe illustration of a white crane above a lotus pond, "
        "ink-and-wash inspired, elegant, no text, no watermark."
    )
    started = time.perf_counter()
    try:
        image_bytes, _raw, status = await _call_image_provider(settings, prompt)
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.verify()
        with Image.open(io.BytesIO(image_bytes)) as image:
            width, height = image.size
            OUTPUT.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            path = OUTPUT / f"image-smoke-{stamp}.png"
            image.convert("RGB").save(path, format="PNG")
    except AppError as exc:
        print(f"IMAGE: FAILED HTTP={exc.status_code} code={exc.code}: {exc.message}")
        return False
    except Exception as exc:
        print(f"IMAGE: FAILED invalid response ({type(exc).__name__}).")
        return False
    elapsed = int((time.perf_counter() - started) * 1000)
    print(
        f"IMAGE: OK status={status} model={settings.image_model_name} "
        f"size={width}x{height} bytes={len(image_bytes)} latency_ms={elapsed}"
    )
    print("IMAGE_FILE:", path)
    return True


async def main_async(args: argparse.Namespace) -> int:
    settings = Settings()
    if not args.text and not args.image:
        args.text = True
    print("LIVE PROVIDER SMOKE TEST — this makes real API requests and may incur cost.")
    print(f"TEXT model: {settings.text_model_name or 'not configured'}")
    print(f"IMAGE model: {settings.image_model_name or 'not configured'}")
    ok = True
    if args.text:
        ok = await check_text(settings) and ok
    if args.image:
        ok = await check_image(settings) and ok
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Test configured real AI providers")
    parser.add_argument("--text", action="store_true", help="make a small text completion request")
    parser.add_argument("--image", action="store_true", help="make an image generation request (costs quota)")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
