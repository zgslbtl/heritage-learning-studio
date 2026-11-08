# v1.5 增量改造变更报告

日期：2026-11-06（Asia/Shanghai）  
协议冻结：**v1.3 与 v1.5 的差异全部按 v1.5 执行**，见 [PROTOCOL_V15_FINAL.md](PROTOCOL_V15_FINAL.md)；正式就绪缺口见 [FORMAL_READINESS_V15.md](FORMAL_READINESS_V15.md)。  
依据：`reference/11-6-平台更新修改文档2-HLSF_Platform_Change_Requirements_v1_5_Peer_Social_20261106.md`  
基线：`PLATFORM_COMPLETE_GUIDE_ZH.md`（2026-11-06 交接版）及改造前实际代码  
原则：保留 PolyU 邮箱登录、FastAPI/React/PostgreSQL/Alembic/Docker/Caddy、AI Provider、`ai_calls`、图片队列、`participants → runs → rounds` 主体与匿名导出；只做增量扩展。

## 1. 已实现的流程

```text
登录 → K0 → 操作说明 → T1（产品设计 + 六字段） → K1 → K2
     → T2（新文物 + Standard AI + 开放说明） → K3 → 体验问卷
     → 同伴互评（盲评） → 模拟 Instagram 作品广场 → 完成
```

- T1 约 24 分钟；T2 约 20 分钟；K0–K3 与问卷无服务端倒计时。
- 测评阶段（K0/K1/K2/K3/问卷）不进入 active round，聊天、创作、图片、资料事件与 HLSF 接口均不可用，符合“服务端禁用”要求。
- 旧 v1.0 阶段（`pre_test`、`round1_*`、`r1_test`、`post_test`、`transfer`、`questionnaire`）保留在数据库/后台标签中用于历史数据展示；新的学生 run 不再进入这些阶段。

## 2. 分组与条件

`G1–G4` 的块分配算法不变，但含义改为：

| 组 | T1 条件/文物 | T2 |
|---|---|---|
| G1 | A，X | Y，Standard AI |
| G2 | A，Y | X，Standard AI |
| G3 | B，X | Y，Standard AI |
| G4 | B，Y | X，Standard AI |

- T1 条件由参与者的组固定；`rounds.condition` 记录实际条件（T1=A/B，T2=A）。
- `runs` 新增 `t1_condition`、`artifact_order`，便于审计。
- 不再让同一学生先后体验 A 和 B 两轮；T2 对所有来源组都关闭 HLSF。

## 3. 数据模型与迁移

迁移：`0003_v15_products_peer_social.py`（产品/互评/社交）、`0004_class_peer_gate.py`（班级闸门）、`0005_class_entry_links.py`（班级链接）

新增/修改：

- `runs.t1_condition`、`runs.artifact_order`
- `rounds.current_work_revision`
- `image_jobs.work_revision_no`
- `work_revisions`：版本化 T1/T2 产品设计；T1 用 `structured_fields` 存六字段 JSON；T2 用 `open_statement`
- `class_entry_links`：班级专属入口链接（只存 token hash，可撤销/轮换）
- `class_peer_gates`：每班自动互评闸门（动态人数、成员冻结时间、开放时计数）
- `class_peer_gate_events`：自动开闸审计事件
- `peer_batches`：班级互评批次（冻结版本；`algorithm_version` + `scale_version`）
- `peer_assignments`：评者 run → 作品 work，唯一约束
- `peer_ratings`：三维评分 JSON + 评论 + 时间
- `social_views`、`social_likes`、`social_comments`、`social_events`：真实曝露/点赞/取消/评论事件

旧 `script_revisions`、`title/body` 脚本列没有删除；旧 API `PUT /rounds/{n}/script` 仍保留，便于历史兼容。新工作台使用 `work` 接口。

## 4. 后端接口新增

认证/班级链接：

