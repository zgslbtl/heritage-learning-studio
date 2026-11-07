#!/usr/bin/env python3
"""Read-only cloud snapshot comparison across a production redeployment.

Requires a saved, private Playwright admin storage state. Does not call models,
create users, or modify research content. Signed URLs/cookies are not recorded.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import httpx

p = argparse.ArgumentParser()
p.add_argument("phase", choices=["before", "after"])
p.add_argument("--auth-state", default=".tools/browser-auth-state.json")
p.add_argument("--acceptance", default="test-artifacts/vercel-beta/acceptance.json")
p.add_argument("--output", default="test-artifacts/vercel-beta/persistence.json")
args = p.parse_args()
acceptance = json.loads(Path(args.acceptance).read_text())
base = acceptance["base_url"]
auth = json.loads(Path(args.auth_state).read_text())
cookies = {row["name"]: row["value"] for row in auth["cookies"] if urlsplit(base).hostname in row["domain"].lstrip(".")}

def get(path, *, headers=None, expected=200, authenticated=True):
    for attempt in range(3):
        try:
            with httpx.Client(base_url=base, cookies=cookies if authenticated else {}, follow_redirects=True,
                              timeout=httpx.Timeout(120, connect=25)) as client:
                response = client.get(path, headers=headers)
            break
        except (httpx.ConnectError, httpx.ConnectTimeout):
            if attempt == 2: raise
    assert response.status_code == expected, (path.split("?")[0], response.status_code)
    return response

def fingerprint(path):
    r = get(path, headers={"Range": "bytes=0-1023"}, expected=206)
    return {"bytes": int(r.headers["content-range"].split("/")[-1]),
            "prefix_sha256": hashlib.sha256(r.content).hexdigest(), "etag": r.headers.get("etag")}

def overview():
    data = get("/api/admin/overview").json()
    assert data["readiness"]["ready_for_students"]
    return {"protocol": data["protocol"], "participants": [
        {k: row[k] for k in ("participant_id", "class_id", "run_id", "stage", "group")}
        for row in data["participants"]]}

def public():
    for path in ("/", "/join", "/admin"):
        assert "text/html" in get(path, authenticated=False).headers["content-type"]
    config = get("/api/auth/config", authenticated=False).json()
    assert config["deployment_mode"] == "beta" and [row["id"] for row in config["classes"]] == [0]
    token = parse_qs(urlsplit(acceptance["entry_url"]).query)["token"][0]
    link = get("/api/auth/class-link?token=" + token, authenticated=False).json()
    assert link["class_id"] == 0
    health = get("/api/health/ready", authenticated=False).json()
    assert health["database"] and health["storage"]
    get(acceptance["images"][0]["url"], authenticated=False, expected=401)
    return {"deep_links": True, "class_link": True, "unauthorized_image_denied": True,
            "database": health["database"], "private_storage": health["storage"]}

with ThreadPoolExecutor(max_workers=3) as pool:
    pending = {"database": pool.submit(overview), "public": pool.submit(public)}
    for item in acceptance["images"]:
        pending["image:" + item["job_id"]] = pool.submit(fingerprint, item["url"])
    export_path = "/api/admin/export-tasks/" + acceptance["export_task_id"] + "/download"
    pending["export"] = pool.submit(fingerprint, export_path)
    snapshot = {key: task.result() for key, task in pending.items()}
out = Path(args.output)
report = json.loads(out.read_text()) if out.exists() else {}
report[args.phase] = snapshot
report[args.phase + "_utc"] = datetime.now(timezone.utc).isoformat()
if args.phase == "after":
    assert report["before"] == snapshot, "Persistent state changed across deployment"
    report["status"] = "passed"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(args.phase, "passed", "participants", len(snapshot["database"]["participants"]), "images", len(acceptance["images"]))
