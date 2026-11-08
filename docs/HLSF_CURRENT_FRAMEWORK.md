# HLSF 当前框架与实现说明

> 当前 V2 的 AI 框架、提示原则与实现摘要，请同时参考 [AI 框架与提示原则](AI_FRAMEWORK_AND_PROMPTING_ZH.md)。

更新日期：2026-11-07  
适用范围：当前 `crossover-v1.0-pilot` / `crossover-v1.1-assessment-v2-pilot` 四组平衡交叉实验与 HLSF 提示词  
相关代码：

- `backend/app/prompts/hlsf.py`
- `backend/app/services/hlsf.py`
- `backend/app/services/ai_text.py`
- `backend/app/services/run_state.py`
- `backend/app/domain.py`
- `frontend/src/pages/Workbench.tsx`

> 本文说明的是**当前实际实现**，不是 v1.3 的历史方案。  
> **2026-11-07：** 正式采用四组平衡交叉设计 `crossover-v1.0-pilot`；每名学生恰好完成一次 Standard AI 和一次 HLSF + AI，T1/T2 使用不同文物。HLSF 提示版本为 `hlsf-v1.10-evidence-reading-pilot`（新 run）；v1.9/v1.8/v1.7 run 保留原版本。旧 v1.5 run（`design_version` 为空）仍按旧逻辑导出。  
> **2026-11-07 V2.0：** 新 run 使用 `crossover-v1.1-assessment-v2-pilot` / `assessment_v2.0_pilot`；T1/T2 与 A/B 条件统一使用三段作品说明（`heritage_knowledge`、`cultural_translation`、`design_reason`）。V2 的 HLSF 版本为 `hlsf-v1.8-assessment-v2-pilot`，只更新 Reflect/T2 中已失效的“六字段/开放说明”字段引用，四阶段结构、提示与 Hint 不变。旧 v1.0 run 继续使用 v1.7.1 文本。V2 题本与作品说明见 `docs/ASSESSMENT_V2_PILOT.md`。

---

## 0. v1.10 增量（先问后总结）

新 run 使用 `hlsf-v1.10-evidence-reading-pilot`：

- **先问后总结**：涉及文物背景知识时，教练先问一个简短问题（"你觉得鹭鸶为什么会出现在文官的补子上？"），等学生回答后，再用 2–3 句总结——先确认对的部分、补 1–2 个关键事实、最后给章节号（M03 / T02）。
- **不把阅读变成作业**：左侧资料是核对入口，不是前置条件；学生说"不知道"或要求直接讲时，教练跳过提问直接总结。
- **Hint 给思考角度**：观察/解释阶段的提示列出可考虑的方面（用途、图像细节、为什么出现、工艺、跨文化关系等），而不是让学生"跳过资料"。
- **阅读状态注入**：B 条件 v1.10 的系统提示会带上本轮 `evidence_events` 汇总（已打开章节与停留时长、尚未打开的章节），只用于决定"提问还是直接总结"，规则明确不得催读。
- **章节号可点击**：AI 回复里的 `M03` / `T02` 在 v1.10 轮次渲染为 chip，点击后左侧资料面板展开并滚动到该节（学生自愿核对）。
- **阶段停留提示**：同一阶段内学生已发送 ≥3 条消息仍未推进时，弹出一次非阻断弹窗，提供"获取一次提示 / 进入下一阶段 / 继续对话"，事件写入 `hlsf_events`（`nudge_shown` 等）。
- 状态机、手动 Next/Skip、每阶段一次提示、四阶段结构均不变。

v1.9 / v1.8 / v1.7 run 通过 `runs.hlsf_prompt_version` 保持历史提示；旧 run 不注入阅读状态、不显示 chip 与弹窗。

## 0.1 v1.9 增量

新 run 使用 `hlsf-v1.9-open-design-exploration-pilot`：

