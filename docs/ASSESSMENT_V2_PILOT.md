# HLSF 测评 V2.0 Pilot：精简题本、统一作品说明与导出

日期：2026-11-07  
状态：已实现为 **assessment_v2.0_pilot**，默认新协议不自动激活；正式使用前仍需专家复核、认知访谈与 Pilot。  
关联文件：

- `backend/app/content/formal_v2/instruments.json`
- `backend/app/content/formal_v2/assessment_keys.json`
- `backend/app/content/formal_v2/rubric.json`
- `docs/ASSESSMENT_ITEM_BANK_V2_ZH.md`

## 1. 版本与协议

| 项目 | 值 |
|---|---|
| 设计版本 | `crossover-v1.1-assessment-v2-pilot` |
| 测评版本 | `assessment_v2.0_pilot` |
| 作品说明版本 | `rationale_v2.0` |
| HLSF 版本（V2 run） | `hlsf-v1.8-assessment-v2-pilot` |
| 计分版本 | `k-v2.0` |
| 旧版本 | `crossover-v1.0-pilot` / `formal_v1` 保留，不覆盖 |

新协议通过 `import-formal-v2` 创建。旧 run 的 `protocol_version_id` 不变，继续使用旧题本、旧作品表单和旧 HLSF 文本；新 run 使用 V2。

## 2. 题量与计分

| 阶段 | 题量 | 自动知识分 | 说明 |
|---|---|---|---|
| K0 | 3 基线 + 6 单选 | 0–6 | 无短答 |
| K1 | 6 单选 + 1 短答 | 0–6 | 短答 0–2 单列 |
| K2 | 6 单选 | 0–6 | 无短答 |
| K3 | 6 单选 + 1 短答 | 0–6 | 短答 0–2 单列 |
| Survey | 7 项 | — | 不计知识分 |

每名学生共 **36 个回答项**：24 道 MC、2 道短答、3 项基线、7 项问卷。  
每套卷 6 道 MC 按 F3/R3 覆盖事实/图像识别与关系理解；本版不再设 E（证据判断）题。短答只在 K1/K3（后测）出现。

**短答评分**：事实准确 1 分 + 关系解释 1 分 = 0–2；平台不自动评分，导出原文，研究者线下双评部分样本。不要把短答并入 MC 的 0–6，也不要把 V2 的 0–6 与 V1 的 0–8 直接相减。

## 3. 卷序与前后测

- K0/K2 使用 `test_form_order` 的第一个字母；K1/K3 使用第二个字母。
- AB 顺序：K0=A、K1=B、K2=A、K3=B；BA 反之。
- 同一学生的前测和后测使用不同卷；跨学生 AB/BA 在班级×组别内平衡。
- 每名学生 2 条短答：K1 使用 T1 后测卷的短答，K3 使用 T2 后测卷的短答；4 条短答文本都有机会被使用。

## 4. 统一三段作品说明

T1/T2、Standard AI/HLSF 均使用同一结构：

| 字段 | 学生端标题 | 建议 |
|---|---|---|
| `heritage_knowledge` | 你从文物中学到了什么？ | 30–45 字，具体史实 + 资料章节/来源 |
| `cultural_translation` | 你怎样把它用到设计里？ | 35–55 字，保留/改变纹样、功能、关系或故事 |
| `design_reason` | 为什么这样设计？ | 30–50 字，用途、目标人群、理由 |

保留产品名称、类别/用途、目标受众、1 张概念图；不强制 100–150 字总长，只做建议。旧 `structured_fields`（六字段）和 `open_statement` 保留，仅历史 run 使用。V2 的 HLSF Reflect 读取三段说明，不再引用“六字段/开放说明”。

## 5. 导入与激活

```bash
cd backend
.venv/bin/python -m app.cli import-formal-v2 --dry-run
.venv/bin/python -m app.cli import-formal-v2
.venv/bin/python -m app.cli import-formal-v2 --activate
```

- `--dry-run` 完整回滚。
- 不带 `--activate` 只创建 inactive 协议，旧 active 协议不变。
- 已有 run 时允许导入；旧 run 保留旧 protocol，新 run 使用新 active 协议。
- 若已有 active V2 协议，默认拒绝；确需新协议时加 `--force-new-version`。

## 6. 数据库迁移

`0013_assessment_v2`：

- `runs.design_version` 扩到 64；
- `work_revisions.rationale_fields` JSON，默认 `{}`；
- `protocol_versions.assessment_version` 64。

旧列不删除；`formal_v1` 内容文件不改。

## 7. 研究导出

新增/变更字段：

- `runs.csv`：`assessment_version`、`rationale_schema_version`。
- `analysis.csv`：`assessment_version`、`mc_max`、`knowledge_pretest_mc`、`knowledge_posttest_mc`、`posttest_short_score_0_2`、`rationale_schema_version`、`final_rationale_fields`。
- `assessments.csv`：`assessment_version`、`mc_max`、`short_answer_pending`。
- `work_revisions.csv`：`rationale_fields_json`、`rationale_schema_version`，并补上 `image_prompt`。
- `survey.csv`：S1–S7 + 每轮实际 `ai_condition` / 文物，不假设第一轮=A。
- `protocol.json`：`assessment_version`、`stage_rules`、短答 rubric。

## 8. 分析口径

- 主要确认性分析：T1 60 vs 60，K1 MC 0–6，控制 K0 MC 0–6、文物、卷序、班级。
- T2/交叉分析为探索性；控制学生、轮次、文物、序列，注意延续效应。
- 短答按文物分别分析 0–2，双评 20–30%，报告 ICC/κ；不与 MC 相加。
- 6 题/卷信度可能偏低；Pilot 报告 McDonald’s omega，主分析可用 item-level GLMM 或 Rasch/CFA 作敏感性分析。
- Survey S1–S6 为单题重复指标；S7 仅探索性。

## 9. 已知边界

- A/B 卷仍可能难度不一致；Pilot 必须检查 `form × time`、练习效应、`uncertain` 比例、地板/天花板。
- 6 题/卷不足以稳定建立三个独立分量表；F/R/E 只用于覆盖检查，知识总分是主要量尺。
- 新协议默认不激活；正式数据收集前需内容专家、认知访谈、Pilot 和伦理确认。

## 10. 验证记录

- 数据库迁移：本地 PostgreSQL 从 `0012_crossover_design` 升级到 `0013_assessment_v2` 通过；旧 5 条 v1.0 run 保留原 protocol，新 active protocol 为 `assessment_v2.0_pilot`。
- 内容导入：`import-formal-v2 --dry-run` 通过；正式导入 17 个 instrument、16 个 form 映射、104 条 item key。
- 流程测试：V2 学生流程 K0→T1→K1→K2→T2→K3→Survey 通过；K0=9、K1=7、K2=6、K3=7、Survey=7。
- 后端：52 passed。
- 前端：11 tests passed；`tsc --noEmit` 与 `vite build` 通过。
- 仍需人工完成：内容专家复核、4–8 名认知访谈、A/B 难度与练习效应 Pilot、短答双评与信度报告、伦理/同意与正式冻结。
