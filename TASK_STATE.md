# Heritage Learning Studio — TASK_STATE

> **2026-11-08 京东云变更合并：** 合并私有OSS存储、认证图片缓存/原图下载，以及study中的班级0共存；beta仍仅开放0。保留当前HLSF、问卷和两轮互评。范围与验证见[合并记录](docs/SERVER_SYNC_20261108.md)。以下较早状态按其日期解释。
>
> **2026-11-08 V2.1 update:** 四组/文物/AI 条件与 T1/T2 流程不变；体验问卷内容版本 `survey-v2.1-pilot`（三组配对指标 + S7 偏好），同伴互评内容版本 `peer-review-v2.1-pilot`（P1–P3），T1/T2 两轮作品均进入互评（正式班每人 6+6=12 件）。测评框架仍为 `assessment_v2.0_pilot`，不需要数据库迁移。详见 [docs/SURVEY_PEER_V21_PILOT.md](docs/SURVEY_PEER_V21_PILOT.md)。
>
> **2026-11-07 V2.0 update:** K0=3 baseline+6 MC, K1/K3=6 MC+1 post-only short answer, K2=6 MC, survey=7; all conditions and both rounds use the same three-part work rationale; legacy six-field/open records remain readable. New runs use `crossover-v1.1-assessment-v2-pilot` / `assessment_v2.0_pilot`; old `crossover-v1.0-pilot` / v1.5 runs keep their protocol. See [docs/ASSESSMENT_V2_PILOT.md](docs/ASSESSMENT_V2_PILOT.md) and [docs/ASSESSMENT_ITEM_BANK_V2_ZH.md](docs/ASSESSMENT_ITEM_BANK_V2_ZH.md).
>
> **2026-11-06 v1.5 update:** T1/T2, K0–K3 + survey, product-design workbench with six fields, HLSF v1.5 (T1-B only), blind peer assessment, simulated Instagram-style work feed, per-class entry links and a dynamic class peer gate are implemented. The gate opens automatically when every user who entered the class has ended T2; no manual open button. See [docs/V15_CHANGE_REPORT.md](docs/V15_CHANGE_REPORT.md) and [docs/CLASS_LINKS_AND_PEER_GATE.md](docs/CLASS_LINKS_AND_PEER_GATE.md). The historical state below describes the earlier v1.0 two-round short-video build.

Updated: 2026-11-05 (Asia/Shanghai)

## Current state

End-to-end MVP implemented. Backend, student UI, researcher console, real DeepSeek/Volcengine
providers, export, deployment assets, automated backend/frontend tests and live browser checks
have been exercised locally. Docker/Compose and public HTTPS remain unverified. The student
entry now uses a PolyU-email gate and per-class shuffled four-group blocks; existing test data
was moved to class 0.

## Done

- Project scaffolding, configuration, `TASK_STATE`, `README`, architecture/data-model/protocol/
  security/readiness documentation.
- Async FastAPI + SQLAlchemy + PostgreSQL schema and initial Alembic migration.
- PolyU-email student login: plaintext unique email, same-email resume, class mismatch guard,
  and a deliberately simple `polyu` substring gate for internal testing.
- Per-class shuffled four-group blocks (G1–G4 once per four new users), serialized allocation,
  30-participant formal capacity; legacy HMAC access-code records retained.
- Existing test data migrated to class 0; classes 1–4 reserved for formal data. Class 0 is
  hidden from the production frontend build and rejected by the production backend.
- Alembic `0002_email_login` migration; admin displays internal email; research export excludes
  email; code CSV download disabled in email mode.
- Opaque student/admin sessions, cookies, login limits, origin checks, role/ownership guards.
- Full stage machine with server deadlines, lazy expiry, R1 AI lockout, resume semantics.
- A/B assignment, B-only HLSF Observe→Explain→Create→Reflect narrative guidance
  (`hlsf-v1.1.1`): story entry point, evidence-linked thread, complete-story organisation,
  script-based reflection, one hint per phase, skip, server state/event audit, prompt-response
  linking, derived story-seed continuity and latest-script context for Create/Reflect.
  A remains free-form with no added narrative/HLSF context.
