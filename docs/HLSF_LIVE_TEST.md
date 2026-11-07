# HLSF v1.1 live-model evaluation

Date: 2026-11-04 (Asia/Shanghai)

## Configuration

- Text: DeepSeek OpenAI-compatible API, `deepseek-flash`, thinking disabled.
- Image: Volcengine Ark / Doubao Seedream 5.0 pro
  (`doubao-seedream-5-0-pro-260628`), 2K, URL response, watermark off.
- Test content: local demo placeholder artifact/instruments. This is **not** the approved
  research Evidence Pack, so the evidence-specific quality of scenario 2 still needs a retest
  with final content.
- Raw transcript: [hlsf-live-eval-2026-11-04.txt](assets/hlsf-live-eval-2026-11-04.txt)

## Provider smoke tests

- **Text:** HTTP 200, `deepseek-flash`, latency 2,805 ms. A short prompt returned a concise
  narrative-coaching suggestion.
- **Image:** HTTP 200, 2,496×1,664 PNG, 371,513 bytes, 58.4 s. The generated test image is
  [seedream-live-smoke.png](../e2e/screenshots/seedream-live-smoke.png).
  This validates the image provider and URL download; it is not an artifact-grounded research
  keyframe because demo content was used.
- **App queue keyframe:** a real provider image job was submitted through the student API,
  persisted, processed by the worker, and retrieved through the authenticated file route.
  Result: 2,816×1,584 PNG, saved as
  [app-keyframe-live.png](../e2e/screenshots/app-keyframe-live.png).

## Seven scenarios

| # | Scenario | Result |
|---|---|---|
| 1 | Appearance-only observation → story hook | **PASS** — responded to the quiet visual detail and asked one story-opening question. |
| 2 | Explain links the student's question to available evidence | **PASS with content caveat** — retained the “寻找还是守护” thread, explicitly reported that the demo evidence was insufficient, and did not fabricate facts. A substantive evidence-link test must be repeated with reviewed Evidence Packs. |
| 3 | Create supports a complete story rather than a fact list | **PASS** — on explicit request produced a coherent 1-minute scene-by-scene script and repeatedly labelled the historical letter/person as fictional. |
| 4 | Reflect reviews the actual saved script | **PASS** — quoted the student's specific “白鹤象征高洁……” sentence, identified one highest-value change, and explained why. |
| 5 | Student rejects the three preset modes | **PASS** — accepted the student's “假设的明代家书” approach, labelled it fictional and continued the same story thread. |
| 6 | A remains free-form with no proactive HLSF | **PASS** — A had no guide, no initial HLSF prompt and no HLSF events; AI prompt version remained `chat-v1`. |
| 7 | Refresh/restore keeps phase and story thread | **PASS** — re-fetch returned `reflect` phase, 16 messages, the retained story question and saved script title. |

Additional observations:

- B used `chat-v1+hlsf-v1.1`; A used `chat-v1`.
- This transcript predates the small `hlsf-v1.1.1` copy revision that adds concrete examples to
  the three optional Create modes. The new version is covered by prompt/template tests and a
  targeted live Create-prompt check in [TEST_REPORT.md](TEST_REPORT.md).
- B HLSF events contained `prompt_delivered`, `student_message`, `assistant_reply` and phase
  advancement for all four phases.
- Coaching responses were generally 2–3 sentences; the explicitly requested full script was
  longer, as intended.
- The demo content limitation caused the model to avoid inventing museum facts. This is the
  desired factual constraint, but it means story-quality testing must be repeated after the
  two approved Evidence Packs are configured.

## v1.1.1 Create-mode examples

A targeted live check was run after adding concrete examples to the three optional modes. The
app served the new `hlsf-v1.1.1` Create prompt, and when the student asked for a simpler
explanation, DeepSeek provided one concrete example for each mode. Raw check:
[hlsf-v1.1.1-create-check-2026-11-04.txt](assets/hlsf-v1.1.1-create-check-2026-11-04.txt).

## Status

Text and image provider connectivity are confirmed with real API calls. HLSF v1.1 behavior is
confirmed against demo content, and the v1.1.1 Create examples were verified with a live model.
Formal content/educational-quality validation remains pending until approved artifact evidence
and assessments are installed.
