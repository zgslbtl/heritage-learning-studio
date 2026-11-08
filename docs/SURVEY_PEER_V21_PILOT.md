# 体验问卷与同伴互评 V2.1 Pilot：内容、数据与边界

> 版本说明（2026-11-09）：本文保留 V2.1 历史记录；当前体验问卷已更新为 V3.0，见 [SURVEY_V3_REVIEW.md](SURVEY_V3_REVIEW.md)。同伴互评部分仍适用。

日期：2026-11-08  
状态：已实现为两个内容版本 `survey-v2.1-pilot` 与 `peer-review-v2.1-pilot`；测评框架仍为 `assessment_v2.0_pilot`，四组交叉设计不变。  
关联实现：`backend/app/content/formal_v2/instruments.json`、`backend/app/services/peer_scales.py`、`backend/app/services/peer.py`、`backend/app/services/export.py`、`frontend/src/pages/PeerAssessmentPage.tsx`。

> 本文是两个 V2.1 内容版本的权威说明。旧 `ASSESSMENT_V2_PILOT.md`、`ASSESSMENT_ITEM_BANK_ZH.md`、`PROTOCOL_V15_FINAL.md` 记录的是历史版本，不按 V2.1 重写。

## 1. 版本与范围

| 项目 | 值 |
|---|---|
| 设计版本 | `crossover-v1.1-assessment-v2-pilot`（不变） |
| 测评版本 | `assessment_v2.0_pilot`（题本/计分框架不变） |
| 协议内容版本 | `v2.1-survey-peer-pilot` |
| 体验问卷内容版本 | `survey-v2.1-pilot` |
| 同伴互评内容版本 | `peer-review-v2.1-pilot` |
| 同伴互评算法 | `peer-v3-two-rounds` |
| 旧问卷/旧互评 | 保留旧 `InstrumentVersion` 与旧 `PeerBatch`，不覆盖 |

本次只改体验问卷与同伴互评；**不修改** K0–K3、T1/T2 流程、HLSF 四阶段、`DESIGN_COACH_B`、`PHASE_PROMPTS`、`PHASE_HINTS`、Standard AI Prompt、四组分配、两件文物、三段作品说明、图片生成、模拟 Instagram、专家 D1–D4 量规。

## 2. 体验问卷 V2.1

### 2.1 学生端题目

标题：**最后几个问题**

指导语：

> 下面的问题想了解你在两轮创作中的真实体验。两轮使用的文物和 AI 互动方式可能不同，请分别回想每一轮的情况。没有正确或错误答案。

页面按三个小节显示：

| 小节 | 题号 | 题目 | 量表 |
|---|---|---|---|
| 第一轮创作 | S1 | 第一轮使用 AI 创作时，我能够探索不同的设计想法或可能性。 | 1–7（非常不同意—非常同意） |
| 第一轮创作 | S2 | 第一轮创作中，采用哪些设计想法主要由我自己决定。 | 1–7 |
| 第一轮创作 | S3 | 完成第一轮文创任务时，你投入了多少心理努力？ | 1–9（极低—极高） |
| 第二轮创作 | S4 | 第二轮使用 AI 创作时，我能够探索不同的设计想法或可能性。 | 1–7 |
| 第二轮创作 | S5 | 第二轮创作中，采用哪些设计想法主要由我自己决定。 | 1–7 |
| 第二轮创作 | S6 | 完成第二轮文创任务时，你投入了多少心理努力？ | 1–9 |
| 总体偏好 | S7 | 如果只比较 AI 的互动与帮助方式，不考虑两件文物本身的差异，你更愿意在以后的文创设计中使用哪一轮的方式？ | 第一轮 / 第二轮 / 两种差不多 / 不确定 |

学生端只显示题干、量表和选项；不显示构念英文名、实验组别、A/B 条件、研究假设或任何自动评分结果。

### 2.2 新旧问卷对照

