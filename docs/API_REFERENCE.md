# 接口与数据说明

以下是阅读代码和排查交互问题的索引，不替代Pydantic请求schema。对应`backend/app/routers/`及`backend/app/schemas.py`，更新基准为2026-11-07。

## 路由与会话

前端和API使用同一origin。学生Cookie为`hls_student`，后台Cookie为`hls_admin`；会话是服务端保存哈希的随机opaque token，Cookie启用HttpOnly、SameSite和生产Secure要求。

浏览器有Origin的写请求需要匹配`PUBLIC_ORIGIN`或额外允许列表。用户ID、run和班级来自当前会话，不由学生随意提交参与者ID。外部集成不要把后台密码或模型密钥放在浏览器代码中。

### 公开与登录接口

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/health/live` | 进程存活 |
| GET | `/api/health/ready` | 数据库、存储、模式与模型配置状态 |
| GET | `/api/auth/config` | 部署模式、允许班级和`contains_polyu`规则 |
| GET | `/api/auth/class-link?token=...` | 验证班级链接并返回锁定班级 |
| POST | `/api/auth/enter` | 输入`email`、`class_id`、可选`class_token`；创建/恢复学生会话 |
| POST | `/api/auth/logout` | 撤销学生会话 |
| POST | `/api/admin/login` | 后台密码登录 |
| POST | `/api/admin/logout` | 撤销后台会话 |

示例只用于自己的开发环境，不是校内邮箱验证：

```http
POST /api/auth/enter
Content-Type: application/json
Origin: http://127.0.0.1:5173

{"email":"polyu-demo-01","class_id":0}
```

返回包括`state`，其中`stage`决定前端显示哪一页。生产环境关闭Swagger；开发环境可查看`/api/docs`与`/api/openapi.json`。

## 学生流程

以下接口均需要学生会话，且受阶段/轮次检查。

| 方法 | `/api/student`之后的路径 | 用途 |
| --- | --- | --- |
| GET | `/state` | 当前参与者、run、阶段与恢复信息 |
| POST | `/tutorial/complete` | 完成教程 |
| GET | `/rounds/{round_no}` | 本轮资料、作品、对话/引导及图片任务 |
| POST | `/rounds/{round_no}/start` | 启动服务端倒计时 |
| POST | `/rounds/{round_no}/finish` | 保存并结束，校验最低作品要求 |
| PUT | `/rounds/{round_no}/work` | 保存产品文字及三段说明，产生版本 |
| PUT | `/rounds/{round_no}/script` | 兼容旧脚本记录 |
| GET / POST | `/rounds/{round_no}/messages` | 查询/提交对话；提交带`client_message_id` |
| POST | `/rounds/{round_no}/messages/{message_id}/retry` | 显式重试未答复消息 |
| POST | `/rounds/{round_no}/hlsf/advance` | B条件推进或跳过，提交`from_phase`、`skip` |
| POST | `/rounds/{round_no}/hlsf/hint` | 领取当前阶段提示 |
| POST | `/rounds/{round_no}/evidence-events` | 资料阅读事件 |
| POST | `/rounds/{round_no}/image-jobs` | 创建持久化图片任务，可带`retry_of` |
| GET | `/image-jobs/{job_id}` | 查询任务；云端可补投未成功投递任务 |
| POST | `/rounds/{round_no}/image-jobs/{job_id}/select` | 选择成功图片 |
| GET | `/instruments/{kind}` | 当前测评题本和已保存答案 |
| PUT | `/instruments/{kind}/draft` | 保存测评草稿 |
| POST | `/instruments/{kind}/submit` | 校验提交测评并推进 |

`round_no`为1或2；`kind`为当前协议允许的`k0/k1/k2/k3/survey`。不能把某轮API换个编号就跨阶段读写。截止时间由服务端处理，客户端只负责显示。

## 互评与社交

| 方法 | `/api/student`之后的路径 | 用途 |
| --- | --- | --- |
| GET | `/peer-assessment` | 正式闸门状态或个人快照、任务和已提交数 |
| POST | `/peer-assessment/{assignment_id}/impression` | 记录作品可见事件 |
| POST | `/peer-assessment/{assignment_id}` | 提交三维评分与可选评论 |
| POST | `/peer-assessment/complete` | 全部已分配任务完成后继续；空池可继续 |
| GET | `/social-feed` | 本班有效T2作品流 |
| POST | `/social/works/{work_id}/view` | 浏览事件 |
| POST | `/social/works/{work_id}/like` | 点赞/取消点赞 |
| POST | `/social/works/{work_id}/comment` | 社交评论 |
| POST | `/social/complete` | 完成作品流阶段 |

互评提交体中的`scores`使用`clarity`、`evidence_link`、`attraction`三个1–5分字段。任务归属和同班作品权限由服务端校验，不能评价本人作品或越班操作。

## 研究者接口

以下以`/api/admin`为前缀，均要求后台会话。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/overview` | 准备状态、当前协议、参与者和汇总 |
| GET | `/participants/{participant_id}` | 完整过程详情和内部登录邮箱 |
| GET | `/readiness` | 是否可激活/允许学生进入及逐项原因 |
| GET | `/artifacts`、`/instruments` | 查询材料版本 |
| POST | `/artifacts/{slot}/versions` | 新建文物版本；multipart或云端`upload_id` |
| POST | `/instruments/{kind}/versions` | 新建题本版本 |
| POST | `/protocol/activate` | 检查后冻结并激活协议 |
| GET | `/class-peer-gates` | 当前可用班级的闸门/内测状态 |
| GET / POST | `/class-links` | 查询/创建班级链接 |
| POST | `/class-links/{link_id}/revoke`、`/rotate` | 撤销或轮换链接 |
| POST | `/social/comments/{comment_id}/hide` | 隐藏社交评论 |
| GET | `/analysis.csv` | 分析长表 |
| GET | `/export` | 本地模式完整ZIP导出 |
| GET | `/runtime` | 直传/异步导出能力与部署模式 |
| POST | `/uploads` | 申请限定单对象的Blob上传 |
| POST | `/export-tasks` | 发起或复用进行中的云端导出 |
| GET | `/export-tasks/{task_id}` | 查询导出状态 |
| GET | `/export-tasks/{task_id}/download` | 授权下载成功ZIP |
| GET | `/provider-connectivity` | 不发送模型密钥的连通性诊断；不是生成验收 |

