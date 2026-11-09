# Heritage Learning Studio 平台完整介绍与技术交接手册

> 文档版本：v1.0（交接版）  
> 最后核对：2026-11-06（Asia/Shanghai）  
> 适用对象：准备接手本平台的研究者、研究助理、全栈开发者、部署运维人员  
> 代码基线：当前工作区 `new_direction/` 下的实际代码  
> 默认语言：中文；技术名词保留英文，便于对照代码

> **V2.0 测评与作品说明已实施（2026-11-07）：** 新 run 使用 `crossover-v1.1-assessment-v2-pilot` / `assessment_v2.0_pilot`，K0=5 baseline+6 MC、K1/K3=6 MC+1 后测短答、K2=6 MC、Survey=7，T1/T2 统一三段作品说明。权威说明见 **[ASSESSMENT_V2_PILOT.md](ASSESSMENT_V2_PILOT.md)**、**[ASSESSMENT_ITEM_BANK_V2_ZH.md](ASSESSMENT_ITEM_BANK_V2_ZH.md)**。旧 `formal_v1` / 六字段 / 开放说明仅保留历史数据读取。
>
> **v1.5 增量改造已实施（2026-11-06）：** T1/T2、K0–K3、六字段产品设计、B-only HLSF v1.5、互评与模拟 Instagram 已加入代码。当前实现的权威差异说明见 **[V15_CHANGE_REPORT.md](V15_CHANGE_REPORT.md)**、协议冻结记录 **[PROTOCOL_V15_FINAL.md](PROTOCOL_V15_FINAL.md)**、正式就绪清单 **[FORMAL_READINESS_V15.md](FORMAL_READINESS_V15.md)**、正式内容与中性界面 **[FORMAL_CONTENT_V15.md](FORMAL_CONTENT_V15.md)**、HLSF 当前框架 **[HLSF_CURRENT_FRAMEWORK.md](HLSF_CURRENT_FRAMEWORK.md)** 和本文件第 23 节。第 2–22 节保留为 v1.0 基线，用于理解历史数据、旧接口和迁移背景；不要用它们描述当前学生流程。

---

## 0. 文档定位与阅读方式

### 0.1 这份文档是什么

这是一份**按“接手者可以独立继续研究和开发”标准编写的平台说明书**。它不只描述“平台能做什么”，还尽量说明：

- 每个页面、每个环节、每个按钮实际调用哪个接口；
- 数据在什么时候、以什么结构写入哪张表；
- 服务端如何判定阶段、计时、权限和失败；
- 研究者如何准备材料、冻结协议、监控进度和导出数据；
- 代码在哪里、改哪里、改完要验证什么；
- 当前实现与 `reference/` 中 v1.3 研究方案书的差距，以及继续开发时的风险。

### 0.2 事实来源与优先级

出现不一致时，按以下优先级判断：

1. **当前代码**（`backend/app/`、`frontend/src/`、`backend/alembic/`、`docker-compose.yml`、`Caddyfile`）；
2. **自动化测试**（`backend/tests/`、`frontend/src/tests/`）；
3. **本文件**；
4. `docs/` 下的其他历史文档；
5. `reference/` 下的研究方案书/PPT（属于研究目标，不等于已实现功能）。

> **重要：** v1.5 已实现两件正式文物、M/T × A/B 题本、K0–K3、T1/T2 产品设计、HLSF v1.5、同伴互评、模拟 Instagram 与班级动态闸门。v1.3 与 v1.5 的差异全部按 v1.5 冻结，见 `PROTOCOL_V15_FINAL.md`。正式文物内容与中性学生界面见 `FORMAL_CONTENT_V15.md`；第 2–22 节保留为 v1.0 基线，不再代表当前学生流程。

### 0.3 一句话概括

**Heritage Learning Studio 是一个面向大学生的文化遗产 AI 共创研究平台：学生用 PolyU 邮箱和班级链接进入，先完成开始前的小问题与操作说明，再围绕两件正式文物各完成一次产品设计；中间穿插简短的“学习回顾”，最后完成体验问卷、匿名同伴互评和模拟作品广场；研究者在 `/admin` 配置不可变材料、冻结协议、监控进度并导出匿名研究数据。**

### 0.4 关键数字

| 项 | 值 |
|---|---:|
| 创作任务 | T1 / T2 两个任务 |
| 任务时长 | T1 约 24 分钟；T2 约 20 分钟 |
| 实验组 | G1–G4，共 4 组 |
| 条件 | 四组平衡交叉：G1/G2 T1 A→T2 B；G3/G4 T1 B→T2 A |
| 文物 | X / Y 两件 |
| 学生界面步骤 | 6 步 |
| 服务端阶段 | 13 个（v1.5；另保留 10 个 v1.0 旧标签） |
| 测评 | 5 个 kind |
| 题目类型 | 5 种 |
| 每轮图片任务上限 | 3 次 |
| 每轮成功关键帧 | 1 张 |
| 正式班 | 4 个 × 30 人 |
| 数据库表 | 29 张（v1.0 18 张 + v1.5 8 张 + 班级链接/闸门 3 张；另加 `alembic_version`） |
| 后台 tab | 3 个（总览、研究材料、准备检查） |
| email 模式 readiness 检查 | 13 项 |

### 0.5 快速导航

| 想了解 | 直接看 |
|---|---|
| 平台有哪些页面、每个按钮做什么 | 第 4 节（含 4.8 研究者后台） |
| 实验如何分组、A/B 是什么、谁得到学习引导 | 第 2 节、第 5 节 |
| 阶段如何流转、14 分钟如何计时 | 第 3 节 |
| 数据库每张表、每个字段 | 第 9 节 |
| 事件日志、AI 调用、图片任务如何审计 | 第 10 节 |
| 所有 API 的路径、权限、错误码 | 第 11 节 |
| 导出的 ZIP 里到底有什么 | 第 12 节 |
| 如何部署、备份、恢复、重置 | 第 15 节 |
| v1.5 新流程、互评、作品广场 | 第 23 节 + [V15_CHANGE_REPORT.md](V15_CHANGE_REPORT.md) |
| 代码结构、改哪里 | 第 16、21 节 |
| 当前实现和 v1.3 方案书的差距 | 第 19 节 |
| 已知问题、风险、待办 | 第 20 节 |
| 出问题怎么排查 | 第 22 节 |

### 0.6 读代码时先建立的四个概念

1. **Study Run（研究运行）**：一个参与者从进入到完成的整条记录，`runs` 表一行。
2. **Round（创作轮次）**：一次 14 分钟创作，`rounds` 表一行；每个 run 最多两行（round 1、round 2）。
3. **Stage（阶段）**：状态机中的当前位置，例如 `pre_test`、`round1_active`、`r1_test`。阶段由服务端写死在 `runs.stage`。
4. **Condition（条件）**：某一轮是 A（自由创作）还是 B（有 HLSF 学习引导）。条件不是参与者属性，而是**每一轮**的属性；同一个人两轮会各经历一次 A 和一次 B（见第 2 节）。

---

## 1. 平台概览

### 1.1 产品定位

- **研究对象**：大学生在文化遗产资料支持下使用生成式 AI 完成文化内容创作的学习活动。
- **当前任务形态**：点击阅读一件文物的章节化资料 → 与 AI 对话理解/讨论 → 完成产品名称、概念、六方面作品说明 → 生成 1 张产品概念图。
- **实验形态**：四组平衡交叉；每名学生两轮使用不同文物，恰好一次 Standard AI、一次 HLSF + AI；T1/T2 产品设计 + K0–K3 + 问卷 + 互评/作品广场。
- **平台角色**：学生端 + 研究者后台 + 服务端 AI 编排 + 研究数据导出。
- **当前状态**：v1.5 正式内容与界面已接入，可完整演示；**伦理同意、图片授权、专家审核、Pilot、30 人真实 Provider 压测、Docker/Caddy 仍待完成/验证**。

### 1.2 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18、TypeScript、Vite 5，无 React Router（按 `window.location.pathname` 分流） |
| 样式 | 单文件 `frontend/src/styles.css`，CSS 变量设计系统，无 UI 组件库 |
| 后端 | Python 3.9+（容器 3.12）、FastAPI、Pydantic v2、async SQLAlchemy 2、Alembic |
| 数据库 | PostgreSQL 16（本地测试用 `pgserver` 临时实例） |
| 文本模型 | OpenAI-compatible Chat Completions；模板使用 DeepSeek `deepseek-flash` |
| 图片模型 | OpenAI-compatible Images Generations；模板使用 Volcengine Ark / Doubao Seedream |
| 部署 | Docker Compose：`db`（Postgres）+ `api`（FastAPI）+ `caddy`（静态 SPA + 反代 + TLS） |
| 测试 | pytest + 真实临时 PostgreSQL；Vitest + Testing Library；Playwright |

### 1.3 部署拓扑

```text
Browser
  │ HTTPS 80/443
  ▼
Caddy ─── 静态 SPA（/srv/www，React build）
  │       └── /assets/* 长缓存
  └── reverse_proxy /api/* ──► FastAPI（api:8000，1 个 worker）
                                   │
                                   ├── PostgreSQL（db:5432，仅内部网络）
                                   └── /data 持久卷
                                        ├── artifacts/     文物图片
                                        ├── keyframes/     学生生成的关键帧
                                        ├── private/       旧 code 模式的访问码 CSV
                                        └── exports/       导出临时 ZIP
```

关键点：

- **只有 Caddy 发布 80/443**；数据库和 API 不发布宿主机端口。
- 前端和 API 同源，所以 session cookie 是同源 cookie，不需要 CORS。
- API 密钥只存在 API 容器环境变量中，浏览器永远拿不到。
- 当前设计假设**单个 API 进程**：图片 worker、内存限流器、聊天锁都在进程内。扩成多 worker 需要重新设计这些部分（见 20.3）。

### 1.4 目录总览

```text
new_direction/
├── backend/
│   ├── alembic/                 数据库迁移
│   ├── app/
│   │   ├── main.py              FastAPI 应用、生命周期、中间件
│   │   ├── config.py            环境变量与数据目录
│   │   ├── db.py                async engine / session
│   │   ├── models.py            全部 SQLAlchemy 表
│   │   ├── domain.py            阶段、组、条件、HLSF 常量与映射
│   │   ├── schemas.py           Pydantic 请求/测验 schema
│   │   ├── dependencies.py      session/cookie/认证依赖
│   │   ├── security.py          token、HMAC、限流
│   │   ├── errors.py            统一错误 envelope
│   │   ├── bootstrap.py         班级初始化、旧 code 模式 cohort
│   │   ├── cli.py               seed-demo / readiness
│   │   ├── routers/             auth/student/admin/files/health
│   │   ├── services/            业务逻辑（AI、HLSF、图片、导出等）
│   │   └── prompts/hlsf.py      HLSF 固定提示词与版本
│   ├── tests/                   后端测试
│   └── requirements*.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx              按路径分流学生/研究者
│   │   ├── api.ts               fetch 封装与 ApiError
│   │   ├── types.ts             前端类型
│   │   ├── pages/               学生页面 + AdminApp
│   │   ├── components/          通用组件、后台组件
│   │   └── styles.css           全部样式
│   ├── e2e/                     Playwright 测试（注意：部分已过时）
│   └── package.json
├── docs/                        架构、协议、安全、测试等文档
├── scripts/                     dev runtime、备份、恢复、部署检查、live smoke
├── reference/                   研究方案书、理论文档、文物资料（不是运行代码）
├── docker-compose.yml
├── Dockerfile.caddy
├── Caddyfile
├── Makefile
├── .env.example
└── README.md
```

### 1.5 当前状态速览

| 项目 | 状态 |
|---|---|
| 学生入口（PolyU 邮箱 + 班级） | 可用 |
| K0 / K1 / K2 / K3 / 体验问卷 | 可用（内容可配置，默认是 demo 占位） |
| T1/T2 产品设计（24/20 分钟） | 可用 |
| G1–G4 四组平衡交叉；T2 依组为 A/B | 可用（新 Pilot） |
| B 组 HLSF 四阶段引导 | 可用（`hlsf-v1.1.1`） |
| 文本 AI | 可用（真实 DeepSeek 已验证） |
| 图片队列 + 关键帧 | 可用（真实 Volcengine Ark 已验证） |
| 研究者后台 | 可用 |
| 同伴互评 / 模拟 Instagram 作品广场 | 可用（P1 最小实现） |
| 研究数据 ZIP 导出 | 可用 |
| Docker / Caddy / 公网 HTTPS | 配置存在，**未在交付环境实际验证** |
| 正式研究内容 / 伦理 / 评分 / 删除机制 | **未包含** |
| 同伴互评 / 模拟 Instagram / T2 迁移创作 / K0–K3 | **未实现**（v1.3 方案书内容） |

---

## 2. 研究设计与实验逻辑

### 2.1 当前研究设计（代码事实）

当前平台使用的是一套**两轮、四组平衡、组内交叉（within-subject crossover）**的设计：

- 每个参与者完成 **两轮创作**（Round 1、Round 2）。
- 每轮被分配一个 **文物**（X 或 Y）和一个 **条件**（A 或 B）。
- 四个组 G1–G4 覆盖“文物顺序 × 条件顺序”的四种组合：
  - G1：R1 = X+A，R2 = Y+B
  - G2：R1 = Y+A，R2 = X+B
  - G3：R1 = X+B，R2 = Y+A
  - G4：R1 = Y+B，R2 = X+A
- 因此：
  - 每个人在 **一轮中经历 A（自由创作）**，在 **另一轮中经历 B（HLSF 引导）**；
  - 每个人都会看到 X 和 Y 两件文物，只是顺序不同；
  - 不存在“某个人全程 A”或“全程 B”的组。
- G1/G2 的第一轮是 A；G3/G4 的第一轮是 B。这样第一轮的条件也做了平衡。

| 组 | Round 1 | Round 2 |
|---|---|---|
| G1 | 文物 X + 条件 A | 文物 Y + 条件 B |
| G2 | 文物 Y + 条件 A | 文物 X + 条件 B |
| G3 | 文物 X + 条件 B | 文物 Y + 条件 A |
| G4 | 文物 Y + 条件 B | 文物 X + 条件 A |

实现位置：`backend/app/domain.py` 的 `GROUP_ASSIGNMENTS` 和 `round_assignment()`。

> **与 v1.3 方案书的关键差异：** v1.3 推荐 A/B **between-subject**（每人只在一个条件），T1 训练、T2 撤除脚手架迁移；当前代码是每个人 **both conditions** 的 crossover。两者能回答的研究问题不同，不能把当前数据当成 v1.3 的 T1/T2 数据。

### 2.2 A 与 B 到底差什么

**A（自由创作）**

- 三栏工作台：文物资料、AI 对话、我的作品。
- AI 的基础系统提示只包含：通用创作助手角色、以证据为事实依据、不得编造、用学生语言回答、不暴露实验条件。
- 不显示学习引导、不发 HLSF 提示、不注入叙事教练上下文、不注入故事种子/最新脚本。
- 学生可以自由提问、讨论、要求 AI 帮写/改脚本。

**B（HLSF 引导创作）**

- 同样三栏、同样模型、同样证据、同样工具、同样 14 分钟、同样图片额度。
- 多出：
  1. 顶部“学习引导 / Learning Guide”阶段条（观察 → 解释 → 创作 → 反思）；
  2. 进入本轮时自动出现一条固定的“观察”阶段提示；
  3. 每个阶段可点一次“获取一次提示”，每阶段最多一次；
  4. 可点“下一阶段”或“跳过”推进；
  5. AI 请求额外带 B 专属的叙事教练系统提示、当前阶段教练目标、故事种子、以及 Create/Reflect 阶段的最新脚本；
  6. 所有提示/提示词/推进/跳过/回复都写入 HLSF 事件表。

**v1.10 新增（仅新 run，旧 run 行为不变）**

- **先问后总结**：AI 先就文物背景问一个简短问题，学生回答后用 2–3 句总结并标注章节；
- **章节号可点击**：回复中的 `M03` / `T02` 渲染为 chip，点击后左侧「文物资料」自动展开并滚动到该节（核对用，不是必做步骤）；
- **阶段停留提示**：同一阶段连续对话 ≥3 轮仍未推进时，弹出一次「要进入下一阶段吗？」对话框，可「获取一次提示」「进入下一阶段」或「继续对话」；关闭后本阶段不再出现，事件记入 `hlsf_events`。

**完全一致的部分（A/B parity）**

- 同一件文物证据包；
- 同一个文本模型、模型名、temperature、max tokens、timeout；
- 同一个图片模型、额度、尺寸；
- 同样的三栏界面、脚本编辑器、证据访问、关键帧工具；
- 同样的 14 分钟服务端计时；
- 同样“最多 3 次图片任务、最多 1 张成功关键帧”；
- 同样的事实约束、语言行为、失败提示；
- 学生界面永远不显示 group / condition / A/B。

### 2.3 班级、容量与分配

**班级**

- `CLASS_COUNT=4`，正式班级是 1–4。
- 班级 0 是内部测试班：
  - 仅非 production 环境存在；
  - 前端 dev build 显示 0–4，production build 只显示 1–4；
  - 后端 production 直接拒绝 `class_id=0`；
  - 班级 0 不设人数上限；
  - 本地/测试数据应放在班级 0，正式分析只用 1–4。
- 每个正式班默认容量 `PARTICIPANTS_PER_CLASS=30`。

**邮箱登录**

- 学生输入任意包含子串 `polyu`（不区分大小写）的非空字符串即可进入。
- 服务端会 `trim().lower()` 后作为唯一邮箱存储。
- 这不是真正的身份认证：不验证邮箱所有权，任何人输入一个含 `polyu` 的字符串都能进入；同一个人可以用不同邮箱创建多个账号。当前靠人工监控。
- 同一邮箱再次进入：
  - 同班级 → 恢复同一个 participant/run；
  - 不同班级 → 409 `email_class_mismatch`。
- 邮箱明文存储在 `participants.email`，唯一索引；只在研究者后台显示，**不进入研究导出**。

**组分配算法**

对每个班独立做“四人一块”的洗牌：

```text
index = 该班已存在的 email 参与者数量（用于新用户）
block_no, position = divmod(index, 4)
order = shuffle(["G1","G2","G3","G4"], seed=HMAC(pepper, "hlsf-block:{class_id}:{block_no}"))
group = order[position]
```

- 每个完整的 block 恰好包含 G1–G4 各一次。
- 30 人时，前 28 人组成 7 个完整 block，最后 2 人落在第 8 个 block 的前两个位置；实际人数约为 8/8/7/7（取决于 block 边界）。
- seed 来自服务端 `ANON_CODE_PEPPER`，客户端不可预测。
- 新用户分配在班级行 `SELECT ... FOR UPDATE` 下串行执行，避免并发拿到同一个位置。
- 重新登录不消耗新位置。

**风险点**

- 容量检查只统计 `email IS NOT NULL` 的参与者。如果同一个班同时存在旧的 code 参与者，`alias_count` 不会把他们算进去，可能导致组平衡偏移。正式部署应使用全新数据库（email 模式不预生成 code 参与者）。
- 修改 `ANON_CODE_PEPPER` 会改变后续 block 的洗牌顺序；**参与者一旦开始分配，绝不能改 pepper**。

### 2.4 两轮创作任务

每一轮的任务结构相同：

1. 阅读左侧文物资料（图片、年代、类型、简介、历史事实、来源证据、待探究）；
2. 与 AI 对话；
3. 在右侧写：
   - 视频标题（前端最多 50 字，后端最多 200 字符）；
   - 视频脚本（前端最多 10000 字符，建议 140–180 字，超过 180 有提示）；
4. 生成 1 张关键帧（需要先有非空脚本；最多 3 次任务；成功后不能再生成）；
5. 点“保存并继续”结束本轮，或等到 14 分钟超时。

**不强制完整**：允许空脚本/无关键帧结束，前端会二次确认；研究数据里保留完整性状态（脚本是否为空、是否有成功关键帧、结束原因）。

**服务端计时**：点击“开始本轮”才启动 deadline；断网/关页面不暂停；服务端在每次学生请求时惰性检查是否超时并推进阶段。

### 2.5 五个测评

| 阶段 | `kind` | 位置 | 作用 | 默认 demo 内容 |
|---|---|---|---|---|
| 前测 | `pre_test` | 入口之后、R1 之前 | 基线 | 1 道单选占位 |
| R1 独立测试 | `r1_test` | R1 之后、R2 之前 | 禁用 AI 的独立测试 | 1 道简答占位 |
| 后测 | `post_test` | R2 之后 | 后测 | 1 道单选占位 |
| 迁移题 | `transfer` | 后测之后 | 迁移任务（当前只是问卷式 instrument，不是 v1.3 的 T2 创作） | 1 道简答占位 |
| 问卷 | `questionnaire` | 最后 | 体验/背景问卷 | 1 道 5 点 Likert 占位 |

- 每个测评是 **协议冻结时选定的 `instrument_versions` 版本**。
- 题目类型：单选、多选、简答、证据判断（行 × 是/否）、Likert。
- 支持自动保存草稿；提交后不可修改；不做自动评分。
- **测评没有服务端倒计时**；只有创作轮有 14 分钟 deadline。`duration_seconds` 记录从草稿创建到提交的时间。

### 2.6 时间预算

> **v1.5 current:** T1 24 min + T2 20 min + assessments/peer/social ≈94 min; see section 23.

界面文案写“约 60 分钟”，由 5 个步骤组成：

| 步骤 | 环节 | 服务端是否强制时长 |
|---|---|---|
| 1 | 入口 + 前测 | 否 |
| 2 | 任务 1（14 分钟） | 是，840 秒 |
| 3 | R1 独立测试 | 否 |
| 4 | 任务 2（14 分钟） | 是，840 秒 |
| 5 | 后测 + 迁移 + 问卷 | 否 |

实际总时长取决于学生做测评的速度。`ROUND_DURATION_SECONDS` 可配置，但前端文案仍写“14 分钟”；修改时长时需要同步修改前端文案与测试。

### 2.7 完整学生旅程（按时间顺序）

```text
打开 /
  → 输入 PolyU 邮箱 + 班级
  → 服务端创建/恢复 participant/run（stage=pre_test）
  → 前测（可自动保存，提交）
  → round1_ready：任务说明 + “开始本轮”
  → round1_active：14 分钟三栏工作台
       左侧证据 / 中间 AI（B 有引导）/ 右侧脚本 + 关键帧
  → 点“保存并继续”或超时
  → r1_test：禁用 AI 的独立测试
  → round2_ready：第二轮任务说明
  → round2_active：第二轮三栏工作台（另一件文物、另一种条件）
  → post_test
  → transfer
  → questionnaire
  → complete：完成页，可退出
```

---

## 3. 状态机、计时与恢复

### 3.1 十个阶段

定义在 `backend/app/domain.py`：

| 阶段 | 中文标签 | 前端页面 | 下一步 |
|---|---|---|---|
| `pre_test` | 前测 / Pre-test | 测评页 | 提交 → `round1_ready` |
| `round1_ready` | 任务 1 / Task 1 | 任务说明页 | 开始 → `round1_active` |
| `round1_active` | 任务 1 / Task 1 | 工作台 | 完成/超时 → `r1_test` |
| `r1_test` | R1 独立测试 / Round 1 Assessment | 测评页（AI 禁用） | 提交 → `round2_ready` |
| `round2_ready` | 任务 2 / Task 2 | 任务说明页 | 开始 → `round2_active` |
| `round2_active` | 任务 2 / Task 2 | 工作台 | 完成/超时 → `post_test` |
| `post_test` | 后测 / Post-test | 测评页 | 提交 → `transfer` |
| `transfer` | 迁移题 / Transfer Task | 测评页 | 提交 → `questionnaire` |
| `questionnaire` | 问卷 / Questionnaire | 测评页 | 提交 → `complete` |
| `complete` | 完成 / Complete | 完成页 | 终止 |

`STEP_BY_STAGE` 把阶段映射到界面上的 5 步：

| 步骤 | 阶段 |
|---|---|
| 1 | `pre_test` |
| 2 | `round1_ready`、`round1_active` |
| 3 | `r1_test` |
| 4 | `round2_ready`、`round2_active` |
| 5 | `post_test`、`transfer`、`questionnaire`、`complete` |