| 旧 V2.0 | 新 V2.1 | 说明 |
|---|---|---|
| S1/S4：AI 帮助我更容易理解文物知识 | S1/S4：设计探索支持 | 构念从“知识理解帮助”改为“探索不同设计想法/可能性”，更贴近 HLSF 的 Create 目标 |
| S2/S5：我能够自己决定采用哪些设计想法 | S2/S5：设计自主选择（措辞更明确） | 仍是自主/选择构念 |
| S3/S6：心理努力 1–9 | S3/S6：心理努力 1–9（措辞更明确） | 保留 Paas 单题 9 点思路 |
| S7：轮次偏好 4 选项 | S7：轮次偏好，明确“只比较 AI 互动方式、不考虑文物差异” | 选项改为“两种差不多” |

### 2.3 研究依据与改编边界

- **Perceived Design Exploration**：参照 Cherry & Latulipe (2014) Creativity Support Index 的 Exploration 构念，改写为单题 1–7 指标。
- **Perceived Choice / Autonomy**：参照 Intrinsic Motivation Inventory (IMI) 的 Perceived Choice 构念，改写为单题 1–7 指标。
- **Mental Effort**：参照 Paas (1992) 的单题 9 点心理努力量表。
- S1/S2/S4/S5 是**研究者按构念改写的单题指标**，不是完整 CSI/IMI 量表，不能宣称具有原量表的信度/效度；S3/S6 也不是完整认知负荷量表。
- S1/S4、S2/S5、S3/S6 是不同构念的配对重复测量；**不得把 S1–S7 加总为一个体验总分**。

### 2.4 分析方式

- S1/S4：两轮的感知设计探索支持；
- S2/S5：两轮的感知自主选择；
- S3/S6：两轮的心理努力；
- S7：AI 互动方式偏好，仅作探索性描述。

S7 的偏好轮次按该学生**实际轮次条件**转换：

| S7 原始值 | 含义 | 导出 AI 条件 |
|---|---|---|
| `first` | 第一轮 | 该 run 第一轮的实际条件：`Standard AI` 或 `HLSF + AI` |
| `second` | 第二轮 | 该 run 第二轮的实际条件 |
| `same` | 两种差不多 | `Similar` |
| `uncertain` | 不确定 | `Unsure` |

不能根据组别硬编码“第一轮一定是 A/B”；必须使用 `rounds[1/2].condition`。

## 3. 同伴互评 V2.1

### 3.1 学生端说明

标题：**看看其他同学的设计**

说明：

> 请根据作品图片和作品说明评价。重点是你能否看懂作品想表达的文化内容，以及设计怎样从文物中获得启发。
>
> 不要求你判断历史资料是否绝对正确。请按照自己的理解评价。

评分原则（作为说明文字，不是新题）：

- 设计有创意不等于一定要完全改变文物图案。
- 保留、简化、重新组合、改变用途、转变媒介，都可能体现创造性。
- 与文物外观差异大，不代表一定具有更高创造性。
- 作品图片美观，不代表文化理解一定准确。
- 学生评价的是作品表达和设计转译的可理解程度，而不是承担专业历史考证责任。

### 3.2 三项评分

| 键 | 标签 | 题干 | 1–5 锚点 |
|---|---|---|---|
| `cultural_clarity` | P1 文化表达清晰度 | 这件作品想表达的文物知识或文化意义是否清楚？ | 几乎无法理解 / 表达不太清楚 / 能够理解一部分 / 表达比较清楚 / 表达非常清楚 |
| `cultural_translation` | P2 文化转译清晰度 | 你能否看出这件作品如何将文物的特征、结构、功能或文化意义转化为新的设计？ | 看不出明确联系 / 联系比较模糊 / 能够看出一定联系 / 联系清楚 / 联系清楚且有说服力 |
| `design_originality` | P3 设计创意 | 你认为这件作品对文物内容的设计转化有多少新意？ | 缺少明显的新构思 / 新意较少 / 有一定新想法 / 构思比较新颖 / 构思有明显的新意 |

