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

---

## 2026-11-08 — HLSF v1.10：先问后总结 + 阶段停留提示

- 新 run 使用 `hlsf-v1.10-evidence-reading-pilot`：教练先就文物背景提一个简短问题，学生回答后用 2–3 句总结（确认 + 补充关键事实 + 章节号）；学生说"不知道"或要求直接讲时跳过提问直接总结。左侧资料是核对入口，不是前置作业。
- 新 run 的 B 条件系统提示追加「学生阅读状态」（来自 `evidence_events`：已打开章节、停留时长、未打开章节），只用于决定提问还是直接总结，并禁止催读。
- 前端：AI 回复中的 `M03` / `T02` 渲染为可点击 chip，点击后 `ArtifactReader` 展开并滚动到对应章节，记录 `section_open`（meta `from: chat_ref`）与 `section_ref_click`。
- 前端：同一阶段内学生发送 ≥3 条消息仍未推进时，弹出一次 `PhaseNudgeDialog`（提示 / 下一阶段 / 继续对话）；关闭状态按参与者+轮次+阶段存入 localStorage；事件通过 `POST /api/student/rounds/{n}/hlsf/nudge` 写入 `hlsf_events`（`nudge_shown` / `nudge_dismissed` / `nudge_hint` / `nudge_advance`）。
- v1.9/v1.8/v1.7 run 通过 `runs.hlsf_prompt_version` 保持原提示、原上下文，不显示 chip 与弹窗。
- 无数据库迁移；`evidence_events.csv` / `hlsf_events.csv` 已覆盖新事件类型。

### Tests run

- `backend/.venv/bin/pytest -q`: 75 passed, 4 skipped.
- `npm test`: 26 passed.
- `npm run typecheck`: passed.
- `npm run build`: passed.

---

## 2026-11-08 — K0 人口学题 + 双语策略定案

- `formal_v2/instruments.json` 的 `baseline` 增加 B-04（年龄段，6 档含"不愿透露"）与 B-05（性别，含"非二元／其他"和"不愿透露"），`content_version` 升为 `v2.2-demographics`。两题均为单选、必答、不参与知识分。
- 语言策略：不引入语言切换，固定"中文主 + 英文副"；补齐学生端控件/状态类文案的英文（资料面板"点击展开"、输入框快捷键、图片生成状态、必填标记、匿名数据说明、准备页/教程页卡片、互评与作品广场的空状态、完成页提示）。叙事长文与测评内容保持中文原文。
- 新题只对新建 run 生效；已有 run 绑定的协议与题本不变（`runs.protocol_version_id`）。
- 上库方式：`python -m app.cli import-formal-v2 --dry-run` → `--force-new-version --activate`（本地 / Beta 各自执行）。

### Tests run

- `backend/.venv/bin/pytest -q`: 77 passed, 4 skipped.
- `npm test`: 26 passed.
- `npm run typecheck`: passed.
- `npm run build`: passed.

---

## 2026-11-08 — 内容英文化（理解辅助）

- 文物资料：新增 `backend/app/content/formal_v2/artifacts_en.json`（M/T 各 10 节 + 标题与简介），`services/artifacts.student_artifact` 在读取时合并 `title_en` / `introduction_en` / 每节 `title_en`、`body_en`。英文不进入 `artifact_versions`，因此不需要重新导入文物、不产生新的文物版本。
- 测评题：`schemas.Option.label_en`、`Question.prompt_en`、`InstrumentPayload.title_en/instructions_en`；`instruments.json` 与 `formal_content.KIND_*_EN` 写入英文；`services/instruments.instrument_payload` 透出这些字段。中文题干、选项值、题序与计分不变。
- 前端：`ArtifactReader` 在每段中文下显示英文段（左侧细线、小号灰字），章节与文物标题显示英文；`AssessmentPage` 显示英文说明、题干与选项；新增 `.section-en`、`.prompt-en`、`.option-en`、`.section-title-en`、`.artifact-title-en` 样式。
- `content_version` 升为 `v2.3-bilingual`，需重新 `import-formal-v2 --force-new-version --activate` 让新 run 拿到英文题干。

### Tests run

- `backend/.venv/bin/pytest -q`: 78 passed, 4 skipped.
- `npm test`: 26 passed.
- `npm run typecheck`: passed.
- `npm run build`: passed.

---

## 2026-11-08 — 明细提示全面双语

- 创作面板：生成配额徽章、图片提示说明、概念图占位、产品名称/类别/受众占位与示例、设计概念与作品说明占位、三段说明与六字段的 hint/placeholder、选图按钮、提交同意说明、本地草稿提示全部补齐英文。
- 测评页：未答完提示、其他专业输入占位。
- 准备页/教程页：任务说明、时长与字段卡片、匿名与数据说明、开始前提示。
- 互评页：三段时间说明标签、六字段标签、状态徽章（已提交/待评价）、评语占位、闸门与盲评说明。
- 作品广场：标题、说明、点赞/评论按钮与状态、评论占位、点赞说明。
- 样式：`field-hint`、`prompt-help-note`、`keyframe-placeholder` 内的 `.en` 改为块级，避免中英挤在同一行。