### 3.2 状态推进由谁控制

**全部由服务端控制。** 前端不保存“我在第几步”，只根据 `GET /api/student/state` 返回的 `stage` 渲染。直接改 URL 不能跳阶段，因为：

- `/` 是单页应用，路由只有 `/` 和 `/admin`；
- 阶段来自数据库；
- 所有写接口都会检查 `run.stage` 和 `round` 状态。

### 3.3 计时语义

- 开始：`POST /api/student/rounds/{n}/start`，服务端写入 `started_at`、`deadline_at = started_at + ROUND_DURATION_SECONDS`。
- 倒计时：前端 `useCountdown` 每 500ms 根据 `deadline_at` 计算；最后 120 秒变红。
- 服务端权威：每次学生请求先 `_load_run()`，若处于 active round 且 `deadline_at <= now`，调用 `sync_expired_stage()`：
  - 把 `round.finished_at` 设为 `deadline_at`；
  - `finish_reason="timeout"`；
  - 推进到 `r1_test` 或 `post_test`；
  - 记录 `stage_events.meta_json={"reason":"timeout","round_no":n}`。
- 到期后的写请求：`round_expired` 409。
- 学生自己点完成：如果当前时间 <= deadline，`finish_reason="student_finished"`；否则按 timeout 处理，`finished_at=deadline_at`。
- 重复完成：如果 round 已 finished，`finish_round` 直接返回；路由在阶段已变化时返回当前 state，不报错。

### 3.4 刷新、断网、关页面

- 刷新：`StudentApp` 重新 `GET /api/student/state`，然后按阶段加载页面。
- 工作台刷新：重新并行拉 `rounds/{n}` 和 `messages`，脚本/聊天/关键帧/引导状态都从服务端恢复。
- 本地草稿：
  - 脚本：`localStorage["hls:script:{runId}:{roundNo}:{artifactId}"]`；
  - 测评：`localStorage["hls:assessment:{runId}:{kind}"]`；
  - 本地只是崩溃备份，**不会自动覆盖服务端**；必须点“恢复”。
- 网络恢复：页面每 10 秒静默轮询 state；聊天在等待回复时每 3 秒轮询消息；图片任务每 2 秒轮询。
- 断网不会暂停计时；服务端 deadline 仍然生效。
- 页面关闭不会提交，但已自动保存的脚本/草稿/事件仍在服务端。

### 3.5 R1 独立测试的“AI 禁用”如何实现

- 阶段变为 `r1_test` 后，`run.stage` 不再等于 `round1_active`，所有 round 级接口（chat/script/image/HLSF/evidence）都会 `require_active_round` 失败（`stage_not_active`）。
- 前端只渲染测评页，不渲染工作台；顶部显示“此页面为独立测试阶段，无法使用 AI 对话”。
- 这是服务端能力锁定，不是仅隐藏按钮。

### 3.6 并发与竞态

| 场景 | 机制 |
|---|---|
| 同一班同时新登录 | `SELECT classes ... FOR UPDATE` 串行分配 |
| 同一 run 同时创建测评草稿 | `SELECT runs ... FOR UPDATE` 串行 |
| 同一 round 同时保存脚本 | `SELECT rounds ... FOR UPDATE`，相同内容不产生新版本 |
| 同一 round 同时发两条聊天 | 服务端检查“最后一条必须是 assistant”；前端在 pending 时禁用发送；应用内每 round 一个 `asyncio.Lock` |
| 同一 round 同时创建图片任务 | 锁定 round，检查已有 queued/running/succeeded，再插入 |
| 多个图片 worker 抢任务 | `FOR UPDATE SKIP LOCKED` |
| 同一消息重试 | 只允许最新一条未回复的 user 消息；`message_not_latest` 409 |

> 这些锁大多依赖**单 API 进程**；多进程/多副本部署时，应用内 `chat_locks`、内存限流器不再全局有效。

---

## 4. 学生端页面与交互

### 4.0 页面/环节（“节目”）清单

| # | 页面/环节 | 触发条件 | React 组件 | 主要接口 | 产生/更新数据 |
|---|---|---|---|---|---|
| 1 | 学生入口 | 未登录 | `EntryPage` | `POST /api/auth/enter` | participant、run、session、初始 stage_event |
| 2 | 前测 | `stage=pre_test` | `AssessmentPage` | `GET /instruments/pre_test`、`PUT draft`、`POST submit` | assessment_responses、stage_events |
| 3 | R1 任务说明 | `stage=round1_ready` | `ReadyPage` | `POST /rounds/1/start` | round、stage_events、B 的 hlsf_state/message |
| 4 | R1 工作台 | `stage=round1_active` | `Workbench` | `GET /rounds/1`、messages、script、image、hlsf、evidence | scripts、messages、image_jobs、evidence_events、hlsf_events、ai_calls |
| 5 | R1 独立测试 | `stage=r1_test` | `AssessmentPage` | 同测评 | assessment_responses、stage_events |
| 6 | R2 任务说明 | `stage=round2_ready` | `ReadyPage` | `POST /rounds/2/start` | round、stage_events、B 的 HLSF 初始化 |
| 7 | R2 工作台 | `stage=round2_active` | `Workbench` | 同工作台 | 同上 |
| 8 | 后测 | `stage=post_test` | `AssessmentPage` | 同测评 | assessment_responses、stage_events |
| 9 | 迁移题 | `stage=transfer` | `AssessmentPage` | 同测评 | assessment_responses、stage_events |
| 10 | 问卷 | `stage=questionnaire` | `AssessmentPage` | 同测评 | assessment_responses、stage_events |
| 11 | 完成页 | `stage=complete` | `CompletePage` | `POST /api/auth/logout` | session.revoked_at、清 localStorage |
| 12 | 研究者登录 | `/admin` 未登录 | `AdminLogin` | `POST /api/admin/login` | admin session |
| 13 | 研究总览 | `/admin` 已登录，tab=overview | `AdminOverview` | `GET /api/admin/overview` | 只读 |
| 14 | 研究材料 | tab=content | `AdminContent` | `GET /api/admin/artifacts`、`POST /api/admin/artifacts/{slot}/versions`、`GET /api/admin/instruments`、`POST /api/admin/instruments/{kind}/versions` | 新版本 artifact/instrument |
| 15 | 准备检查/冻结协议 | tab=readiness | `AdminReadiness` | `GET /api/admin/readiness`、`POST /api/admin/protocol/activate` | protocol_versions |
| 16 | 参与者详情 | 点击列表“查看” | `ParticipantDetail` | `GET /api/admin/participants/{id}` | 只读 |
| 17 | 系统健康 | 直接访问 | 无 UI | `/api/health/live|ready` | 只读 |
| 18 | API 文档 | 非 production | Swagger UI | `/api/docs` | 只读 |

> 没有独立 URL 路由；学生页面全部挂在 `/`，后台挂在 `/admin`。刷新后从服务端 state 恢复。

#### 4.0.1 界面参考截图

以下截图来自本地测试环境，用于快速建立视觉印象；其中后台截图拍摄于 email 改造前，列表/文案可能已变化，仅作布局参考。

**学生入口**

![学生入口](../e2e/screenshots/email-entry.png)

**B 组工作台（三栏 + 学习引导）**

![B 组工作台](../e2e/screenshots/workbench-resumed.png)

**完成页**

![完成页](../e2e/screenshots/participant-complete.png)

**研究者总览（历史截图，仅布局参考）**

![研究者总览](../e2e/screenshots/admin-overview.png)


### 4.1 学生入口页 `/`

组件：`frontend/src/pages/EntryPage.tsx`

**布局**

- 顶栏：品牌 `Heritage Learning Studio`、`学生模式 / Student Mode`、右侧 `研究者后台 / Researcher` 链接。
- 左侧：圆形“文”字徽章、场景引言（“假设博物馆正在策划一场丝绸文化主题推广活动……”）、共创任务说明（“邀请你使用我们的设计平台与 AI 一起共创……”）、94 分钟工作坊说明、隐私提示。
- 右侧：
  - “进入平台 / Enter the Platform”面板，步骤徽章“第 1 步 / Step 1”；
  - PolyU 邮箱输入框；
  - 班级下拉：dev 环境 `[0,1,2,3,4]`，production 构建 `[1,2,3,4]`；
  - “开始实验 / Start Experiment”按钮；
  - 恢复说明；
  - 下方“实验安排 / Workshop Schedule”卡片（5 步）。

**交互**

1. 输入邮箱；class 默认 dev=0、prod=1。
2. 点击开始 → `POST /api/auth/enter`，body `{email, class_id}`。
3. 成功返回 `{state}`；`onEnter(state)` 直接把页面切到对应阶段（不跳 URL）。
4. 失败显示 `ErrorNotice`，带 request_id（如果有）。

**服务端行为**

- 限流：每 IP 600 秒内 200 次 `enter`。
- 校验 class 存在；production 拒绝 class 0。
- 邮箱必须包含 `polyu`（小写化后判断）。
- 新邮箱：检查容量 → 计算 group → 创建 participant。
- 旧邮箱：同班恢复；异班 409。
- 创建/恢复 run：如果不存在 run，必须有 active protocol；production 不允许 demo protocol。
- 创建新的 opaque student session，写 cookie `hls_student`。
- 返回学生 state。

**不存在的功能**

- 没有密码、验证码、SSO、邮箱验证；
- 没有知情同意页；
- 没有“退出当前账号”按钮（除非到完成页或清 cookie）；
- 没有多语言切换（中英是并排显示）。

### 4.2 通用学生界面元素

| 元素 | 说明 |
|---|---|
| `BrandMark` | 建筑/柱式 SVG + 标题 + 副标题“AI-Assisted Cultural Heritage Learning & Creation” |
| 顶栏 | 学生页显示品牌、模式、步骤；工作台是紧凑版 |
| `StageSchedule` | 5 步实验安排卡片；当前步骤高亮，之前步骤标 done |
| 步骤徽章 | “第 X 步 / Step X of 5” |
| `Bilingual` | 中文 + 小号灰色英文，不是 i18n 切换 |
| `Spinner` | `role=status`，带中英 loading 文案 |
| `ErrorNotice` | `role=alert`，显示 message、request_id、可选“重试” |
| 响应式 | ≤1200px 缩窄；≤900px 单列；≤560px 更紧凑；打印时隐藏顶栏/按钮/输入区 |

### 4.2b 语言与双语约定

平台**不提供语言切换**，统一采用“中文主 + 英文副”的固定双语排版（实现见 `styles.css` 的 `.en`）：

- **控件、状态与细节提示 100% 双语**：按钮、标签、必填标记、配额徽章、字段提示（`field-hint`）、输入框占位示例、错误、空状态、进度与提示条都带英文；
- **叙事性长文以中文为主**，配英文小标题或英文摘要（如准备页 `lede`、完成页说明）；
- **内容提供英文对照，但只作理解辅助**：
  - 文物资料：英文放在 `backend/app/content/formal_v2/artifacts_en.json`，读取时按章节合并进学生端 payload（`services/artifacts.py`），每个中文段落下显示对应英文段，标题下显示英文标题；**不进入文物版本、评分或导出字段**；
  - 测评题：`instruments.json` 的题干用 `prompt_en`、选项用 `label_en`，说明用 `instructions_en`；中文题干与选项值仍是唯一的答题与计分依据，题序、正确项、分值均不变；
  - AI 回复本身按学生提问语言生成。

规则：英文一律以较小的灰色字呈现，中文为正文；英译不得改变选项值、题目顺序或任何计分逻辑。若将来要出正式英文版（英文独立测量），应作为测量工具的改版单独设计。

### 4.3 测评页（五个 kind 共用）

组件：`frontend/src/pages/AssessmentPage.tsx`

**进入条件**

`GET /api/student/state` 返回 `assessment_kind` 非空，即当前 stage 是 `pre_test`、`r1_test`、`post_test`、`transfer`、`questionnaire` 之一。

**布局**

- 顶栏：品牌 + 当前测评标签 + 步骤徽章。
- 主区：
  - `r1_test` 显示黄色警告条“此页面为独立测试阶段，无法使用 AI 对话”；
  - 面板标题、说明、版本号 `vN`；
  - 可选“本地草稿”提示，带“恢复本地草稿 / 使用服务器版本”；
  - 题目列表；
  - 底部自动保存状态 + “提交 / Submit”；
  - 提交错误。
- 侧栏：实验安排 + “匿名学习数据 / Anonymous learning data”说明（提交后不能返回修改；不显示分数）。
- K0 的“开始前”分组从 `content_version = v2.2-demographics` 起包含 5 题：学习背景、AI 使用频率、文创/遗产训练经历、年龄段（B-04）、性别（B-05）；年龄与性别都提供“不愿透露”，且不参与任何知识分。

**题目渲染**

| 类型 | 控件 | 答案结构 |
|---|---|---|
| `single_choice` | 单选 radio | `string`（option.value） |
| `multi_choice` | 多选 checkbox | `string[]`（去重） |
| `short_text` | textarea + 字数 | `string` |
| `evidence_judgment` | 表格：每行 是/否 | `{row_id: "yes"|"no"}` |
| `likert` | 数字 radio + 可选标签 | `number` |

**自动保存**

- 用户每次修改 → 立即写 `localStorage["hls:assessment:{runId}:{kind}"]`；
- 900ms 防抖后 `PUT /api/student/instruments/{kind}/draft`；
- 显示“正在保存/已自动保存/自动保存失败”；
- 服务端是权威；本地草稿仅在刷新后发现与服务端不同时提示恢复。

**提交**

- `POST /api/student/instruments/{kind}/submit`，带当前 `answers`；
- 服务端校验所有 required；
- 成功后：`status=submitted`、`submitted_at`、`duration_seconds`，阶段推进；
- 前端清本地草稿，`onState` 切换页面；
- 不能重复提交（409 `assessment_submitted`）。

**注意**

- 页面没有倒计时；测评时长不受服务端限制。
- 没有分数、没有正确答案、没有逐题保存时间。
- 如果题目 schema 中有未知字段，前端不会渲染；后端草稿保存会拒绝未知 question id（422）。
- Pydantic 请求校验失败（例如 422 的 body 结构错误）返回 FastAPI 默认 `{"detail": ...}`，前端 `ApiError` 只认 `error` 字段，因此可能只显示“Request failed (HTTP 422)”；这是已知 UX 问题（见 20.2）。

### 4.4 任务说明页（R1/R2）

组件：`frontend/src/pages/ReadyPage.tsx`

**布局**

- 顶栏：`任务 1 / Task 1` 或 `任务 2 / Task 2`，阶段标签，步骤徽章。
- 主面板：
  - eyebrow、标题“文物创作：脚本与关键帧” / “第二次文物创作”、英文副标题；
  - 描述：14 分钟内完成标题、脚本、1 张关键帧；
  - 三张 brief 卡：14 分钟、1 份脚本、1 张关键帧；
  - 提示：点击后开始计时、断网不暂停、自动保存；
  - 错误提示；
  - “开始本轮 / Start Round”。
- 侧栏：实验安排 + 匿名编号提醒。

**交互**

- 只有点击开始才 `POST /api/student/rounds/{n}/start`，此时才创建 round、写 deadline、B 组初始化 HLSF。
- 开始前不展示文物内容；学生不知道本轮是 X 还是 Y，也不知道 A/B。
- 成功返回 `{state, round}`；`onState(state)` 进入工作台。
- 失败可能：`stage_not_ready`（已不是 ready）、`round_already_started`、未登录、网络。

### 4.5 创作工作台（核心页面）

组件：`frontend/src/pages/Workbench.tsx`

**加载流程**

```text
Worker 挂载
  → 并行 GET /api/student/rounds/{n}
  →       GET /api/student/rounds/{n}/messages
  → setRoundData / setMessages / setGuide
```

失败显示错误 + “同步当前阶段 / Sync stage”。

**顶栏**

- 紧凑品牌；
- `Task {n} of 2` + 文物标题；
- 倒计时胶囊（剩余时间，最后 120 秒变红，`aria-live`）；
- 保存状态（保存中/已自动保存/未保存/保存失败）；
- 匿名参与者 chip：UUID 前 6 位大写。

**三栏布局**

```text
┌──────────────┬──────────────────────┬──────────────────┐
│ 文物资料      │ AI 对话 + 学习引导     │ 我的作品          │
│ 图片/简介/事实 │ 消息流/输入框          │ 标题/脚本/关键帧   │
│ 证据/不确定性  │ B 才有阶段条           │ 保存并继续         │
└──────────────┴──────────────────────┴──────────────────┘
```

桌面：`minmax(290px,.95fr) minmax(400px,1.4fr) minmax(330px,1.08fr)`；≤1200px 缩窄；≤900px 单列，聊天区 `max-height:52vh`。

#### 4.5.1 左栏：文物资料 / Artifact Evidence

- 文物图片（3:2，`object-fit: cover`），右下角放大链接，新标签打开原图（受保护接口）。
- 标题、年代/类型。
- 可折叠区块：
  1. **文物简介 / Introduction**（默认展开；包含简介和 facts 列表）
  2. **历史事实 / Historical Facts**
  3. **相关证据 / Related Evidence**
  4. **仍待探究 / Uncertainty**（没有配置时不显示）
- 底部提示：“AI 只能依据以上证据回答。资料不足时，请主动指出不确定之处。”
- 事件记录：
  - 进入面板时记录 `section="artifact"`；
  - 展开简介/事实/证据/不确定性分别记录 `introduction`/`facts`/`evidence`/`uncertainty`；
  - 同一面板会话内去重（`useRef(Set)`）；
  - `POST /rounds/{n}/evidence-events`，`event_type="view"`，`duration_ms` 不传（null）；
  - 失败在底部显示“部分资料查看事件未能保存”。
- 图片通过 `/api/files/artifacts/{version_id}/image`，学生只能看自己 run 中出现的版本。

#### 4.5.2 中栏：AI 对话 / AI Chat

- 标题“AI 对话 / AI Chat”；B 组额外显示“· HLSF-Guided Creation”和“学习引导 / Learning Guide”chip。
- 空状态：AI 头像 + “你可以询问文物资料、讨论文化含义，或请 AI 帮助你改进脚本。”
- 消息：
  - 用户消息右侧，带“你”标记；
  - 助手消息左侧，带“AI”头像；
  - `source` 为 `hlsf_prompt` 或 `hlsf_hint` 时显示“学习引导 / Learning Guide”或“针对性提示 / Hint”标签；
  - 显示本地时间 HH:mm。
- 发送：
  - textarea 最多 4000 字；
  - `⌘/Ctrl + Enter` 发送；
  - 发送按钮 `aria-label="Send message"`；
  - 生成 `client_message_id = crypto.randomUUID()`（或 fallback）；
  - `POST /rounds/{n}/messages`；
  - 成功后追加 user + assistant 两条消息，清空输入；
  - 失败显示错误，并重新拉取消息；若最后一条是 user，显示“重试这条消息”。
- 等待回复：
  - 最后一条是 user 时 `pending=true`，输入框禁用；
  - 每 3 秒 `GET messages` 轮询；
  - 75 秒仍未回复 → 显示错误 + 重试按钮；
  - 服务端聊天是同步的，请求可能持续到文本模型 timeout。
- 重试：
  - `POST /rounds/{n}/messages/{message_id}/retry`；
  - 只允许最新一条未回复的 user 消息；
  - 会创建新的 AI 调用（purpose=`chat_retry`），不会重复插入 user 消息。
- 幂等：
  - 同一 round 的 `client_message_id` 唯一；
  - 重复 POST 同一 id 返回 `{duplicate:true, messages:[原 user 消息]}`，不会再调模型。
- 错误状态：
  - 文本模型未配置 503；
  - 超时 504；
  - 上游错误 502；
  - 上一条未回复 409 `message_pending`。

**B 组学习引导条**

- 四个阶段：观察 Observe → 解释 Explain → 创作 Create → 反思 Reflect；
- 状态：done（已过）/ current（当前）/ upcoming（未到）；
- 完成时显示“学习引导已完成 / Guide complete”；
- 当前阶段操作：
  - “获取一次提示 / Hint”：每阶段一次；用过后按钮变“本阶段提示已使用”并禁用；
  - “下一阶段 / Next”：推进并插入下一阶段固定提示；
  - “跳过 / Skip”：推进，但事件 action=`skipped`。
- 操作期间 `guideBusy` 禁用；错误显示在聊天区。

**A 组**

- 不显示引导条、不显示 HLSF chip；
- 不发初始 HLSF 提示；
- `guide` 为 null。

#### 4.5.3 右栏：我的作品 / My Creation

- 标题 + 版本 chip `v{revision}`。
- 本地草稿提示（如果有）：“恢复 / 忽略”。
- **视频标题**：
  - `#script-title`，前端 `maxLength=50`，必填提示；
  - 字数 `N / 50`（按 Unicode code point 计数）。
- **视频脚本**：
  - `#script-body`，`maxLength=10000`，建议 140–180 字；
  - 字数 `N / 建议 180`；
  - 超过 180 显示黄色提示“已超过建议长度；请确认脚本仍然紧凑。”
- 自动保存：
  - 修改后 1 秒防抖 `PUT /rounds/{n}/script`；
  - 保存中显示“保存中…”；
  - 成功且内容未再变 → “已自动保存”；
  - 保存期间又有修改 → 标“未保存”，500ms 后再保存；
  - 失败显示错误 + “保存失败”；
  - 本地 `localStorage` 立即备份。
- 关键帧：
  - 标题“关键帧 / Key Frame”；额度 `生成额度 {jobs.length}/{limit}`；
  - 成功：显示图片 + “关键帧已生成”；
  - 排队/生成：占位动画 + “图片任务排队中…”/“正在生成关键帧…”；
  - 失败：错误信息 + “重试生成 / Retry”；
  - 生成按钮：`生成关键帧 / Generate Key Frame`；
  - 禁用条件：已锁定、生成中、有 active job、已有成功、额度用完、脚本为空；
  - 额度用完显示“生成额度已用完 / Quota used”；
  - 每 2 秒轮询 active job 状态；
  - 失败原因会显示 `error_message` 或 `error_code`。
- 底部：
  - 保存状态；
  - “✓ 保存并继续 / Save & Continue”；
  - 点击时：
    1. 若脚本非空且没有成功关键帧 → `window.confirm` 询问是否仍结束；
    2. 若脚本为空 → 再次 confirm；
    3. 先 `saveNow()`；
    4. `POST /rounds/{n}/finish`；
    5. 清本地脚本草稿；
    6. `onState(result.state)` + `onRefresh(true)`。
- 锁定态（超时/倒计时为 0）：
  - 页面顶部黄色 banner“本轮时间已结束，正在保存最后的记录并进入下一阶段…”；
  - 所有输入/按钮禁用；
  - 1.2 秒后静默刷新 state，服务端会推进阶段。

**保存失败/并发细节**

- `saveInFlight` 防止同一时刻多个 PUT；
- 保存的是 `latestValues.current` 快照，若保存期间又有编辑，会在 500ms 后再次保存；
- 后端相同 title+body 不产生新 revision（`created=false`）。

### 4.6 完成页

组件：`frontend/src/pages/CompletePage.tsx`

- 顶栏品牌 + “完成 / Complete”徽章。
- 绿色对勾、标题“实验已完成 / Experiment complete”。
- 感谢文案：对话、脚本、关键帧、问卷已保存；研究者只按匿名编号分析。
- 元信息：班级名 + 匿名编号（UUID 前 8 位大写）。
- “结束并退出 / Exit”：
  - `POST /api/auth/logout`；
  - 清所有 `hls:` 开头的 localStorage；
  - `window.location.href="/"`。
- 提示“现在可以安全关闭浏览器页面。”

### 4.7 学生端视觉与可访问性

