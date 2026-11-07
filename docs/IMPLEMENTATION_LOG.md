# Implementation log

## 2026-11-04

### Foundation

- Inspected empty workspace/toolchain: Node 24, npm 11, Python 3.9, Chrome; no Docker/Caddy.
- Created root configuration, dependency manifests, env template, ignore rules and docs.
- Implemented async SQLAlchemy models for the full research data model.
- Added initial Alembic migration and verified it against a real ephemeral PostgreSQL database
  (18 application tables + `alembic_version`).

### Backend vertical slice

- Added 120-code bootstrap with balanced per-class G1–G4 allocation and HMAC storage.
- Added student/admin auth, opaque sessions, security headers, origin checks and access limits.
- Added stage machine, protocol freeze, round timers and lazy expiry.
- Added text AI adapter with explicit errors/no automatic paid retry.
- Added fixed B-only HLSF phases/hints/skip and event logging including student/assistant
  response linkage.
- Added image queue with PostgreSQL persistence, concurrency, restart failure handling and
  private keyframe delivery.
- Added scripts/revisions, evidence events, assessments/drafts/submission and complete export.
- Added versioned evidence packs/instruments, admin readiness and protocol activation.

### Local verification and failures fixed

- Python 3.9 resolved dependency issue: pinned `python-dotenv`; added `greenlet`.
- Fixed incorrect relative imports in services.
- Replaced seed demo's temporary image source and verified image validation.
- 30-user test initially hit a 12-per-IP login limit because all simulated clients shared one
  IP. Raised the code-attempt ceiling to 200/10 min, which supports a 120-seat classroom NAT
  while remaining far below the 40-bit code search space. Admin login remains 6/10 min.
- Added HLSF message/reply events and text-AI `api_errors` recording after reviewing research
  data coverage.
- Production configuration now fails closed if cookies are insecure or public origin is not
  HTTPS.
- Disabled pgserver teardown logging noise in tests.
- Fixed a race exposed by React development StrictMode and real retries: concurrent
  instrument GETs could both miss a draft assessment row and violate
  `uq_assessment_run_kind`. Assessment draft creation now takes a `FOR UPDATE` lock on the
  run; concurrent GETs return 200 and share the same draft. Added a regression test.

### HLSF narrative guidance v1.1

- Replaced the four fixed HLSF prompts and hints with narrative-oriented versions:
  story entry point, evidence-linked knowledge thread, complete story organisation, and
  script-based reflection.
- Added B-only narrative-coach and phase-coaching system instructions. Normal coaching is
  constrained to 1–3 sentences/one question, while direct student requests for script writing
  or revision remain supported.
- Added request-time story-seed context derived from the earliest student message and injected
  the latest saved script during Create/Reflect. No database field or migration was added.
- Confirmed A still receives only the unchanged base/evidence context and no HLSF or narrative
  scaffold.
- Added backend tests for prompts/version, B context, current-script review, missing script,
  A parity, event/AI-call versioning and refresh persistence; added a Playwright phase-flow
  and reload test.

### DeepSeek / real-provider configuration

- Confirmed the official DeepSeek API is OpenAI-compatible for text (`https://api.deepseek.com`,
  `deepseek-flash`) but does not publish a text-to-image generation endpoint.
- Added optional DeepSeek thinking-mode configuration (`TEXT_MODEL_THINKING=disabled` by
  default for the template); the application forwards it as `{"thinking":{"type":...}}`.
- Updated `.env.example` for DeepSeek text and a separately configured OpenAI-compatible
  third-party image endpoint for Janus-style services.
- Added `HLS_USE_REAL_AI=1` to the local runtime so `.env` providers can be used instead of the
  labelled stub, plus `scripts/live_ai_smoke.py` and `docs/DEEPSEEK_SETUP.md`.
- No real credentials or image endpoint are present. Real text/image calls and the seven
  live HLSF narrative scenarios remain unverified; no stub results are presented as live.
- Added a backend payload regression test for the DeepSeek thinking switch.
- Accommodated the supplied Volcengine Ark/Doubao Seedream image API: configurable
  `response_format`/`watermark`, 2K size support, URL download path, and removal of the
  nonportable `n` request field. `.env` now contains the non-secret Ark base/model settings.
- Added a backend payload regression test for the image fields.
- Real provider verification completed on 2026-11-04:
  - DeepSeek text: HTTP 200 with `deepseek-flash`, thinking disabled.
  - Volcengine Ark image: HTTP 200 with Doubao Seedream 5.0 pro; 2,496×1,664 PNG, URL download.
  - Seven HLSF scenarios run through the app on demo content; all behavioural checks passed,
    with scenario 2 marked for retest against approved Evidence Packs because demo evidence has
    no substantive facts.
- Added `scripts/live_hlsf_eval.py`, `docs/HLSF_LIVE_TEST.md` and the raw live transcript.
- Fixed story-seed extraction to prefer the first question asked during Observe.
- Replaced an over-broad image-key update with verified distinct provider credentials, then
  submitted a real keyframe through the app image queue. The worker produced a 2,816×1,584 PNG
  and the authenticated file route returned it successfully.
- HLSF v1.1.1 adds concrete examples for Historical Detective, Microhistorical Scenario and
  Process Reconstruction in the students' Create prompt and reinforces the explanation
  instruction in B's internal coaching context. No other phase/state/UI behavior changed.
- Replaced student access-code entry with a PolyU-email gate (`polyu` substring, plaintext
  unique email, resume, class mismatch guard). Email is shown only in the authenticated admin
  console and excluded from research export.
- Added `0002_email_login` (nullable code fields, email unique/index) and per-class shuffled
  four-group block allocation. Existing test participants were moved to class 0; classes 1–4
  are reserved for formal data. Class 0 is dev-only and rejected in production.
- Added `AUTH_MODE=email`, email-bootstrap behavior (no pre-generated cohort in email mode),
  readiness checks, admin search/display and email-mode code-CSV disablement.

### Tests run

- `backend/.venv/bin/pytest -q`: 23 passed (real ephemeral PostgreSQL, including email login and allocation tests).
- `npm run typecheck`: passed.
- `npm run build`: passed.
- `npm test`: 5 passed.
- Playwright full flow, HLSF narrative phases and mobile narrow-viewport test: 3 passed before the email-auth change; the mobile entry test passed again after it.
- `bash -n` on backup/restore scripts: passed.
- Compose YAML parsed; only Caddy publishes ports.

### Not yet verified

- Docker image build and Compose startup (Docker absent).
- Caddy syntax/TLS/public accessibility (Caddy binary download timed out; Docker absent).
- Real model API credentials and model quality.
- Formal research approvals/content/consent.
