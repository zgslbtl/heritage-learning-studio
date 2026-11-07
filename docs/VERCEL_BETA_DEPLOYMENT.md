# Vercel 班级0内测

本部署独立于 Docker 正式环境。应用为 `DEPLOYMENT_MODE=beta`，同时使用
`ENVIRONMENT=production`、HTTPS 和 Secure Cookie。只有班级0可以进入。

## 用户规则

- 保留输入 `strip().lower()` 后包含 `polyu` 的登录判断，无口令、验证码或邮箱所有权验证。
- 班级链接固定班级，不作为身份验证。相同输入恢复相同参与者进度。
- K0–K3、问卷、A/B 条件内容保持原版本，T1 为24分钟、T2为20分钟。
- 班级0持续接受新用户。首次进入互评时冻结个人快照，最多6份其他人的有效T2作品；
  不足6份按实际数量，没有作品可以继续。后加入的作品不会改变已分配任务。
- 班级1–4在内测环境由后端拒绝。正式 `study` 模式继续使用原有全班互评规则。

## 云端组件

- 专用 Vercel 项目：`heritage-learning-beta`，所属空间 `lisanlu666-6622`。
- Vercel Services：Vite前端与FastAPI后端同域，`/api/*` 路由至后端。
- Marketplace Neon：独立的 `heritage-learning-beta-db`，Free计划，Singapore区域。
- 私有 Blob：`heritage-learning-beta-media`，Singapore区域；图片与ZIP不公开。
- Vercel Queues：`heritage-beta-tasks`，显式声明私有 `tasks` 服务触发器，并发2。
- Python运行时3.12，单次函数最多300秒，业务任务预算270秒。

生产资源不连接本地历史数据库，也不导入历史参与者、会话、作品或测试日志。
原有 `.env` 仅用于读取已有模型服务配置，密钥只进入专用项目服务端环境变量。
管理员凭据保存在本机 `.local-runtime/vercel-beta-admin.txt`，不进入部署文件。

## 运行与持久化

云端关闭启动自动初始化和常驻图片worker。部署初始化单独执行迁移、创建班级0、
导入并激活现有V2内容包；函数冷启动只检查连接，不覆盖内容、不重置正在执行的任务。

当前迁移头为`0015_beta_peer_snapshots`：班级0允许每人一个冻结互评快照，
正式班级继续保留唯一活跃互评批次约束。之后的代码部署不自动执行迁移。

图片任务和投递状态先写入 `runtime_tasks`，再发送队列；轮询可补投失败消息。
数据库执行租约、任务状态和检查点防止重复消息重新生成。保存优化提示词及供应商结果，
中断后的结果不明时标记失败并允许手动重试，不自动再次收费调用。
供应商返回后先把原始结果持久化，随后校验、保存PNG并写入成功状态。

授权文件接口检查本人、互评任务、同班有效作品和管理员权限后，才生成60秒读取链接。
后台图片通过限类型、限大小、限单个对象的签名URL直传，再由后端读取并验证图像。
完整导出通过后台任务生成私有ZIP，清单标记 `deployment_mode=beta` 和互评策略。

数据库连接使用NullPool；Neon连接强制TLS并关闭语句缓存。聊天串行控制和登录限流
由PostgreSQL协调，不依赖函数实例内存。

Services 的自动订阅发现在本次公网构建中未注册消费者，因此采用显式
`queue/v2beta` 触发器。私有服务没有公开重写路由，由官方Python SDK处理投递、
租约和确认。队列投递记录跨部署恢复，数据库同时限制全局图片并发。

## 接口增补

- `GET /api/auth/config`：返回可用班级、部署模式及现有登录规则。
- `GET /api/admin/runtime`：后台上传、导出能力配置。
- `POST /api/admin/uploads`：管理员申请一次受限上传。
- 原文物版本接口增加可选 `upload_id`；本地仍可使用原有multipart图片。
- `POST /api/admin/export-tasks`：发起或复用进行中的导出。
- `GET /api/admin/export-tasks/{id}`：查询状态。
- `GET /api/admin/export-tasks/{id}/download`：授权下载。

## 部署与回滚

在项目根目录使用 `vercel deploy --prod`。资源和密钥由Vercel项目配置管理；
不要上传本地环境文件。`.vercelignore` 排除密钥、参考文献、历史运行、备份及测试数据。

首次初始化前确认目标是新建的内测Neon数据库、无参与者记录，并保留内容导入dry-run结果。
后续部署不重复激活协议，不改变pepper。代码回滚选择此前的Vercel部署，
保留数据库和Blob；不得通过删除资源或回退破坏性数据库迁移来回滚代码。

公网验收和最终地址记录见 `VERCEL_BETA_ACCEPTANCE.md`。本地测试通过不代表公网验收通过，
工程验收也不构成正式研究工具或学习效果验证。