- OpenAI-compatible text adapter with full call/error recording and explicit failures.
- Persistent PostgreSQL image queue, two-slot worker concurrency, retries, restart recovery,
  one-success keyframe rule, private file delivery.
- Autosaved versioned scripts, material view events, data-driven pre/R1/post/transfer/
  questionnaire instruments, draft autosave and validation.
- React student application (entry/pre-test, workbench, assessments, completion) including
  timer, refresh recovery, local draft recovery, admin console with content editors,
  readiness/activation and research detail.
- Versioned content/protocol freeze, readiness gate, demo-content marking.
- Complete ZIP/CSV/media export, legacy protected code CSV (internal only), backup/restore scripts.
- Docker Compose/Caddy configuration with only 80/443 published and internal database/API.
- Local runtime (PostgreSQL via pgserver + explicitly labelled test AI stub) and Playwright
  browser test.

## Verification so far

- Backend pytest: 23 passed against real ephemeral PostgreSQL; adds PolyU-email gate,
  same-email resume, class mismatch, per-class block allocation and allocation reproducibility
  to the prior 20-test suite.
- Frontend TypeScript/build and Vitest: passing (5 tests + production build).
- Playwright: the mobile entry test passed after the email-auth change. The desktop full-flow
  and HLSF specs were updated but not rerun after the auth migration. A live system-Chrome
  check verified the email entry, class-0 selection, pre-test page and production build hiding
  class 0.
- Alembic initial and `0002_email_login` migrations executed successfully against PostgreSQL;
  the live local schema is at head.
- Compose YAML parses; only Caddy publishes ports. Shell scripts pass `bash -n`.
- Caddy binary/Docker runtime validation could not be completed (Docker absent; Caddy binary
  download timed out). This is recorded as externally pending.

## DeepSeek / real-provider integration

- DeepSeek official text configuration is documented and supported through the existing
  OpenAI-compatible adapter; optional `TEXT_MODEL_THINKING` is forwarded as DeepSeek's
  `thinking` field.
- The local runtime can use real providers from `.env` with `HLS_USE_REAL_AI=1`; default
  automated/browser runs remain on the labelled stub.
- A direct `scripts/live_ai_smoke.py` text/image provider check and `docs/DEEPSEEK_SETUP.md`
  were added. Payload tests cover DeepSeek thinking-mode forwarding and Volcengine Ark image
  fields (`2K`, `response_format`, `watermark`).
- `.env` contains the non-secret DeepSeek/Volcengine endpoints, the real provider keys, and
  `AUTH_MODE=email`.
- Real DeepSeek text and Volcengine Ark/Doubao image calls were successfully executed locally
  on 2026-11-04. A real image job also completed through the app queue (2,816×1,584 PNG) and
  was served through the authenticated file endpoint. The seven HLSF scenarios passed on demo
  content; scenario 2 still needs a formal Evidence Pack retest. Official DeepSeek API has no
  text-to-image endpoint, so keyframes use the separate Volcengine image service.

## Pending external verification / blockers

- Docker image build and Compose startup.
- Caddy automatic HTTPS and public-domain checks.
- Formal-content model-quality validation. Live DeepSeek/Volcengine API calls and demo-content
  HLSF scenarios have passed; the approved Evidence Pack retest is still pending.
- 30-participant load against real provider rate limits; local concurrency uses test stub.
- Formal email-mode load and duplicate-account monitoring; class 0 currently contains internal
  test data only.
- Approved evidence packs and instruments, scoring rubrics, ethics/consent, retention/deletion,
  provider data-processing review, backup restore drill, security review.
- Public deployment acceptance is NOT claimed.

## Notes

- Demo content is neutral and marked; production readiness rejects it.
- No silent mock-success path exists in application code. The browser/load tests use an
  explicitly labelled local HTTP stub and do not validate model quality.
