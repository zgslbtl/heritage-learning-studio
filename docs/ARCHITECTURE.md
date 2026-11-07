# Architecture

> **v1.5 notice (2026-11-06):** the student stage machine is now K0 → tutorial → T1 → K1 → K2 → T2 → K3 → survey → peer assessment → social feed. See [V15_CHANGE_REPORT.md](V15_CHANGE_REPORT.md).


## Deployment shape

```
Browser
  │ HTTPS 80/443
  ▼
Caddy ─── static SPA (/srv/www) + reverse proxy /api/* ──► FastAPI (api:8000)
                                                             │
                                                             ├── PostgreSQL (db:5432)
                                                             └── /data volume
                                                                 evidence images
                                                                 keyframes
                                                                 legacy code CSV (email mode)
                                                                 generated exports
```

Only Caddy publishes ports. PostgreSQL and FastAPI are on an internal Compose network. Caddy
serves the built React SPA and the API under the same origin, so session cookies are
same-origin. No API key ever reaches the browser.

The MVP deliberately runs one API process. The persistent image worker and the small
in-memory login/code-attempt limiter therefore have a single authoritative view. The image
queue still claims rows with `FOR UPDATE SKIP LOCKED` so the persistence logic remains
correct if scaling is revisited.

## Backend modules

- `config.py` — server-only settings and data paths.
- `db.py` / `models.py` — async SQLAlchemy 2 models.
- `bootstrap.py` — formal classes 1–4 plus class 0 outside production; email mode creates
  no pre-generated codes. Group allocation happens on first email login in shuffled per-class
  blocks. Access codes are HMAC-SHA256 hashes at rest.
- `routers/auth.py` — PolyU-email login plus legacy code login, opaque student sessions,
  researcher password login/logout, rate limiting, origin protection.
- `routers/student.py` — state/resume, rounds, scripts, chat, HLSF, evidence events, image
  jobs, assessments.
- `routers/admin.py` — overview, participant detail (with internal email), content versioning,
  readiness, protocol activation, legacy cohort CSV endpoint, research export.
- `routers/files.py` — private evidence/keyframe responses with ownership checks.
- `services/run_state.py` — protocol snapshot, stage machine, deadline enforcement, round
  payloads.
- `services/ai_text.py` — OpenAI-compatible text client, full call/error audit, no automatic
  retries.
- `services/hlsf.py` + `prompts/hlsf.py` — B-only narrative scaffold, phase persistence,
  hints, and v1.1 phase/system guidance. `ai_text.py` derives the B story seed and injects the
  latest saved script for Create/Reflect; A context is unchanged.
- `services/image_queue.py` — durable queue, worker, provider call, file validation, retries.
- `services/assessments.py` / `instruments.py` — versioned schema renderer/validation.
- `services/export.py` — complete ZIP/CSV/media export.
- `services/readiness.py` — activation and student-readiness gates.

## Stage machine

```
pre_test
  → round1_ready → round1_active → r1_test
  → round2_ready → round2_active
  → post_test → transfer → questionnaire → complete
```

The server owns every transition. `round1_active` and `round2_active` carry a server-side
deadline. Any request that observes an expired round lazily finalizes it and moves the run to
the R1 test or post-test. Writes to a finished/expired round are rejected. Direct route
navigation cannot skip a stage.

The R1 test stage exposes no usable AI, chat, script, image or evidence mutation endpoints.
All assistance routes are limited to an active creation round.

## Client

A single stage-driven student application:

- unauthenticated → PolyU-email entry (legacy code path retained for internal tooling);
- active assessment → data-driven assessment page;
- round-ready → task brief and 14-minute start gate;
- active round → three-column workspace (evidence, AI chat + optional guide, creation);
- complete → closing page.

A separate `/admin` SPA handles researcher login, overview/detail, material version editors,
readiness and protocol activation. State is restored from the API at every load; local
storage is only an unsynced-crash backup and requires explicit restore.

## Request safety

- Server sessions are random opaque tokens; only SHA-256 hashes are stored.
- Cookies: HttpOnly, Secure in production, SameSite=Lax.
- Mutating requests with a browser `Origin` are checked against `PUBLIC_ORIGIN`.
- All student queries are scoped by participant session; media has explicit ownership checks.
- Errors are returned as explicit structured responses and recorded for AI/image operations.