- 设计语言：纸张米色背景、深蓝主色、金色点缀、衬线标题 + 无衬线正文；中英并排。
- 主要色值：`--paper #f7f4ed`、`--surface #fffdf8`、`--ink #28333a`、`--navy #385a73`、`--gold #b49a72`、`--green #4d7a62`、`--red #a24e43`。
- 字体：标题 `Iowan Old Style / Songti SC / STSong / Noto Serif CJK SC / Georgia`；正文系统 sans（PingFang SC / Microsoft YaHei 等）。
- CSS 变量集中在 `frontend/src/styles.css` 的 `:root`。
- 断点：1200 / 900 / 560；打印隐藏顶栏、按钮、聊天输入、创作 footer。
- 可访问性：
  - 主要输入有 `aria-label`；
  - 错误 `role=alert`；
  - spinner `role=status`；
  - 倒计时最后 120 秒 `aria-live=polite`；
  - 题目用 `fieldset/legend`；
  - 图片有 alt；
  - 但**没有完整的键盘焦点样式、跳过导航、屏幕阅读器全流程测试**。
- 没有暗色模式、没有语言切换、没有路由动画（除滚动到顶部）。

### 4.8 研究者后台（`/admin`）

组件：`frontend/src/pages/AdminApp.tsx` + `components/Admin*.tsx` + `ParticipantDetail.tsx`

#### 4.8.0 入口、认证与导航

- `/admin` 由 `App.tsx` 按路径分流到 `AdminApp`。
- 未登录时显示 `AdminLogin`：只有一个“研究者密码 / Researcher password”输入框。
- 登录成功写 `hls_admin` cookie；`AdminApp` 重新 `GET /api/admin/overview`。
- 顶栏：
  - 紧凑品牌；
  - “研究者后台 / Researcher Console”徽章；
  - 三个 tab：`总览`、`研究材料`、`准备检查`；
  - `学生入口` 链接（`/`）；
  - `退出登录`（`POST /api/admin/logout`）。
- 登录失败：
  - 401 `admin_invalid`；
  - 429 `too_many_attempts`（6 次/10 分钟/IP）；
  - 503 `admin_not_configured`。
- 没有用户名、角色、多用户、MFA、操作审计。
- `AdminApp` 加载 overview 时：
  - 401 → 显示登录页；
  - 其他错误 → 顶部全局错误 + 重试；
  - 已登录但 overview 失败且无数据 → 居中错误页。

#### 4.8.1 总览 / Overview

组件：`components/AdminOverview.tsx`

**顶部**

- 标题“实验进度 / Research overview”。
- 右侧：
  - `刷新 / Refresh`（重新加载 overview）；
  - `导出完整研究数据`（普通链接到 `/api/admin/export`，浏览器下载 ZIP）。
- 如果 `readiness.ready_for_students=false`，显示黄色警告“研究尚未准备完毕…”。

**统计卡**

| 卡 | 数据 |
|---|---|
| 参与者 | `counts.participants` |
| 已进入实验 | `counts.started`（有 run 的人数） |
| 已完成 | `counts.completed`（stage=complete） |
| 图片并发上限 | 当前只是占位显示“服务端配置”/“—”，不是真实运行指标 |

**分组/阶段分布**

- 分组：G1–G4 横向条形图，按 `counts.by_group`。
- 阶段：`counts.by_stage` 的 key/value 列表（key 是英文 stage，如 `complete`、`round1_active`、`not_started`）。

**参与者列表**

- 搜索框：匹配 participant UUID、邮箱、code 后 4 位、班级名。
- 筛选：全部班级 / 全部小组 / 全部阶段。
- 表格列：
  - 参与者（UUID 前 8 位 + 邮箱或 `••••last4`）
  - 班级
  - 分组 badge（G1–G4）
  - 阶段（中文 label）
  - 最近活动（本地时间）
  - 完成状态（完成/进行中）
  - “查看 / View” → 参与者详情
- 没有分页；大班/大数据量时一次渲染全部行，可能变慢。
- 空筛选结果提示“没有符合筛选条件的参与者。”
- 底部说明：UUID 匿名标识；邮箱仅供内部核对，不写入导出；class 0 仅内部测试。

**服务端 `GET /api/admin/overview`**

- 先 `build_readiness()`；
- 查询所有 Participant + ClassGroup + 可选 Run；
- 生成 rows、`by_stage`、`by_group`、`started`、`completed`；
- 返回 `readiness`、`protocol`、`participants`、`counts`、`server_time`。
- `stage_label` 用 `STAGE_LABELS`；没有 run 的显示“未开始 / Not started”。
- 包含 `email`、`code_last4`（这是后台可见的个人数据）。

#### 4.8.2 研究材料 / Content

组件：`components/AdminContent.tsx`

- 顶部两个 segmented tabs：
  - `文物 Evidence Packs`
  - `测验与问卷 Instruments`
- 说明：“保存内容会创建不可变的新版本，不会修改学生已经开始的冻结协议。正式数据收集前需完成审核并重新激活协议。”

**文物 Evidence Pack 编辑器**

- X/Y 两列，每列对应一个 `ArtifactForm`。
- 显示最新版本号、demo 警告、当前图片预览。
- 字段：
  - 标题 / Title（必填，≤200）
  - 年代 / Era（≤120）
  - 类型 / Type（≤120）
  - 简介 / Introduction（textarea）
  - 历史事实 / Facts（每行一条）
  - 来源证据 / Evidence（每行一条）
  - 待探究 / Uncertainty（每行一条）
  - 图片 / Image（首次必须；后续不选则复用上一版）
- 保存按钮：“保存为新版本 / Save version”。
- 保存成功提示“已创建 vN…”。
- 失败 `ErrorNotice`。
- “历史版本 / Versions”折叠列表：vN、title、时间、DEMO 标记。
- 前端把多行文本按 `\n` 切分、trim、去空行后作为 JSON 数组提交。
- 后端 `create_artifact_version`：
  - slot 必须 X/Y；
  - title 必填；
  - 每列表 ≤50 条；
  - 图片 ≤12MB、≤30MP、>2400px 缩略；
  - 保存 PNG、sha256；
  - 新版本号 = 当前最大 +1。
- 没有删除版本、没有预览学生端、没有富文本。

**测验/问卷编辑器**

- 左侧 kind 导航：pre_test / r1_test / post_test / transfer / questionnaire，显示当前版本或“未配置”。
- 右侧表单：
  - 标题 / Title
  - 说明 / Instructions
  - 题目构建器：
    - 题目 ID（可编辑，需唯一）
    - 类型下拉
    - 必答 checkbox
    - 题干 textarea
    - 单选/多选：每行 `value|label`
    - 简答：最大字数
    - 证据判断：每行 `id|label`
    - Likert：min/max（scale_labels 不在 UI 编辑；已有 schema 的 labels 会随对象保留）
    - 删除题目（至少保留 1 题）
  - “+ 添加题目 / Add question”
  - 保存为新版本
  - 历史版本折叠列表
- 保存调用 `POST /api/admin/instruments/{kind}/versions`，后端 Pydantic 校验：
  - 至少 1 题；
  - question id 唯一；
  - 选择/证据判断的选项/行校验；
  - Likert min/max。
- 保存不会自动激活协议；需要去 readiness 激活。

#### 4.8.3 准备检查 / Readiness

组件：`components/AdminReadiness.tsx`

**页面内容**

- 标题“协议冻结与准备检查”。
- 状态 pill：可供学生使用 / 尚未准备好。
- 说明：正式收集前必须配置两套审核过的 Evidence Pack、五项测验/问卷、真实 AI 模型；激活后协议冻结；已有研究记录后不能切换。
- demo 内容警告（如果 `demo_present`）。
- 检查项网格：每项 `✓`/`!` + 标题 + detail。
- “冻结新协议 / Freeze a protocol”：
  - 当前协议 ID、激活时间、DEMO/Research 状态；
  - 激活按钮；
  - 按钮 disabled 条件：`!ready_to_activate || activating || run_count > 0`；
  - 已有 run 时显示“已有 N 条研究记录；协议已锁定，不能再次激活。”
- 伦理/正式运行前提列表（静态文案）。

**检查项（email 模式共 13 项）**

| key | 通过条件 | detail |
|---|---|---|
| `admin_password` | `len(ADMIN_PASSWORD) >= 16` | 设置 16+ 字符 |
| `code_pepper` | `len(ANON_CODE_PEPPER) >= 16` | 分配后不可改 |
| `login_mode` | email 模式 | 邮箱登录启用 |
| `classes` | 班级 1..CLASS_COUNT 都存在 | 列出找到的 ID |
| `artifact_x` | 最新 X 有 title + image | 标题/证据/图片 |
| `artifact_y` | 最新 Y 有 title + image | 同上 |
| `instruments` | 五个 kind 都有最新版本 | 缺失列表 |
| `text_model` | 三项文本配置齐全 | 环境变量 |
| `image_model` | 三项图片配置齐全 | 环境变量 |
| `storage` | DATA_DIR 可写 | 路径 |
| `protocol` | 有 active protocol | 激活前学生不能进入 |
| `production_content` | production 下不含 demo | 非 production 允许 demo |
| `protocol_lock` | `run_count == 0` | 有 run 后锁定 |

code 模式会改为 `codes` + `codes_csv`，而不是 `login_mode` + `classes`。

**两个布尔值的准确含义**

- `ready_to_activate`：
  - 所有“激活必需检查”通过；
  - 必需 keys：admin_password、code_pepper、artifact_x、artifact_y、instruments、text_model、image_model、storage、production_content、protocol_lock；
  - email 模式另加 login_mode、classes；
  - **不要求**当前已有 active protocol。
- `ready_for_students`：
  - 有 active protocol；
  - 除 `protocol`、`protocol_lock` 外的所有检查通过；
  - production 下不能有 demo；
  - 这是后台警告/研究准备度指标；学生入口的实际硬门禁是“存在 active protocol（production 下还必须非 demo）”，不是所有 readiness 检查项。

> 当前本地实例 `ready_for_students=true` 但 `ready_to_activate=false`，因为已有 17 个 run 导致 `protocol_lock=false`；这正是“已有数据后不能再换协议”的表现。

**激活协议 `POST /api/admin/protocol/activate`**

- 读取 readiness；不 ready → 409 `protocol_not_ready`，details.failed_checks。
- demo + production → 409 `demo_content_blocked`。
- 非 production + allow_demo（admin 路由传入 `not is_production`）→ 允许 demo。
- 把旧 active 置 false；新建 ProtocolVersion：
  - 最新 X/Y artifact；
  - 五个最新 instrument；
  - `is_demo` = 任一内容 demo；
  - `is_active=true`、`activated_at=now`。
- 返回新 protocol + readiness。
- 没有“恢复旧协议”按钮；旧协议行保留但 active=false。

#### 4.8.4 参与者详情 / Participant detail

组件：`components/ParticipantDetail.tsx`

**加载**

`GET /api/admin/participants/{participant_id}`；404 `participant_not_found`。

**顶部**

- 返回列表；
- 标题：UUID 前 8 位；
- group badge；
- 元信息网格：
  - 班级
  - 内部标识（email 或 `••••last4`）
  - 阶段
  - 最近活动
  - 条件顺序（如 `B1 → A2`；来自 rounds 的 condition+round_no）
  - 完成（是/否）

**轮次**

每个 round 一个 section：

- 标题“第 N 轮 · 条件 X · 文物标题”；
- 开始/截止/结束/结束原因；
- 文物图片 + 简介。

**对话**

- 完整消息流；
- 每条显示 R1/R2、role、source、时间；
- `<pre>` 保留格式；
- 没有分页/搜索/导出单条。

**脚本版本**

- 每个 revision 一个折叠项；
- R、vN、title、时间；
- 展开 `<pre>` body。

**关键帧任务**

- 每个 job：status、round、attempt；
- 错误信息；
- 成功图片预览；
- 折叠 Prompt。

**测评**

- 每个 kind 一个折叠项：kind、status、duration；
- 展开 `answers` JSON。

**HLSF / 资料事件**

- `hlsf_events` + `evidence_events` 原始 JSON（`<pre>`）。

**阶段时间**

- `stage_events` 原始 JSON。

**AI 调用与错误**

- `api_errors`（如果有）红色错误块；
- 每个 `ai_calls` 折叠项：status/purpose/prompt_version/latency；
- 展开完整 JSON（含 request messages、response_text）。

> 该页面是**只读**的：没有编辑、删除、重跑、导出单个参与者、模拟登录。

#### 4.8.5 导出

- 总览页的“导出完整研究数据”是一个普通 `<a href="/api/admin/export">`，不是 fetch。
- 浏览器会带 admin cookie 下载 ZIP；失败会显示 JSON 错误页（不是前端错误提示）。
- 导出是同步生成；没有进度条；大导出可能长时间等待。
- 生成后临时文件在响应结束时删除。
- 导出内容见第 12 节。

#### 4.8.6 后台的边界与风险

- 后台没有“学生管理”（删除/重置/改分组/改阶段）。
- 没有“协议版本列表/回滚”。
- 没有“单参与者导出”。
- 没有“审计日志”（谁在何时导出/改内容/登录）。
- 没有“实时刷新”；总览需要手点刷新。
- 邮箱明文可见，后台 session 泄露=个人数据泄露。
- 导出包含 AI prompt/对话/自由文本，需按敏感数据管理。

---

## 5. HLSF 学习引导（B 组专属）

### 5.1 版本与位置

- 代码：`backend/app/prompts/hlsf.py`
- 服务：`backend/app/services/hlsf.py`
- 当前版本：`HLSF_VERSION = "hlsf-v1.1.1"`
- 阶段：`observe` → `explain` → `create` → `reflect` → `complete`
- 仅 B 组；A 组的 `guide_payload()` 返回 `None`。

### 5.2 阶段标签

| id | 中文 | 英文 | UI 图标 |
|---|---|---|---|
| `observe` | 观察 | Observe | ◉ |
| `explain` | 解释 | Explain | ◌ |
| `create` | 创作 | Create | ▣ |
| `reflect` | 反思 | Reflect | ↻ |
| `complete` | 完成 | Complete | — |

### 5.3 固定阶段提示词（会作为 assistant 消息写入消息流）

> 这些不是模型生成的，是服务端固定文本；它们会出现在聊天记录中，也会作为历史消息发给模型。

#### Observe（观察）

```text
如果你要向一位不了解这件文物的人讲一个故事，请选一个最能引起好奇的细节，
说说你想围绕它提出什么问题。

If you were telling someone unfamiliar with this artifact a story, choose the
detail that most sparks their curiosity, then say what question you would want
the story to raise.
```

#### Explain（解释）

```text
回到你刚才提出的故事问题，结合左侧资料，说说哪些事实或证据能解释它，
以及你希望观众怎样一步步理解这些知识。

Return to the story question you raised. Using the evidence on the left, what
facts or sources help explain it, and how would you help the audience understand
the knowledge step by step?
```

#### Create（创作）

```text
现在请把这些知识组织成一个故事，而不只是罗列信息。可以先确定故事主题、
叙事视角和必须传达的关键知识。下面三种方式只是可选启发，你也完全可以用
自己的方式：
· 历史侦探：比如从一个细节为何出现出发，像查案一样带着观众寻找证据；
· 微观历史场景：比如假设一位工匠、使用者或旁观者身处某个场景（必须标明
虚构），从他的视角讲述；
· 过程重建：比如按设计、制作、使用和意义变化的时间顺序讲述。
你打算从哪个视角展开这个故事？

Now shape this knowledge into a story rather than a list of facts. Decide on a
theme, a narrative perspective and the key knowledge the audience needs. These
three modes are optional inspirations; your own approach is equally valid:
· Historical detective: for example, start from why a detail exists and uncover
evidence like a case;
· Microhistorical scenario: for example, imagine a clearly labelled fictional
artisan, user or bystander in a situation and tell it through their eyes;
· Process reconstruction: for example, follow design, making, use and changing
meaning over time.
From which perspective would you tell it?
```

#### Reflect（反思）

```text
请对照右侧你已保存的脚本，检查：故事开头的问题是否得到回答，故事是否连贯，
文化知识是否准确，哪些内容有证据支持、哪些属于解释或想象。请先找出最值得
改进的一处，再说说你准备怎么改。

Review the script you have saved on the right: check whether it answers the
question it opens with, whether the story is coherent and the cultural knowledge
is accurate, and which parts are evidence, interpretation or imagination.
Identify the one change most worth making, then say how you would revise it.
```

### 5.4 每阶段提示（Hint）

每阶段最多一次。点击后作为 `source="hlsf_hint"` 的 assistant 消息插入。

| 阶段 | 提示全文 |
|---|---|
| observe | 提示：先挑一个让你自己也好奇的具体细节，再把它变成一个“为什么”或“怎么会”的问题；不必现在写完整故事。<br>Hint: pick one concrete detail that makes you curious, then turn it into a why/how question. Do not draft the full story yet. |
| explain | 提示：只选一两条与故事问题直接相关的资料，想清楚观众先知道什么、后知道什么；不要把所有资料一次讲完。<br>Hint: choose only one or two evidence items that directly answer your story question, and decide what the audience should learn first and later. Avoid an information dump. |
| create | 提示：可以先用一句话概括故事主线，再按“引发好奇→展开探索→揭示文化知识→回到文物及意义”搭一个骨架；三种叙事方式只是启发，不必采用。<br>Hint: summarise the story in one line, then build a spine: hook → exploration → revealed knowledge → return to the artifact and its meaning. The three modes are optional inspirations. |
| reflect | 提示：先只选一个最影响故事效果的修改点，并检查哪些句子是证据、哪些是你的解释或想象；如果使用虚构人物或情境，要明确标为假设。<br>Hint: choose just one change that would most improve the story, and separate evidence from interpretation or imagination. Clearly label invented people or scenes as hypothetical. |

### 5.5 状态机与边界

| 动作 | 前置 | 结果 |
|---|---|---|
| 开始 B 轮 | `start_round` 且 condition=B | 创建 `hlsf_states(phase=observe, hint_used=false)`；插入 Observe prompt；写 `prompt_delivered` 事件 |
| 获取提示 | 当前 phase，未用过，未 complete | 插入 hint；`hint_used=true`；写 `hint_delivered` |
| 下一阶段 | `from_phase == state.phase`，非 complete | 写 `advanced`；推进；插入下一阶段 prompt；`hint_used=false` |
| 跳过 | 同上 | 写 `skipped`；推进；插入下一阶段 prompt；`hint_used=false` |
| 从 reflect 推进 | phase=reflect | 写 `advanced`/`skipped`；phase=complete；`completed_at`；写 `guide_completed`；不插入新 prompt |
| 重复提示 | 已用过 | 409 `hint_already_used` |
| 阶段不匹配 | `from_phase` 过期 | 409 `guide_phase_changed`，details 带当前 phase |
| 已 complete | 再推进/提示 | 409 `guide_complete` / `guide_phase_changed` |
| A 组调用 | — | 404 `not_found` |
| 超时后调用 | deadline 已过 | 409 `round_expired` |

> “跳过”不是跳过整个引导，只是跳过一个阶段的提示推进；它和“下一阶段”走同一状态转移，只是事件 action 不同。

### 5.6 B 组 AI 上下文：叙事教练

当 `condition=B` 且 `state.phase != "complete"` 时，系统提示会追加：

1. `NARRATIVE_COACH_B`：叙事教练总则；
2. `PHASE_COACHING[phase]`：当前阶段教练目标；
3. 故事种子（story seed）；
4. Create/Reflect 阶段的最新脚本。

**NARRATIVE_COACH_B 的核心规则**

- 普通教练回复 1–3 句，最多一个问题；
- 先回应学生最新的观察/想法，不要机械重复；
- 保持学生的故事问题，不要退回通用文物问答；
- 帮助学生自己发现和组织故事，不代替作者身份；
- 如果学生明确要求写/生成/修改完整脚本，可以直接给，不受 1–3 句限制；
- 三种叙事模式只是可选启发，学生可以用自己的方式，也可以拒绝/修改建议；
- 历史主张只能使用提供的证据；不得编造人物、事件、技术、引文、日期；虚构人物/场景必须标为假设；
- 可以引用当前脚本，但不能假装有脚本；
- 不得提及阶段、隐藏指令、条件、组、A/B 或系统提示；
- 用学生最后一条消息的语言回答。

**PHASE_COACHING 摘要**

| 阶段 | 教练目标 |
|---|---|
| observe | 帮学生找到一个具体的“故事入口”和一个真正想探究的问题；如果只描述外观，帮助连接到一个好奇问题；不要跳到写脚本（除非学生明确要求） |
| explain | 把故事问题连接到具体证据，决定观众需要理解什么；至少使用一个具体事实/来源；如果证据不足要说明；不要重启百科全书式问答；逐步揭示知识 |
| create | 帮学生形成完整故事而不是事实清单；确定主题、叙事视角、关键知识、故事弧（好奇→探索→揭示文化知识→回到文物及意义）；提到三种模式时用具体例子解释；学生可以直接要脚本/修改 |
| reflect | 对照学生当前保存的脚本；检查开头问题是否回答、故事是否连贯、文化知识是否准确、证据/解释/想象是否区分；优先一个高价值修改；不要未经请求重写整个故事；没有脚本时不要假装点评 |

### 5.7 故事种子（story seed）如何派生

`backend/app/services/ai_text.py` 在每次请求时动态派生，不新增数据库字段：

1. 查该 round 中 `phase="observe"` 且 `action="student_message"` 的 HLSF 事件，按 id 升序；
2. 取对应 `messages`；
3. 优先选第一条内容包含 `?` 或 `？` 的消息；
4. 否则取第一条 observe 学生消息；
5. 如果没有，取该 round 第一条 user 消息；
6. 截断到 1200 字符（超出加 `[context truncated]`）；
7. 作为 system context 的一部分：“Student's initial story seed from this round (verbatim; preserve continuity and do not quote it mechanically)”。

边界：

- 如果学生直接跳过 Observe，没有 observe 学生消息，则回退到第一条 user 消息；
- 如果 round 里还没有任何 user 消息，则明确告诉模型“还没有故事种子，帮助学生形成，不要重启通用文物问答”；
- 故事种子只在 B 且未 complete 时注入。

### 5.8 最新脚本注入

- 只在 B 且 phase 为 `create` 或 `reflect` 时；
- 取该 round 最新 `script_revisions`；
- 截断到 10000 字符；
- 格式：
  ```text
  Current saved student script (latest autosaved revision; it may be incomplete):
  Title: ...
  Body:
  ...
  ```
- 如果 reflect 阶段没有脚本，明确告诉模型“不要假装点评脚本，邀请学生写/保存”；
- Create 阶段没有脚本时不注入。

### 5.9 事件与审计

`hlsf_states` 只保存当前 phase/hint 状态；`hlsf_events` 保存完整动作序列：

| action | 触发 | message_id |
|---|---|---|
| `prompt_delivered` | 初始/推进后插入固定提示 | 对应 assistant 消息 |
| `hint_delivered` | 点击提示 | 对应 assistant 消息 |
| `student_message` | B 组学生在未完成阶段发消息 | 对应 user 消息 |
| `assistant_reply` | B 组 AI 回复成功 | 对应 assistant 消息 |
| `advanced` | 点击下一阶段 | 无 |
| `skipped` | 点击跳过 | 无 |
| `guide_completed` | 从 reflect 推进到 complete | 无 |

每条事件带 `meta_json={"prompt_version": "hlsf-v1.1.1"}`（多数动作）；学生消息/回复事件没有 prompt_version，但可通过 AI call / 固定文本对应。

研究者后台的参与者详情会显示 `hlsf_events` 原始 JSON；导出为 `hlsf_events.csv`。

### 5.10 A 组如何保证没有 HLSF

代码级保证：

- `guide_payload()` 对非 B 返回 `None`；
- `start_round` 只在 B 调用 `start_guide`；
- student `/hlsf/*` 路由对非 B 返回 404；
- `send_message` 只在 B 写 HLSF 事件；
- `request_chat_reply` 只在 B 且 state 存在且未 complete 时追加叙事教练上下文；
- A 的 `prompt_version` 是 `chat-v1`，B 是 `chat-v1+hlsf-v1.1.1`；
- 前端 `guide` 为 null 时不渲染引导条。

### 5.11 修改 HLSF 时要注意

