#!/usr/bin/env python3
"""Drive the seven required HLSF scenarios against a real configured model API.

This is a local evaluation helper, not a production endpoint. It uses the running app,
real provider configuration, demo research content, and writes no API keys.

Usage:
  backend/.venv/bin/python scripts/live_hlsf_eval.py
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("HLS_BASE_URL", "http://127.0.0.1:8000")
ADMIN_PASSWORD = os.environ.get("HLS_ADMIN_PASSWORD", "local-dev-admin-password-123")
CODES = ROOT / ".local-runtime" / "data" / "private" / "access_codes.csv"


def post(client: httpx.Client, path: str, payload: Any | None = None) -> Any:
    response = client.post(BASE + path, json=payload if payload is not None else {})
    if response.status_code >= 400:
        raise RuntimeError(f"POST {path} -> {response.status_code}: {response.text[:600]}")
    return response.json()


def get(client: httpx.Client, path: str) -> Any:
    response = client.get(BASE + path)
    if response.status_code >= 400:
        raise RuntimeError(f"GET {path} -> {response.status_code}: {response.text[:600]}")
    return response.json()


def assistant_text(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "assistant" and message.get("source") == "assistant":
            return str(message.get("content", ""))
    return "(no assistant reply)"


def chat(client: httpx.Client, round_no: int, text: str) -> str:
    data = post(
        client,
        f"/api/student/rounds/{round_no}/messages",
        {"content": text, "client_message_id": str(uuid4())},
    )
    return assistant_text(data.get("messages", []))


def advance(client: httpx.Client, round_no: int, phase: str) -> Dict[str, Any]:
    return post(
        client,
        f"/api/student/rounds/{round_no}/hlsf/advance",
        {"from_phase": phase, "skip": False},
    )


def read_codes() -> List[Dict[str, str]]:
    with CODES.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def demo_answers(instrument_payload: Dict[str, Any]) -> Dict[str, Any]:
    answers: Dict[str, Any] = {}
    for question in instrument_payload["instrument"]["questions"]:
        qid = question["id"]
        qtype = question["type"]
        if qtype in ("single_choice", "multi_choice"):
            value = question["options"][0]["value"]
            answers[qid] = [value] if qtype == "multi_choice" else value
        elif qtype == "short_text":
            answers[qid] = "占位回答 / placeholder answer"
        elif qtype == "evidence_judgment":
            answers[qid] = {row["id"]: "yes" for row in question["rows"]}
        elif qtype == "likert":
            answers[qid] = question.get("scale_min", 1)
    return answers


def login_student(code: str, class_id: str) -> httpx.Client:
    client = httpx.Client(base_url=BASE, timeout=120.0)
    response = client.post(
        "/api/auth/enter", json={"code": code, "class_id": int(class_id)}
    )
    if response.status_code != 200:
        raise RuntimeError(f"student login failed: {response.status_code} {response.text[:500]}")
    instrument = client.get("/api/student/instruments/pre_test")
    if instrument.status_code != 200:
        raise RuntimeError(f"instrument load failed: {instrument.status_code} {instrument.text[:500]}")
    pre = client.post(
        "/api/student/instruments/pre_test/submit",
        json={"answers": demo_answers(instrument.json())},
    )
    if pre.status_code != 200:
        raise RuntimeError(f"pre-test failed: {pre.status_code} {pre.text[:500]}")
    return client


def valid_text(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def main() -> int:
    admin = httpx.Client(base_url=BASE, timeout=60.0)
    login = admin.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    if login.status_code != 200:
        raise RuntimeError(f"admin login failed: {login.status_code} {login.text[:300]}")
    overview = admin.get("/api/admin/overview").json()
    codes = {row["participant_id"]: row for row in read_codes()}
    unused = [p for p in overview["participants"] if p["stage"] == "not_started"]
    b_person = next((p for p in unused if p["group"] in {"G3", "G4"}), None)
    a_person = next((p for p in unused if p["group"] in {"G1", "G2"}), None)
    if not b_person or not a_person:
        raise RuntimeError("Need at least one unused B-first and one unused A-first participant")
    b_row = codes[b_person["participant_id"]]
    a_row = codes[a_person["participant_id"]]

    b = login_student(b_row["access_code"], b_row["class_id"])
    started = post(b, "/api/student/rounds/1/start")
    initial = get(b, "/api/student/rounds/1/messages")
    print("=" * 90)
    print("HLSF LIVE EVALUATION — demo artifact content; real configured model")
    print("B participant:", b_person["participant_id"], "group:", b_person["group"])
    print("guide version:", initial["guide"]["version"])
    print("fixed Observe prompt:", valid_text(initial["messages"][0]["content"]))
    print("=" * 90)

    print("\n[SCENARIO 1] Appearance-only observation -> story hook")
    r1 = chat(
        b,
        1,
        "我看到了白色的鹤、莲花、深蓝色的云纹和水波，画面很安静。",
    )
    print(valid_text(r1))

    print("\n[SCENARIO 2] Student forms a story question")
    r2 = chat(
        b,
        1,
        "我想问：这只鹤为什么总是和莲花一起出现？它是在寻找什么，还是在守护什么？",
    )
    print(valid_text(r2))

    advance(b, 1, "observe")
    explain_prompt = get(b, "/api/student/rounds/1/messages")
    print("\nExplain fixed prompt:", valid_text(explain_prompt["messages"][-1]["content"]))
    print("\n[SCENARIO 2] Explain connects the student's question to evidence")
    r3 = chat(
        b,
        1,
        "我最初的故事问题是：鹤为什么和莲花一起出现？请结合左侧资料，帮我想观众应该先知道什么、后知道什么。",
    )
    print(valid_text(r3))

    advance(b, 1, "explain")
    create_prompt = get(b, "/api/student/rounds/1/messages")
    print("\nCreate fixed prompt:", valid_text(create_prompt["messages"][-1]["content"]))
    print("\n[SCENARIO 5] Student rejects the three preset narrative modes")
    r4 = chat(
        b,
        1,
        "我不想用历史侦探、微观历史或过程重建。我想用一封假设的明代家书来讲述，可以吗？先帮我确定故事重点。",
    )
    print(valid_text(r4))
    print("\n[SCENARIO 3] Explicit request: help produce a coherent one-minute script")
    r5 = chat(
        b,
        1,
        "请直接帮我用这封假设的明代家书写一个约 1 分钟的视频脚本，不要只列举文物信息。",
    )
    print(valid_text(r5))

    script_title = "白鹤与莲花的家书"
    script_body = (
        "【开场】一封没有寄出的家书落在案上。\n"
        "【发展】写信的人望向屏风上的白鹤与莲花，想起离乡前的清晨。\n"
        "【揭示】白鹤象征高洁，莲花象征清净，也寄托着对仕途顺利的期望。\n"
        "【结尾】今天再看这件纹样，我们看到的不只是装饰，也是明代人对品格与理想的想象。"
    )
    saved = b.put(
        "/api/student/rounds/1/script",
        json={"title": script_title, "body": script_body},
    )
    if saved.status_code != 200:
        raise RuntimeError(f"script save failed: {saved.status_code} {saved.text[:400]}")
    advance(b, 1, "create")
    reflect_prompt = get(b, "/api/student/rounds/1/messages")
    print("\nReflect fixed prompt:", valid_text(reflect_prompt["messages"][-1]["content"]))
    print("\n[SCENARIO 4] Reflect references the actual saved script and one revision")
    r6 = chat(
        b,
        1,
        "请只根据我右侧保存的脚本，指出一个最值得修改的地方，并说明为什么。",
    )
    print(valid_text(r6))

    print("\n[SCENARIO 7] Persistence after re-fetching state/messages")
    refreshed_messages = get(b, "/api/student/rounds/1/messages")
    refreshed_state = get(b, "/api/student/state")
    print("guide phase:", refreshed_messages["guide"]["phase"])
    print("message count:", len(refreshed_messages["messages"]))
    print("story question retained:", "鹤为什么和莲花一起出现" in json.dumps(refreshed_messages, ensure_ascii=False))
    print("script title retained:", get(b, "/api/student/rounds/1")["script"]["title"])
    print("server stage:", refreshed_state["stage"])

    print("\n" + "=" * 90)
    print("[SCENARIO 6] A condition remains free-form")
    a = login_student(a_row["access_code"], a_row["class_id"])
    a_started = post(a, "/api/student/rounds/1/start")
    a_messages = get(a, "/api/student/rounds/1/messages")
    print("A guide:", a_messages["guide"])
    print("A initial messages:", len(a_messages["messages"]))
    a_reply = chat(
        a,
        1,
        "我想写一个关于这件文物的故事，请给我一个有趣的开头。",
    )
    print(valid_text(a_reply))

    print("\n" + "=" * 90)
    print("PROMPT AUDIT")
    for label, person in (("B", b_person), ("A", a_person)):
        detail = get(admin, f"/api/admin/participants/{person['participant_id']}")
        versions = sorted({call["prompt_version"] for call in detail["ai_calls"]})
        print(label, "AI prompt versions:", versions)
        print(label, "HLSF events:", [(event["phase"], event["action"]) for event in detail["hlsf_events"]])

    print("\nDONE. Review the transcripts above against the seven acceptance scenarios.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("LIVE EVAL FAILED:", exc, file=sys.stderr)
        raise SystemExit(1)