- `GET /api/auth/class-link?token=...`
- `POST /api/auth/enter` 支持可选 `class_token`
- `GET /api/admin/class-links`
- `POST /api/admin/class-links`
- `POST /api/admin/class-links/{id}/revoke`
- `POST /api/admin/class-links/{id}/rotate`
- `GET /api/admin/class-peer-gates`（只读自动闸门状态）

学生侧：

- `POST /api/student/tutorial/complete`
- `PUT /api/student/rounds/{n}/work`
- `GET /api/student/peer-assessment`
- `POST /api/student/peer-assessment/complete`（必须放在动态 assignment 路由之前）
- `POST /api/student/peer-assessment/{assignment_id}`
- `GET /api/student/social-feed`
- `POST /api/student/social/works/{work_id}/view`
- `POST /api/student/social/works/{work_id}/like`
- `POST /api/student/social/works/{work_id}/comment`
- `POST /api/student/social/complete`

研究者侧：

- `POST /api/admin/social/comments/{comment_id}/hide`
- 参与者详情新增 `works`、`peer_assignments`、`social_events`
- 导出新增作品、互评、社交 CSV

## 5. 产品设计工作台

T1 右栏：

- 产品名称（必填）
- 产品类别/用途
- 目标受众
- 设计概念
- 六字段说明：文化特征、历史功能与社会意义、资料与证据、文化延续、文化转译/再情境化、创新与设计理由
- 1 张产品概念图（图片失败仍可提交文字）

T2 右栏：

- 产品名称
- 产品类别/用途（可选）
- 目标受众（可选）
- 简短设计概念
- 1 张产品概念图
- 一个开放式作品说明（必填）

完成 T1 时服务端要求六字段齐全；完成 T2 时要求开放说明和产品名称。图片始终不是完成前置条件。

## 6. 图片提示词

`build_product_prompt()` 取代短视频关键帧提示词用于新轮次：

- 输入：文物标题/年代/类型/事实/证据 + 产品名称/类别/受众/设计概念/六字段/开放说明
- 输出方向：文创产品概念效果图、产品设计图/棚拍式视觉、文化上尊重、无文字/水印/品牌/伪造铭文
- `image_jobs.work_revision_no` 记录图片基于哪一版设计
- 旧 `build_image_prompt()` 保留给历史脚本轮次

## 7. HLSF v1.5

`backend/app/prompts/hlsf.py` 版本提升为 `hlsf-v1.5.0`：

- Observe：指出两个文化特征，区分直接观察与猜测
- Explain：结合资料解释一个特征的历史功能/文化关系/来源，资料不足要说明
- Create：保留哪项文化意义、如何转译为现代产品外观/功能/使用体验、为什么这样设计，不要只复制纹样
- Reflect：区分史实/解释/当代创作，选一项设计决策修改，最终由学生决定

B 组 AI 上下文改为产品设计教练 + 当前工作记录（`work_revisions`），不再注入 story seed / 短视频脚本 / 历史侦探等旧叙事内容。T2 强制关闭 HLSF：不显示阶段条、不发初始提示、不注入教练上下文、`/hlsf/*` 返回 404。

## 8. 互评与作品广场

### 互评

- 每个班有独立入口链接，链接绑定 class 1–4；学生首次用 PolyU 邮箱进入时创建 user，同邮箱恢复。
- 互评是否开放，只看该班**所有已进入 user 的 T2 是否都已结束**，不要求固定 30 人；29 人全部结束就开放 29 人，没人来的学生不会创建 user，不参与等待。
- T2 结束包括学生提交和 T2 超时自动结束；T2 超时但文字不完整的作品不进入作品池，但不阻塞全班。
- 全班 T2 结束后服务端自动冻结成员、生成 `PeerBatch` 和 assignments；**不需要管理员现场手动开放**。
- 开放瞬间写入 `membership_frozen_at`；之后新邮箱不能加入该班（409 `class_closed`），已有 user 可恢复。
- 从同班有效 T2 作品中分配；`peer-v2-balanced` 按实际 N 计算（N>=7 每人/每件 6，N<7 每人 N-1），尽量 3 件来自 T1 A、3 件来自 T1 B；排除自己；缺席/作品不足时自动降级。
- 同一评者不重复评同一作品；刷新/重登不重新洗牌。
- 每件作品三维 1–5 分：文化信息清晰度、知识—设计联系、整体吸引力；可选评论。
- 必须完成自己的所有分配才能进入作品广场；不等待全班完成互评；无作品/无分配时允许继续。
- 学生端只显示匿名 `work_code`，不显示作者、条件、已有评分或点赞数。

