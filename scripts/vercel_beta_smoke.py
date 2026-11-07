#!/usr/bin/env python3
"""Opt-in real-cloud acceptance. Creates clearly labelled Class 0 QA records.

Requires ADMIN_PASSWORD in the environment. Uses real configured AI providers;
run only against the dedicated beta deployment. No credentials enter the report.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="https://heritage-learning-beta.vercel.app")
parser.add_argument("--report", default="test-artifacts/vercel-beta/acceptance.json")
parser.add_argument("--retry-failed-images", action="store_true", help="Explicitly start one new attempt for an already failed image stage")
args = parser.parse_args()
base = args.base_url.rstrip("/")
output = Path(args.report)
output.parent.mkdir(parents=True, exist_ok=True)
report = json.loads(output.read_text()) if output.exists() else {
    "base_url": base, "started_utc": datetime.now(timezone.utc).isoformat(),
    "purpose": "DEPLOYMENT QA — synthetic inputs, not research findings", "checks": {},
    "alias_prefix": "deployment-qa-polyu-" + uuid.uuid4().hex[:10], "images": [],
}


def save():
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2))


def record(name, value=True):
    report["checks"][name] = value
    save()
    print(name, value, flush=True)


def client():
    return httpx.Client(base_url=base, timeout=httpx.Timeout(180, connect=25), headers={"Origin": base}, follow_redirects=True)


def request(c, method, path, *, status=200, **kwargs):
    for attempt in range(3):
        try:
            r = c.request(method, path, **kwargs)
            break
        except (httpx.ConnectError, httpx.ConnectTimeout):
            # No HTTP request has been transmitted; do not retry read timeouts.
            if attempt == 2: raise
            print("QA transport reconnect", method, path, flush=True)
    if r.status_code != status:
        raise RuntimeError(f"{method} {path} returned {r.status_code}: {r.text[:700]}")
    return r.json() if "json" in r.headers.get("content-type", "") else r


class RemoteZip(io.RawIOBase):
    """Inspect a large private ZIP using authenticated byte ranges."""
    def __init__(self, c, path):
        self.client, self.path, self.position = c, path, 0
        response = request(c, "GET", path, status=206, headers={"Range": "bytes=0-0"})
        if response.status_code != 206: raise RuntimeError("Private export did not support range downloads")
        self.size = int(response.headers["content-range"].split("/")[-1])

    def seekable(self): return True
    def tell(self): return self.position
    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        return self.position
    def read(self, size=-1):
        end = self.size - 1 if size < 0 else min(self.size - 1, self.position + size - 1)
        if end < self.position: return b""
        response = request(self.client, "GET", self.path, status=206, headers={"Range": f"bytes={self.position}-{end}"})
        if response.status_code != 206: raise RuntimeError("Private export range failed")
        self.position += len(response.content)
        return response.content


def assessment(c, kind):
    data = request(c, "GET", f"/api/student/instruments/{kind}")
    answers = {}
    for q in data["instrument"]["questions"]:
        kind_ = q["type"]
        if kind_ == "single_choice": answers[q["id"]] = q["options"][0]["value"]
        elif kind_ == "multi_choice": answers[q["id"]] = [q["options"][0]["value"]]
        elif kind_ == "short_text": answers[q["id"]] = "DEPLOYMENT QA: synthetic answer, not research data."
        elif kind_ == "likert": answers[q["id"]] = (q.get("scale_min", 1) + q.get("scale_max", 5)) // 2
        elif kind_ == "evidence_judgment": answers[q["id"]] = {row["id"]: "yes" for row in q["rows"]}
        else: raise RuntimeError("Unknown question type " + kind_)
    request(c, "PUT", f"/api/student/instruments/{kind}/draft", json={"answers": answers})
    restored = request(c, "GET", f"/api/student/instruments/{kind}")
    assert restored["answers"] == answers
    request(c, "POST", f"/api/student/instruments/{kind}/submit", json={"answers": answers})
    return len(answers)


def image(c, round_no, data):
    jobs = data["image_jobs"]
    job = jobs[-1] if jobs else request(c, "POST", f"/api/student/rounds/{round_no}/image-jobs", json={})["job"]
    if job["status"] == "failed" and args.retry_failed_images:
        previous_id = job["id"]
        job = request(c, "POST", f"/api/student/rounds/{round_no}/image-jobs", json={"retry_of": previous_id})["job"]
        record(f"manual_image_retry_round_{round_no}", {"retry_of": previous_id, "job_id": job["id"]})
    deadline = time.monotonic() + 360
    previous = None
    while job["status"] in ("queued", "running"):
        if job["status"] != previous:
            print("image", round_no, job["id"], job["status"], flush=True); previous = job["status"]
        if time.monotonic() > deadline: raise RuntimeError("Cloud image task did not finish within six minutes: " + job["id"])
        time.sleep(4)
        job = request(c, "GET", "/api/student/image-jobs/" + job["id"])["job"]
    if job["status"] != "succeeded":
        raise RuntimeError(f"Image task {job['id']}: {job.get('error_code')}: {job.get('error_message')}")
    request(c, "POST", f"/api/student/rounds/{round_no}/image-jobs/{job['id']}/select")
    media = c.get(job["image_url"], headers={"Range": "bytes=0-1023"})
    assert media.status_code == 206 and media.content.startswith(b"\x89PNG")
    size = int(media.headers["content-range"].split("/")[-1])
    item = {"job_id": job["id"], "round_no": round_no, "url": job["image_url"],
            "bytes": size, "prefix_sha256": hashlib.sha256(media.content).hexdigest(),
            "etag": media.headers.get("etag"), "width": job["width"], "height": job["height"]}
    report["images"] = [row for row in report["images"] if row["job_id"] != job["id"]] + [item]
    record(f"real_image_round_{round_no}", {"status": job["status"], "bytes": item["bytes"]})


def progress(c, label, *, real_ai=False):
    while True:
        state = request(c, "GET", "/api/student/state")
        stage = state["stage"]
        print(label, stage, flush=True)
        if stage in ("k0", "k1", "k2", "k3", "survey"):
            record(label + "_" + stage + "_items", assessment(c, stage))
        elif stage == "tutorial": request(c, "POST", "/api/student/tutorial/complete")
        elif stage in ("t1_ready", "t2_ready"):
            no = 1 if stage.startswith("t1") else 2
            started = request(c, "POST", f"/api/student/rounds/{no}/start")
            assert abs(started["round"]["remaining_seconds"] - (1440 if no == 1 else 1200)) < 20
            record(label + f"_round_{no}_duration", 1440 if no == 1 else 1200)
        elif stage in ("t1_active", "t2_active"):
            no = 1 if stage.startswith("t1") else 2
            data = request(c, "GET", f"/api/student/rounds/{no}")
            artifact_image = c.get(data["artifact"]["image_url"], headers={"Range": "bytes=0-1023"})
            assert artifact_image.status_code == 206 and artifact_image.content
            work = {"product_name": f"DEPLOYMENT QA {label} T{no}", "product_category": "帆布袋",
                    "target_audience": "内测验收", "design_concept": "DEPLOYMENT QA: 将可见的对称构图转化为帆布袋图案。",
                    "rationale_fields": {"heritage_knowledge": "DEPLOYMENT QA: 以资料中可见纹样和构图为依据。",
                        "cultural_translation": "DEPLOYMENT QA: 将对称关系转译为现代帆布袋图案。",
                        "design_reason": "DEPLOYMENT QA: 这是功能验收中的设计推测，不是研究结论。"},
                    "image_prompt": "DEPLOYMENT QA: 一只浅色帆布袋，使用文物参考中的对称纹样作克制的现代图案设计，产品摄影。"}
            request(c, "PUT", f"/api/student/rounds/{no}/work", json=work)
            if real_ai:
                messages = request(c, "GET", f"/api/student/rounds/{no}/messages")["messages"]
                if not any(m["role"] == "user" for m in messages):
                    reply = request(c, "POST", f"/api/student/rounds/{no}/messages", json={
                        "client_message_id": str(uuid.uuid4()),
                        "content": "DEPLOYMENT QA: 请用一句话说明如何把文物的对称构图转化成帆布袋图案，并区分史实与设计推测。"})
                    assert any(m["role"] == "assistant" and m["content"] for m in reply["messages"])
                    record(f"real_text_round_{no}")
                image(c, no, request(c, "GET", f"/api/student/rounds/{no}"))
            request(c, "POST", f"/api/student/rounds/{no}/finish", json={"consent_future_research": False})
        elif stage == "peer_assessment":
            peer = request(c, "GET", "/api/student/peer-assessment")
            assert peer["waiting"] is False
            assert peer["total"] <= 6
            for assignment in peer["assignments"]:
                if assignment.get("image_url"):
                    media = c.get(assignment["image_url"], headers={"Range": "bytes=0-1023"})
                    assert media.status_code == 206 and media.content.startswith(b"\x89PNG")
                    record("peer_authorized_image")
                request(c, "POST", f"/api/student/peer-assessment/{assignment['assignment_id']}", json={
                    "scores": {"clarity": 3, "evidence_link": 3, "attraction": 3}, "comment": "DEPLOYMENT QA"})
            record(label + "_peer_count", peer["total"])
            request(c, "POST", "/api/student/peer-assessment/complete")
        elif stage == "social_feed":
            feed = request(c, "GET", "/api/student/social-feed")
            for item in feed["works"]:
                if not item["is_own"]:
                    request(c, "POST", f"/api/student/social/works/{item['work_id']}/like")
                    request(c, "POST", f"/api/student/social/works/{item['work_id']}/comment", json={"content": "DEPLOYMENT QA"})
                    break
            request(c, "POST", "/api/student/social/complete")
        elif stage == "complete":
            record(label + "_completed", state["participant"]["id"])
            return state
        else: raise RuntimeError("Unexpected stage " + stage)


try:
    with client() as admin:
        config = request(admin, "GET", "/api/auth/config")
        assert [item["id"] for item in config["classes"]] == [0]
        assert config["login_rule"] == "contains_polyu"
        record("only_class_zero")
        request(admin, "POST", "/api/auth/enter", status=403, json={"email": "qa@example.com", "class_id": 0})
        request(admin, "POST", "/api/auth/enter", status=401, json={"email": "qa-polyu", "class_id": 1})
        record("server_class_and_polyu_checks")
        request(admin, "POST", "/api/admin/login", json={"password": os.environ["ADMIN_PASSWORD"]})
        assert request(admin, "GET", "/api/admin/readiness")["ready_for_students"]
        if "entry_url" not in report:
            link = request(admin, "POST", "/api/admin/class-links", json={"class_id": 0, "label": "班级0 · 内部测试"})
            report["entry_url"] = link["url"]; save()
        for label in ("A", "B"):
            with client() as student:
                alias = report["alias_prefix"] + "-" + label.lower()
                entered = request(student, "POST", "/api/auth/enter", json={"email": "  " + alias.upper() + "  ", "class_id": 0})
                assert entered["state"]["participant"]["class_id"] == 0
                state = progress(student, label, real_ai=label == "A")
                request(student, "POST", "/api/auth/logout")
                resumed = request(student, "POST", "/api/auth/enter", json={"email": alias, "class_id": 0})["state"]
                assert resumed["run_id"] == state["run_id"] and resumed["stage"] == "complete"
                record(label + "_logout_resume")
        task = {"id": report["export_task_id"]} if report.get("export_task_id") else request(admin, "POST", "/api/admin/export-tasks", json={})
        report["export_task_id"] = task["id"]; save()
        for attempt in range(90):
            data = request(admin, "GET", "/api/admin/export-tasks/" + task["id"])
            if data["status"] == "failed": raise RuntimeError("Export failed: " + str(data.get("error_code")))
            if data["status"] == "succeeded": break
            time.sleep(3)
        else: raise RuntimeError("Cloud export did not finish")
        download = RemoteZip(admin, data["download_url"])
        with zipfile.ZipFile(download) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["deployment_mode"] == "beta"
            assert manifest["internal_testing"] is True
            assert not manifest["missing_files"], manifest["missing_files"]
            assert b"polyu" not in archive.read("participants.csv").lower()
        record("private_export", {"bytes": download.size, "participants": manifest["participants"], "missing_files": [], "verified": "range downloads, ZIP directory, manifest and participant CSV"})
    report["status"] = "passed"
    report.pop("failure", None)
    report["completed_utc"] = datetime.now(timezone.utc).isoformat(); save()
except Exception as exc:
    report["status"] = "incomplete"
    report["failure"] = str(exc); save()
    raise