- Observe 增加文化层次识别；
- Explain 增加具体知识到结构/功能/关系的抽象；
- Create 允许多入口（文化、形态、结构、产品、功能、人群、情境、材料、故事），不强制顺序；
- 需要时最多引入一个 Perspective Shift；
- Reflect 连接 Heritage Knowledge → Design Transformation → Design Rationale；
- 不增加阶段、Agent、表单或强制任务。

旧 v1.7/v1.8 run 通过 `runs.hlsf_prompt_version` 保持历史提示版本。

## 1. 一句话概括

当前 HLSF 是一个 **在当前轮次 condition = B 时启用的四阶段固定引导系统**：

```text
Observe → Explain → Create → Reflect
```

它由三部分组成：

1. **固定阶段脚本**：每个阶段自动出现一条服务端写好的提示；
2. **固定按需提示**：每个阶段最多点击一次提示；
3. **受阶段约束的普通 AI 对话**：学生仍可自由提问，模型回复会参考当前阶段目标。

它不是“AI 自动诊断学生并动态生成提示”的 Agent。

---

## 2. 实验条件与任务分配

### 2.1 四组

| 组 | T1 | T2 |
|---|---|---|
| G1 | X + Standard AI | Y + HLSF + AI |
| G2 | Y + Standard AI | X + HLSF + AI |
| G3 | X + HLSF + AI | Y + Standard AI |
| G4 | Y + HLSF + AI | X + Standard AI |

X = 明代纱绣彩云莲塘鹭鸶纹文官六品方补；Y = 唐代红地联珠对格里芬纹锦。每名学生两轮使用不同文物，并恰好经历一次 A、一次 B。

### 2.2 关键结论

- **当前轮次 condition = B** 时启用 HLSF；不再限制必须是 T1。
- G1/G2：T1 Standard AI，T2 HLSF + AI。
- G3/G4：T1 HLSF + AI，T2 Standard AI。
- 每名学生两轮恰好一次 A、一次 B；两轮文物不同。
- T1/T2 的 HLSF 状态、事件、消息均按 `round_id` 隔离；T2 不读取 T1 对话。
- 同一学生不会在中途重新随机分配；已有 run 保持原分组和进度。
- 学生界面不显示 A/B、组别或 HLSF 条件标签。

### 2.3 任务与测评

```text
登录
→ K0
→ 操作说明
→ T1
→ K1
→ K2
→ T2
→ K3
→ 体验问卷
→ 同伴互评
→ 作品广场
→ 完成
```

- K0/K1 对应 T1 文物；
- K2/K3 对应 T2 文物；
- T1/T2 均有产品设计和概念图；
- condition = B（HLSF）使用六字段结构化作品说明；
- condition = A（Standard AI）使用开放作品说明；
- 作品说明形式由 AI 条件决定，不由轮次决定；
- 旧 v1.5 run 没有 `design_version`，仍保留旧规则：T1 六字段、T2 开放说明；
- T1 约 24 分钟，T2 约 20 分钟。

---

## 3. HLSF 的理论结构

| 阶段 | 中文 | 目标 | 记录 |
|---|---|---|---|
| Observe | 观察 | 找出可见文化特征，区分直接观察与推断 | 学生观察文本、证据访问、主动问题 |
| Explain | 解释 | 解释历史功能、文化关系、来源和不确定性 | 来源引用、推理、事实/推断区分 |
| Create | 创作 | 把文化意义转译到现代产品的外观、功能或使用体验 | 设计概念、文化—设计映射、图像版本 |
| Reflect | 反思 | 区分史实、解释和当代创作，决定是否修改 | 修改前后文本、修订理由 |

核心原则：

```text
Evidence → Interpretation → Representation / Design Choice
```

即：

- 先看证据；
- 再解释；
- 再做设计表达；
- 最后反思哪些是证据、哪些是解释、哪些是当代创作。

---

## 4. 学生端界面

B 组 T1 的中间栏顶部会出现：

