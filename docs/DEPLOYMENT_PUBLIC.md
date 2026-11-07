# 部署与运维指南

适用于本仓库2026-11-07版本。目标是从公开源码建立自己的环境，不复制原部署的凭据、参与者数据或历史运行。交互见[操作手册](USER_GUIDE_ZH.md)。

## 选择运行方式

| 方式 | 数据库 | 文件 | 图片任务 | 用途 |
| --- | --- | --- | --- | --- |
| 本地模拟启动器 | 临时/本机pgserver | `.local-runtime/data` | 本地worker + 模型测试桩 | 检查界面与工程流程 |
| 本地真实服务 | 自己的PostgreSQL | 自己的持久化目录 | 本地worker + 配置的模型 | 开发与真实供应商测试 |
| Docker/Caddy | Compose PostgreSQL卷 | `app_data`卷 | 单API进程本地worker | 自建服务器部署 |
| Vercel beta | 独立Neon PostgreSQL | 私有Blob | 私有tasks服务订阅Queues | 班级0陆续内测 |

内测与正式研究分别使用独立数据库、文件存储和环境变量。不要只靠前端显示的班级标签隔离正式数据。

## 本地真实服务

要求Python 3.12、Node.js 20+和PostgreSQL。以下命令在全新克隆目录中操作。

### 安装

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
cp .env.example backend/.env
```

本地后端从`backend/.env`读取配置；Docker Compose从根目录`.env`读取。这两种文件位置不要混淆。已有配置时直接编辑，不覆盖原文件。

编辑`backend/.env`，至少配置：

```dotenv
ENVIRONMENT=development
DEPLOYMENT_MODE=beta
STORAGE_BACKEND=local
QUEUE_BACKEND=local
PUBLIC_ORIGIN=http://127.0.0.1:5173
COOKIE_SECURE=false
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@127.0.0.1:5432/heritage_beta
DATA_DIR=../data
AUTO_BOOTSTRAP=true
DB_NULL_POOL=false
```

另外填写独立的`ADMIN_PASSWORD`、`ANON_CODE_PEPPER`、文本和图片模型配置。可用`openssl rand -hex 32`分别生成秘密值，不使用文档中的占位符。数据库需要事先创建；真实密码中的URL特殊字符需编码。

### 迁移、内容与启动

在后端目录执行：

```bash
cd backend
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m app.cli import-formal-v2 --dry-run
.venv/bin/python -m app.cli import-formal-v2 --activate
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

另开终端，在项目根目录：

```bash
npm --prefix frontend run dev
```

访问`http://127.0.0.1:5173`与`/admin`。Vite将`/api`转发到8000，浏览器从前端域名访问，不需要单独设置跨域Cookie。

`import-formal-v2`导入两件文物、V2题本、评分元数据和协议；`--activate`用于新环境激活。生产内容初始化命令不会导入任何参与者。已有run或协议时，先检查状态及备份，不反复强制导入/激活。

开发环境也可通过`.venv/bin/python -m app.cli seed-demo`导入中性占位内容，但需要相应模型配置或模拟服务；`seed-demo`拒绝生产环境。`app.cli readiness`同样是开发环境CLI，生产环境通过后台`/api/admin/readiness`检查。

## Docker与Caddy

准备DNS域名、Docker/Compose和可用的80/443端口。项目根目录：

```bash
cp .env.example .env
# 编辑域名、数据库、随机密钥及模型服务配置。
docker compose up -d --build
docker compose ps
```

根目录配置至少包括：

```dotenv
ENVIRONMENT=production
DEPLOYMENT_MODE=study
STORAGE_BACKEND=local
QUEUE_BACKEND=local
SITE_ADDRESS=study.example.org
PUBLIC_ORIGIN=https://study.example.org
COOKIE_SECURE=true
DATA_DIR=/data
```

`ADMIN_PASSWORD`和`ANON_CODE_PEPPER`至少16字符。数据库密码建议用随机十六进制值，避免Compose拼接连接URL时的转义问题。需要单独的班级0 Docker环境时，把`DEPLOYMENT_MODE`设为`beta`，并使用独立Compose项目/卷和域名。

API容器启动命令会运行迁移；文物与题本导入是额外步骤：

```bash
docker compose exec api python -m app.cli import-formal-v2 --dry-run
docker compose exec api python -m app.cli import-formal-v2 --activate
```

仅Caddy公开80/443。不要额外映射PostgreSQL端口，也不要通过静态目录公开整个`/data`。Caddy同时服务SPA与API，深链接`/join`和`/admin`回退到前端入口。

该公开发布未新增Docker运行验收；静态配置检查通过不等于已验证镜像构建、TLS证书签发或目标服务器网络。

## Vercel班级0内测

### 项目组成

根目录`vercel.json`是Services配置的入口：

| Service | Root / entrypoint | 路由或触发 |
| --- | --- | --- |
| `web` | `frontend` / Vite | 除API外的页面；SPA回退`index.html` |
| `api` | `backend` / `app.main:app` | `/api/*` |
| `tasks` | `backend` / `app.queue_consumer:app` | 私有`queue/v2beta`触发器，无公共重写 |

队列主题`heritage-beta-tasks`，声明并发2；数据库执行租约另外限制跨实例图片并发。Python运行时3.12，函数配置300秒，业务任务预算270秒，部署区域sin1。

Services及队列功能的账号可用性、套餐和控制台行为需要在自己的账户确认；不要因为源码有配置就默认所有账户均已开通。

### 新环境资源

1. 创建专用Vercel项目，项目根目录指向仓库根目录。
2. 从Marketplace建立**全新**Neon PostgreSQL数据库并连接项目；由账户持有人完成需要的首次使用条款。
3. 建立私有Blob存储并连接专用项目，不选公开访问桶。
4. 确认私有队列触发器实际注册；部署Ready后仍要用一次任务验证消费者。
5. 设置生产环境变量，使用独立后台密码和pepper。