1. 修改 `PHASE_PROMPTS`/`PHASE_HINTS`/`NARRATIVE_COACH_B` 后，**必须提升 `HLSF_VERSION`**；
2. 正式研究前冻结版本；已收集数据后不要改同一版本号；
3. 修改 phase 名称会影响 `hlsf_states.phase`、事件、前端图标匹配（`observe/explain/create/reflect` 字符串硬编码在 `Workbench.tsx` 的图标判断中），需要同步改；
4. 修改故事种子/脚本注入逻辑后，要回归 A 组上下文（A 不能出现任何叙事/HLSF 标记）；
5. 现有测试：`backend/tests/test_hlsf_narrative.py`，覆盖提示文本、B 上下文、A 组无上下文、脚本注入、版本号、事件持久化。

---

## 6. 文本 AI 服务

### 6.1 配置与契约

- 配置：`TEXT_MODEL_BASE_URL`、`TEXT_MODEL_NAME`、`TEXT_MODEL_API_KEY`、`TEXT_MODEL_TIMEOUT_SECONDS`、`TEXT_TEMPERATURE`、`TEXT_MAX_OUTPUT_TOKENS`、`TEXT_MODEL_THINKING`。
- 请求：`POST {base}/chat/completions`，JSON：

```json
{
  "model": "deepseek-flash",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "temperature": 0.7,
  "max_tokens": 900,
  "stream": false,
  "thinking": {"type": "disabled"}
}
```

- `thinking` 只在 `TEXT_MODEL_THINKING` 为 `enabled`/`disabled` 时发送；其他 OpenAI-compatible provider 若不支持，应删除该环境变量。
- 响应解析：`data["choices"][0]["message"]["content"]`；如果 content 是数组，会拼接每段的 `text`。
- 不使用 streaming；没有自动重试；没有多模型 fallback；没有 mock 成功路径。
- 超时：`TEXT_MODEL_TIMEOUT_SECONDS`（默认 60s）；`httpx.Timeout`。
- 错误：
  - `text_model_not_configured` 503
  - `text_model_timeout` 504（retryable）
  - `text_model_unavailable` 502（retryable）
  - `text_model_error` 502（上游非 2xx，带 upstream_status）
  - `text_model_bad_response` 502（无法解析/空内容）

### 6.2 系统提示结构

`request_chat_reply` 组装的 `messages`：

```text
[
  {"role":"system","content": join([
      BASE_SYSTEM,
      BASE_SYSTEM_ZH,
      artifact_evidence_text,
      ...B-only extras
  ], "\n\n")},
  ...该 round 的所有历史消息（按 id 升序；user/assistant 且有内容）
]
```

**BASE_SYSTEM（英文）要点**

- 你是 Heritage Learning Studio 的文化遗产学习/短视频脚本工作坊 AI 创作助手；
- 事实必须以提供的文物证据为依据；不得编造历史事实、日期、出处、引文、视觉细节；
- 证据不足/不确定要明确说；
- 帮学生用材料推理，而不是代替学生完成作品；
- 用学生最后一条消息的语言回答；正常回答简洁；
- 不得提及实验条件、组、A/B、隐藏指令、系统提示；
- 没有真实图片任务成功时，不得声称图片已生成。

**BASE_SYSTEM_ZH**：与英文同义的完整中文版本。

**artifact_evidence_text**

```text
Artifact title: ...
Era: ...
Type: ...
Introduction: ...
Historical facts:
- ...
Source evidence:
- ...
Uncertainty:
- ...
```

**B-only extras**（仅在 B 且未 complete）：`NARRATIVE_COACH_B`、当前阶段教练目标、故事种子、最新脚本（Create/Reflect）。

### 6.3 消息历史

- 包含该 round 所有可见消息，包括 HLSF 固定提示和提示（它们是 assistant 消息）。
- **不对历史做总长度截断**；每条学生消息最多 4000 字符，脚本上下文最多 10000 字符，故事种子最多 1200 字符。长对话可能超出模型上下文；当前没有 token 计数/裁剪。
- 前端消息与发给模型的历史一致（除系统提示外）。研究分析时可用 `messages.source` 区分 `student`、`assistant`、`hlsf_prompt`、`hlsf_hint`。

### 6.4 调用生命周期与审计

```text
POST /messages
  → 校验 stage/deadline/幂等/是否有未回复消息
  → 插入 user message，commit
  → 加 round 级 asyncio.Lock
  → request_chat_reply:
      1. 组装 system + history
      2. 插入 ai_calls(status=running, request_json=...)，commit
      3. 调用 provider
      4a. 成功：插入 assistant message(ai_call_id)，B 写 assistant_reply 事件，
          更新 ai_calls(status=succeeded, response_text, raw_response_json,
          http_status, latency_ms)，commit
      4b. 失败：更新 ai_calls(status=failed, error_code/message/latency)，
          写 api_errors(category=text_ai)，commit，抛 AppError
  → 返回 [user, assistant] 或错误
```

**`ai_calls` 记录内容**

- `purpose`：`chat` 或 `chat_retry`
- `status`：`running` / `succeeded` / `failed`
- `model`、`prompt_version`（A=`chat-v1`，B=`chat-v1+hlsf-v1.1.1`）
- `request_json`：provider、model、完整 messages、temperature、max_tokens（**包含 system prompt 和对话**）
- `response_text`、`raw_response_json`
- `http_status`、`error_code`、`error_message`、`latency_ms`
- `created_at`、`completed_at`

> `request_json` 含完整系统提示和对话，属于敏感研究数据；只在后台/导出中可见，不进浏览器。

### 6.5 失败与重试语义

- 用户消息在调用模型前已提交；失败后它仍是该 round 最后一条 user 消息。
- 前端显示错误 + “重试这条消息”；重试调用 `POST /messages/{id}/retry`。
- 重试只允许最新一条未回复的 user 消息；否则 409 `message_not_latest`。
- 重试会创建新的 `ai_calls`（purpose=`chat_retry`），不会重复写 user message。
- 如果模型超时但上游实际生成成功，学生重试可能得到第二次回复；这是研究数据中需要留意的重复风险（没有幂等去重上游响应）。
- 前端等待 75 秒后会提示可重试，但服务端请求可能仍在进行；因为前端会轮询消息，若服务端稍后成功，轮询会拿到回复。

### 6.6 并发与顺序

- 每个 round 一个 `asyncio.Lock`，同一 round 的聊天串行。
- 服务端还要求“最后一条消息不能是 user”，防止并发双发。
- 单进程锁；多副本部署时需数据库级锁/队列。

### 6.7 替换文本模型

只需改环境变量，前提是 provider 兼容：

- `POST {base}/chat/completions`
- Bearer key
- `choices[0].message.content` 文本
- 可选 `thinking` 字段（不支持就不要设置）

若 provider 的请求/响应不同，改 `backend/app/services/ai_text.py` 的 `_call_provider()`，不要在生产代码里加“失败后假装成功”的 mock。

---

## 7. 图片关键帧服务

### 7.1 前置条件

- 文本模型/图片模型配置齐全（`image_configured` 为真）；
- `IMAGE_WORKER_ENABLED=true`；
- 该轮未结束、未超时；
- 已有非空脚本（最新 revision 的 body 非空）；
- 该轮没有成功关键帧；
- 该轮没有 queued/running 任务；
- 该轮任务总数 < `IMAGE_JOB_LIMIT_PER_ROUND`（默认 3）。

### 7.2 图片提示词模板

服务端在入队时构建，保存在 `image_jobs.prompt`：

```text
Create one historically grounded keyframe illustration for a one-minute
cultural-heritage educational short video. This is a visual accompaniment to
the student's script, not a replacement for museum evidence.

Artifact: {title} ({era}; {type}).
Evidence and facts: {facts 前 12 条，分号连接}. {evidence 前 8 条，分号连接}.
Student script title: {title}.
Student script: {body 前 6000 字符}

Visual direction: elegant museum-education illustration, respectful and
non-sensational, coherent period-appropriate material culture, clear focal
subject, cinematic wide composition. Do not add readable text, captions,
watermarks, logos, or invented inscriptions. Avoid anachronistic objects.
```

注意：

- 不包含 `introduction` 和 `uncertainty`；
- 不包含学生对话，只包含脚本；
- 图片 prompt 是固定的，不经过 AI 改写；
- `script_revision_no` 记录入队时使用的脚本版本。

### 7.3 任务状态机

```text
（学生点生成）
  → queued
  → worker claim: running（attempts += 1）
      → 成功：succeeded（file_path/mime/sha256/width/height/http_status）
      → 失败：failed（error_code/error_message）
  → 学生重试失败任务
      → 新 job: queued（retry_of_id=旧 job.id；旧 job 保持 failed）
```

- 每轮最多 3 个 job（包括失败/重试）。`attempts` 是 worker 领取次数，不是 provider 重试次数。
- 一旦有 succeeded，不能再生成（`keyframe_exists`）。
- 有 queued/running 时不能新建（`image_job_active`）。
- 失败后重试必须指向该轮一个 failed job（`retry_of`），否则 404/409。
- 服务端重启时，所有 `running` 任务被标记为 `failed`，`error_code=server_restart`，需要学生手动重试。

### 7.4 Worker 实现

- 启动：`ImageWorker.start()`：
  - 如果 `IMAGE_WORKER_ENABLED` 为 false，直接返回（任务会一直 queued）；
  - 先把所有 running 标记 failed(server_restart)；
  - 如果图片模型未配置，只记 warning，不启动；
  - 创建 `IMAGE_MAX_CONCURRENCY` 个循环任务（clamp 1–8，默认 2）。
- 领取：`SELECT ... WHERE status='queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1`，改 running、`attempts += 1`、`started_at`，commit。
- 处理：读取 job/round/run/participant；调用 provider；下载/解码；校验；存储；更新 job。
- 空转：没有任务时等待 1 秒再轮询。
- 停止：取消任务；`CancelledError` 向上抛；不自动重试当前任务。

### 7.5 Provider 契约

请求：

```http
POST {IMAGE_MODEL_BASE_URL}/images/generations
Authorization: Bearer {IMAGE_MODEL_API_KEY}
Content-Type: application/json

{
  "model": "doubao-seedream-5-0-pro-260628",
  "prompt": "...",
  "size": "2K",
  "response_format": "url",
  "watermark": false
}
```

- `response_format`/`watermark` 只在配置时发送；
- 不发送 `n`。

响应支持：

```json
{"data": [{"url": "https://..."}]}
```

或

```json
{"data": [{"b64_json": "..."}]}
```

- `url` 必须是 http/https；会 follow redirect；
- 下载结果最大 25 MB；
- 使用 Pillow `verify()` + `load()` 校验；
- 最大 40,000,000 像素；
- 非 RGB/RGBA 转 RGBA；
- 统一保存为优化 PNG；
- 原子写入：先写 `.{job_id}.tmp`，再 replace；
- 计算 sha256；
- 存储路径：`DATA_DIR/keyframes/{participant_uuid}/round-{n}/{job_id}.png`。

### 7.6 错误码

| code | HTTP | 场景 |
|---|---|---|
| `image_model_not_configured` | 503 | 图片模型未配置 |
| `round_expired` | 409 | 轮次已结束/超时 |
| `script_required` | 422 | 没有非空脚本 |
| `keyframe_exists` | 409 | 已有成功关键帧 |
| `image_job_active` | 409 | 已有 queued/running |
| `image_quota_exhausted` | 429 | 任务数达到上限 |
| `invalid_retry` | 422/409 | retry_of 格式错误或不是 failed |
| `image_job_not_found` | 404 | 任务不存在/不属于该轮 |
| `image_model_timeout` | 504 | provider 超时 |
| `image_model_unavailable` | 502 | 连接失败 |
| `image_model_error` | 502 | provider 非 2xx |
| `image_model_bad_response` | 502 | 无 data / 无 url/b64 / 无效 base64 |
| `image_download_failed` | 502 | URL 下载失败/非 2xx |
| `image_result_too_large` | 413 | 文件/像素过大 |
| `image_result_invalid` | 502 | 不是有效图片 |
| `image_internal_error` | 500 | worker 未预期异常 |
| `server_restart` | — | 重启时 running 被标记失败 |

### 7.7 文件读取与权限

- `GET /api/files/keyframes/{job_id}`：
  - 需要任何已登录 actor（学生或 admin）；
  - 学生只能读自己 run 的 job；
  - admin 可读所有；
  - job 必须 `succeeded` 且有 `file_path`；
  - 路径必须位于 `DATA_DIR` 内；
  - 返回 `image/png`（或 job.mime），`Content-Disposition: inline`，`Cache-Control: private, max-age=300`。
- `GET /api/files/artifacts/{version_id}/image`：
  - 学生只能读自己 run 里出现过的 artifact version；
  - admin 可读所有；
  - 路径必须在 `DATA_DIR` 内。

### 7.8 成本与额度

- 每轮 3 次任务，最多 1 张成功图。
- 失败也占额度；学生需要谨慎重试。
- 默认并发 2；30 人同时生成会排队。
- 图片生成通常比文本慢很多（真实 smoke 约 58 秒），前端需要轮询。
- 图片 provider 与文本 provider 是独立服务；DeepSeek 官方没有公开文生图端点，模板使用 Volcengine Ark。

### 7.9 替换图片 provider

要求：

- 请求接受 model/prompt/size，可选 response_format/watermark；
- 返回 `data[0].url` 或 `data[0].b64_json`；
- 否则改 `_call_image_provider()` / `_parse_image_response()`。

不要让图片失败阻断文本任务：当前实现中，图片失败只影响关键帧，脚本仍可提交/结束本轮。

---

## 8. 测评引擎（Instruments / Assessments）

### 8.1 五种测评类型

`ASSESSMENT_KINDS = ["pre_test", "r1_test", "post_test", "transfer", "questionnaire"]`

每个 kind 有独立版本序列，协议冻结时把五个 kind 的版本 ID 写入 `protocol_versions.instrument_versions`。

### 8.2 Instrument schema

```json
{
  "title": "前测",
  "instructions": "请根据你的理解作答。",
  "questions": [
    {
      "id": "q1",
      "type": "single_choice",
      "prompt": "...",
      "required": true,
      "options": [
        {"value": "a", "label": "选项 A"},
        {"value": "b", "label": "选项 B"}
      ]
    }
  ]
}
```

题目字段：

| 字段 | 适用类型 | 规则 |
|---|---|---|
| `id` | 全部 | 1–60 字符，`[A-Za-z0-9_-]`；instrument 内唯一 |
| `type` | 全部 | `single_choice` / `multi_choice` / `short_text` / `evidence_judgment` / `likert` |
| `prompt` | 全部 | 1–2000 字符 |
| `required` | 全部 | 默认 true |
| `options` | 单选/多选 | 至少 2 个；`value` 唯一；`label` 1–500 |
| `max_length` | 简答 | 1–4000；默认 200 |
| `rows` | 证据判断 | 至少 1 行；`row.id` 唯一；`label` 1–1000 |
| `scale_min` / `scale_max` | Likert | 1–10；必须都提供；min < max |
| `scale_labels` | Likert | 可选，按点位对应 |

`InstrumentPayload` 还要求：至少 1 题；question id 唯一。

### 8.3 答案校验矩阵

| 类型 | 答案形状 | 校验 | 提交时 required 缺失 |
|---|---|---|---|
| single_choice | `str` | 必须是 options 中的 value | 422 `answers_incomplete` |
| multi_choice | `list[str]` | 每项合法；去重；required 时空数组算缺失 | 422 |
| short_text | `str` | 去空格；长度 ≤ max_length | 422 |
| evidence_judgment | `{row_id: "yes"|"no"}` | row 必须存在；值只能是 yes/no；required 时必须覆盖所有 rows | 422 |
| likert | `int` | 不能是 bool；min ≤ value ≤ max | 422 |

其他规则：

- 未知 question id → 422 `invalid_answers`；
- 无效值 → 422 `invalid_answers`；
- 草稿（draft）允许 required 缺失，但仍会清洗/校验已填值；
- 已提交后再 PUT/提交 → 409 `assessment_submitted`；
- 提交时未知/无效/缺失 → 422，details 带 `invalid` 或 `missing`。

> 注意：`short_text` 长度后端用 Python `len()`，前端计数器用 `Array.from()`（按 code point）；对 emoji 等代理对可能有一个字符的差异。不是研究关键问题，但改字数限制时需注意。

### 8.4 测评生命周期

```text
GET /api/student/instruments/{kind}
  → 校验当前 stage 的 assessment kind 是否匹配
  → 取协议中的 instrument version
  → 取/创建 AssessmentResponse(status=draft, answers_json={})
  → 返回 instrument + answers + status + started_at + updated_at

PUT /api/student/instruments/{kind}/draft
  → 同一套 stage/version 校验
  → 清洗 answers（require_complete=false）
  → 更新 answers_json/updated_at
  → 返回 status/answers/updated_at

POST /api/student/instruments/{kind}/submit
  → 清洗 answers（require_complete=true）
  → status=submitted, submitted_at, duration_seconds
  → transition_stage(next)
  → 返回 status/submitted_at/state
```

- `started_at` 是草稿首次创建时间（GET 时创建），不是学生第一次输入时间。
- `duration_seconds = submitted_at - started_at`；如果学生打开页面后长时间不提交，会包含空闲时间。
- 没有按题计时、没有题目顺序随机化、没有防复制/防切屏。
- 提交后 `onState` 进入下一阶段；浏览器前进/后退不会回到已提交测评（服务端 stage 已变）。

### 8.5 阶段与测评的绑定

`ASSESSMENT_STAGE_KIND`：

```python
{
  "pre_test": "pre_test",
  "r1_test": "r1_test",
  "post_test": "post_test",
  "transfer": "transfer",
  "questionnaire": "questionnaire",
}
```

`NEXT_AFTER_ASSESSMENT`：

```python
{
  "pre_test": "round1_ready",
  "r1_test": "round2_ready",
  "post_test": "transfer",
  "transfer": "questionnaire",
  "questionnaire": "complete",
}
```

### 8.6 Demo 内容

`backend/app/cli.py` 的 `DEMO_QUESTIONS`：

| kind | 标题 | 题目 |
|---|---|---|
| pre_test | 前测占位 / Pre-test placeholder | 1 道单选 `demo_prior`（A/B） |
| r1_test | R1 测试占位 / R1 placeholder | 1 道简答 `demo_reflection`，最多 120 字 |
| post_test | 后测占位 / Post-test placeholder | 1 道单选 `demo_post`（是/否） |
| transfer | 迁移题占位 / Transfer placeholder | 1 道简答 `demo_transfer`，最多 200 字 |
| questionnaire | 问卷占位 / Questionnaire placeholder | 1 道 5 点 Likert `demo_satisfaction` |

这些内容标记 `is_demo=True`；production 不能激活 demo 内容（激活接口会拒绝）。

### 8.7 研究者如何编辑测评

`/admin` → 研究材料 → 测验与问卷 Instruments：

- 左侧 kind 导航；
- 标题、说明；
- 题目构建器：题目 ID、类型、是否必答、题干；
- 单选/多选：每行 `value|label`；
- 简答：最大字数；
- 证据判断：每行 `id|label`；
- Likert：min/max（标签只在默认/已有 schema 中保留，编辑器不直接编辑 scale_labels；保存时会带上原 `scale_labels` 如果未变）；
- 可添加/删除题目（至少 1 题）；
- 保存总是创建**新版本**，不修改旧版本。

> 编辑器没有“预览学生端”的功能；保存后需要到 readiness 激活新协议（前提是还没有任何 run）。已有 run 时协议锁定，不能切换。

---

## 9. 数据模型（PostgreSQL）

> **v1.5 addendum:** migration `0003` adds `work_revisions`, `peer_batches`, `peer_assignments`, `peer_ratings`, `social_views`, `social_likes`, `social_comments`, `social_events`; `runs` adds `t1_condition`/`artifact_order`; `rounds` adds `current_work_revision`; `image_jobs` adds `work_revision_no`. The table-by-table text below describes the v1.0 baseline; see section 23 and [V15_CHANGE_REPORT.md](V15_CHANGE_REPORT.md) for the additions.

### 9.1 ER 关系概览

```text
classes 1 ─── N participants 1 ─── 1 runs 1 ─── N rounds
                                      │              ├── N messages
                                      │              ├── N script_revisions
                                      │              ├── N image_jobs
                                      │              ├── 1 hlsf_states
                                      │              ├── N hlsf_events
                                      │              └── N evidence_events
                                      ├── N assessment_responses
                                      ├── N stage_events
                                      └── N ai_calls
protocol_versions 1 ─── N runs（每个 run 冻结一个 protocol）
protocol_versions N ─── 1 artifact_versions（X/Y 各一个版本）
protocol_versions 1 ─── N instrument_versions（通过 JSON 引用五个 ID）
```

注意：SQLAlchemy 模型**没有定义 relationship()**，全部是显式查询/外键；上图是逻辑关系。

### 9.2 表逐项说明

#### `classes`

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | int PK | — | 0=内部测试，1–4=正式班 |
| `name` | varchar(80) | not null | 显示名，如“班级 1 / Class 1” |

#### `participants`

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | UUID PK | default uuid4 | 研究匿名 ID |
| `class_id` | int FK classes.id | not null, index | 班级 |
| `group_name` | varchar(8) | not null, index | G1–G4 |
| `email` | varchar(320) | nullable, unique, index | 明文 PolyU 邮箱；email 模式下必填 |
| `access_code_hmac` | varchar(64) | nullable, unique, index | 旧 code 模式 HMAC |
| `access_code_last4` | varchar(4) | nullable | 旧 code 模式后 4 位 |
| `created_at` | timestamptz | not null | 创建时间 |

约束：`uq_participant_email`（email 唯一）。

#### `sessions`

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | UUID PK | — | — |
| `token_hash` | varchar(64) | unique, index | SHA-256(token) |
| `role` | varchar(16) | not null | `student` / `admin` |
| `participant_id` | UUID FK participants.id | nullable, index | 学生 session 关联 |
| `created_at` | timestamptz | not null | — |
| `expires_at` | timestamptz | not null, index | 过期时间 |
| `revoked_at` | timestamptz | nullable | 登出撤销 |

#### `artifact_versions`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | — |
| `slot` | varchar(1) | X / Y |
| `version` | int | 每个 slot 从 1 递增 |
| `title` | varchar(200) | 文物标题 |
| `era` | varchar(120) | 年代 |
| `artifact_type` | varchar(120) | 类型（注意 DB 列名 `artifact_type`，API 字段 `type`） |
| `introduction` | text | 简介 |
| `facts` | JSON list | 历史事实 |
| `evidence` | JSON list | 来源证据 |
| `uncertainty` | JSON list | 待探究/不确定 |
| `image_path` | varchar(500) | 相对 `DATA_DIR`，如 `artifacts/uuid.png` |
| `image_mime` | varchar(100) | 通常 `image/png` |
| `image_sha256` | varchar(64) | 图片哈希 |
| `is_demo` | bool | 演示内容标记 |
| `created_at` | timestamptz | — |

约束：`uq_artifact_slot_version(slot, version)`。

#### `instrument_versions`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | — |
| `kind` | varchar(32) | 五种 kind |
| `version` | int | 每个 kind 从 1 递增 |
| `title` | varchar(200) | — |
| `instructions` | text | — |
| `schema_json` | JSON | 完整 `InstrumentPayload` |
| `is_demo` | bool | — |
| `created_at` | timestamptz | — |

约束：`uq_instrument_kind_version(kind, version)`。

#### `protocol_versions`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | — |
| `artifact_x_version_id` | UUID FK | 冻结的 X 版本 |
| `artifact_y_version_id` | UUID FK | 冻结的 Y 版本 |
| `instrument_versions` | JSON | `{kind: version_uuid_str}` |
| `is_demo` | bool | 是否包含 demo 内容 |
| `is_active` | bool | 当前激活协议 |
| `created_at` | timestamptz | — |
| `activated_at` | timestamptz | — |

约束：部分唯一索引 `uq_protocol_single_active`，只允许一个 `is_active=true`。

#### `runs`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | — |
| `participant_id` | UUID FK participants.id | **unique**，一人一 run |
| `protocol_version_id` | UUID FK protocol_versions.id | 冻结协议 |
| `stage` | varchar(32) | 十阶段之一 |
| `created_at` | timestamptz | — |
| `last_activity_at` | timestamptz | 每次学生请求更新 |
| `completed_at` | timestamptz | 进入 complete 时写 |

