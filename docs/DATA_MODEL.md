# Data model

> **v1.5 notice (2026-11-06):** migration `0003_v15_products_peer_social` adds `work_revisions`, `peer_batches`, `peer_assignments`, `peer_ratings`, `social_views`, `social_likes`, `social_comments`, `social_events`, plus `runs.t1_condition/artifact_order` and round/image revision fields. See [V15_CHANGE_REPORT.md](V15_CHANGE_REPORT.md).

> **V2.1 notice (2026-11-08):** no migration. `instrument_versions.schema_json` carries `survey_version`; `peer_batches.scale_version` + `config_json.scale` freeze the peer-review definition; `peer_ratings.scores_json` stores either legacy `clarity/evidence_link/attraction` or new `cultural_clarity/cultural_translation/design_originality`. See [SURVEY_PEER_V21_PILOT.md](SURVEY_PEER_V21_PILOT.md).


All timestamps are UTC. Study identifiers are random UUIDs. Internal PolyU email, legacy
access codes, session tokens, password material and model API keys are not exported.

| Table | Purpose |
|---|---|
| `classes` | Four formal class records (1–4) plus class 0 in non-production internal deployments. |
| `participants` | Study UUID, class, block-assigned group, unique internal PolyU email, and legacy code HMAC/last 4 (nullable). |
| `sessions` | Opaque hashed student/admin sessions with expiry. |
| `artifact_versions` | Immutable evidence-pack versions by slot X/Y: title, era, type, image metadata, introduction, facts, evidence, uncertainty. |
| `instrument_versions` | Immutable versions of five assessment/questionnaire schemas (`pre_test`, `r1_test`, `post_test`, `transfer`, `questionnaire`). |
| `protocol_versions` | Frozen references to two artifact versions and five instrument versions; one active protocol. |
| `runs` | One study run per participant, frozen protocol, current stage and completion. |
| `stage_events` | Entry/exit timestamps and durations for every stage. |
| `rounds` | Round, artifact version, condition, start/deadline/finish, reason and latest script revision. |
| `script_revisions` | Every distinct title/body revision with source and time. |
| `messages` | Visible full dialogue, including HLSF prompt/hint provenance and idempotency key. |
| `hlsf_states` | Current B-only guide phase and hint state. |
| `hlsf_events` | Prompt delivery, advance, skip, hint and completion events. |
| `ai_calls` | Sanitized model request, response text, prompt version, status, latency and upstream error. |
| `image_jobs` | Prompt, source script revision, queue status, attempts, result file checksum/dimensions and errors. |
| `evidence_events` | Artifact section view events and optional dwell time. |
| `assessment_responses` | Frozen instrument version, draft/submitted raw answers, start/submit timing. |
| `api_errors` | Captured image/provider/application errors with run/participant association. |

## Study protocol freeze

Admin edits always create a new immutable artifact or instrument version. A run captures a
single active protocol, so later edits cannot change an in-progress participant's materials.
A new protocol can only be activated before any run exists. Readiness must pass and the
selected versions must be non-demo in production.

## Exports

`participants.csv`, `runs.csv`, `stage_events.csv`, `rounds.csv`, `messages.csv`,
`hlsf_events.csv`, `evidence_events.csv`, `script_revisions.csv`, `image_jobs.csv`,
`assessments.csv`, `assessment_answers.csv`, `ai_calls.csv`, `api_errors.csv`,
`protocol.json`, `manifest.json`, data dictionary, `files/{participant_uuid}/...`.

The export includes all script revisions in CSV and current scripts as `.txt`; keyframe images
are copied as originals. No scoring is applied. Missing media are recorded in the manifest
rather than silently omitted.
