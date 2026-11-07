# Test report

> **v1.5 update (2026-11-06):** the platform now has T1/T2 + K0–K3, product-design work, B-only HLSF v1.5, peer assessment and a simulated work feed. Current test results and the changed files are recorded in [V15_CHANGE_REPORT.md](V15_CHANGE_REPORT.md). The table below remains the v1.0 baseline.

Date: 2026-11-05 (Asia/Shanghai)
Environment: macOS arm64, Python 3.9.6, Node 24.14.0, Chrome 156, ephemeral PostgreSQL 16.2
via `pgserver`. Docker daemon, Caddy binary and public DNS were unavailable.

## Result summary

| Area | Result |
|---|---|
| Backend pytest (real PostgreSQL) | **23 passed** |
| 30 concurrent participant flow | **passed**, including 30 chat + image jobs and worker concurrency check |
| Text AI failure + retry | **passed** |
| Image failure + retry | **passed** |
| Timer expiry / late-write rejection | **passed** |
| Student data isolation | **passed** |
| Admin auth/content versioning/export | **passed** |
| Alembic initial + email migration | **passed** (schema upgraded to 0002 on the live local DB) |
| Frontend TypeScript | **passed** |
| Frontend production build | **passed** |
| Frontend Vitest | **5 passed** |
| Playwright browser end-to-end | **1 mobile entry pass after email-auth; full flow/HLSF not rerun** |
| Static deployment checks | **passed** (only Caddy publishes 80/443; DB/API internal) |
| Shell syntax | **passed** |
| Docker build/Compose start | **NOT RUN — Docker unavailable** |
| Caddy syntax/TLS/public HTTPS | **NOT TESTED — Caddy/Docker/domain unavailable** |
| HLSF v1.1.1 prompt/context/phase tests | **passed with labelled test stub** |
| Real-model HLSF narrative scenarios (7 required) | **7/7 behaviour checks passed on demo content; formal-content retest pending** |
| Real DeepSeek text provider | **PASS** — HTTP 200, `deepseek-flash`, 2.8 s smoke |
| Real Volcengine Ark image provider | **PASS** — 2,496×1,664 provider smoke and 2,816×1,584 app-queue keyframe |
| Formal research content/consent/rubrics | **NOT INCLUDED by design** |

## Commands

```bash
cd backend
PYTHONPYCACHEPREFIX=../.pycache .venv/bin/pytest -q
# 23 passed

cd frontend
npm run typecheck
npm run build
npm test
# typecheck/build passed; 5 tests passed

cd frontend
npx playwright test e2e/mobile.spec.ts --config=playwright.config.ts
# 1 passed after the email-auth change. The desktop full-flow/HLSF specs were not rerun.

PYTHONPYCACHEPREFIX=.pycache backend/.venv/bin/python scripts/check_deployment.py
# STATIC DEPLOYMENT CHECK: PASS

bash -n scripts/backup.sh
bash -n scripts/restore.sh
```

## Backend coverage

`backend/tests/` exercises:

- email login gate/resume/class mismatch, per-class shuffled block allocation, class 0
  internal handling; legacy code mode remains covered for fixtures;
- all G1–G4 round mappings;
- full B→A student journey: pre-test, round 1 HLSF, chat, image, script, R1 independent test
  with AI locked, round 2 A, post-test, transfer, questionnaire, completion;
- full A-side HLSF rejection and B-only initial guide;
- HLSF hint-once, phase advance, skip, completion and persisted events;
- HLSF student-message/assistant-reply audit in admin detail;
- HLSF v1.1.1 narrative templates, concrete Create-mode examples, phase coaching, derived
  story-seed continuity, current-script injection for Create/Reflect, missing-script handling,
  and prompt-version logging;
- DeepSeek-compatible optional `thinking` payload forwarding, including the disabled-mode
  configuration used by the local template;
- Volcengine Ark image request fields: `size` preset, `response_format`, and `watermark`;
- PolyU-email gate, same-email resume, class mismatch rejection, per-class shuffled block
  allocation, and stable allocation order;
- A context regression: no narrative coaching, story seed, current script or HLSF markers;
- concurrent assessment GETs (including development StrictMode/retry races) returning the
  same draft without a unique-constraint failure;
- legacy code HMAC at rest and CSV path (internal code mode); email mode disables the CSV
  download;
- wrong legacy code/class generic errors, cross-student keyframe denial, admin denial;
- server deadline finalization and late-write 409;
- text-provider failure recorded in `ai_calls` + `api_errors` and retry success;
- image-provider failure with reason and retry success;
- 30 concurrent participants, each with chat/script/image/finish; image provider observed
  inflight concurrency never exceeding the configured limit;
- legacy admin code CSV behavior, artifact version creation, instrument version creation, schema validation,
  overview/detail, protocol lock after first run, cross-origin mutation rejection;
- ZIP research export contents: participants/runs/messages/scripts/images/assessments/
  protocol/manifest; no access code or API key appears.