#### `stage_events`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | bigint PK | — |
| `run_id` | UUID FK runs.id | index |
| `stage` | varchar(32) | — |
| `entered_at` | timestamptz | — |
| `completed_at` | timestamptz | 离开时写 |
| `duration_seconds` | int | 离开时计算 |
| `meta_json` | JSON | 额外信息 |

当前阶段通常有一条 `completed_at=NULL` 的开放事件。

#### `rounds`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | — |
| `run_id` | UUID FK runs.id | index |
| `round_no` | int | 1/2 |
| `artifact_version_id` | UUID FK | 该轮文物版本 |
| `condition` | varchar(1) | A/B |
| `started_at` | timestamptz | — |
| `deadline_at` | timestamptz | — |
| `finished_at` | timestamptz | nullable |
| `finish_reason` | varchar(24) | `student_finished` / `timeout` |
| `current_script_revision` | int | 最新脚本版本号 |
| `created_at` | timestamptz | — |

约束：`uq_run_round(run_id, round_no)`。

#### `script_revisions`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | bigint PK | — |
| `round_id` | UUID FK rounds.id | index |
| `revision_no` | int | 从 1 递增 |
| `title` | varchar(200) | — |
| `body` | text | — |
| `source` | varchar(24) | 当前总是 `autosave` |
| `created_at` | timestamptz | — |

约束：`uq_script_revision(round_id, revision_no)`。相同 title+body 不产生新版本。

#### `messages`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | bigint PK | — |
| `round_id` | UUID FK rounds.id | index |
| `role` | varchar(16) | `user` / `assistant` |
| `source` | varchar(24) | `student` / `assistant` / `hlsf_prompt` / `hlsf_hint` |
| `content` | text | 完整可见文本 |
| `client_message_id` | varchar(80) | nullable；幂等键 |
| `ai_call_id` | UUID | nullable；逻辑关联 ai_calls.id（**没有 FK**） |
| `created_at` | timestamptz | — |

约束：`uq_message_client_id(round_id, client_message_id)`。`null` 不参与唯一冲突（Postgres 允许多个 NULL）。

#### `hlsf_states`

| 列 | 类型 | 说明 |
|---|---|---|
| `round_id` | UUID PK/FK rounds.id | 一轮一行 |
| `phase` | varchar(16) | observe/explain/create/reflect/complete |
| `hint_used` | bool | 当前阶段是否用过提示 |
| `updated_at` | timestamptz | — |
| `completed_at` | timestamptz | 完成时间 |

只有 B 轮有记录。

#### `hlsf_events`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | bigint PK | — |
| `round_id` | UUID FK | index |
| `phase` | varchar(16) | 事件发生阶段 |
| `action` | varchar(32) | 见 5.9 |
| `message_id` | bigint FK messages.id | nullable |
| `meta_json` | JSON | prompt_version 等 |
| `created_at` | timestamptz | — |

#### `ai_calls`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | — |
| `run_id` | UUID FK runs.id | index |
| `round_id` | UUID FK rounds.id | nullable, index |
| `purpose` | varchar(24) | chat / chat_retry |
| `status` | varchar(16) | running/succeeded/failed |
| `model` | varchar(160) | — |
| `prompt_version` | varchar(24) | chat-v1 / chat-v1+hlsf-v1.1.1 |
| `request_json` | JSON | 完整 request |
| `response_text` | text | 模型文本 |
| `raw_response_json` | JSON | 原始响应 |
| `http_status` | int | — |
| `error_code` | varchar(80) | — |
| `error_message` | text | — |
| `latency_ms` | int | — |
| `created_at` | timestamptz | — |
| `completed_at` | timestamptz | — |

#### `image_jobs`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | — |
| `round_id` | UUID FK | index |
| `script_revision_no` | int | 入队时脚本版本 |
| `prompt` | text | 完整图片提示词 |
| `status` | varchar(16) | queued/running/succeeded/failed |
| `attempts` | int | worker 领取次数 |
| `retry_of_id` | UUID | nullable；逻辑关联旧 job（**没有 FK**） |
| `model` | varchar(160) | — |
| `file_path` | varchar(500) | 相对 `DATA_DIR` |
| `mime` | varchar(100) | — |
| `sha256` | varchar(64) | — |
| `width` / `height` | int | — |
| `http_status` | int | provider 状态 |
| `error_code` / `error_message` | varchar/text | — |
| `created_at` / `started_at` / `finished_at` | timestamptz | — |

#### `evidence_events`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | bigint PK | — |
| `round_id` | UUID FK | index |
| `section` | varchar(80) | artifact/introduction/facts/evidence/uncertainty |
| `event_type` | varchar(40) | 当前 `view` |
| `duration_ms` | int | nullable；前端当前不传 |
| `created_at` | timestamptz | — |

#### `assessment_responses`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | — |
| `run_id` | UUID FK | index |
| `kind` | varchar(32) | 五种 |
| `instrument_version_id` | UUID FK | 冻结版本 |
| `answers_json` | JSON | `{question_id: value}` |
| `status` | varchar(16) | draft/submitted |
| `started_at` | timestamptz | 草稿创建 |
| `updated_at` | timestamptz | — |
| `submitted_at` | timestamptz | — |
| `duration_seconds` | int | — |

约束：`uq_assessment_run_kind(run_id, kind)`。

#### `api_errors`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | bigint PK | — |
| `request_id` | varchar(80) | 当前 AI 错误写 null |
| `participant_id` | UUID | nullable, index |
| `run_id` | UUID | nullable, index |
| `category` | varchar(32) | text_ai / image_ai |
| `endpoint` | varchar(300) | chat / image-worker |
| `status_code` | int | — |
| `error_code` | varchar(80) | — |
| `message` | text | — |
| `created_at` | timestamptz | — |

### 9.3 枚举与不变量

| 项 | 值 |
|---|---|
| Group | G1/G2/G3/G4 |
| Condition | A/B |
| Artifact slot | X/Y |
| Stage | pre_test, round1_ready, round1_active, r1_test, round2_ready, round2_active, post_test, transfer, questionnaire, complete |
| HLSF phase | observe, explain, create, reflect, complete |
| Image status | queued, running, succeeded, failed |
| Assessment status | draft, submitted |
| Session role | student, admin |

不变量：

- 一个 participant 最多一个 run；
- 一个 run 最多一个 round1、一个 round2；
- 一个 round 只有一个 `hlsf_states`；
- 一个 run 每个 kind 只有一个 assessment response；
- 最多一个 active protocol；
- 每个 round 最多一个 succeeded image job（应用层保证，不是 DB 唯一约束）；
- 邮箱唯一；
- 所有时间戳 UTC。

### 9.4 迁移

- `0001_initial.py`：`Base.metadata.create_all()` 创建全部表。
- `0002_email_login.py`：给 `participants` 加 `email`（nullable）、唯一约束、索引；把 `access_code_hmac/last4` 改为 nullable；可重复执行（检查列/约束是否存在）。
- 启动时 Docker API 执行 `alembic upgrade head`；本地 dev 手动执行。
- 新表/列必须写显式 Alembic 迁移，不要改 `0001`（历史已执行）。

---

## 10. 事件与审计数据字典

### 10.1 `stage_events`

每次阶段切换：

- 关闭上一条 `completed_at IS NULL` 的事件，写 `completed_at`、`duration_seconds`；
- 插入新阶段事件；
- 进入 `complete` 时写 `run.completed_at`。

`meta_json` 常见内容：

| 场景 | meta |
|---|---|
| round start | `{"round_no": 1}` |
| round finish | `{"reason": "student_finished", "round_no": 1}` |
| timeout | `{"reason": "timeout", "round_no": 1}` |
| assessment submit | `{"assessment": "pre_test", "duration_seconds": 123}` |

用途：

- 计算每个阶段停留时长；
- 复原参与时间线；
- 检查是否异常快速/超时。

注意：当前阶段通常没有 `completed_at`，导出时是空值；分析时需要把最后一条开放事件视为进行中。

### 10.2 `evidence_events`

- section 由前端硬编码：`artifact`、`introduction`、`facts`、`evidence`、`uncertainty`；
- 每个 panel 会话去重，刷新后重新记录；
- `duration_ms` 目前不传，始终 null；
- 只能说明“打开过”，不能精确说明“看了多久”；
- 不是眼动/阅读深度指标。

### 10.3 `hlsf_events`

见 5.9。分析时：

- `prompt_delivered` + `message_id` 可以定位固定提示；
- `student_message`/`assistant_reply` 用于定位 B 组在哪个阶段互动；
- `advanced`/`skipped` 用于计算阶段推进方式；
- `guide_completed` 标记完成。

### 10.4 `ai_calls`

| 字段 | 分析用途 |
|---|---|
| purpose | 区分正常聊天/重试 |
| status | 成功率 |
| prompt_version | A/B 上下文版本 |
| request_json.messages | 实际发给模型的完整上下文（含 system prompt） |
| response_text | 模型可见回复 |
| latency_ms | 延迟 |
| error_code/message | 失败原因 |
| http_status | 上游状态 |

注意：失败的调用没有 assistant message；成功调用与 assistant message 通过 `ai_call_id` 逻辑关联（没有 FK）。

### 10.5 `image_jobs`

| 字段 | 分析用途 |
|---|---|
| status | 生成成功率/失败率 |
| attempts | worker 领取次数（通常 1；重启/重试另算新 job） |
| prompt | 实际图片提示词（可用于复现/分析） |
| script_revision_no | 图片基于哪个脚本版本 |
| error_code/message | 失败原因 |
| width/height/sha256 | 结果质量/去重 |
| created/started/finished | 排队与生成时长 |

### 10.6 `api_errors`

当前只记录：

- `category=text_ai`，`endpoint=chat`；
- `category=image_ai`，`endpoint=image-worker`。

不记录普通 4xx（如 409 stage）、登录失败、导出失败等。`request_id` 在 AI 错误中通常为 null。

### 10.7 如何复原一个学生的时间线

推荐顺序：

1. `runs`：created_at、stage、completed_at；
2. `stage_events`：每个阶段 entered/completed；
3. `rounds`：started/deadline/finished/reason；
4. `messages`：按 id；
5. `script_revisions`：按 round + revision；
6. `image_jobs`：按 round + created；
7. `hlsf_events`：按 id；
8. `evidence_events`：按 id；
9. `assessment_responses`：按 started；
10. `ai_calls` / `api_errors`：按 created。

### 10.8 分析时的常见坑

- **不要把消息数当学习深度**；HLSF 固定提示也会计入消息。
- **不要把 AI 生成内容当学生理解**；需要区分学生主动输入与模型输出。
- **B 组多出固定提示消息**；比较 A/B 消息数时要过滤 `source`。
- **图片失败也占额度**；`image_jobs` 行数不等于成功图片数。
- **HLSF 完成不等于学习完成**；学生可以一路点 Next/Skip。
- **R1 独立测试**不是随机分组后的后测，它紧接 R1，主要作用是 AI 锁定的独立作答。
- **transfer** 当前只是问卷式 instrument，不是 v1.3 的 T2 创作任务。

---

## 11. API 参考

### 11.1 通用约定

- Base path：`/api`
- 请求/响应：JSON（文件上传用 multipart；导出/图片是二进制）
- 认证：HttpOnly cookie，不需要 Authorization header
  - 学生：`hls_student`
  - 管理员：`hls_admin`
- Cookie：`HttpOnly`、`SameSite=Lax`、production `Secure`、`Path=/`
- 错误 envelope：

```json
{
  "error": {
    "code": "stage_not_active",
    "message": "This task is not active. Refresh to see your current stage.",
    "request_id": "uuid",
    "retryable": false,
    "details": {}
  }
}
```

- `details` 只在非空时出现。
- 每个响应带 `X-Request-ID`；请求可带 `X-Request-ID`，否则服务端生成。
- 非 GET/HEAD/OPTIONS 请求如果带 `Origin`，必须匹配 `PUBLIC_ORIGIN`/`EXTRA_ALLOWED_ORIGINS`，否则 403 `origin_rejected`。
- 没有 CORS 中间件；跨域浏览器请求不会得到 CORS 头。
- `Cache-Control: no-store` 自动加到 `/api/*`（除非已设置）。
- 生产环境关闭 `/api/docs`、`/api/openapi.json`、`/api/redoc`。
- FastAPI 请求体校验失败（Pydantic 422）返回默认 `{"detail":[...]}`，不是统一 envelope。

### 11.2 认证接口

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| POST | `/api/auth/enter` | 无 | 学生邮箱/旧 code 进入；创建 session |
| POST | `/api/auth/logout` | 学生 cookie（可选） | 撤销学生 session，清 cookie |
| POST | `/api/admin/login` | 无 | 研究者密码登录；限流 6/10min/IP |
| POST | `/api/admin/logout` | admin cookie（可选） | 撤销 admin session |
| GET | `/api/admin/session` | admin | 返回 `{authenticated:true}`；前端当前未使用 |

**POST /api/auth/enter**

```json
// email 模式
{"email": "name@polyu.edu.hk", "class_id": 1}

// 旧 code 模式
{"code": "ABCD2345", "class_id": 1}
```

- `EnterRequest` 要求 code/email 恰好一个。
- 成功：`{"state": StudentState}` + `Set-Cookie: hls_student=...`
- 错误：
  - 401 `invalid_access`（班级不存在/旧 code 无效）
  - 403 `polyu_email_required`
  - 409 `email_class_mismatch` / `class_full` / `email_already_registered`
  - 429 `too_many_attempts`
  - 503 `study_setup_incomplete`（无 active protocol，或 production demo protocol）

**POST /api/admin/login**

```json
{"password": "..."}
```

- 成功：`{"ok":true}` + `Set-Cookie: hls_admin=...`
- 401 `admin_invalid`
- 429 `too_many_attempts`
- 503 `admin_not_configured`

### 11.3 学生接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/student/state` | 当前阶段、步骤、参与者、active round、assessment kind |
| GET | `/api/student/rounds/{round_no}` | 该轮 artifact/script/timing/jobs/guide |
| POST | `/api/student/rounds/{round_no}/start` | 开始一轮 |
| POST | `/api/student/rounds/{round_no}/finish` | 结束一轮 |
| PUT | `/api/student/rounds/{round_no}/script` | 保存脚本（自动保存） |
| GET | `/api/student/rounds/{round_no}/messages?after_id=` | 拉消息（可增量） |
| POST | `/api/student/rounds/{round_no}/messages` | 发消息并同步等 AI 回复 |
| POST | `/api/student/rounds/{round_no}/messages/{message_id}/retry` | 重试最新未回复消息 |
| POST | `/api/student/rounds/{round_no}/hlsf/advance` | B 组推进/跳过 |
| POST | `/api/student/rounds/{round_no}/hlsf/hint` | B 组请求提示 |
| POST | `/api/student/rounds/{round_no}/evidence-events` | 记录资料查看 |
| POST | `/api/student/rounds/{round_no}/image-jobs` | 创建关键帧任务 |
| GET | `/api/student/image-jobs/{job_id}` | 查询任务状态 |
| GET | `/api/student/instruments/{kind}` | 获取测评 schema + 草稿 |
| PUT | `/api/student/instruments/{kind}/draft` | 保存草稿 |
| POST | `/api/student/instruments/{kind}/submit` | 提交测评 |

**GET /api/student/state 响应（示意）**

```json
{
  "participant": {
    "id": "uuid",
    "class_id": 1,
    "class_name": "班级 1 / Class 1"
  },
  "run_id": "uuid",
  "stage": "round1_active",
  "stage_label": "任务 1 / Task 1",
  "step": 2,
  "total_steps": 5,
  "completed": false,
  "assessment_kind": null,
  "assessment_label": null,
  "active_round": {
    "round_no": 1,
    "started_at": "...",
    "deadline_at": "...",
    "remaining_seconds": 812,
    "artifact_title": "...",
    "guide": {
      "version": "hlsf-v1.1.1",
      "phase": "observe",
      "hint_used": false,
      "completed_at": null,
      "phases": [{"id":"observe","label_zh":"观察","label_en":"Observe"}]
    },
    "image_job_limit": 3
  },
  "server_time": "..."
}
```

- `guide` 只有 B 组 active round 才有；A 组为 null。
- `active_round` 只在 round active 时存在；评估阶段为 null。
- `assessment_kind` 只在评估阶段非空。

**GET /api/student/rounds/{n} 响应（示意）**

```json
{
  "round_no": 1,
  "artifact": {
    "id": "uuid",
    "title": "...",
    "era": "...",
    "type": "...",
    "introduction": "...",
    "facts": ["..."],
    "evidence": ["..."],
    "uncertainty": ["..."],
    "image_url": "/api/files/artifacts/{id}/image"
  },
  "script": {"title": "", "body": "", "revision": 0, "updated_at": null},
  "started_at": "...",
  "deadline_at": "...",
  "remaining_seconds": 800,
  "finished": false,
  "image_jobs": [
    {
      "id": "uuid",
      "status": "succeeded",
      "prompt": "...",
      "attempts": 1,
      "error_code": null,
      "error_message": null,
      "image_url": "/api/files/keyframes/{id}",
      "width": 2816,
      "height": 1584,
      "created_at": "...",
      "finished_at": "..."
    }
  ],
  "image_job_limit": 3,
  "guide": null
}
```

> 代码内部 `round_payload()` 把 `image_job_limit` 初始设为 0；`GET /rounds`、`POST /start` 和 `GET /state` 路由会用 settings 覆盖为真实值。不要直接复用 service 返回值而忘记覆盖。

**POST /messages**

```json
{"content": "这件文物的纹样意味着什么？", "client_message_id": "uuid"}
```

- 成功：

```json
{
  "duplicate": false,
  "messages": [
    {"id": 12, "role": "user", "source": "student", "content": "...", "created_at": "..."},
    {"id": 13, "role": "assistant", "source": "assistant", "content": "...", "created_at": "..."}
  ],
  "guide": { ... } // B 组
}
```

- 重复 id：`{"duplicate": true, "messages": [原 user 消息]}`。
- 409 `message_pending`：上一条还没回复。
- 409 `round_expired`。
- 503/504/502 文本模型错误。

**POST /script**

```json
{"title": "标题", "body": "脚本正文"}
```

- 返回 `{"revision": 3, "created": true, "title": "...", "body": "...", "updated_at": "..."}`
- 相同内容返回 `created=false` 和现有 revision。
- 422 `script_too_long`（>200 title 或 >10000 body）。
- 409 `round_finished` / `round_expired`。

**POST /image-jobs**

```json
{} 
// 或
{"retry_of": "failed-job-uuid"}
```

- 返回 `{"job": ImageJob}`。
- 首次入队时服务端会再保存一次脚本？不，前端先生 `saveNow()`，服务端只读取已保存的最新脚本；如果脚本未保存会 422 `script_required`。
- 错误见 7.6。

**HLSF advance**

```json
{"from_phase": "observe", "skip": false}
```

- 返回 `{"guide": Guide, "messages": [新 assistant prompt]}`。
- 最后一阶段返回 messages 空数组，guide.phase=complete。

**HLSF hint**

```json
{"phase": "observe"}
```

- 返回 `{"guide": Guide, "messages": [hint]}`。
- 每阶段一次。

**Evidence event**

```json
{"section": "introduction", "event_type": "view", "duration_ms": null}
```

- 返回 `{"ok": true, "id": 123}`。
- 不检查 section 枚举；前端硬编码。

**Assessment**

- `GET` 返回 `{instrument, answers, status, started_at, updated_at, server_time}`。
- `PUT draft` body `{"answers": {...}}`，返回 `{status, answers, updated_at}`。
- `POST submit` body `{"answers": {...}}`，返回 `{status, submitted_at, state}`。

### 11.4 研究者接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/admin/readiness` | 13 项检查 + active protocol + latest content + counts |
| GET | `/api/admin/overview` | 参与者列表、统计、分组/阶段分布 |
| GET | `/api/admin/participants/{participant_id}` | 单个参与者完整详情 |
| GET | `/api/admin/artifacts` | X/Y 最新版本 + 版本列表 |
| POST | `/api/admin/artifacts/{slot}/versions` | 新建 artifact 版本（multipart） |
| GET | `/api/admin/instruments` | 五个 kind 最新 + 版本列表 |
| POST | `/api/admin/instruments/{kind}/versions` | 新建 instrument 版本（JSON） |
| POST | `/api/admin/protocol/activate` | 冻结当前最新内容为新协议 |
| GET | `/api/admin/cohort/codes.csv` | 旧 code 模式 CSV（email 模式 404） |
| GET | `/api/admin/export` | 生成并下载 ZIP |

**POST /api/admin/artifacts/{slot}/versions**

`multipart/form-data` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `title` | text | 必填，≤200 |
| `era` | text | ≤120 |
| `artifact_type` | text | ≤120 |
| `introduction` | text | ≤20000 |
| `facts_json` | text | JSON 字符串数组，≤50 条 |
| `evidence_json` | text | 同上 |
| `uncertainty_json` | text | 同上 |
| `image` | file | 首次必填；后续不传则复用上一版图片 |

- 每次调用创建新版本；版本号自动 +1。
- 图片限制：≤12 MB、≤30 MP；超过 2400px 会缩略；统一转 PNG。
- 返回 `{"artifact": AdminArtifact}`。

**POST /api/admin/instruments/{kind}/versions**

JSON `InstrumentPayload`（见 8.2）。创建新版本。

**POST /api/admin/protocol/activate**

- 无 body（schema `ProtocolActivate` 存在但路由未使用 body）。
- 读取 readiness；不 ready → 409 `protocol_not_ready`，details 带 failed_checks。
- demo 内容 + production → 409 `demo_content_blocked`。
- 非 production 且 `allow_demo=True`（admin 路由传入）→ 允许激活 demo。
- 先把当前 active 置 false，再创建新 active protocol。
- 返回 `{"protocol": ..., "readiness": ...}`。

**GET /api/admin/export**

- 生成 ZIP（详见第 12 节）。
- `Content-Type: application/zip`，文件名 `heritage-research-export-YYYYmmdd-HHMMSS.zip`。
- 响应完成后后台任务删除临时文件。
- 大导出可能耗时；当前同步生成。

### 11.5 文件接口

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| GET | `/api/files/artifacts/{version_id}/image` | student/admin | 文物图片；学生必须在其 run 中拥有该版本 |
| GET | `/api/files/keyframes/{job_id}` | student/admin | 关键帧；学生必须拥有该 job 的 run |

- 不是公开静态文件；不要直接暴露 `DATA_DIR`。
- `Content-Disposition: inline`；`Cache-Control: private, max-age=300`。
- 路径遍历防护：`resolve()` 后必须位于 `DATA_DIR`。

### 11.6 健康接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health/live` | 返回 `{"status":"ok"}`，不查数据库 |
| GET | `/api/health/ready` | 查 DB + DATA_DIR；返回 `status/database/database_error/storage/text_model_configured/image_model_configured/auth_mode/environment`；失败 503 |

Docker API healthcheck 使用 `/api/health/ready`。

非 production 环境还开放：

- `GET /api/docs` — Swagger UI；
- `GET /api/openapi.json` — OpenAPI schema；
- `/api/redoc` 关闭。

production 下三者都为 `None`（不可访问）。

### 11.7 错误码总表（按类别）

**认证/权限**

| code | HTTP | 含义 |
|---|---|---|
| `not_authenticated` | 401 | 无有效学生 session |
| `admin_unauthorized` | 401 | 无有效 admin session |
| `admin_invalid` | 401 | 研究者密码错误 |
| `admin_not_configured` | 503 | 未设置 ADMIN_PASSWORD |
| `invalid_access` | 401 | 旧 code/班级无效 |
| `polyu_email_required` | 403 | 邮箱不含 polyu |
| `email_class_mismatch` | 409 | 邮箱已注册到其他班 |
| `class_full` | 409 | 班级满 |
| `email_already_registered` | 409 | 并发注册冲突 |
| `too_many_attempts` | 429 | 限流 |
| `origin_rejected` | 403 | Origin 不在允许列表 |

**阶段/轮次**