旧`/cohort/codes.csv`仅为遗留code模式保留；当前email模式禁用该下载。

## 文件与任务语义

`routers/files.py`校验本人/后台、分配互评或同班有效作品访问，再返回本地文件或Blob的307短时签名跳转。客户端应跟随跳转；Range读取沿文件服务完成，不把原图或ZIP整体装入API响应。

云端任务表`runtime_tasks`包含种类、执行状态、投递状态、租约、检查点、错误和文件key：

```text
创建记录并提交 → 尝试投递 → 队列消费者领取执行租约
  → 图片：优化提示词 → 记录供应商调用开始 → 持久化结果 → 校验PNG → 成功
  → 导出：构建ZIP → 私有文件上传 → 成功
```

重复消息读取状态/锁去重；活跃租约避免多实例同时执行。图片已完成则不重新调用供应商；已开始但结果不明的调用不会静默自动再试。任务查询会尝试恢复符合条件的投递，不意味着所有失败任务都会自动重新生成。

私有`tasks`服务使用官方Python SDK处理队列消息认证、租约与确认。它不是供浏览器直接发起图片任务的公开URL。

## 数据表索引

| 数据 | 主要表 |
| --- | --- |
| 班级、登录和会话 | `classes`, `participants`, `sessions`, `rate_limit_buckets` |
| 文物/测评/协议版本 | `artifact_versions`, `instrument_versions`, `protocol_versions`, `protocol_assessment_forms`, `assessment_item_keys` |
| 流程与轮次 | `runs`, `stage_events`, `rounds` |
| 创作、对话与引导 | `work_revisions`, `script_revisions`, `messages`, `hlsf_states`, `hlsf_events`, `evidence_events` |
| 模型、图片和云任务 | `ai_calls`, `api_errors`, `image_jobs`, `runtime_tasks` |
| 测评 | `assessment_responses` |
| 班级链接与闸门 | `class_entry_links`, `class_peer_gates`, `class_peer_gate_events` |
| 互评和社交 | `peer_batches`, `peer_assignments`, `peer_impressions`, `peer_ratings`, `social_views`, `social_likes`, `social_comments`, `social_events` |

具体列、外键与索引以`models.py`及Alembic迁移为准。0015保留正式班级唯一活跃互评批次约束，同时允许班级0按reviewer run保存独立快照。时间字段按UTC存储，分析时再转换时区。

## 导出解读

导出把参与者UUID、class/group、run、round、文物与协议版本连接起来，包含作品全部修订、当前文本、消息、引导、资料事件、测评原答案/长表、图片及任务、互评、社交和错误。`protocol.json`保存冻结语义，数据字典解释各CSV，`manifest.json`记录部署模式、内测标识及缺失文件。

不应把CSV记录数直接当作独立样本数，也不应把图片重试任务当作不同参与者。研究导出不含登录邮箱/访问码/会话密钥，但自由文本可能出现个人信息，应在分享前人工核查。源码仓库不发布运行数据库或ZIP。