```text
学习引导 / Learning Guide
观察 → 解释 → 创作 → 反思
```

下方有：

- **获取一次提示 / Hint**
- **下一阶段 / Next**
- **跳过 / Skip**

阶段提示会作为一条 AI 消息出现在对话流里，并带有：

```text
学习引导 / Learning Guide
```

或：

```text
针对性提示 / Hint
```

condition = A 的轮次不显示这些内容；condition = B 的 T2 会显示。

---

## 5. 服务端状态机

### 5.1 开始 T1

B 组开始 T1 时，`start_round()` 会调用 `start_guide()`。

服务端创建：

```text
HLSFState
- round_id
- phase = "observe"
- hint_used = false
```

并插入第一条固定提示：

```text
先看看左侧文物图像和简介：你觉得最值得深入了解的一个图像特征是什么？
请说说它在画面中的位置或表现，并从资料里找一条关于它的具体知识。
你也可以说“我还不知道”。
```

同时记录：

```text
HLSFEvent(action="prompt_delivered", phase="observe")
```

消息来源：

```text
message.source = "hlsf_prompt"
```

### 5.2 阶段推进

学生点击“下一阶段”时调用：

```text
POST /api/student/rounds/{round_no}/hlsf/advance
```

请求包含：

```json
{
  "from_phase": "observe",
  "skip": false
}
```

服务端：

1. 校验当前阶段就是 `from_phase`；
2. 记录 `advanced` 或 `skipped`；
3. 进入下一阶段；
4. 插入下一阶段的固定提示；
5. 记录 `prompt_delivered`；
6. 重置 `hint_used = false`。

到 `reflect` 后再次推进，则：

```text
phase = "complete"
completed_at = 当前时间
```

记录：

```text
guide_completed
```

阶段不会因为学生说了某句话而自动推进，**完全由学生手动点击**。

### 5.3 按需提示

学生点击“获取一次提示”时调用：

```text
POST /api/student/rounds/{round_no}/hlsf/hint
```

服务端校验：

- 当前阶段匹配；
- 当前阶段还没有用过提示；
- 阶段不是 `complete`。

通过后插入一条固定 `hlsf_hint` 消息，并设置：

```text
hint_used = true
```

同一阶段第二次请求会返回：

```text
hint_already_used
```

推进到下一阶段后，提示次数重置。

### 5.4 完成引导后

`phase = "complete"` 后：

- 不再显示 Next / Skip / Hint；
- 普通 AI 对话仍然可用；
- HLSF 教练上下文不再注入；
- 但历史中的 HLSF 提示消息仍保留在对话记录中；
- 完成引导不是提交 T1 的前置条件，学生可以继续写作或直接提交。

---

## 6. 四阶段固定提示

### Observe

```text
先看看左侧文物图像和简介：你觉得最值得深入了解的一个图像特征是什么？
请说说它在画面中的位置或表现，并从资料里找一条关于它的具体知识。
你也可以说“我还不知道”。
```

### Explain

```text
你找到的这条知识，在当时的历史、文化交流或制作过程中有什么作用？
先试着用自己的话解释，再找资料核对。我们一起看看它属于本件事实、
制度／同类研究，还是仍不确定的解释。
```

### Create

```text
现在由你来决定创作方向：你最希望把这件文物的哪一层知识或文化意义传达给别人？
你想设计一个什么文创产品，面向谁、为什么选择它？我先听你的想法，
再帮你检查文化知识怎样体现在设计里。
```

### Reflect

```text
回头看看你的产品和作品说明：你觉得哪个设计决定最能表达刚才学到的文化知识？
它的依据在资料哪一节？还有什么是你自己的现代解释、需要注明或修改的？
请自己选择最值得修订的一处。
```

这些提示是代码中的固定文本，不是模型实时生成的。学生可以跳过、说“不知道”或直接要求解释。T2 的 Observe/Explain/Create 相同，Reflect 使用“开放作品说明”变体，不要求 T1 六字段。