### 服务端环境变量

```dotenv
ENVIRONMENT=production
DEPLOYMENT_MODE=beta
AUTH_MODE=email
STORAGE_BACKEND=blob
QUEUE_BACKEND=vercel
AUTO_BOOTSTRAP=false
IMAGE_WORKER_ENABLED=false
COOKIE_SECURE=true
PUBLIC_ORIGIN=https://YOUR-PROJECT.vercel.app
DATA_DIR=/tmp/heritage-learning
DB_NULL_POOL=true
DB_POOL_SIZE=2
DB_MAX_OVERFLOW=0
IMAGE_MAX_CONCURRENCY=2
T1_DURATION_SECONDS=1440
T2_DURATION_SECONDS=1200
```

再配置真实的`DATABASE_URL`、`BLOB_READ_WRITE_TOKEN`、`BLOB_STORE_ID`、`ADMIN_PASSWORD`、`ANON_CODE_PEPPER`与模型环境变量。不要给模型密钥添加`VITE_`前缀。区域由平台`VERCEL_REGION`提供，与队列区域保持一致。

数据库层接受Neon PostgreSQL URL并归一化为asyncpg、启用TLS、关闭相关语句缓存。`DATA_DIR`只做缓存，原图和导出必须落到私有Blob，不能依赖函数本地磁盘持久化。

### 初始化与部署

先在受控终端中安全注入**目标内测项目**的服务端环境变量；不要把密钥写入仓库。确认数据库为空，再执行：

```bash
cd backend
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m app.cli import-formal-v2 --dry-run
.venv/bin/python -m app.cli import-formal-v2 --activate
```

目标云端参数应通过进程环境覆盖本地`.env`，且初始化终端的`DATA_DIR`使用可写本地临时目录。Blob正式写入由非dry-run导入完成。当前迁移头为`0015_beta_peer_snapshots`。

回到根目录部署：

```bash
vercel login
vercel link
vercel deploy --prod
```

这些操作创建或更新云端项目，不是本地预览命令。后续函数冷启动不再重复迁移/导入，也不把其他实例的运行中任务标记失败。代码升级含新迁移时，应独立执行兼容迁移并保留数据。

### 文件上传、读取与导出

1. 后台申请一次限定对象、类型和大小的上传签名。
2. 浏览器直接PUT到私有Blob，再把`upload_id`提交给文物版本接口。
3. 后端校验原文件大小、格式及内容，建立新版本。
4. 学生或研究者读取文件时先校验会话和对象权限，再307跳转至60秒读取链接。
5. 导出经队列构建ZIP并放入Blob，后台轮询后授权下载。

大图片和ZIP使用直传/短时链接，避免整个文件通过API函数中转。不要复制签名链接进README、issue或公开日志。仓库中的原始文物内容图片是源码资料，与运行时授权生成图片的权限机制不同。

### 上线验收

依次验证：

1. 无Cookie可打开首页、`/join`和`/admin`，但不能读取受保护图片/后台数据。
2. `/api/auth/config`仅返回班级0，直接请求班级1也被拒绝。
3. 后台准备检查通过；创建班级0链接，输入大小写/空格归一化正确。
4. 真实文本和图片调用成功，图片经过队列并持久化，不只是配置保存成功。
5. 刷新及退出重登恢复；时长不重置。
6. 首位用户0份互评可继续，后加入者能得到当时作品；旧任务不随新作品变化。
7. 大文件直传、授权图片和异步ZIP导出可用，清单无意外缺失文件。
8. 再部署一次，比较参与者/run、协议、文件长度及哈希，验证持久性。
9. 使用实际参与者的设备与网络复核，不以工具代理的成功替代浏览器直连验收。

`scripts/vercel_beta_smoke.py`会写入明确标记的合成验收数据并调用真实模型；只有明确要运行真实验收时才执行。`scripts/vercel_beta_persistence.py before/after`使用本机私有Playwright后台storage state，比较现有数据和文件，不负责创建云端资源。相关本机状态、测试报告和导出不随源码发布。

## 备份、回滚与故障处理

Docker部署可用：

```bash
./scripts/backup.sh
# 在独立演练环境确认后，再使用恢复命令。
CONFIRM_RESTORE=YES ./scripts/restore.sh /path/to/backup
```

恢复会覆盖目标数据；备份数据库、文件与环境密钥应分别保管。上述脚本针对Compose卷，不是Neon/Blob的云端备份工具；云端需要单独保留数据库恢复能力和对象备份方案。

代码回滚应把域名指向此前可运行部署，保留Neon和Blob，不删除数据、不更换pepper。迁移0015修改班级0快照唯一索引；已有多个个人快照时downgrade会拒绝，不能靠删快照解决回滚。

| 故障 | 首要检查 |
| --- | --- |
| 首页连接超时 | 浏览器网络、DNS、代理、域名到部署的连接 |
| 页面正常但入口配置失败 | `/api/auth/config`和同域API重写 |
| 后台登录失败 | 生产环境变量、密码、Cookie、Origin、限流时间 |
| 图片长期排队 | 触发器注册、区域、投递状态、执行租约与消费者日志 |
| 已成功图片打不开 | 会话权限、Blob配置、对象是否存在、签名是否过期 |
| 导出失败 | 后台任务错误、文件清单、Blob权限及函数执行预算 |
| 本地草稿丢失 | 是否已成功同步、是否换了标识/班级、是否运行了重建演示库的启动器 |

分享日志时只保留错误类型、任务ID和request ID，不公开密钥、Cookie或带签名URL。