### 模拟 Instagram

- `social_feed` 阶段展示同班全部有效 T2 作品（含自己的），按每位学生固定随机顺序。
- 不能给自己的作品点赞/评论；一人一作品最多一票，可取消；评论多条；真实事件写入数据库。
- 不显示点赞总数/评论热度；不接真实 Instagram。
- 学生点“完成浏览”后进入 `complete`。

### 当前边界

- “全班”指该班链接下已经创建 user 的参与者；没来的人不创建 user，因此不参与计数。当前登录不是 SSO/roster，无法自动核对指定姓名名单。
- 若某 user 进入后长期停在 T2 之前、既不完成也不超时，闸门会继续等待；这是异常账号，需要另行处理（不是手动开放互评）。
- 开放后新邮箱不能加入该班；开放后才恢复的异常账号可能不在冻结批次中，需要研究者记录/按预案处理。
- 当前未实现“评价者 × 作品交叉随机效应”分析或信度计算；仅保存原始数据供外部分析。
- 社交点赞/评论只做最小实现；按研究组决定不做事前审核/审核 UI，保留隐藏评论应急接口。作品也不做人工审核。

## 9. 导出新增

新增 CSV：

- `work_revisions.csv`
- `class_entry_links.csv`
- `class_peer_gates.csv`
- `class_peer_gate_events.csv`
- `peer_batches.csv`
- `peer_assignments.csv`
- `peer_ratings.csv`
- `social_views.csv`
- `social_likes.csv`
- `social_comments.csv`
- `social_events.csv`

`runs.csv` 增加 `t1_condition`、`artifact_order`；`rounds.csv` 增加 `current_work_revision`、`task`；`image_jobs.csv` 增加 `work_revision_no`。`files/` 增加当前 `work-rN.txt`。旧 `script_revisions.csv` 保留。

## 10. 测试与验证

2026-11-06 执行：

- 后端：`46 passed`（包含 T1/T2 + K0–K3 全流程、HLSF v1.5、T2 无 HLSF、30 并发、班级链接、动态自动闸门、互评/社交交互、导出、正式内容导入与 form 分配）
- 前端：`4 files / 11 tests passed`
- 前端 `tsc --noEmit`：通过
- 前端 `vite build`：通过
- Alembic `0001 → 0002 → 0003 → 0004 → 0005 → 0006` 在临时 PostgreSQL 数据库执行：通过
- 迁移后确认存在 `work_revisions`、`peer_*`、`social_*` 表
- 新临时数据库执行 `alembic upgrade head` + `python -m app.cli seed-demo` + `readiness`：通过（demo protocol active，ready_for_students=true）

未验证（与改造前相同）：

- Docker Compose 实际构建/启动；
- Caddy 公网 TLS；
- 真实 30 人 + 真实 provider 限流/队列；
- 伦理同意、图片授权、30 人真实 Provider 压测、T2 评分工作台、Pilot；
- 浏览器 Playwright 全流程（旧 spec 仍使用 code CSV/旧阶段，需要另做 v1.5 E2E）。

## 11. 运行与兼容注意

- 使用**新测试数据库**或清空旧开发库后重新 `seed-demo`。旧库中的 active protocol 不含 K0–K3 五个新 instrument，新 run 会被 `study_setup_incomplete` 拒绝。
- 旧 run 的 stage 不在新 `STAGE_ORDER` 中，学生 API 会返回 `legacy_run`；后台仍可读取历史。
- `ANON_CODE_PEPPER` 仍不可在参与者分配后修改。
- `T1_DURATION_SECONDS` / `T2_DURATION_SECONDS` 可调整；前端文案目前写 24/20，需要同步。
- 正式研究前仍需替换 DEMO 题库/作品说明，审查 HLSF 文案，完成伦理与数据治理。