可选意见：

> 你觉得这件作品最有意思的地方是什么？或者还有哪里可以改进？

### 3.3 新旧互评对照

| 旧 V2.0 | 新 V2.1 | 说明 |
|---|---|---|
| `clarity` 文化信息表达是否清楚 | `cultural_clarity` 文化表达清晰度 | 构念基本延续，措辞更聚焦“作品想表达的文物知识/文化意义” |
| `evidence_link` 文物知识与设计选择的联系 | `cultural_translation` 文化转译清晰度 | 从“知识—设计联系”改为“特征/结构/功能/文化意义如何转化为新设计” |
| `attraction` 作品整体设计吸引力 | `design_originality` 设计创意 | **构念替换**：旧 attraction 不能被解释为 P3 设计创意 |

旧批次的 `clarity/evidence_link/attraction` 保留在旧列；新批次只写 `cultural_clarity/cultural_translation/design_originality`。两个版本不合并、不互相映射。

### 3.4 研究依据与边界

- Lin (2007) Cultural Product Design Model：支持“文化内容—设计转译”的评价方向；
- Amabile (1982) Consensual Assessment Technique：支持由评审者判断作品创造性；
- Besemer & O'Quin 的 Creative Product Semantic Scale：提示新颖性与审美吸引力应区分，因此本版把旧“视觉吸引力”改为“设计创意”。

这些文献用于指导指标设计，**不代表 P1–P3 已经是验证过的标准量表**。P3 不等于发散思维能力；学生可能只提交一个方案，真正的发散过程需结合 AI 对话和作品版本记录。P1–P3 也不能混入专家 D1–D4。

## 4. 互评批次与分配

- 互评仍在全班所有已进入学生完成 T2 后由现有单一闸门统一开放；T1 作品已冻结。
- 正式班级：每轮目标 `min(6, N-1, 该轮有效作品数)`；正常 30 人班为每名学生 **6 T1 + 6 T2 = 12 件**，每件作品每轮约 **6 份**独立评分。
- 每轮独立做 reviewer-round → work 最大流分配；排除本人两轮作品；小班/缺轮按实际作品降级，不伪造作品。
- 班级 0 内测模式是例外：保留“最多 6 件、每位作者 T1/T2 成对”的轻量快照；正式班级为 6+6。
- 旧批次（`scale_version=peer-scale-v2`）不会被自动改成两轮或 V2.1；旧评分保留。

### 4.1 混合列表与后台区分

学生端把 T1/T2 作品混合为一个列表，不显示轮次、条件、组别或作者。后台仍可逐条区分：

```text
peer_assignments.work_id
  → work_revisions.round_id
  → rounds.round_no / condition / artifact_version_id
  → runs.group_name / condition_sequence / artifact_sequence
```

因此 `peer_ratings.csv` 每条评分都能导出：

- `reviewed_round_no`：1 或 2；
- `reviewed_ai_condition`：A/B；
- `reviewed_ai_condition_label`：Standard AI / HLSF + AI；
- `reviewed_artifact_id` / `reviewed_artifact_slot` / `object_code`；
- `reviewed_group_id`、`condition_sequence`、`artifact_sequence`。

## 5. 展示内容

每张互评卡片显示：

1. 文物名称；
2. 文物时代/类型，以及来自冻结 `artifact_versions.introduction` 的客观介绍；
3. 作品名称与产品类别；
4. 最终确认的作品图片（`rounds.selected_image_job_id`）；
5. 三段作品说明：从文物中学到了什么 / 怎样把知识用到设计里 / 为什么这样设计；
6. P1–P3 评分与可选意见。

不显示：学生真实身份、组别、A/B 标签、使用的 AI 方式、知识测验成绩、HLSF 聊天记录或隐藏 Prompt。旧版作品没有三段说明时，显示旧六字段只读回退，不冒充三段。

