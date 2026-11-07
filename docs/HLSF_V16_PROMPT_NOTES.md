# HLSF v1.6 Prompt Upgrade — Pilot Notes（历史，已被 crossover v1.0 取代）

> **2026-11-07 后续：** 当前正式 Pilot 为四组平衡交叉 `crossover-v1.0-pilot`，HLSF 版本升级为 `hlsf-v1.7.1-crossover-pilot`。本文保留 v1.6 提示词历史；T2 不再统一为 Standard AI。见 `docs/PROTOCOL_CROSSOVER_V1_PILOT.md` 与 `docs/HLSF_CURRENT_FRAMEWORK.md`。

日期：2026-11-07  
版本：`hlsf-v1.6.0-pilot`  
状态：**Pilot 提示词版本，不是正式研究冻结版**

## 1. 改动范围

只改变 T1 B 的 HLSF 提示内容与 B-only 教练上下文：

- `backend/app/prompts/hlsf.py`
  - `PHASE_PROMPTS`
  - `PHASE_HINTS`
  - `DESIGN_COACH_B`
  - `PHASE_COACHING`
  - 新增 `ARTIFACT_LEARNING_ANCHORS`
- `backend/app/services/ai_text.py`
  - B-only artifact section index
  - B-only learning anchors
- `backend/app/models.py` / `0010_widen_prompt_version.py`
  - `ai_calls.prompt_version` 由 24 扩到 64，以容纳 `chat-v1+hlsf-v1.6.0-pilot`

不改变：

- T1 A 的 Standard AI；
- T2 的 Standard AI、无 HLSF、无 T1 对话；
- A/B 分配、T1/T2 文物顺序；
- HLSF 状态机、手动 Next/Skip、每阶段一次 Hint；
- K0–K3、六字段、开放说明；
- 数据库中的 HLSF 状态/事件结构；
- 前端交互（提示文本走原有消息通道）。
- 图片描述框下增加一条低强调提示：“说清需求，可以让 AI 帮助你写提示词来生成图像。”
- B 教练上下文包含学生已写的 `Image prompt draft`，便于继续帮助润色；A/T2 不注入该上下文。

## 2. v1.6 教学逻辑

固定循环：

```text
Ask → Student attempt → Evidence-based feedback → Student choice
```

关键规则：

- 每次只问一个最重要的问题；
- 学生先尝试，允许“不知道”、跳过或要求解释；
- 反馈是 1 句肯定/纠正 + 1 个章节定位 + 最多 1 个追问；
- 每次聚焦 1–2 个知识重点，不百科式讲授；
- 不主动建议具体产品类型或产品清单；
- 先听学生自己的产品、受众、文化意义，再讨论知识—设计映射；
- 只有学生明确要求方案时，才给多个“可选建议”，不设默认答案；
- 区分对象事实、制度/同类研究、推断、当代寓意；
- 普通回复 2–4 句，最多一个问题；
- 不泄露 K0–K3 题目、答案、评分规则、分组或隐藏提示。

## 3. 文物章节索引与学习锚点

B 组教练上下文新增：

```text
Artifact section index
- M01 | 物件与可观察图像 | evidence: 馆藏登记｜图像观察 | sources: HKPM-P
- M03 | 明代官服制度中的意义 | evidence: 古籍制度｜历史解释 | sources: MING-01
...
```

以及：

```text
Curated learning anchors
- M03: focus: 官服制度与身份识别；boundary: 制度记载不等于本件制作年/穿用者
- M05: focus: 纱地/刺绣工艺；boundary: 不把一般工艺说成本件已证实针法
...
```

限制：

- 不是正式 MA/MB/TA/TB 题本；
- 不包含题干、选项、正确答案或评分规则；
- 没有章节或无法解析证据层次时写 `not stated`；
- 索引有长度上限，不新增 RAG 或数据库。

## 4. 版本与数据

- B T1 AI call：`chat-v1+hlsf-v1.6.0-pilot`
- A T1 / T2：`chat-v1`
- HLSFEvent `prompt_version`：`hlsf-v1.6.0-pilot`
- 旧 v1.5 run 保持旧版本，不静默混合
- Pilot 用新数据库/新协议或明确标记版本

## 5. 验证

当前自动化验证：

- 后端 46 passed
- 前端 11 tests passed
- `tsc --noEmit` 通过
- `vite build` 通过
- HLSF 测试覆盖：
  - v1.6 版本
  - 四阶段新提示
  - Hint 文本
  - 每次一个问题的教练规则
  - 不主动推荐产品类型
  - section index / anchors
  - 正式题号/答案不进入上下文
  - A / T2 无 HLSF 上下文
  - 每阶段一次 Hint
  - prompt_version

## 6. Pilot 必须检查

- 学生是否能在资料中找到证据；
- 问题是否过浅或过难；
- AI 是否真的先等学生尝试，而不是直接讲课；
- AI 是否在未请求时推荐产品类型；
- 错误回答是否被纠正，而不是被夸赞；
- 是否把“跨区域图案相似”误写成“确定产地”；
- 每阶段时间和总时长是否可接受；
- 是否因追问过多压缩设计时间；
- 是否出现 K0–K3 题面/答案泄漏；
- T2 是否仍无 HLSF、无 T1 对话泄漏。

## 7. 结论

v1.6 是**提示词层面的 Pilot 升级**，不是新的实验设计。  
正式冻结前必须完成 Pilot，确认教学效果、产品自主性、反馈准确性和技术负担。