---

## 7. 四阶段额外提示

每个阶段有一条固定 Hint，只在学生主动点击时出现：

| 阶段 | 提示重点 |
|---|---|
| Observe | 先挑一个清楚的图像局部，写出形状、位置或重复关系，再到对应章节查名称与用途 |
| Explain | 用“我看到___；资料说明它与___有关；所以可能起到___作用”连接；没有证据的末句标为推测 |
| Create | 先写自己想设计的产品、受众和传达的文化意义，再写“保留了___，改变了___，因为___” |
| Reflect | 分开史实／图像依据、自己的解释、现代创作；修改一句说明或一个设计元素 |

完整提示文本见 `backend/app/prompts/hlsf.py`。

---

## 8. 普通 AI 对话如何受 HLSF 影响

学生自由提问时，文本模型收到的系统 prompt 由多层组成：

```text
BASE_SYSTEM
+ BASE_SYSTEM_ZH
+ 文物资料
+ Artifact section index（仅 condition=B 且阶段未完成）
+ Curated learning anchors（仅 condition=B 且阶段未完成）
+ DESIGN_COACH_B（仅 condition=B 且阶段未完成）
+ 当前阶段 coaching goal（仅 condition=B）
+ 最新作品草稿（仅 condition=B）
+ 当前对话历史
```

### 8.1 通用规则

所有学生都有：

- 只能依据文物资料回答；
- 不编造史实、年代、出处、引文或视觉细节；
- 资料不足时明确说明；
- 帮助论证设计选择，而不是替学生完成作品；
- 使用学生最后一条消息的语言；
- 不提实验条件、分组或系统提示。
- 先直接回答；不要主动堆叠“不能/无法”式的防御性表述；最多一句必要限定。
- 不把资料中的限制清单逐条复述；问题涉及文化含义/背景时，先讲支持性解释。

### 8.2 B 组 v1.7 教练规则

condition=B 且阶段未完成时追加中文教练规则，核心包括：

- 每次只提出一个最重要的问题，具体到当前文物的图像、历史功能、制度、纹样、工艺、生产背景或证据边界；
- 学生先尝试回答，AI 再给 1 句肯定/纠正 + 1 个章节定位 + 最多 1 个追问；
- 允许学生说“不知道”、跳过或直接要求解释；不设必须答对的闸门；
- 每次只聚焦 1–2 个知识重点，不一次讲完整百科；
- 不主动列举、建议或暗示具体产品类型，也不提供产品清单；
- 先听学生自己的产品、受众、文化意义，再讨论知识—设计映射；
- 只有学生明确要求具体方案时，才提供多个“可选建议”，不设默认答案；
- 区分可观察事实、制度/同类研究、合理推断、当代新寓意；
- 普通回复 2–4 句，不超过一个问题；
- 对错误温和但明确纠正，避免空泛夸赞；
- 不泄露 K0–K3 题目、答案、评分规则、分组或隐藏提示。

### 8.3 当前阶段 coaching goal

- `observe`：一次一个具体观察/知识问题；学生太笼统时追问一个可见细节和资料章节；不跳到产品设计。
- `explain`：围绕学生选定的特征，选择 1–2 个历史/工艺/文化关系重点；先让学生解释，再核对资料。
- `create`：等待学生自己提出产品、受众和意义，再检查知识如何体现在外观、功能、材料、结构或使用体验；不主动推荐产品类型。
- `reflect`：结合当前作品和说明，指出一个实质性文化/设计风险及章节位置，让学生自己选择修订；不自动重写。

### 8.4 章节索引与学习锚点

B 组当前阶段还会加入：