| code | HTTP | 含义 |
|---|---|---|
| `study_setup_incomplete` | 503 | 无 active protocol / production demo |
| `stage_not_active` | 409 | 当前 stage 不允许该操作 |
| `stage_not_ready` | 409 | 不能开始该轮 |
| `round_not_started` | 409 | round 未创建 |
| `round_already_started` | 409 | 重复开始 |
| `round_expired` | 409 | 已超时 |
| `round_finished` | 409 | 已结束 |
| `assessment_not_active` | 409 | 当前 stage 不是该测评 |
| `assessment_submitted` | 409 | 已提交 |
| `message_pending` | 409 | 上一条未回复 |
| `message_not_found` | 404 | 消息不存在 |
| `message_not_latest` | 409 | 只能重试最新消息 |
| `guide_not_started` | 409 | B 引导未初始化 |
| `guide_phase_changed` | 409 | 阶段已变 |
| `guide_complete` | 409 | 引导已完成 |
| `hint_already_used` | 409 | 本阶段提示已用 |

**内容/测评**

| code | HTTP | 含义 |
|---|---|---|
| `instrument_missing` | 503 | 协议没有该测评/版本丢失 |
| `instrument_not_found` | 404 | 未知 kind |
| `invalid_answers` | 422 | 未知题/无效值 |
| `answers_incomplete` | 422 | 必答缺失 |
| `protocol_not_ready` | 409 | readiness 未通过 |
| `demo_content_blocked` | 409 | production 不允许 demo |
| `artifact_not_found` | 404 | 文物版本不存在 |
| `artifact_image_missing` | 404 | 图片文件缺失 |
| `artifact_missing` | 503 | artifact version 丢失 |
| `artifact_slot_not_found` | 404 | slot 不是 X/Y |
| `invalid_field` | 422 | 表单字段错误 |
| `invalid_image` | 422 | 上传不是有效图片 |
| `image_too_large` | 413 | 文物图片过大 |
| `image_required` | 422 | 首版必须上传图片 |
| `script_too_long` | 422 | 脚本超长 |
| `script_required` | 422 | 无脚本不能生成关键帧 |

**图片/文本**

| code | HTTP | 含义 |
|---|---|---|
| `text_model_not_configured` | 503 | 文本模型未配置 |
| `text_model_timeout` | 504 | 文本超时 |
| `text_model_unavailable` | 502 | 文本连接失败 |
| `text_model_error` | 502 | 文本上游错误 |
| `text_model_bad_response` | 502 | 文本响应不可用 |
| `image_model_not_configured` | 503 | 图片模型未配置 |
| `image_job_active` | 409 | 已有任务 |
| `keyframe_exists` | 409 | 已有成功图 |
| `image_quota_exhausted` | 429 | 额度用完 |
| `invalid_retry` | 422/409 | 重试目标无效 |
| `image_job_not_found` | 404 | 任务不存在 |
| `image_model_timeout` | 504 | 图片超时 |
| `image_model_unavailable` | 502 | 图片连接失败 |
| `image_model_error` | 502 | 图片上游错误 |
| `image_model_bad_response` | 502 | 图片响应不可用 |
| `image_download_failed` | 502 | URL 下载失败 |
| `image_result_too_large` | 413 | 结果过大 |
| `image_result_invalid` | 502 | 结果不是图片 |
| `image_internal_error` | 500 | worker 异常 |

**文件/其他**

| code | HTTP | 含义 |
|---|---|---|
| `not_found` | 404 | 通用 |
| `run_not_found` | 401/404 | run 不存在 |
| `participant_not_found` | 404 | 参与者不存在 |
| `protocol_missing` | 500 | 协议丢失 |
| `image_not_found` | 404 | 图片不存在 |
| `image_not_ready` | 404 | 图片任务未成功 |
| `image_missing` | 404 | 图片文件缺失 |
| `codes_not_used` | 404 | email 模式无 code CSV |
| `codes_csv_missing` | 404 | code CSV 不存在 |
| `internal_error` | 500 | 未捕获异常 |

---

## 12. 研究数据导出

### 12.1 ZIP 结构

```text
heritage-research-export-YYYYmmdd-HHMMSS.zip
├── participants.csv
├── runs.csv
├── stage_events.csv
├── rounds.csv
├── messages.csv
├── hlsf_events.csv
├── evidence_events.csv
├── script_revisions.csv
├── image_jobs.csv
├── assessments.csv
├── assessment_answers.csv
├── ai_calls.csv
├── api_errors.csv
├── protocol.json
├── README_data_dictionary.md
├── manifest.json
└── files/
    └── {participant_uuid}/
        └── round-{1|2}/
            ├── script-r{revision}.txt
            └── keyframe-{job_id}.png
```

### 12.2 各 CSV 列

**participants.csv**

`participant_id, class_id, class_name, group, created_at`

**runs.csv**

`participant_id, class_id, class_name, group, run_id, protocol_version_id, stage, created_at, last_activity_at, completed_at`

**stage_events.csv**

`participant_id, run_id, stage, entered_at, completed_at, duration_seconds, meta_json`

**rounds.csv**

`participant_id, class_id, class_name, group, round_no, condition, artifact_id, artifact_title, started_at, deadline_at, finished_at, finish_reason, current_script_revision`

**messages.csv**

`participant_id, class_id, group, run_id, round_no, message_id, role, source, content, created_at`

**hlsf_events.csv**

`participant_id, round_no, phase, action, message_id, meta_json, created_at`

**evidence_events.csv**

`participant_id, round_no, section, event_type, duration_ms, created_at`

**script_revisions.csv**

`participant_id, round_no, revision_no, title, body, source, created_at`

**image_jobs.csv**

`participant_id, class_id, group, round_no, job_id, status, attempts, prompt, model, error_code, error_message, file, created_at, started_at, finished_at, width, height, sha256`

- `file` 是 ZIP 内路径，如 `files/{uuid}/round-1/keyframe-{job}.png`；失败任务为空。

**assessments.csv**

`participant_id, class_id, class_name, group, kind, instrument_version_id, instrument_version, status, answers_json, started_at, submitted_at, duration_seconds`

**assessment_answers.csv**（长表）

`participant_id, class_id, class_name, group, kind, question_id, question_type, question_prompt, answer_json, answer_text, submitted_at`

- 每题一行；`answer_text` 对非字符串用 JSON 字符串。

**ai_calls.csv**

`participant_id, run_id, round_no, purpose, status, model, prompt_version, request_json, response_text, http_status, error_code, error_message, latency_ms, created_at, completed_at`

**api_errors.csv**

`participant_id, run_id, category, endpoint, status_code, error_code, message, created_at`

**protocol.json**

```json
{
  "export_version": "export-v1",
  "active_protocol": { ... } | null,
  "artifact_versions": [ ...所有版本... ],
  "instrument_versions": [ ...所有版本... ]
}
```

- 包含所有 artifact/instrument 版本，不只是 active；
- `active_protocol` 只包含当前 active；
- 包含 artifact 的 facts/evidence/uncertainty、instrument 的完整 schema。

**README_data_dictionary.md**：内置说明，列出每个文件。

**manifest.json**：

```json
{
  "export_version": "export-v1",
  "generated_at": "...",
  "participants": 120,
  "runs": 17,
  "rounds": 30,
  "messages": 123,
  "script_revisions": 40,
  "image_jobs": 12,
  "assessments": 20,
  "missing_files": [],
  "notes": "No scoring is included. Raw research data only.",
  "csv_rows": { ... }
}
```

### 12.3 导出中不包含什么

- `participants.email`（PolyU 邮箱）
- 旧 `access_code_hmac` / `access_code_last4`
- `sessions` / token hash
- 管理员密码
- API keys
- 前端 `localStorage`
- `hlsf_states` 表本身（但 `hlsf_events` + `messages` 可以复原）
- 评分/量规结果（平台不做评分）
- 删除/同意记录（平台没有）

### 12.4 导出的敏感内容

- `ai_calls.request_json` 包含完整 system prompt + 对话；
- `messages.content` 包含学生自由文本；
- `assessment_answers` 包含问卷回答；
- `files/` 包含学生生成图片和脚本；
- 这些都属于研究数据/潜在个人数据，导出文件必须加密、限权、离机保存。

### 12.5 CSV 安全性

- 所有 CSV 为 UTF-8 with BOM（Excel 友好）。
- 以 `=`, `+`, `-`, `@`, tab, CR 开头的字符串会前置 `'`，降低 CSV 注入风险。
- 这**会改变 CSV 字面值**；原始值在 JSON 字段（如 `answers_json`）里保留。
- `None` → 空字符串；datetime → UTC ISO；dict/list → JSON 字符串。

### 12.6 媒体文件

- 只导出**当前脚本**的 `.txt`（最新 revision），所有 revision 在 CSV。
- 关键帧只导出 `status=succeeded` 且文件存在的原图；缺失记录到 `manifest.missing_files`。
- 关键帧文件名使用 job UUID；路径在 `image_jobs.file`。
- 文物图片不在导出中（它们是研究材料，不是参与者数据；`protocol.json` 有哈希）。

---

## 13. 安全、隐私与合规

### 13.1 身份与访问控制

**学生登录是“演示访问门”，不是认证**

- 只要字符串包含 `polyu` 就通过；不验证邮箱所有权；
- 任何人可以输入一个含 `polyu` 的地址进入；
- 同一个人可以用不同邮箱创建多个参与者；
- 这是明确接受的测试阶段设计，正式研究前必须改为 SSO/验证码/邀请码，或至少人工核对名单；
- 邮箱明文存储，研究者后台可见，研究导出不含。

**Session**

- 学生/管理员都是 opaque random token（`secrets.token_urlsafe(32)`）；
- 数据库只存 SHA-256(token)；
- Cookie：`hls_student` / `hls_admin`，HttpOnly、SameSite=Lax、production Secure、Path=/；
- 过期时间：学生 `SESSION_TTL_HOURS`（默认 24h），管理员 `ADMIN_SESSION_HOURS`（默认 8h）；
- 登出写 `revoked_at`；服务端每次检查 `revoked_at` 和 `expires_at`；
- 没有 refresh token。

**研究者**

- 单一共享密码 `ADMIN_PASSWORD`（≥16 字符 production）；
- `hmac.compare_digest` 比较；
- 限流 6 次/10 分钟/IP；
- 没有用户名、没有多用户、没有审计日志（谁登录/谁导出没有记录）。

### 13.2 隔离

- 所有学生接口从 session 推导 participant，不接受 participant_id 路径参数；
- 图片任务/文件通过 run join 校验 ownership；
- 文物图片只对“自己 run 中出现过该 artifact version”的学生开放；
- 管理员接口全部要求 admin session；
- Postgres/API/DATA_DIR 不在宿主机发布；
- 只有 Caddy 发布 80/443。

### 13.3 传输与头部

