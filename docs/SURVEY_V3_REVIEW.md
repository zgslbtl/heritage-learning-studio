# HLSF 学生体验问卷 V3.0｜研究审核稿

## Material Passport

- Material: questionnaire software/content revision, `survey-v3.0-review`.
- Source: researcher-supplied Chinese items in the November 9, 2026 request.
- Status: engineering implementation; no psychometric validation or study findings.
- English: working translation for bilingual presentation; translation review remains necessary.

## Presentation and timing

All S1–S19 are required in the single `survey` stage, after the second design task and K3. The first nine items ask retrospectively about round 1; the next nine ask about round 2. A third page asks overall preference. There is no experience questionnaire between the two tasks. Both language versions, item headings, subgroup headings, endpoints and midpoint anchors are displayed together. Researcher notes, reverse-scoring flags and computed scores are excluded from the student payload.

The exact frozen Chinese and English wording is in `backend/app/content/formal_v2/instruments.json`, `survey`.

| Items | Construct | Raw response range | Researcher output |
|---|---|---|---|
| S1–S2 / S10–S11 | Exploration | 0–10 | Mean per round |
| S3–S4 / S12–S13 | Expressiveness | 0–10 | Mean per round |
| S5–S8 / S14–S17 | Perceived choice in design | 1–7 | Mean per round after reversal |
| S9 / S18 | Mental effort | 1–9 | Single raw response per round |
| S19 | Overall AI interaction preference | first / second / same / uncertain | Round preference plus actual round condition |

S7, S8, S16 and S17 are reverse-scored as `8 - raw`. Raw answers remain unchanged. The computed values live in researcher-only `score_json` and `v3_*` export columns. Each construct requires all of its own items to be valid; incomplete constructs remain blank. **No overall questionnaire total is calculated.** These descriptive calculation rules are not evidence that a construct or translation has been validated.

## Researcher notes — not displayed to students

- S1、S2、S10、S11：CSI Exploration，研究情境翻译与轻微改编。
- S3、S4、S12、S13：CSI Expressiveness，研究情境翻译与改编。
- S5–S8、S14–S17：参考 IMI Perceived Choice，将活动选择调整为设计过程中的选择，属于实质性情境改编。
- S9、S18：参考 Paas 单题心理努力测量。
- S19：研究者自编偏好题。
- S7、S8、S16、S17 必须反向计分。
- 所有构念分开报告，不加总为统一分数。
- 本稿不是已经验证的中文量表，需进行翻译复核、内容审查与实证检验。

The attributions above are supplied by the researcher and are not an independent source verification. The English wording is a working translation of the supplied Chinese text.

## Release and historical compatibility

Run `python -m app.cli release-survey-v3` inside the production API after deploying the code. It creates one new survey instrument and one active protocol reusing the previous artifacts, knowledge instruments, keys and assessment forms. It does not rewrite any historical run, instrument or response. The command is idempotent. New runs use V3; an existing run remains on its frozen questionnaire version. A fresh `import-formal-v2` also uses V3 content.

`survey.csv` includes raw S1–S19 and explicit instrument/content versions. Historical V2.1 columns retain their old meanings and remain blank for V3. V3 preference uses `s19_preferred_*`; historical `s7_preferred_*` fields remain blank for V3. Four `v3_s*_reversed` columns expose the reversal, with separate `v3_exploration_mean_rN`, `v3_expressiveness_mean_rN`, `v3_perceived_choice_mean_rN`, and `v3_mental_effort_rN` columns. No S7 historical preference is reinterpreted as a reverse-scored choice item.

For operational rollback, reactivate the previous protocol for future runs in a transaction after deactivating the current protocol. Preserve any runs created under V3 and their referenced versions. Database backups remain on the server; participant records and credentials must never be committed.