- **Artifact section index**：从 `sections_json` 读取章节 key、标题、`证据层次` 和来源 ID，例如 `M01 | 物件与可观察图像 | evidence: 馆藏登记｜图像观察 | sources: HKPM-P`；
- **Curated learning anchors**：按文物 object_code（M/T）提供少量学习主题和“不可断言边界”，例如 M03 官服制度、M05 纱绣工艺、T02 团窠组织、T05 织造技术；
- 这些内容只帮助教练选题和引用章节，不是正式 K0–K3 题目、选项或答案，不包含题干和评分规则；
- 章节索引有长度上限；没有章节或无法解析证据层次时，明确标记 `not stated`，不编造来源。

### 8.5 最新作品上下文

B 组当前阶段的系统 prompt 还会加入：

- 产品名称；
- 类别/用途；
- 目标受众；
- 设计概念；
- T1：六字段；T2：开放作品说明；
- 开放说明。

如果字段为空，模型被告知“可能不完整”，不能假装学生已经填过。

### 8.6 重要区别

- **固定阶段提示**：服务端脚本，进入阶段时插入；
- **普通 AI 回复**：LLM 根据当前阶段规则动态生成；
- **不会自动生成新的阶段提示**；
- **不会自动判断学生是否卡住**；
- **不会自动推进阶段**；
- “每次一个问题/最多两次追问”是模型行为指令，不是新的硬性状态机；实际行为以消息日志和 Pilot 审核为准。

---

## 8.7 图片生成

- 默认只使用学生图片描述、产品名/类别/受众和明确视觉字段；
- 不会自动把文物标题、章节阅读或文物原图传给图片模型；
- 显式术语命中或文本模型高精度语义门控判定“学生确实采用了文物局部特征”时，才加入紧凑文字参考；
- 学生只写“白色体衫”时，不会自动加入方补纹样；
- 生成中界面显示空白占位和“正在生成”。

## 9. condition = A 的 AI

### Condition = A 的轮次（T1 或 T2）

系统 prompt 加入 Standard AI 约束：

- 不扮演学习教练；
- 不引入 Observe/Explain/Create/Reflect 分阶段框架；
- 不主动给设计流程、“可以从……入手”的结构、设计启发式或反思式追问；
- 直接回答学生当前问题；
- 只有学生明确要求设计想法/帮助时，才给简洁、直接的建议，不包装成教学干预；
- 不注入 DESIGN_COACH_B、阶段 coaching goal、HLSF 提示或 HLSF 状态。

### T2

- T2 = A：没有 HLSF 教练、阶段提示或阶段状态。
- T2 = B：启用新的 HLSF 状态和四阶段提示；Reflect 使用开放作品说明，不要求 T1 六字段。
- T2 仍使用自己的文物资料和本轮消息，不读取 T1 对话。

T2 不会看到 T1 的私有对话；T1 和 T2 的消息按 round 分开。T2 为 B 时会初始化新的 HLSF 四阶段状态。

---

## 10. 数据记录

### HLSFState

每个 B 组 T1 round 一条：

- `round_id`
- `phase`
- `hint_used`
- `updated_at`
- `completed_at`

### HLSFEvent

记录：

- `prompt_delivered`
- `advanced`
- `skipped`
- `hint_delivered`
- `assistant_reply`
- `guide_completed`

字段包括：

- round；
- phase；
- action；
- message_id；
- prompt_version；
- 时间。

### Message

HLSF 消息来源：

- `hlsf_prompt`：阶段引导；
- `hlsf_hint`：按需提示；
- `assistant`：普通 AI 回复；
- `student`：学生消息。

### AiCall

任何 condition = B 的轮次（T1 或 T2）的 prompt version 记录为：

```text
chat-v2+hlsf-v1.10-evidence-reading-pilot
```

condition = A 的轮次：

```text
chat-v2
```

用于区分是否带入了 HLSF 教练上下文。

---

## 11. 当前实现的可复现性

当前 HLSF 是高度脚本化的（新 run 为 `hlsf-v1.10-evidence-reading-pilot`）：