- Caddy 终止 TLS；自动 HTTPS。
- Caddy 设置：
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: same-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()`
  - CSP：`default-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; object-src 'none'`
  - HSTS 1 年
  - 移除 `Server`
  - `/api/*` 请求体最大 25MB
- FastAPI 也设置 nosniff/frame/referrer；API 响应默认 `no-store`。
- 没有 CORS；同源。
- **注意：CSP/HSTS 只在 Caddy 层；直接访问 FastAPI 端口没有这些头。**

### 13.4 输入与上传

- Pydantic 校验 JSON 形状/长度；
- 文物图片：≤12MB、≤30MP、Pillow verify、缩略到 2400px、转 PNG、sha256；
- 生成图片：≤25MB、≤40MP、Pillow verify、转 PNG、原子写入；
- 文件路径 resolve 后必须在 DATA_DIR 内；
- CSV 注入防护（见 12.5）；
- 前端转义由 React 默认完成；没有 `dangerouslySetInnerHTML`。

### 13.5 限流

| 端点 | 限制 | 键 |
|---|---|---|
| `/api/auth/enter` | 200 次 / 600 秒 | 客户端 IP |
| `/api/admin/login` | 6 次 / 600 秒 | 客户端 IP |

- 内存 deque，单进程；
- 共享 NAT 的教室可能共享 IP，所以 enter 限制较宽；
- 没有账户锁定、验证码、渐进延迟。

### 13.6 密钥与配置

- 所有密钥只在服务端 `.env`/容器环境；
- `.env` 被 `.gitignore`/`.dockerignore` 排除；
- 浏览器不包含任何 API key；
- API key 不写入日志/导出；
- 生产启动强制：ADMIN_PASSWORD ≥16、ANON_CODE_PEPPER ≥16、COOKIE_SECURE=true、PUBLIC_ORIGIN 为 https。

### 13.7 数据保护

- 研究导出不含邮箱/code/token/密码/密钥；
- 但导出含自由文本、对话、问卷、生成图片，仍属个人数据/敏感研究数据；
- `ai_calls.request_json` 含完整 prompt 和对话；
- 备份包含数据库 + DATA_DIR，必须加密、限权、离机；
- 没有自动保留期限/删除机制；
- 没有同意记录；
- 没有数据主体访问/删除流程；
- 没有管理员操作审计；
- 没有入侵检测/异常导出告警。

### 13.8 正式研究前必须补齐

- 伦理/IRB 批准；
- 知情同意（平台当前没有同意页）；
- 数据保留期限、删除流程、备份保留策略；
- 邮箱/班级/分组/自由文本/图片的 DPIA；
- 外部 AI provider 的数据处理条款、跨境传输、是否用于训练、成本上限；
- 真实身份的访问控制与最小化；
- 安全评审、渗透测试、依赖漏洞扫描；
- 生产环境监控/告警/日志保留；
- 若使用真实 SSO，替换当前 `polyu` 子串门。

---

## 14. 配置项

### 14.1 环境变量总表

| 变量 | 默认 | 作用 |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` 启用严格检查；Compose 强制 production |
| `SITE_ADDRESS` | `localhost` | Caddy 域名；Compose 必填；API 只用于启动日志 |
| `PUBLIC_ORIGIN` | `http://localhost:5173` | 浏览器 origin，用于 mutation Origin 校验；production 必须 https |
| `COOKIE_SECURE` | `false` | production 必须 true |
| `POSTGRES_DB` | `heritage` | Compose 数据库名 |
| `POSTGRES_USER` | `heritage` | Compose 数据库用户 |
| `POSTGRES_PASSWORD` | 无 | Compose 必填；建议字母数字，避免 URL 特殊字符 |
| `DATABASE_URL` | `postgresql+asyncpg://heritage:heritage@127.0.0.1:5432/heritage` | 实际 SQLAlchemy URL；Compose 用内部 db 构造 |
| `ADMIN_PASSWORD` | 空 | 研究者密码；production ≥16 |
| `ANON_CODE_PEPPER` | 空 | 组分配 HMAC seed + 旧 code HMAC；production ≥16；**分配后不可改** |
| `AUTH_MODE` | `email` | `email` 或 `code`（旧模式） |
| `DATA_DIR` | `data` | 持久数据根；Compose `/data` |
| `AUTO_BOOTSTRAP` | `true` | 启动时确保班级；email 模式不生成 code |
| `IMAGE_WORKER_ENABLED` | `true` | 是否启动图片 worker |
| `T1_DURATION_SECONDS` | `1440` | T1 秒数（24 分钟） |
| `T2_DURATION_SECONDS` | `1200` | T2 秒数（20 分钟） |
| `ROUND_DURATION_SECONDS` | `840` | 旧版回退值；新流程使用 T1/T2 时长 |
| `SESSION_TTL_HOURS` | `24` | 学生 session |
| `ADMIN_SESSION_HOURS` | `8` | 管理员 session |
| `DB_POOL_SIZE` | `20` | SQLAlchemy pool |
| `DB_MAX_OVERFLOW` | `20` | pool overflow |
| `LOG_LEVEL` | `INFO` | 配置存在，但当前 `logging.basicConfig` 固定 INFO；未实际生效 |
| `TEXT_MODEL_BASE_URL` | 无 | 文本 provider base（不含 `/chat/completions`） |
| `TEXT_MODEL_NAME` | 无 | 模型名 |
| `TEXT_MODEL_API_KEY` | 无 | 服务端 key |
| `TEXT_MODEL_TIMEOUT_SECONDS` | `60` | 文本超时 |
| `TEXT_TEMPERATURE` | `0.7` | 采样温度 |
| `TEXT_MAX_OUTPUT_TOKENS` | `900` | 最大输出；clamp 1–4000 |
| `TEXT_MODEL_THINKING` | 空 | `enabled`/`disabled`；DeepSeek 专用 |
| `IMAGE_MODEL_BASE_URL` | 无 | 图片 provider base（不含 `/images/generations`） |
| `IMAGE_MODEL_NAME` | 无 | 图片模型 |
| `IMAGE_MODEL_API_KEY` | 无 | 图片 key |
| `IMAGE_MODEL_TIMEOUT_SECONDS` | `120` | 图片超时 |
| `IMAGE_MODEL_SIZE` | `1024x1024` | 请求尺寸；模板 `2K` |
| `IMAGE_MODEL_RESPONSE_FORMAT` | 空 | `url`/`b64_json` |
| `IMAGE_MODEL_WATERMARK` | 空 | bool；模板 false |
| `IMAGE_MAX_CONCURRENCY` | `2` | worker 并发，clamp 1–8 |
| `IMAGE_JOB_LIMIT_PER_ROUND` | `3` | 每轮任务上限 |
| `CLASS_COUNT` | `4` | 正式班数量 |
| `PARTICIPANTS_PER_CLASS` | `30` | 每班容量 |
| `EXTRA_ALLOWED_ORIGINS` | 空 | 额外允许的浏览器 origin 列表；配置方式需按 pydantic-settings 的 list 解析 |

### 14.2 数据目录

```text
DATA_DIR/
├── artifacts/       文物图片（PNG）
├── keyframes/       学生关键帧（PNG）
│   └── {participant_uuid}/round-{n}/{job_id}.png
├── private/
│   └── access_codes.csv   仅旧 code 模式
└── exports/
    └── heritage-export-*.zip   临时文件，下载后删除
```

- 目录启动时自动 `mkdir -p`；
- 备份脚本打包整个 `/data`；
- 恢复会先清空 `/data` 再解包。

### 14.3 生产启动检查

`create_app()` 在 production 下直接抛 RuntimeError（进程起不来）如果：

- `ADMIN_PASSWORD` 长度 < 16；
- `ANON_CODE_PEPPER` 长度 < 16；
- `COOKIE_SECURE` 不是 true；
- `PUBLIC_ORIGIN` 为空或不以 `https://` 开头。

这是 fail-closed 设计，不要绕过。

---

## 15. 部署与运维

### 15.1 Docker Compose 结构

| 服务 | 镜像/构建 | 端口 | 卷 | 说明 |
|---|---|---|---|---|
| `db` | `postgres:16-alpine` | 不发布 | `db_data` | 健康检查 `pg_isready` |
| `api` | `backend/Dockerfile` | 不发布，`expose 8000` | `app_data:/data` | 启动 `alembic upgrade head && uvicorn ... --workers 1` |
| `caddy` | 根目录 `Dockerfile.caddy`（先构建前端） | `80:80`, `443:443`, `443:443/udp` | `caddy_data`, `caddy_config` | 静态 SPA + `/api/*` 反代 |

- `api` 依赖 `db` healthy；`caddy` 依赖 `api` healthy。
- `api` 的 `ENVIRONMENT=production` 由 Compose 强制。
- `DATABASE_URL` 由 `POSTGRES_*` 拼接；密码含 `$`/`#`/空格/URL 分隔符时可能出错，建议字母数字长密码或 URL 编码。
- `api` 以 uid 10001 非 root 运行；`/data` 属主 appuser。
- 单 worker：图片 worker、聊天锁、限流都在进程内。

### 15.2 首次部署

```bash
cp .env.example .env
# 填写：SITE_ADDRESS, PUBLIC_ORIGIN, COOKIE_SECURE=true,
# POSTGRES_PASSWORD, ADMIN_PASSWORD, ANON_CODE_PEPPER,
# DATABASE_URL, TEXT_MODEL_*, IMAGE_MODEL_*
docker compose up -d --build
docker compose ps
```

然后：

1. 打开 `https://<SITE_ADDRESS>/admin`；
2. 用 `ADMIN_PASSWORD` 登录；
3. 研究材料 → 配置两套 Evidence Pack（X/Y）和五个 instrument；
4. 准备检查 → 确认所有检查通过；
5. 激活协议；
6. 学生从 `/` 用班级 1–4 进入；
7. 首次部署没有 active protocol 时，学生会看到“study setup incomplete”。

### 15.3 本地开发（无 Docker）

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.txt --no-cache-dir

cp .env.example .env
# ENVIRONMENT=development
# COOKIE_SECURE=false
# PUBLIC_ORIGIN=http://127.0.0.1:5173
# 本地 DATABASE_URL
# AUTH_MODE=email

cd backend
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

另一个终端：

```bash
cd frontend
npm ci --no-audit --no-fund
npm run dev
```

打开 `http://127.0.0.1:5173`；Vite 把 `/api` 代理到 8000，cookie 同源。

### 15.4 本地一键运行时（测试专用）

```bash
# 终端 1：临时 PostgreSQL + 明确标注的假 AI + demo 内容 + API:8000
PYTHONPYCACHEPREFIX=$PWD/.pycache backend/.venv/bin/python scripts/dev_runtime.py

# 终端 2：前端
cd frontend && npm run dev

# 终端 3：Playwright（注意 e2e 现状见 17.5）
cd frontend && npx playwright test --config=playwright.config.ts
```

- `scripts/dev_runtime.py` 每次默认**删除并重建**本地 `heritage_dev` 数据库和 `.local-runtime/data`；
- `HLS_PRESERVE=1` 保留；
- `HLS_USE_REAL_AI=1` 使用 `.env` 的真实 provider（会检查六个必需变量）；
- 默认假 AI 文本回复带 `[LOCAL TEST STUB — NOT A REAL MODEL]`，图片是纯色 1280×720 PNG；
- 本地研究者密码：`local-dev-admin-password-123`；
- 本地学生：任意含 `polyu` 的邮箱 + class 0。

**绝不能**用这个本地运行时收集正式研究数据，也不能把 stub 结果当作真实模型验证。

### 15.5 Demo 内容

```bash
cd backend
.venv/bin/python -m app.cli seed-demo
.venv/bin/python -m app.cli readiness
```

- `seed-demo` 创建：
  - 两件占位文物 X/Y（灰色 PNG，标记 DEMO）；
  - 五个占位 instrument（标记 DEMO）；
  - 激活一个 demo protocol（非 production）。
- 它会拒绝在有 run 时执行；production 下 `cli` 直接拒绝运行。
- demo 内容在 admin 显示警告；production readiness 不允许 demo。

### 15.6 测试

```bash
# 后端：真实临时 PostgreSQL + 测试 HTTP stub
cd backend
PYTHONPYCACHEPREFIX=../.pycache .venv/bin/pytest -q

# 前端
cd frontend
npm run typecheck
npm run build
npm test
```

### 15.7 备份与恢复

```bash
./scripts/backup.sh
# backups/<UTC timestamp>/{database.dump,appdata.tar.gz,manifest.txt,SHA256SUMS}

CONFIRM_RESTORE=YES ./scripts/restore.sh /path/to/backup
```

- 备份脚本从 `.env` 取数据库凭据；
- 使用 `docker compose exec`，要求栈在运行；
- 恢复会**停 API、清空 /data、pg_restore --clean**，是破坏性的；
- `.env`/密钥不包含在备份中，需单独用 secret manager 保存；
- 备份含个人数据，必须加密、限权、离机；
- 交付前应做一次真实恢复演练（当前未做）。

### 15.8 升级/迁移

```bash
docker compose up -d --build
# API 容器启动时自动 alembic upgrade head
```

- 新迁移必须 `alembic revision` 生成并 review；
- 不要在已有数据的库上改 `0001`；
- 大版本升级前先备份；
- 迁移失败容器不会启动，`docker compose logs api` 查看。

### 15.9 健康检查与日志

```bash
curl https://<domain>/api/health/live
curl https://<domain>/api/health/ready
docker compose logs -f --tail=200 api
docker compose logs -f --tail=200 caddy
```

- `/api/health/ready` 失败返回 503；Caddy 依赖它做健康检查。
- 日志格式：`%(asctime)s %(levelname)s %(name)s %(message)s`。
- 不记录请求体/API key；AI 请求体在数据库 `ai_calls` 中，不在日志。

### 15.10 静态部署检查

```bash
PYTHONPYCACHEPREFIX=.pycache backend/.venv/bin/python scripts/check_deployment.py
```

检查：

- Compose 有 db/api/caddy；
- db/api 不发布端口；
- Caddy 端口正好 80/443/udp；
- API 数据卷；
- Caddyfile 反代/SPA fallback/HSTS；
- `.env.example` 关键变量；
- Dockerfile/Caddyfile/脚本存在。

**它不验证 Docker 构建、Caddy TLS、公网可达性。**

### 15.11 生产运维清单

- [ ] 独立生产数据库，不复用本地测试库；
- [ ] 强随机 `ADMIN_PASSWORD`（≥16）、`ANON_CODE_PEPPER`（≥16，备份且不再改）；
- [ ] `AUTH_MODE=email`；
- [ ] `COOKIE_SECURE=true`、`PUBLIC_ORIGIN=https://...`；
- [ ] 只开放 80/443；
- [ ] 配置真实文本/图片 provider，先做 smoke；
- [ ] 配置两套审核过的 Evidence Pack 和五个 instrument；
- [ ] readiness 全绿、激活协议；
- [ ] 备份/恢复演练；
- [ ] 监控 provider 错误、磁盘、队列；
- [ ] 确认班级 0 数据不进入正式分析；
- [ ] 共享设备上每个学生结束后退出/清 session；
- [ ] 伦理/同意/保留/删除/provider 数据条款完成。

---

## 16. 代码地图与请求生命周期

### 16.1 后端模块职责

| 文件 | 职责 |
|---|---|
| `app/main.py` | FastAPI app、lifespan、迁移后启动、bootstrap、ImageWorker 启停、中间件、路由挂载、production 门禁 |
| `app/config.py` | Settings、路径、`is_production`、`text_configured`/`image_configured` |
| `app/db.py` | async engine/session factory |
| `app/models.py` | 18 张表 |
| `app/domain.py` | Group/Condition/Stage/HLSF 枚举、G1–G4 映射、阶段→测评映射、步骤映射 |
| `app/schemas.py` | 请求体、Question/InstrumentPayload、错误 envelope |
| `app/dependencies.py` | cookie 读取、session 校验、student/admin 依赖、cookie 设置 |
| `app/security.py` | token、SHA256、HMAC、code、RateLimiter |
| `app/errors.py` | AppError + 统一错误处理 |
| `app/bootstrap.py` | `ensure_classes`、旧 code cohort、CSV |
| `app/cli.py` | seed-demo/readiness |
| `routers/auth.py` | 学生 enter/logout、admin login/logout/session |
| `routers/student.py` | 学生 state/round/script/chat/HLSF/evidence/image/assessment |
| `routers/admin.py` | readiness/overview/detail/content/protocol/export |
| `routers/files.py` | 文物图/关键帧私有读取 |
| `routers/health.py` | live/ready |
| `services/run_state.py` | 阶段机、计时、round payload、student state、协议内容 |
| `services/ai_text.py` | 文本 provider、上下文、消息、AI 审计 |
| `services/hlsf.py` | B 引导状态、提示、推进、事件 |
| `services/image_queue.py` | 图片任务、worker、provider、校验、存储 |
| `services/artifacts.py` | 文物版本、图片处理、序列化 |
| `services/instruments.py` | instrument 版本、schema 校验、答案校验 |
| `services/assessments.py` | 测评草稿/提交/阶段推进 |
| `services/scripts.py` | 脚本 revision |
| `services/readiness.py` | readiness、协议激活、summary |
| `services/export.py` | ZIP/CSV/媒体导出 |
| `services/serialization.py` | message/image job DTO |
| `prompts/hlsf.py` | HLSF 固定文本/版本/教练上下文 |

### 16.2 前端模块职责

| 文件 | 职责 |
|---|---|
| `App.tsx` | `/admin` vs 学生端 |
| `api.ts` | fetch、cookie、错误解析、`ApiError` |
| `types.ts` | 全部 DTO 类型 |
| `pages/StudentApp.tsx` | 学生 state 加载、10s 轮询、按 stage 分发 |
| `pages/EntryPage.tsx` | 邮箱/班级入口 |
| `pages/AssessmentPage.tsx` | 五种测评 + 五种题型 |
| `pages/ReadyPage.tsx` | 两轮任务说明/开始 |
| `pages/Workbench.tsx` | 三栏工作台、聊天、HLSF、脚本、图片 |
| `pages/CompletePage.tsx` | 完成/退出 |
| `pages/AdminApp.tsx` | 后台认证、tab、参与者详情切换 |
| `components/AdminLogin.tsx` | 密码登录 |
| `components/AdminOverview.tsx` | 统计/筛选/列表/导出 |
| `components/AdminContent.tsx` | 文物/测评编辑器 |
| `components/AdminReadiness.tsx` | 检查/激活 |
| `components/ParticipantDetail.tsx` | 单参与者全量详情 |
| `components/StageSchedule.tsx` | 5 步安排 |
| `components/common.tsx` | 品牌、spinner、bilingual、错误、倒计时、localStorage 清理 |
| `styles.css` | 全部样式/设计 token/响应式 |

### 16.3 请求生命周期示例

#### 学生登录

```text
EntryPage.submit
  → POST /api/auth/enter
  → rate limit
  → class lookup
  → email normalize / polyu check
  → lock class row
  → existing participant? resume : allocate group + insert
  → create_or_resume_run
      → active protocol? production demo check?
      → insert run + pre_test stage_event
  → insert AuthSession (token hash)
  → commit
  → set cookie
  → student_state (guide/active round/assessment kind)
  → return {state}
  → StudentApp.onEnter
```

#### 发送一条消息

```text
ChatPanel.send
  → POST /api/student/rounds/1/messages {content, client_message_id}
  → _load_run (sync expired stage)
  → require_active_round
  → deadline check
  → duplicate client_message_id?
  → last message role must be assistant
  → insert user Message, commit
  → B: insert hlsf_event(student_message)
  → round lock
  → request_chat_reply
      → build system + history (+ B context)
      → insert AiCall(running), commit
      → provider POST
      → success: insert assistant Message, B assistant_reply, update AiCall, commit
      → failure: update AiCall + ApiError, raise
  → return messages + guide
  → ChatPanel append
```

#### 生成关键帧

```text
CreationPanel.generate
  → saveNow() (PUT script)
  → POST /rounds/1/image-jobs
  → require active/deadline
  → lock round
  → latest script non-empty?
  → already succeeded/active/quota?
  → validate retry_of
  → build prompt from artifact + script
  → insert ImageJob(queued)
  → commit, return job
  → UI polls GET /image-jobs/{id} every 2s
  → worker claims, calls provider, validates, stores, updates
  → UI shows image or error/retry
```

#### 提交测评

```text
AssessmentPage.submit
  → POST /instruments/pre_test/submit {answers}
  → assessment_context: lock run, stage check, protocol instrument, get/create response
  → validate_answers(require_complete=true)
  → status=submitted, submitted_at, duration
  → transition_stage(next)
  → commit
  → return state
  → onState → StudentApp renders next stage
```

#### 导出

```text
AdminOverview 点击导出（普通 <a href>）
  → GET /api/admin/export
  → build_export:
      查询全部表 → 生成 CSV/JSON/媒体 → 写临时 ZIP
  → FileResponse application/zip
  → BackgroundTask 删除临时文件
```

### 16.4 修改代码的约定

1. **服务端权威**：阶段、计时、权限、答案校验不能只靠前端。
2. **内容不可变**：artifact/instrument 编辑永远创建新版本；不要 update 旧行。
3. **协议冻结**：run 创建时绑定 protocol；不要运行时替换。
4. **不要加 mock 成功路径**：provider 失败必须显式失败；测试 stub 只用于测试。
5. **所有时间 UTC**：数据库 timestamptz；API ISO；前端本地化。
6. **学生查询必须按 session 限定**；不要加 participant_id 路径参数。
7. **文件路径必须限制在 DATA_DIR**。
8. **新表必须有 Alembic 迁移**，不要只改 models。
9. **改 HLSF 文本必须升版本**，并冻结。
10. **改前端 API 类型时同步 `types.ts` 和后端序列化**。
11. **不要在前端存 API key**；不要新增 CORS。
12. **单进程假设**：新增后台任务/锁时考虑是否可多进程。

---

## 17. 测试与验证现状

> **v1.5 current status:** 26 backend tests and 5 frontend tests pass; `tsc`/`vite build` and a fresh-DB Alembic migration/seed check pass. The detailed v1.0 baseline below is retained for history; see section 23.8 and [V15_CHANGE_REPORT.md](V15_CHANGE_REPORT.md) for the current suite.

### 17.1 本次实际执行（2026-11-06）

| 命令 | 结果 |
|---|---|
| `cd backend && PYTHONPYCACHEPREFIX=../.pycache .venv/bin/pytest -q` | **23 passed in 25.50s** |
| `cd frontend && npm test -- --reporter=dot` | **3 files / 5 tests passed** |

本次没有重新运行 `npm run typecheck`、`npm run build`、Playwright。历史记录（2026-11-05）显示 typecheck/build 通过；Playwright 在 email 改造后只重跑了 mobile entry，full-flow/HLSF 未重跑。

### 17.2 后端测试覆盖

`backend/tests/`：

- `test_smoke.py`：基础健康/入口
- `test_email_login.py`：PolyU 邮箱门、恢复、班级不匹配、class 0、分配
- `test_allocation.py`：G1–G4 映射、block 分配
- `test_flow.py`：完整两轮学生流程、阶段、计时、AI 锁定
- `test_hlsf_narrative.py`：HLSF 文本、B 上下文、A 无上下文、脚本注入、事件
- `test_text_failure.py`：文本失败记录/重试
- `test_security_and_reliability.py`：隔离、超时、图片失败/重试、并发、导出
- `test_admin_api.py`：admin 认证、内容版本、协议锁、导出
- `test_load.py`：30 并发参与者 + 图片并发上限

测试用**真实临时 PostgreSQL**（`pgserver`）和本地 HTTP 测试 stub；stub 明确标注，不代表模型质量/可用性。

### 17.3 前端测试覆盖

`frontend/src/tests/`：

- `countdown.test.tsx`：倒计时格式
- `entry.test.tsx`：入口渲染/提交
- `assessment.test.tsx`：测评渲染/草稿/提交（3 个）

### 17.4 真实 provider 验证（历史）

- DeepSeek 文本：HTTP 200，`deepseek-flash`，thinking disabled，约 2.8s；
- Volcengine Ark 图片：HTTP 200，`doubao-seedream-5-0-pro-260628`，2K URL，2,496×1,664 PNG；
- App 图片队列真实任务：2,816×1,584 PNG，通过认证文件接口读取；
- HLSF 七个场景在 demo 内容上通过；场景 2（证据连接）因 demo 证据不足，需要用正式 Evidence Pack 复测。

见 `docs/HLSF_LIVE_TEST.md`、`docs/TEST_REPORT.md`。

### 17.5 Playwright 的现状（重要）

`frontend/e2e/` 下的 spec **与当前 email 登录不完全匹配**：

- `full-flow.spec.ts` 和 `hlsf-narrative.spec.ts` 读取 `.local-runtime/data/private/access_codes.csv`，用旧 `code` 字段登录；
- 当前默认 `AUTH_MODE=email`，email 模式不生成 code CSV；
- 它们还期待页面出现“已生成参与者”等旧文案/元素；
- 因此这些 spec 很可能失败或需要改造。

`mobile.spec.ts` 已改为邮箱入口，理论上可跑。**不要直接把 Playwright 通过当作当前端到端已验证**；需要先改造 spec 以使用 email 登录（或临时 code 模式 + 生成 CSV）。

### 17.6 未验证/不能声称通过

- Docker 镜像构建、Compose 启动；
- Caddy 配置/TLS/公网 HTTPS；
- 真实 30 人 + 真实 provider 的限流/吞吐；
- 备份恢复演练；
- 正式内容的教育质量/评分者一致性；
- 伦理/同意/数据删除；
- 多进程/多副本扩展；
- 移动端全流程（只有入口窄屏测试）。

---

## 18. 当前本地实例快照（2026-11-06）

> 这是本机 `.local-runtime` 的**测试数据**，不是正式研究数据，也不代表生产状态。该库仍为 v1.0 旧协议/旧 run，**不能直接用于 v1.5 新流程**；v1.5 需要新测试库或备份后重建。

- API：`http://127.0.0.1:8000`，前端：`http://127.0.0.1:5173`
- `ENVIRONMENT=development`
- `AUTH_MODE=email`
- 数据库：`heritage_dev`（pgserver 临时 PostgreSQL）
- 当前 active protocol：demo（`is_demo=true`）
- 文物：X/Y 各 1 版，均为 demo 占位图
- 测评：五个 kind 各 1 版，均为 demo 占位
- 参与者：124（全部 class 0；本地测试历史数据）
- 已开始 run：17
- 已完成：7
- 阶段分布：complete 7、round1_active 5、pre_test 5、not_started 107
- 分组分布：G1 32、G2 30、G3 32、G4 30
- 本地研究者密码：`local-dev-admin-password-123`
- 本地学生：任意含 `polyu` 的邮箱 + class 0

当前表行数（只作本地调试参考，不是研究结果）：

| 表 | 行数 | 表 | 行数 |
|---|---:|---|---:|
| `classes` | 5 | `artifact_versions` | 2 |
| `instrument_versions` | 5 | `protocol_versions` | 1 |
| `participants` | 124 | `runs` | 17 |
| `rounds` | 19 | `stage_events` | 90 |
| `messages` | 91 | `script_revisions` | 21 |
| `image_jobs` | 11 | `hlsf_events` | 114 |
| `evidence_events` | 44 | `assessment_responses` | 41 |
| `ai_calls` | 19 | `api_errors` | 4 |
| `sessions` | 45 |  |  |

> 正式部署应使用全新数据库、class 1–4、非 demo 内容；不要把这份本地库迁到生产。

---

## 19. 与 v1.3 研究方案书的差距

参考文件：`reference/11-6研究计划更新-HLSF_v1_3_Research_Protocol_and_Platform_Specification_20261106.docx`

### 19.1 一张表看清

| 维度 | 当前代码（本平台） | v1.3 方案书（目标） |
|---|---|---|
| 总时长 | 约 60 分钟（两轮 14 分钟 + 测评） | 推荐 90 分钟连续，或两次 55–60 分钟 |
| 主要任务 | 短视频标题 + 脚本 + 1 张关键帧 | 文创产品设计 + 产品概念图 + 六字段结构化说明 |
| 任务结构 | R1、R2 两轮同构创作 | T1 训练（含 Observe/Explain/Create/Reflect 子阶段）+ T2 撤除脚手架的迁移创作 |
| A/B 设计 | **within-subject crossover**：每人两轮各一次 A/B | **between-subject**：每人只在一个条件；T2 所有人 Standard AI |
| 分组 | G1–G4 交叉文物顺序 × 条件顺序 | 班内 A/B 各半，组内平衡文物顺序 |
| 知识测验 | 五个可配置 instrument（默认 demo） | K0/K1/K2/K3 四次平行知识测验，按文物蓝图命题 |
| 评价 | 不评分，只存原始答案 | T2 4×0–3 分表现量规、双评分者、ICC、过程编码 |
| 同伴互评 | 无 | K3 + 问卷后，模拟 Instagram 作品流，4 件×2 题 + 点赞评论 |
| 同意/教程 | 无 | consent → K0 → tutorial → T1… |
| 社交模块 | 无 | 站内模拟 Instagram，不接真实 API |
| 产品字段 | 标题/脚本/关键帧 | 文化特征、历史功能/社会意义、资料依据、有意延续、现代转译、创新理由 |
| T2 输出 | 无（当前 `transfer` 只是问卷式 instrument） | 新文物 Y 的开放式创作 + 开放说明；无 HLSF 提示 |
| MaxDiff | 无 | 明确不在本次平台内 |
| 数据表 | 18 张，见第 9 节 | 需要新增 T2 作品、同伴互评、点赞/评论、K 测验蓝图等 |

### 19.2 当前代码与 v1.3 的概念映射（不要混用）

- 当前 `pre_test` ≈ K0 的位置，但**内容不是** v1.3 的知识蓝图；
- 当前 `r1_test` 是 R1 后的 AI 锁定测试，不是 K1/K2；
- 当前 `post_test`/`transfer`/`questionnaire` 是三个独立 instrument，不是 v1.3 的 K3 + survey + peer feed；
- 当前 `round2_active` 是第二轮创作，不是 v1.3 的 T2（因为第二轮仍可能给 B 引导，且任务是短视频脚本不是产品设计）；
- 当前 G1–G4 不是 v1.3 的 A/B 分组，而是四条件交叉。

### 19.3 如果目标是 v1.3，需要做什么

这不是小改，涉及研究设计和数据模型：

1. **参与者级条件**：在 participant/run 上增加 T1 的 `condition`（A/B），而不是每轮 condition；T1 按参与者条件，T2 所有人统一 Standard AI（无 HLSF）。
2. **T1/T2 任务模型**：新增产品设计字段（六字段说明）、产品类别、概念图；T2 使用新文物、开放说明、无 HLSF。
3. **K0–K3 题库**：新增知识蓝图/题目版本/评分键；四个时间点；可能需要题目级表。
4. **阶段机重写**：consent → K0 → tutorial → T1 四阶段 → K1 → K2 → T2 → K3 → survey → peer_feed → done。
5. **同伴互评/模拟 Instagram**：新增作品流、曝光、评分、点赞、评论表；匿名化；K3 后才解锁；不能评自己。
6. **评分/量规**：平台可以继续不自动评分，但需要导出评分工作台/评分表；双评分者/ICC 在平台外。
7. **同意与教程**：新增 consent 记录、tutorial 页面。
8. **时间/排程**：90 分钟或两次活动；T1/T2 时长可按 pilot 调整。
9. **导出**：新增 T2 作品、同伴互评、曝光、点赞/评论、K 测验长表；更新数据字典。
10. **UI**：产品设计工作台、六字段表单、T2 开放说明、作品流、互评页。
11. **测试**：新增大量端到端/数据一致性测试；重做 Playwright。

**建议**：如果当前 MVP 只是预试/工程验证，保留它；如果正式研究要按 v1.3 执行，另开分支/新版本，不要在当前数据模型上“打补丁”到无法审计。

---

## 20. 已知问题、风险与待办

### 20.1 研究/内容层面

- [ ] **正式 Evidence Pack 未配置**：当前只有 demo 占位；不能用于研究结论。
- [ ] **五个 instrument 未定稿**：demo 只有 1 题；没有知识蓝图、评分键、信效度。
- [ ] **没有评分/量规**：平台不评分；需要外部评分流程。
- [ ] **没有同意页**：正式研究前必须补齐或使用外部同意流程。
- [ ] **没有数据保留/删除机制**：需要制度 + 工具。
- [ ] **没有 K0–K3 / T2 / 同伴互评**：与 v1.3 目标差距大。
- [ ] **邮箱门不是认证**：可重复注册、可伪造；需人工监控或换 SSO。
- [ ] **class 0 测试数据**：本地库全部在 class 0；正式部署必须用新库/排除。
- [ ] **没有 pilot/认知访谈**：题目措辞、难度、时长未验证。
- [ ] **没有评分者培训/ICC**：如果要做表现评分。

### 20.2 工程/UX 层面

- [ ] **Pydantic 422 不是统一 envelope**：前端可能只显示“Request failed (HTTP 422)”；建议加 `RequestValidationError` handler。
- [ ] **测评没有倒计时**：如果研究需要限时测验，需要新增服务端 deadline/自动提交。
- [ ] **`LOG_LEVEL` 未生效**：日志固定 INFO；需要把 settings.log_level 接入 logging。
- [ ] **Playwright spec 过时**：仍用 code CSV/旧文案；email 模式下会失败。
- [ ] **E2E 未覆盖 email 全流程**：需要改造并重跑。
- [ ] **图片任务失败也占额度**：学生可能 3 次都失败后无法再生成；这是设计选择，但需在指导语中说明。
- [ ] **`image_job_limit=0` 内部默认**：`round_payload()` 默认 0，依赖路由覆盖；如果新增调用方忘记覆盖，前端会显示 0 额度。
- [ ] **AI 历史不裁剪**：长对话可能超上下文；需要 token 预算/裁剪策略。
- [ ] **没有请求超时/取消的前端控制**：聊天请求可能长时间挂起；只有 75 秒提示。
- [ ] **没有管理员操作审计**：谁导出、谁改内容、谁激活协议没有记录。
- [ ] **没有 CSRF token**：依赖 SameSite=Lax + Origin 检查；高风险部署可加 token。
- [ ] **没有多因素认证**：admin 只有密码。
- [ ] **没有账号锁定**：只有 IP 限流。
- [ ] **没有自动备份/监控**：脚本存在，但未接入 cron/告警。
- [ ] **没有删除/导出个人数据流程**。
- [ ] **没有无障碍完整测试**：键盘焦点、屏幕阅读器、对比度未系统验证。
- [ ] **前端没有错误边界**：未捕获渲染异常会白屏。
- [ ] **没有离线/弱网专门处理**：只有轮询和本地草稿。
- [ ] **Caddy/Docker 未实测**：配置存在但未构建/起栈/TLS 验证。
- [ ] **真实 30 人 + provider 限流未测**：本地用 stub。
- [ ] **单进程假设**：多副本需重做限流、聊天锁、图片 worker 协调。
- [ ] **备份恢复未演练**。
- [ ] **没有依赖漏洞扫描/SAST**。

### 20.3 扩展性风险

- 图片 worker 在 API 进程内，图片生成会占用 API 的 asyncio 事件循环（HTTP 调用是 async，但 Pillow 解码/保存在事件循环中执行；大图可能阻塞）。
- 单 worker uvicorn + 2 个图片任务 + 30 学生，可能在高并发下变慢。
- 聊天锁是进程内 dict，永不清理（round 数量增长会积累小对象；影响很小，但可清理）。
- `RateLimiter` 内存 dict 也会增长。
- 导出同步生成，大班/大量图片时请求可能很久。
- 数据库没有分区/归档；研究规模大时需要。

### 20.4 文档层面的不一致

- `docs/HLSF_LIVE_TEST.md` 写 `hlsf-v1.1`，代码是 `hlsf-v1.1.1`；
- `docs/TEST_REPORT.md` 写 Playwright full-flow/HLSF 未在 email 改造后重跑，e2e spec 仍用 code；
- `README.md` 说“two timed creation rounds and five research instruments”，准确；但不要把它读成 v1.3 的 T1/T2；
- `reference/` 的 v1.3 方案书不是已实现功能；
- `TASK_STATE.md` 是历史状态快照，可能落后于代码。

---

## 21. 交接与扩展指南

### 21.1 接手第一天做什么

1. 读本文件第 1–5、9–13 节；
2. 跑 `backend/.venv/bin/pytest -q` 和 `npm test`；
3. 用 `scripts/dev_runtime.py` + `npm run dev` 起本地；
4. 用 class 0 + 任意 polyu 邮箱走一遍完整学生流程；
5. 用 `/admin` 看总览、材料、readiness、参与者详情、导出；
6. 对照第 19 节确认研究目标：是继续当前 MVP，还是改造成 v1.3；
7. 确认 `.env` 的 provider/密钥归属和费用；
8. 确认正式内容/伦理/评分责任人。

### 21.2 替换/新增 Evidence Pack

1. `/admin` → 研究材料 → 文物 Evidence Packs；
2. 选 X 或 Y；
3. 填 title/era/type/introduction/facts/evidence/uncertainty；
4. 首次必须上传图片；后续不传则复用；
5. 保存 → 创建新版本；
6. **已有 run 时协议锁定**，不能激活新版本；正式研究前完成；
7. 若要新建一个全新 slot（Z），需要改：
   - `domain.SLOTS`
   - `ProtocolVersion` 增加列/JSON
   - G1–G4 映射
   - readiness/export/UI
   - 这不是配置能完成的。

### 21.3 新增/修改测评题目

1. `/admin` → 研究材料 → 测验与问卷；
2. 选择题型、题干、选项/行/量表；
3. 保存新版本；
4. 正式研究前重新激活协议；
5. 若要新增题型（如排序、矩阵、文件上传）：
   - `schemas.QuestionType`
   - `Question` validator
   - `instruments.validate_answers`
   - `AssessmentPage.QuestionField`
   - `AdminContent` 编辑器
   - 导出 `assessment_answers` 的 `answer_text`
   - 测试

### 21.4 修改 HLSF 提示词/阶段

1. 改 `backend/app/prompts/hlsf.py`；
2. 提升 `HLSF_VERSION`；
3. 如果新增阶段：
   - `domain.HLSF_ORDER` / `HLSFPhase`
   - `PHASE_LABELS`/`PHASE_PROMPTS`/`PHASE_HINTS`/`PHASE_COACHING`
   - `hlsf.advance_guide` 的末阶段判断
   - `Workbench.tsx` 的图标/文案
   - 测试/导出（phase 字符串）
4. 如果修改教练规则，回归 A 组上下文，确保没有泄漏；
5. 正式研究前冻结版本并在论文/附录记录。

### 21.5 修改分组/条件设计

当前四组映射在 `domain.GROUP_ASSIGNMENTS`。如果要改成 between-subject：

1. 在 `Participant` 或 `Run` 增加 participant-level condition；
2. 改 `round_assignment` 不再按 round 取 condition；
3. 改 `rounds.condition` 仍记录每轮实际条件（便于审计）；
4. 改分配算法（4 组 → 2 组 × 文物顺序）；
5. 改 `PROTOCOL.md`、前端无关（前端不显示）；
6. 迁移旧数据需要明确规则；
7. 更新测试/导出/分析脚本。

**不要**只改 `GROUP_ASSIGNMENTS` 而不改分配/文档，否则数据和文档会不一致。

### 21.6 新增一个 AI provider

文本：

1. 设 `TEXT_MODEL_*`；
2. 如请求/响应不同，改 `_call_provider()`；
3. 保留 `ai_calls` 记录（request/response/error/latency）；
4. 不要静默 fallback；
5. 跑真实 smoke。

图片：

1. 设 `IMAGE_MODEL_*`；
2. 如请求/响应不同，改 `_call_image_provider()`/`_parse_image_response()`；
3. 保留 URL/b64 两条路径；
4. 验证 ≤25MB/≤40MP/Pillow；
5. 跑真实队列 smoke。

### 21.7 新增导出字段

1. 确认字段在数据库；
2. 在 `export.py` 对应 CSV 的 `fieldnames` 和 row dict 增加；
3. 更新 `README_data_dictionary.md`；
4. 更新 `manifest` 计数（如新增表）；
5. 更新 docs/本文件；
6. 测试导出不泄漏 email/token/key；
7. 注意 CSV 注入转义。

### 21.8 新增后台页面

1. `AdminApp` 增加 tab；
2. 新建 `components/AdminXxx.tsx`；
3. 后端加 `/api/admin/...`，必须 `Depends(get_current_admin)`；
4. 前端 `api<T>()`；
5. 加 loading/error/empty；
6. 更新本文件第 4.8 节。

### 21.9 修改前端文案

- 学生入口/完成页：`EntryPage.tsx` / `CompletePage.tsx`；
- 任务说明：`ReadyPage.tsx` 的 `TASK_INFO`；
- 聊天/工作台：`Workbench.tsx`；
- 测评标签：`AssessmentPage.tsx` 的 `KIND_LABELS`；
- 后台：`AdminContent.tsx` 的 `KIND_NAMES` 等；
- 步骤：`StageSchedule.tsx`；
- 时长：`ReadyPage`、`StageSchedule`、`EntryPage` 写死 T1 24 / T2 20 / 总约 94 分钟；改 `T1_DURATION_SECONDS` / `T2_DURATION_SECONDS` 时要同步。

### 21.10 重置本地环境

```bash
# 停掉 dev_runtime，然后
rm -rf .local-runtime/pgdata .local-runtime/data
# 重新启动（会重建 DB + demo）
PYTHONPYCACHEPREFIX=$PWD/.pycache backend/.venv/bin/python scripts/dev_runtime.py
```

不要把 `.local-runtime` 提交/备份到生产。

### 21.11 变更完成定义（DoD）

- [ ] 后端测试通过；
- [ ] 前端 typecheck/build/test 通过；
- [ ] 新增/修改的 API 有权限/阶段/错误测试；
- [ ] 数据库迁移可 upgrade（必要时 downgrade）；
- [ ] 导出/数据字典同步；
- [ ] 文档（本文件 + 相关 docs）同步；
- [ ] 没有引入 mock 成功路径/密钥泄漏；
- [ ] 真实浏览器走一遍受影响流程；
- [ ] 正式研究相关变更已冻结版本并记录。

---

## 22. 故障排查

| 症状 | 可能原因 | 处理 |
|---|---|---|
| 学生入口提示“study setup incomplete” | 没有 active protocol；production 下 protocol 是 demo | `/admin` → 准备检查 → 配置/激活非 demo 协议 |
| 入口 403 `polyu_email_required` | 邮箱不含 `polyu` | 换 PolyU 邮箱；这是演示门 |
| 入口 409 `class_full` | 该班 email 参与者达 30 | 换班/清理测试数据；class 0 无上限 |
| 入口 409 `email_class_mismatch` | 邮箱已注册到其他班 | 选原班级；或换邮箱 |
| 入口 429 | 同 IP 进入过多 | 等待；检查是否 NAT/脚本 |
| 开始本轮 409 `stage_not_ready` | 当前不是 round_ready | 刷新；检查是否已开始/已超时 |
| 工作台空白/报错 | API 不可达、session 过期 | 刷新；重新登录；看 `/api/health/ready` |
| 倒计时到 0 但页面没动 | 前端定时器/网络 | 1.2 秒后会自动刷新；手动刷新；服务端会在下次请求推进 |
| 聊天一直“正在思考” | 文本 provider 慢/超时 | 等 75 秒提示；重试；查 `ai_calls`/`api_errors` |
| 聊天 503 | 文本模型未配置 | 检查 `TEXT_MODEL_*`；重启 API |
| 聊天 504/502 | provider 超时/错误 | 查 provider 状态/密钥/额度；重试 |
| 聊天 409 `message_pending` | 上一条没回复 | 点重试；不要连发 |
| 脚本不保存 | 超时/网络/后端 422 | 看保存状态；检查长度；刷新恢复 |
| 关键帧按钮灰 | 无脚本/已有成功/有任务/额度用完/超时 | 写脚本；等任务；看额度 0/3 |
| 图片失败 `server_restart` | 服务端重启时任务在跑 | 手动重试（消耗新任务额度） |
| 图片一直排队 | worker 未启动/未配置/并发占满 | 查 `IMAGE_WORKER_ENABLED`、`IMAGE_MODEL_*`、日志、队列 |
| 导出 401 | admin session 过期 | 重新登录 `/admin` |
| 导出 ZIP 缺图片 | 文件丢失/路径不对 | 看 `manifest.missing_files`；检查 DATA_DIR/权限 |
| 后台看不到“下载访问码 CSV” | email 模式禁用 | 正常；code 模式才有 |
| 后台 429 | 密码错误次数多 | 等 10 分钟；确认 `ADMIN_PASSWORD` |
| 生产启动失败 | 密码/pepper/secure/https 检查 | 看日志，按 14.3 修 |
| Caddy 502 | API 不健康/未启动 | `docker compose ps/logs api`；查 healthcheck |
| Caddy TLS 失败 | DNS/80/443/防火墙 | 检查 DNS 指向、端口、Caddy 日志 |
| `alembic` 失败 | DB 不可达/迁移冲突 | 查 DATABASE_URL；备份后处理 |
| Playwright 失败 | spec 仍用 code CSV/旧文案 | 改 spec 用 email；或临时 code 模式 |
| 前端白屏 | 构建/JS 错误/缓存 | 看 console；重新 build；清缓存 |
| 页面样式错乱 | 旧 dist/Caddy 缓存 | 重新 build/部署；强刷 |
| 数据目录不可写 | 权限/卷 | `chown`/检查 volume；health ready 会报 storage false |

### 22.1 常用诊断命令

```bash
# 健康
curl -s http://127.0.0.1:8000/api/health/ready | jq

# 最近 API 日志
docker compose logs --tail=200 api

# 数据库表
docker compose exec db psql -U heritage -d heritage -c '\dt'

# 迁移版本
docker compose exec api alembic current

# 本地进程
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:5173 -sTCP:LISTEN

# 备份校验
shasum -a 256 backups/<stamp>/*
```

### 22.2 数据恢复原则

- 先停 API，避免写入；
- 备份当前库/数据（即使要恢复，也保留现场）；
- 按 `restore.sh` 流程；
- 恢复后检查 `/api/health/ready`、admin 总览、导出；
- 记录恢复时间、备份来源、影响范围。

---

## 23. v1.5 当前实现增量（2026-11-06）

> 本节描述改造后的**当前**学生流程与新增能力。第 2–22 节是 v1.0 基线，保留用于历史数据/旧接口/迁移理解。完整变更清单见 [V15_CHANGE_REPORT.md](V15_CHANGE_REPORT.md)。

### 23.1 新流程与阶段

```text
登录（k0）→ 操作说明（tutorial）→ T1 任务说明（t1_ready）→ T1 创作（t1_active）
→ K1 → K2 → T2 任务说明（t2_ready）→ T2 创作（t2_active）
→ K3 → 体验问卷（survey）→ 同伴互评（peer_assessment）
→ 模拟作品广场（social_feed）→ 完成（complete）
```

- T1 约 24 分钟（`T1_DURATION_SECONDS=1440`）；T2 约 20 分钟（`T2_DURATION_SECONDS=1200`）。
- K0/K1 对应 T1 文物；K2/K3 对应 T2 新文物；K2 在 T2 之前。
- 所有测评阶段（k0/k1/k2/k3/survey）都不进入 active round，聊天、作品、资料、图片、HLSF 接口在服务端不可用。
- 旧 v1.0 阶段仍保留在后台标签和数据库中，但新的学生 run 不会进入；旧 run 的学生 API 返回 `legacy_run`。

### 23.2 新分组含义

| 组 | T1 | T2 |
|---|---|---|
| G1 | A，X | Y，Standard AI |
| G2 | A，Y | X，Standard AI |
| G3 | B，X | Y，Standard AI |
| G4 | B，Y | X，Standard AI |

- 块分配算法不变；`runs.t1_condition` / `runs.artifact_order` 记录固定条件与顺序。
- T1 的 `rounds.condition` 是 A/B；T2 的 `rounds.condition` 始终 A。
- T2 不显示 HLSF 阶段条、不发固定提示、不注入教练/训练历史；`/rounds/2/hlsf/*` 返回 404。

### 23.3 新工作台与作品数据

- T1 右栏：产品名称、产品类别/用途、目标受众、设计概念、六字段说明、1 张概念图。
- T2 右栏：产品名称、简短设计概念、1 张概念图、一个开放作品说明。
- 新接口：`PUT /api/student/rounds/{n}/work`；数据存 `work_revisions`（版本化），不再用 title/body 脚本。
- 旧 `PUT /api/student/rounds/{n}/script` 仍保留，但新工作台不调用；旧 `script_revisions` 不删除。
- 完成 T1 要求产品名称、类别、受众、设计概念和六字段齐全；完成 T2 要求产品名称和开放说明；图片失败不阻塞文字提交。
- 图片提示词改为文创产品概念效果图，`image_jobs.work_revision_no` 记录基于哪一版作品。

### 23.4 HLSF v1.5

- 版本：`hlsf-v1.5.0`。
- 四阶段目标从“短视频叙事”改为“文化知识理解 + 产品设计转译”：
  - Observe：两个文化特征，区分看见/猜测；
  - Explain：一个特征的历史功能、文化关系、资料依据与不确定性；
  - Create：保留哪项文化意义、如何转译为现代产品外观/功能/体验、为什么；
  - Reflect：区分史实/解释/当代创作，选一项设计决策修改。
- B 组 AI 上下文来自当前 `work_revisions`（产品字段/六字段/开放说明），不再注入 story seed 或短视频脚本。
- T2 对所有组关闭 HLSF；A 组 T1 也没有 HLSF。
- 旧 `hlsf-v1.1.1` 文案仅存在于历史数据/旧文档；新运行使用 1.5.0。

### 23.5 互评与作品广场

**班级链接与自动闸门**：

- 每个班 1–4 有独立入口链接 `/join?token=...`，链接绑定班级，学生进入时班级锁定。
- 学生首次用 PolyU 邮箱进入时创建 user；没来的人不创建 user，不参与等待。
- 阶段 `peer_assessment`；当该班**所有已进入 user 的 T2 都结束**（提交或超时）时，服务端自动冻结成员、生成 `PeerBatch` 并开放互评。
- 不要求固定 30 人：29 人全部结束就开放 29 人；每班仍上限 30。
- 开放后新邮箱不能加入该班（409 `class_closed`），已有 user 可恢复。
- 数据：`class_entry_links`、`class_peer_gates`、`class_peer_gate_events`。
- 运行说明：[CLASS_LINKS_AND_PEER_GATE.md](CLASS_LINKS_AND_PEER_GATE.md)。

**互评**：

- 互评池包含每名学生的 T1 与 T2 最终作品；闸门仍只在全班 T2 结束后打开。
- 正式班级目标每件作品 6 个评分、每名评审 12 件（6 件 T1 + 6 件 T2）；小班按实际人数降级（N=2 时每件 1 个评分、每人 2 件）。
- 排除自己的两件作品；同一评者不重复评同一作品；A/B 条件作为二次平衡目标。
- 三维 1–5 分（P1 文化表达清晰度、P2 文化转译清晰度、P3 设计创意），可选评论；内容版本 `peer-review-v2.1-pilot`。旧批次仍用旧 `clarity/evidence_link/attraction`，不得与新维度合并。
- 学生只见匿名 `work_code`、作品图、文物名称与冻结介绍、三段作品说明；混合 T1/T2 列表，不显示轮次、作者、条件、已有评分/热度。
- 必须提交全部分配才能继续；无作品/无分配时允许继续。
- 数据：`peer_batches`、`peer_assignments`、`peer_ratings`；后台和导出按 T1/T2、`reviewed_round_no` / `reviewed_ai_condition` 汇总收到的评分，并保留原始三维分。

**作品广场**：

- 阶段 `social_feed`；展示同班全部有效 T1/T2 两轮作品（含自己的），按每个学生固定哈希顺序，并在卡片上标注轮次。
- 不能给自己的作品点赞/评论；一人一作品最多一票，可取消；评论多条。
- 不显示点赞总数/评论热度；不接真实 Instagram。
- 数据：`social_views`、`social_likes`、`social_comments`、`social_events`；后台可隐藏评论。
- 完成后进入 `complete`。

**边界**：无 roster/SSO，无法核对指定姓名；没来的人不创建 user 即可被排除，但进入后长期不完成 T2 的异常账号会阻塞等待；T2 超时但文字不完整的作品不进入作品池，不阻塞全班。当前未实现信度/交叉随机效应分析。

### 23.6 新导出

新增 `work_revisions.csv`、`class_entry_links.csv`、`class_peer_gates.csv`、`class_peer_gate_events.csv`、`peer_batches.csv`、`peer_assignments.csv`、`peer_ratings.csv`、`peer_work_scores.csv`、`social_views.csv`、`social_likes.csv`、`social_comments.csv`、`social_events.csv`；`runs.csv` 增加 `t1_condition`/`artifact_order`；`rounds.csv` 增加 `current_work_revision`/`task`；`image_jobs.csv` 增加 `work_revision_no`；`analysis.csv` 增加每轮 T1/T2 互评汇总列；`files/` 增加 `work-rN.txt`。旧脚本 CSV 保留。

### 23.7 迁移与旧数据

- 迁移：`0003_v15_products_peer_social`、`0004_class_peer_gate`、`0005_class_entry_links`（增量，不删除旧列）。
- 旧开发库的 active protocol 不含 K0–K3/survey，新 run 会被 `study_setup_incomplete` 拒绝；请使用新测试库或重新 seed-demo。
- 旧 run 的学生 API 返回 `legacy_run`；后台仍可查看/导出历史。
- `ANON_CODE_PEPPER` 仍不可在分配后修改。

### 23.8 当前验证

- 后端 `28 passed`；前端 5 tests；`tsc --noEmit` 与 `vite build` 通过；迁移与 demo seed/readiness 在临时 PostgreSQL 上通过。
- Docker/Caddy 公网、真实 30 人 + provider 限流、正式伦理/内容/评分仍未验证。

---

## 附录 A：关键文件索引

| 文件 | 用途 |
|---|---|
| [README.md](../README.md) | 项目简介/快速开始 |
| [TASK_STATE.md](../TASK_STATE.md) | 历史任务状态（可能落后） |
| [docs/ARCHITECTURE.md](ARCHITECTURE.md) | 架构简述 |
| [docs/PROTOCOL.md](PROTOCOL.md) | 实验协议（A/B、HLSF、图片） |
| [docs/DATA_MODEL.md](DATA_MODEL.md) | 数据模型简述 |
| [docs/AUTH_AND_ALLOCATION.md](AUTH_AND_ALLOCATION.md) | 邮箱登录/分组分配 |
| [docs/SECURITY.md](SECURITY.md) | 安全说明 |
| [docs/RESEARCH_READINESS.md](RESEARCH_READINESS.md) | 正式研究前检查 |
| [docs/TEST_REPORT.md](TEST_REPORT.md) | 测试报告 |
| [docs/HLSF_LIVE_TEST.md](HLSF_LIVE_TEST.md) | 真实模型 HLSF 场景 |
| [docs/CLASS_LINKS_AND_PEER_GATE.md](CLASS_LINKS_AND_PEER_GATE.md) | 班级链接/自动互评闸门运行说明 |
| [docs/DEEPSEEK_SETUP.md](DEEPSEEK_SETUP.md) | DeepSeek/Ark 配置 |
| [docs/IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) | 实现日志 |
| [backend/app/models.py](../backend/app/models.py) | 全部表 |
| [backend/app/domain.py](../backend/app/domain.py) | 阶段/组/条件映射 |
| [backend/app/services/run_state.py](../backend/app/services/run_state.py) | 状态机/计时 |
| [backend/app/services/ai_text.py](../backend/app/services/ai_text.py) | 文本 AI/上下文 |
| [backend/app/services/image_queue.py](../backend/app/services/image_queue.py) | 图片队列 |
| [backend/app/services/export.py](../backend/app/services/export.py) | 导出 |
| [backend/app/prompts/hlsf.py](../backend/app/prompts/hlsf.py) | HLSF 提示词 |
| [backend/app/routers/student.py](../backend/app/routers/student.py) | 学生 API |
| [backend/app/routers/admin.py](../backend/app/routers/admin.py) | 后台 API |
| [frontend/src/pages/Workbench.tsx](../frontend/src/pages/Workbench.tsx) | 工作台 |
| [frontend/src/pages/AssessmentPage.tsx](../frontend/src/pages/AssessmentPage.tsx) | 测评页 |
| [frontend/src/components/AdminContent.tsx](../frontend/src/components/AdminContent.tsx) | 材料编辑器 |
| [frontend/src/styles.css](../frontend/src/styles.css) | 设计系统 |
| [docker-compose.yml](../docker-compose.yml) | 部署 |
| [Caddyfile](../Caddyfile) | 反代/TLS/头部 |
| [scripts/dev_runtime.py](../scripts/dev_runtime.py) | 本地测试运行时 |
| [scripts/backup.sh](../scripts/backup.sh) / [restore.sh](../scripts/restore.sh) | 备份/恢复 |
| [reference/11-6研究计划更新-HLSF_v1_3_Research_Protocol_and_Platform_Specification_20261106.docx](../reference/11-6研究计划更新-HLSF_v1_3_Research_Protocol_and_Platform_Specification_20261106.docx) | v1.3 目标方案（非已实现） |

---

## 附录 B：术语表

| 术语 | 含义 |
|---|---|
| HLSF | Heritage Learning Scaffolding Framework，本研究的四阶段学习脚手架：Observe → Explain → Create → Reflect |
| Condition A | 自由创作条件：普通 AI 助手，无 HLSF 引导 |
| Condition B | HLSF 引导条件：固定阶段提示 + 每阶段一次提示 + 叙事教练上下文 |
| Artifact X / Y | 两件文物证据包；每轮分配一件 |
| G1–G4 | 四组交叉分配：文物顺序 × 条件顺序 |
| Run | 一个参与者的完整研究运行 |
| Round | 一次 14 分钟创作（R1/R2） |
| Stage | 状态机阶段（pre_test、round1_active 等） |
| Evidence Pack | 文物证据包：图片、简介、事实、来源、不确定性 |
| Instrument | 测评/问卷 schema（五种 kind） |
| Protocol | 冻结的内容版本集合：两个 artifact + 五个 instrument |
| Keyframe | 根据脚本生成的关键帧图片 |
| HLSF State | B 组当前阶段/提示状态（`hlsf_states`） |
| HLSF Event | B 组提示/推进/回复事件（`hlsf_events`） |
| Readiness | 是否满足激活/开放学生的检查 |
| Demo content | 明确标记的占位内容，不可用于正式研究 |
| Participant UUID | 研究匿名 ID，导出主键 |
| R1 Test | 第一轮后的 AI 禁用独立测试 |
| Transfer | 迁移题（当前是问卷式 instrument，不是 v1.3 的 T2 创作） |

---

## 附录 C：交接检查清单

### C.1 代码与环境

- [ ] 能本地起 API + 前端；
- [ ] 能跑 23 个后端测试、5 个前端测试；
- [ ] 知道 `.env` 位置和密钥归属；
- [ ] 知道 `.local-runtime` 是测试数据，不是生产；
- [ ] 知道 `AUTH_MODE=email` 和 `polyu` 门的限制；
- [ ] 知道 `ANON_CODE_PEPPER` 不可改；
- [ ] 知道当前 active protocol 是 demo；
- [ ] 知道 Docker/Caddy 未实测。

### C.2 研究

- [ ] 确认研究问题是当前两轮设计还是 v1.3 T1/T2；
- [ ] 确认 A/B 是 crossover 还是 between-subject；
- [ ] 确认正式 Evidence Pack 作者/审核人；
- [ ] 确认五个 instrument 的题目/评分键；
- [ ] 确认评分量规/评分者培训；
- [ ] 确认伦理/同意/保留/删除；
- [ ] 确认 provider 数据处理/跨境/费用；
- [ ] 确认班级/人数/时间表；
- [ ] 确认 pilot 计划。

### C.3 运维

- [ ] 生产域名/DNS/TLS；
- [ ] 生产数据库/强密码/pepper；
- [ ] 备份/恢复演练；
- [ ] 监控/告警/日志；
- [ ] 只开 80/443；
- [ ] 真实 provider smoke；
- [ ] 30 人负载/限流测试；
- [ ] 正式开放前的 readiness 截图/记录。

### C.4 数据

- [ ] 导出一次 ZIP，检查所有 CSV/媒体/ manifest；
- [ ] 确认导出不含邮箱/token/key；
- [ ] 确认 `ai_calls.request_json` 的敏感性；
- [ ] 确认分析脚本使用 participant UUID，不 join 邮箱；
- [ ] 确认 class 0 数据排除规则；
- [ ] 确认缺失文件处理。

---

## 附录 D：本文件维护说明

- 本文件描述的是**当前代码**；代码变更后请同步更新对应章节。
- 若实现 v1.3，请新增“v1.3 实现状态”章节，不要直接覆盖本文件的历史描述。
- 若修改 HLSF 版本、阶段、导出字段、API，至少更新：第 5、6、9、11、12、19 节。
- 若修改部署/环境变量，更新第 14、15 节。
- 若修改测试，更新第 17 节。
- 所有截图位于 `e2e/screenshots/`，但部分截图来自 email 改造前，仅作 UI 参考。

---

**文档结束。**