## 12. 正式内容与中性学生界面（2026-11-07）

- 接入两件正式文物：M 鹭鸶方补、T 联珠对格里芬纹锦；章节化资料 + 高清图 + 受保护媒体端点。
- 接入 M/T × A/B 共 16 个 K form、K0 baseline 与 5 题 survey；组内 AB/BA 题本平衡。
- K0 先 baseline、再知识组；学生页面不显示 K/T 编码、题型、required、版本号、分值或答案键。
- 删除文物资料中的 M09/T09 与所有现代产品/设计方向提示，避免对 T1 设计产生额外引导。
- 文物资料页支持章节展开、图片 lightbox、来源 chip，并记录 section/media/source 点击与停留时长。
- 新增隐藏答案键与选择题研究者评分；短答与 T2 量规继续平台外评分。
- 新增 `docs/FORMAL_CONTENT_V15.md`。


## 13. 作品提交时的后续研究同意（2026-11-07）

- T2 最终作品提交处底部增加小字提示：“提交即表示同意将今天的学习数据用于后续研究”。
- 不设置勾选框；提交即记录为同意，不阻塞任务。
- `runs` 增加 `consent_future_research`、`consent_recorded_at`、`consent_version=work-submit-v1`。
- `runs.csv` 导出这三个字段。
- 迁移：`0008_work_submit_consent.py`。
- 仍需伦理批准的正式措辞；该底部提示不替代完整知情同意书、撤回/删除流程。


## 14. B-01“其他”专业背景输入（2026-11-07）

- K0 baseline 的“专业背景”选“其他”后出现输入框，可填写具体专业背景。
- 后端选项支持 `allow_text`，答案保存为 `{value, text}`；未填写时提交会提示。
- 前端测试与正式内容导入测试覆盖。


## 15. 学生图片描述、多图生成与选图提交（2026-11-07）

- 右侧创作面板顶部新增较大的“用文字描述你希望的产品图”输入框，学生可描述外观、材质、颜色、构图、场景和氛围。
- 图片 prompt 以学生描述为主要视觉方向；产品字段、六字段/开放说明作为补充；正式文物章节摘要也作为证据补充。
- 图片生成不再默认限制 3 次；`IMAGE_JOB_LIMIT_PER_ROUND=0` 表示不限次数，仍保持同一轮同时只跑一个图片任务。
- 学生可连续生成多张；第一张成功后自动选中，可点击“选择这张”切换。
- `rounds.selected_image_job_id` 保存最终选图；互评和作品广场只使用这张图。
- `work_revisions.image_prompt` 保存学生图片描述并随版本导出。
- 迁移：`0009_image_prompt_selection.py`。
- 后端 46 passed；前端 11 tests passed。


## 16. 后测问卷 Likert 端点标签与偏好题（2026-11-07）

- 修复 Likert 标签错位：现在只在 1 和最大值显示“非常不同意/非常同意”或“极低/极高”，不再把“非常同意”错误显示在 2 下面。
- survey 新增 S6–S9：
  - S6 更喜欢直接向 AI 提问、自己决定方向；
  - S7 更喜欢 AI 分阶段提示；
  - S8 分阶段提示会限制创作自由（反向题）；
  - S9 未来愿意继续使用分阶段引导。
- survey 说明增加“无论今天是否看到分阶段提示，请按偏好回答”；A/B 都可回答，但属于偏好/探索性测量，不是干预后直接比较。
- 前端 11 tests passed。


## 17. HLSF v1.6 Prompt Pilot（2026-11-07）