## 6. 导出字段

### 6.1 `survey.csv`

保留原始 `S1`–`S7`，追加：

- `student_id`、`group_id`、`condition_sequence`、`artifact_sequence`
- `survey_version`、`survey_instrument_version`
- `s1_exploration_r1`、`s2_autonomy_r1`、`s3_mental_effort_r1`
- `s4_exploration_r2`、`s5_autonomy_r2`、`s6_mental_effort_r2`
- `s7_preferred_round`、`s7_preferred_round_label`
- `s7_preferred_ai_condition`、`s7_preferred_condition_code`
- `round1_artifact_id`、`round2_artifact_id`

历史保护：只有 `survey_version=survey-v2.1-pilot` 的响应才填 canonical `s1_...`–`s6_...`；旧版本这些列留空，避免把旧 S1“知识理解帮助”误标为“设计探索”。只有 S7 为单选题时才填 `s7_preferred_*`。

### 6.2 `peer_ratings.csv`

保留旧列，追加：

- `review_version`
- `reviewer_student_id`、`reviewed_student_id`、`reviewed_work_id`
- `reviewed_round_no`、`reviewed_ai_condition`、`reviewed_ai_condition_label`
- `reviewed_artifact_id`、`reviewed_artifact_slot`、`reviewed_group_id`
- `condition_sequence`、`artifact_sequence`
- `cultural_clarity`、`cultural_translation`、`design_originality`
- `optional_comment`、`submitted_at`

旧批次对应新列为空，旧 `clarity/evidence_link/attraction` 保留。

### 6.3 `peer_work_scores.csv`

每件作品一行：`review_version`、`round_no`、`ai_condition`、`artifact_id/slot`、`object_code`、`group_id`、`rating_count`、三个新维度均值（旧批次为旧维度均值）。**不输出 overall 综合分**；需要平均分时应先检查评分数量、分布和评分者间一致性，并保留 `peer_ratings.csv` 原始分。

### 6.4 `analysis.csv`

追加 `peer_review_version`、`peer_cultural_clarity_mean`、`peer_cultural_translation_mean`、`peer_design_originality_mean`；保留旧 peer 列以读旧数据。

## 7. 导入、激活与版本核验

```bash
cd backend
.venv/bin/python -m app.cli import-formal-v2 --dry-run
# 目标库无 active V2：
.venv/bin/python -m app.cli import-formal-v2 --activate
# 目标库已有 active V2：
.venv/bin/python -m app.cli import-formal-v2 --force-new-version --activate
```

- 不清空数据库、不删除旧 run、不覆盖旧题本/旧回答。
- 旧 run 的 `protocol_version_id` 不变；新 run 使用新 active 协议。
- 已在进行的 run 若仍绑定旧协议，继续使用旧 survey。
- 互评量表按批次冻结：已开放旧批次保持旧量表；新批次使用 V2.1。

**数据库迁移：不需要。** `survey_version` 写入 `instrument_versions.schema_json`；`review_version` 写入 `peer_batches.scale_version` 与 `config_json`；三项评分写入 `peer_ratings.scores_json`。

### 7.1 本地验证结果（2026-11-08）

- 本地 `heritage_dev` 在已有 6 条旧 run 的情况下导入成功；旧 run 仍绑定 `assessment_v1`，未被清空或重写。
- 新 active 协议：`assessment_v2.0_pilot`，`research_rubric_json.content_version = v2.1-survey-peer-pilot`。
- 新 survey：numeric version `2`，`survey_version = survey-v2.1-pilot`，7 题。
- 生产/云端环境未在本机自动切换；需按第 7 节在目标环境备份后人工执行。

## 8. 测试与已知风险

### 8.1 测试结果

- 后端：`76 passed, 4 skipped`（完整 pytest）。
- 前端：`13 passed`（6 个测试文件），`tsc --noEmit` 与 `vite build` 通过。