The AI endpoints in these tests are a local **HTTP test stub** served on localhost and reached
through the real client/queue code. The stub labels its replies. These tests validate
transport, error handling, queue persistence, data recording and isolation—not model quality,
model availability, or provider policy.

## Browser test

The Playwright suite runs against a local-only runtime that uses ephemeral PostgreSQL and the
explicitly labelled test AI stub, then drives installed Chrome:

- reads an unused B-first participant from the researcher API;
- enters via the internal legacy code path for group-controlled E2E, completes pre-test;
- confirms no condition/group text in the student UI;
- starts round 1, receives the fixed HLSF Observe prompt, chats, writes a script;
- a dedicated HLSF test advances through Observe → Explain → Create → Reflect, checks the
  new narrative prompts and hint, saves a script, completes the guide and verifies phase,
  prompt and script persistence after reload;
- waits for autosave, reloads the page, verifies script and chat resume;
- generates a keyframe, finishes round 1;
- verifies the AI-disabled R1 banner, submits the R1 assessment;
- starts round 2 A, verifies there is no learning guide, chats, writes/generates, finishes;
- completes post-test, transfer task and questionnaire;
- confirms the completion page;
- logs into the researcher console, sees the participant table, opens materials and readiness,
  and confirms a ZIP export response.

Screenshots:

- `../e2e/screenshots/workbench-resumed.png` — resumed B workbench with HLSF guide.
- `../e2e/screenshots/participant-complete.png` — completed student flow.
- `../e2e/screenshots/admin-overview.png` — researcher overview (snapshot before email auth).
- `../e2e/screenshots/mobile-entry.png` — narrow-viewport entry page.

## Migration

The initial Alembic revision was run against a fresh PostgreSQL database. It created:
`ai_calls, alembic_version, api_errors, artifact_versions, assessment_responses, classes,
evidence_events, hlsf_events, hlsf_states, image_jobs, instrument_versions, messages,
participants, protocol_versions, rounds, runs, script_revisions, sessions, stage_events`.

## Real-model HLSF acceptance status

Real DeepSeek text and Volcengine Ark/Doubao image calls were executed on 2026-11-04. The
seven HLSF scenarios were driven through the running app against **demo placeholder content**.
See [HLSF_LIVE_TEST.md](HLSF_LIVE_TEST.md) and its
[raw transcript](assets/hlsf-live-eval-2026-11-04.txt).

| Required live scenario | Status |
|---|---|
| 1. Appearance-only input → story hook/core question | PASS |
| 2. Explain → evidence-linked continuity | PASS with content caveat — demo evidence is insufficient; no fabrication, formal Evidence Pack retest required |
| 3. Create → complete story rather than fact list | PASS |
| 4. Reflect → concrete script-based revision | PASS |
| 5. Student refuses preset modes → free approach | PASS |
| 6. A → no new proactive educational prompts | PASS |
| 7. Refresh → phase, story thread, logs intact | PASS |

This validates API connectivity, HLSF prompt behavior and factual restraint. It does **not**
validate the eventual reviewed museum content, learning outcomes or scoring. Retest scenario 2
and content quality after installing the two approved Evidence Packs.

## Known defects/fixes during verification

- Missing Python `greenlet` for async SQLAlchemy was found and added.
- Python 3.9-compatible `python-dotenv` pin was required.
- A shared-IP login limit initially blocked the 30-client test; it was raised to 200 per
  10 minutes (still far below the code space) while admin login remains at 6 per 10 minutes.
- HLSF prompt-response audit and text-provider `api_errors` were added after a coverage
  review.
- Autosave now preserves edits made while a prior save is in flight.
- Concurrent instrument GETs could race assessment draft creation and return HTTP 500;
  creation is now serialized per run and covered by a regression test.
- HLSF v1.1 replaced the knowledge-oriented phase prompts with narrative coaching and added a
  B-only narrative system context. v1.1.1 adds concrete examples for the three optional Create
  modes. Backend tests verify story-seed continuity, current-script review, A-context parity
  and versioned logging; a live DeepSeek check verified the new Create copy and an explanatory
  model response.
- Production startup fails closed on insecure cookies/non-HTTPS public origin.
- Backup/restore scripts passed shell syntax only; they were not executed because Docker is
  unavailable.

## Environment limitations — not claimed as passed

1. **Docker Compose runtime and image builds** — no Docker daemon in this environment.
2. **Caddy config/TLS/public HTTPS** — Docker/Caddy binary and a public domain were absent.
   The Caddyfile was statically checked only.
3. **Real models** — no API keys/endpoints. No claim of model correctness, availability,
   cost, content safety, or provider throughput is made.
4. **Real 30-user load through Caddy and the actual provider** — local PostgreSQL/API load
   used a labelled test stub. Provider-side rate limiting remains untested.
5. **Backup/restore drill** — scripts exist and are syntax-checked, not runtime-tested.
6. **Formal research validity** — consent, ethics, reviewed evidence packs, scoring rubrics,
   retention/deletion and data-transfer review remain external blockers.