- 提示版本升级为 `hlsf-v1.6.0-pilot`。
- T1 B 四阶段提示、Hint、教练上下文改为 v1.6 知识驱动循环：一个具体问题 → 学生尝试 → 证据反馈 → 学生选择。
- 明确禁止主动推荐具体产品类型；只在学生明确请求时提供可选方案。
- B-only 上下文新增文物章节索引与 curated learning anchors，不含 K0–K3 题面/答案。
- 不改变 T1 A、T2、HLSF 状态机、手动 Next/Skip、每阶段一次 Hint。
- `ai_calls.prompt_version` 宽度扩到 64（迁移 0010）。
- 文档：`docs/HLSF_V16_PROMPT_NOTES.md`；当前框架文档已更新。
- 这是 Pilot 版本，不是正式协议冻结。


## 18. Image Prompt Optimizer（2026-11-07）

- 图片生成前新增文本模型压缩：长 source prompt → 简体中文、≤300 字的 optimized prompt。
- 图片模型尝试携带文物参考图；当前 Seedream 端点拒绝 `image` 字段，自动回退纯文生图并记录 `reference_image_used=false`。
- `image_jobs` 新增 `source_prompt`、`prompt_optimizer_version`、`reference_image_used`（迁移 0011）。
- 文本编辑调用记录为 `purpose=image_prompt_optimization`，不保存图片 base64。
- 真实生成已验证：优化后约 127 个汉字，输出 2496×1664。
- 文档：`docs/IMAGE_PROMPT_OPTIMIZER.md`。


## 19. Four-Group Balanced Crossover Pilot（2026-11-07）

- 正式采用 `crossover-v1.0-pilot`：G1/G2 = T1 A → T2 B；G3/G4 = T1 B → T2 A。
- 每名学生两轮不同文物、恰好一次 A、一次 B；班级内按 8/7/7/8 或 7/8/8/7 配额随机分配。
- `Run` 增加 `design_version`、`condition_sequence`、`artifact_sequence`（迁移 0012）；旧 run 保持 `design_version` 空，T2 仍按 v1.5 Standard AI 解释。
- HLSF 改为任意 condition=B 轮次启用；T2 B 使用开放作品说明的 Reflect 变体；T1/T2 状态按 round_id 隔离。
- 新增 `analysis.csv` 和 `/api/admin/analysis.csv` 过滤导出；保留旧协议历史。
- 测试覆盖四组映射、T2 HLSF、开放说明、导出与 G1/G2/G3/G4 流程。


## 20. Student-Area Image Isolation, Loading State and Portfolio PDF（2026-11-08）

- 图片 prompt 默认只使用学生 `image_prompt` / product metadata；不再自动注入文物标题、章节阅读或文物参考图。
- 显式术语 + 文本模型高精度语义门控决定是否加入紧凑文物文字参考；`IMAGE_REFERENCE_ENABLED=false`；模型失败/不确定时 fail closed。
- 生成按钮点击后立即显示“正在生成”空白占位，而不是等待完成。
- 新 `/api/student/portfolio` 返回本人 T1/T2 作品；最终页使用 html2canvas + jsPDF 下载 PDF，再完成工作坊。
- PDF 文件名为 `hlsf-portfolio-<short-id>.pdf`，实测 2 页。
- 后端 60 passed；前端 6 files / 13 tests passed。


## 21. HLSF v1.9 Open-Design Exploration Prompt Pilot（2026-11-08）

- 新 run 使用 `hlsf-v1.9-open-design-exploration-pilot`；旧 v1.7/v1.8 run 通过 `runs.hlsf_prompt_version` 保持原版本。
- Observe：文化层次识别；Explain：具体知识到关系抽象；Create：多入口、开放式、视角转换；Reflect：证据驱动的设计判断与修订。
- 保留四阶段、手动 Next/Skip、每阶段一次 Hint、三段说明、测验和 A/B 条件。
- Standard AI 不接收任何新增 HLSF 规则。
- 新 run 的 A 条件加入共享学生自主性 guardrail（`standard-guardrail-v1`）：学生未提出方向前不列具体产品/类别/用途菜单；明确要求例子时仍可给可选建议；不加入 HLSF 阶段。
- 新增 `runs.hlsf_prompt_version`（迁移 0016）并加入 runs 导出。
- 自动化：后端 75 passed；前端 6 files / 13 tests passed。
