#!/usr/bin/env python3
"""Securely update provider keys in .env without echoing them.

Usage:
  backend/.venv/bin/python scripts/set_provider_keys.py --text
  backend/.venv/bin/python scripts/set_provider_keys.py --image
  backend/.venv/bin/python scripts/set_provider_keys.py --text --image

The hidden input is written to the project .env and never printed.
"""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def set_key(lines: list[str], key: str, value: str) -> list[str]:
    found = False
    result = []
    for line in lines:
        if line.startswith(key + "="):
            result.append(f"{key}={value}")
            found = True
        else:
            result.append(line)
    if not found:
        result.append(f"{key}={value}")
    return result


def prompt_key(label: str) -> str:
    value = getpass.getpass(f"Paste {label} (hidden): ").strip()
    if not value:
        raise SystemExit(f"{label} is empty; nothing changed.")
    if len(value) < 12:
        raise SystemExit(f"{label} looks too short; nothing changed.")
    return value


def atomic_write(path: Path, text: str) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.chmod(temp, 0o600)
    temp.replace(path)
    os.chmod(path, 0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description="Securely update service API keys in .env")
    parser.add_argument("--text", action="store_true", help="set TEXT_MODEL_API_KEY")
    parser.add_argument("--image", action="store_true", help="set IMAGE_MODEL_API_KEY")
    args = parser.parse_args()
    if not args.text and not args.image:
        args.text = True

    if not ENV_PATH.exists():
        raise SystemExit("Missing .env. Copy .env.example to .env first.")
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    if args.text:
        lines = set_key(lines, "TEXT_MODEL_API_KEY", prompt_key("DeepSeek API key"))
    if args.image:
        lines = set_key(lines, "IMAGE_MODEL_API_KEY", prompt_key("Volcengine Ark image API key"))
    atomic_write(ENV_PATH, "\n".join(lines) + "\n")
    print("Updated .env securely (key not printed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