- 四阶段固定；
- 阶段提示固定；
- 每阶段最多一条固定 hint；
- 新 run 提示版本固定为 `hlsf-v1.10-evidence-reading-pilot`；v1.9/v1.8/v1.7 run 保留原 version；
- 模型只负责在阶段规则下进行普通对话；
- 所有阶段进入、推进、跳过、提示和 AI 回复都有事件记录。

这意味着：

- B 组学生看到的阶段提示完全一致；
- 研究可以区分“固定干预”与“学生自由对话”；
- 可以分析学生是否跳过、是否使用提示、在哪个阶段停留；
- 不会因为模型自由生成不同阶段提示而产生干预漂移。

---

## 12. 当前边界与已知限制

### 12.1 不是自适应 Agent

当前不会：

- 自动判断学生理解水平；
- 自动识别学生卡点；
- 自动生成个性化阶段提示；
- 自动推进阶段。

### 12.2 HLSF 启用规则

当前代码：

```python
def _is_hlsf_round(round_obj):
    return round_obj.condition == "B"
```

因此：

- T1/T2 都可能启用 HLSF；
- T2 为 B 时使用 T2 Reflect 提示和开放作品说明；
- T1/T2 的 HLSF 状态按 round_id 隔离；
- 旧 v1.5 run 的 T2 仍是 A，不会因新代码获得 HLSF。

### 12.3 分组是四组平衡交叉

当前是：

```text
G1：X+A → Y+B
G2：Y+A → X+B
G3：X+B → Y+A
G4：Y+B → X+A
```

每班 30 人，目标配额 8/7/7/8 或 7/8/8/7；每班 T1 为 15 A / 15 B、15 X / 15 Y。四班合计每组 30 人。

这适合回答：

1. T1 的 A/B 随机对照（60 vs 60）；
2. 两轮重复测量中的 AI 条件、文物和轮次效应；
3. 先 HLSF 后普通 AI（G3/G4）的 T2 延续探索。

限制：

- 两轮是同一学生的重复测量，不能当成 240 个独立样本；
- T2 结果可能受 T1 学习经历影响，不能直接解释为纯即时 HLSF 效应；
- 顺序/携带效应需要在统计模型中考虑。

### 12.4 引导完成不是提交前置条件

学生可以跳过阶段、直接完成 T1；研究分析时需要结合 `HLSFEvent` 判断实际暴露，而不是只看“是否进入 B 组”。

### 12.5 提示文本是固定版本

修改 `PHASE_PROMPTS`、`PHASE_HINTS`、`DESIGN_COACH_B` 或 `PHASE_COACHING` 都会改变干预，需要：

- 提升 `HLSF_VERSION`；
- 重新冻结协议；
- 重新做 Pilot；
- 在导出中区分版本。

---

## 13. 相关文档

- `docs/PROTOCOL_CROSSOVER_V1_PILOT.md`：四组平衡交叉 Pilot 协议
- `docs/PROTOCOL_V15_FINAL.md`：旧 v1.5 协议冻结决策（保留历史）
- `docs/FORMAL_CONTENT_V15.md`：正式文物、题本、图片与选图
- `docs/V15_CHANGE_REPORT.md`：v1.5 变更报告
- `docs/FORMAL_READINESS_V15.md`：正式采集前缺口

---

## 14. 最简总结

```text
T1/T2 的 B 轮：
  固定四阶段
  → 每阶段一条固定提示
  → 每阶段最多一次固定 hint
  → 学生自由对话，LLM 按当前阶段规则回复
  → 学生手动 Next / Skip
  → 完成后普通 AI 继续可用

T1/T2 的 A 轮：
  普通 AI，无阶段、无提示、无教练上下文

T2：
  不继承 T1 的对话或 HLSF 状态；B 轮初始化新的四阶段状态
```

当前 HLSF 的核心不是“让 AI 自动教”，而是：

> **用固定的四阶段结构约束 AI 的教学行为，同时保留学生自由提问和自主设计空间。**
