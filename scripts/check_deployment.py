#!/usr/bin/env python3
"""Static deployment checks. This does NOT replace running Docker or Caddy."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failures = []
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    services = compose.get("services", {})
    for required in ("db", "api", "caddy"):
        if required not in services:
            failures.append(f"missing service {required}")
    if services.get("db", {}).get("ports"):
        failures.append("database publishes host ports")
    if services.get("api", {}).get("ports"):
        failures.append("API publishes host ports")
    caddy_ports = set(services.get("caddy", {}).get("ports", []))
    if caddy_ports != {"80:80", "443:443", "443:443/udp"}:
        failures.append(f"unexpected Caddy ports: {sorted(caddy_ports)}")
    if "app_data:/data" not in services.get("api", {}).get("volumes", []):
        failures.append("API app data is not on a persistent volume")
    caddyfile = (ROOT / "Caddyfile").read_text()
    for required in ("reverse_proxy api:8000", "try_files {path} /index.html", "Strict-Transport-Security"):
        if required not in caddyfile:
            failures.append(f"Caddyfile missing: {required}")
    env = (ROOT / ".env.example").read_text()
    for required in (
        "ADMIN_PASSWORD",
        "ANON_CODE_PEPPER",
        "DATABASE_URL",
        "TEXT_MODEL_API_KEY",
        "IMAGE_MODEL_API_KEY",
        "COOKIE_SECURE",
        "PUBLIC_ORIGIN",
    ):
        if required not in env:
            failures.append(f".env.example missing: {required}")
    for path in ("backend/Dockerfile", "Dockerfile.caddy", "Caddyfile", "scripts/backup.sh", "scripts/restore.sh"):
        if not (ROOT / path).exists():
            failures.append(f"missing file: {path}")
    if failures:
        print("STATIC DEPLOYMENT CHECK: FAIL")
        for failure in failures:
            print(" -", failure)
        return 1
    print("STATIC DEPLOYMENT CHECK: PASS")
    print("Only Caddy publishes host ports; database/API are internal; persistent app data is mounted.")
    print("Docker image build, Caddy certificate issuance, and public HTTPS were NOT tested by this script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