### 8.2 已知风险与解释边界

1. **12 件互评负担**：每名学生 6 T1 + 6 T2，明显高于原 6 件；需确认课堂时间可接受。
2. **班级 0 例外**：内测模式仍为最多 6 件（3 位作者 × 两轮）；与正式班 12 件不同，导出以 `review_version`/`batch_id` 区分。
3. **旧批次不回溯**：已冻结的 T2-only 或旧量表批次不会自动变成两轮/V2.1；如需改版只能受控重建，旧批次标记 superseded、旧评分保留。
4. **版本错位**：升级后仍在进行的 run 可能“旧 survey + 新 peer scale”，导出用 `survey_version` / `review_version` 区分；分析时不要把两个 peer 版本合并。
5. **`assessment_version` 仍是 v2.0**：V2.1 是内容版本，不是新的 assessment 框架；不要用它改四组分配或 K 计分。
6. **S7 的混杂**：两轮文物不同，S7 只比较 AI 互动方式；仍是探索性指标。
7. **量表边界**：S1/S2/S4/S5 是改写单题，不是完整 CSI/IMI；P1–P3 不是验证量表；P3 不是发散思维测量。
8. **T2 携带效应**：T2 互评可能受第一轮 HLSF 经历影响，不能直接解释为纯即时 AI 条件比较。
9. **不合成总分**：问卷不求和；互评不输出 overall 综合分。若研究团队需要综合指标，应在分析计划中另行说明并先做信度/一致性检查。

## 9. 变更文件清单

### 后端
- `backend/app/content/formal_v2/instruments.json`：Survey V2.1 题目、三小节、S7 选项、`survey_version`、`content_version`。
- `backend/app/schemas.py`：`InstrumentPayload.survey_version`。
- `backend/app/services/formal_content.py`：问卷指导语与 `content_version` 写入协议 rubric。
- `backend/app/domain.py`：`A=Standard AI / B=HLSF + AI` 条件标签。
- `backend/app/services/peer_scales.py`（新增）：V2/V2.1 互评量表定义与批次解析。
- `backend/app/services/peer.py`：6/轮、按轮次分配与缺轮降级、量表快照、文物/三段说明 payload、按批次校验评分、汇总函数。
- `backend/app/services/export.py`：survey/peer 新列、版本字段、历史守卫、数据字典。
- `backend/app/routers/admin.py`：分析 CSV 新列与 fallback 字段。

### 前端
- `frontend/src/types.ts`：`PeerReviewScale`、`PeerDimension`、peer payload 新字段。
- `frontend/src/pages/PeerAssessmentPage.tsx`：动态 P1–P3、锚点、文物介绍、三段说明、评分原则、混合列表。
- `frontend/src/components/ParticipantDetail.tsx`：按 `review_version` 显示 P1–P3 或旧维度。
- `frontend/src/styles.css`：锚点、文物介绍、三段说明样式。
- `frontend/src/tests/peer.test.tsx`、`frontend/src/tests/survey.test.tsx`（新增）。

### 测试
- `backend/tests/conftest.py`、`test_peer_social.py`、`test_peer_allocation.py`、`test_assessment_v2.py`、`test_class_links_gate.py`、`test_beta_cloud.py`、`test_flow.py` 等。

### 文档
- 新增本文；更新 `ASSESSMENT_V2_PILOT.md`、`ASSESSMENT_ITEM_BANK_V2_ZH.md`、`API_REFERENCE.md`、`USER_GUIDE_ZH.md`、`DEPLOYMENT_HANDOVER_V2.md`、`PROTOCOL_CROSSOVER_V1_PILOT.md`、`PLATFORM_COMPLETE_GUIDE_ZH.md`、`DATA_MODEL.md`、`TEST_REPORT.md`、`README.md`、`TASK_STATE.md`。

### 数据库
- 无迁移；无表/列变更；旧 run、旧回答、旧评分、旧批次全部保留。
