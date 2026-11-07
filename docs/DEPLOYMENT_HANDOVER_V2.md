# Heritage Learning Studio V2.0 部署交接文档

> **给接手 Agent 的第一句话：** 这是一份可执行 runbook，不是概念说明。按顺序做；每一步都保留命令输出（不要记录密钥）。遇到“停止条件”时停下来报告，不要强行迁移、覆盖数据库或点击旧的管理员激活按钮。
>
> **部署对象：** 当前工作区的 V2.0 代码（`crossover-v1.1-assessment-v2-pilot` / `assessment_v2.0_pilot`），Docker Compose + Caddy + PostgreSQL。
>
> **重要：** 这套平台的“PolyU 邮箱登录”不是 SSO，也不验证邮箱所有权；任何包含 `polyu` 的字符串都可能进入。**公网部署前必须加真正的访问控制**（VPN / Cloudflare Access / Tailscale / 反向代理认证 / 机构 SSO）。详见第 12 节。

---

## 0. 先确认你拿到了什么

部署前向项目所有者确认以下信息；缺失时不要猜：

| 项目 | 需要确认 |
|---|---|
| 服务器 | SSH 地址、用户、sudo 权限、操作系统版本 |
| 域名 | 例如 `study.example.org`；能否修改 DNS A/AAAA |
| 端口 | 80/443 是否可对外开放；是否有云防火墙 |
| 代码 | 私有 Git 仓库地址或冻结的源码 tarball（含 `frontend/package-lock.json`） |
| AI 文本 | `TEXT_MODEL_BASE_URL`、模型名、API key、配额 |
| AI 图片 | `IMAGE_MODEL_BASE_URL`、模型名、API key、配额 |
| 管理密码 | 由谁生成 `ADMIN_PASSWORD`；不要复用示例 |
| 分配 pepper | `ANON_CODE_PEPPER` 由谁生成；参与者开始后绝不能改 |
| 研究状态 | 只是内部演示，还是要收集真实人类数据 |

**停止条件：**

- 没有域名/HTTPS，但准备用 `ENVIRONMENT=production`；
- 没有文本或图片 provider key；
- 已有生产数据库但没有最近备份；
- 服务器上已有 80/443 服务且不能停；
- 准备把 `.local-runtime` 本地测试库或 `formal_v1` 旧协议直接当生产库；
- 准备公开收集真实数据，但还没有真正的身份认证、伦理/同意、图片授权。

### 最短路径（详细步骤见后文）

1. DNS：`A study.example.org -> 服务器 IP`。
2. 安装 Docker/Compose；只开 22/80/443。
3. 拉代码到 `/opt/heritage-learning-studio`，`cp .env.example .env`。
4. 填域名、HTTPS origin、Postgres/Admin/Pepper、文本/图片 key。
5. `docker compose build --pull && docker compose up -d`。
6. `docker compose ps` + `/api/health/ready` + `alembic current`。
7. `import-formal-v2 --dry-run`，再 `import-formal-v2 --activate`。
8. `/admin` 登录，准备检查看到 `assessment_v2.0_pilot`。
9. 生成班级 1–4 链接，做一条学生 smoke（K0 9 → K1 7 → K2 6 → K3 7 → Survey 7）。
10. `./scripts/backup.sh`，加密离机；记录部署日志。

> **未验证项：** 本次交接没有在真实公网服务器上实际执行 Docker 构建、Caddy 证书签发和公网 HTTPS。第一次请用 staging 或在维护窗口做，并保留回滚。

---

## 1. 部署的是什么

```text
Internet
  │ 80/443
Caddy（TLS + 静态 SPA + /api/* 反代）
  ├── /srv/www：frontend/dist
  └── api:8000（FastAPI，单 worker）
        └── db:5432（PostgreSQL 16，内部网络）
```

| 服务 | 构建 | 端口 | 持久化 |
|---|---|---|---|
| `db` | `postgres:16-alpine` | 不发布 | `db_data` |
| `api` | `backend/Dockerfile` | 内部 8000 | `app_data:/data` |
| `caddy` | `Dockerfile.caddy`（先构建前端） | 80/443/udp | `caddy_data`、`caddy_config` |

关键版本：

- 设计版本：`crossover-v1.1-assessment-v2-pilot`
- 测评版本：`assessment_v2.0_pilot`
- 题本：K0=3 基线+6 单选；K1/K3=6 单选+1 后测短答；K2=6 单选；Survey=7；每生 36 项
- 作品说明：T1/T2、A/B 条件统一三段（`heritage_knowledge`、`cultural_translation`、`design_reason`）
- 数据库迁移 head：`0013_assessment_v2`
- 旧 `formal_v1` / `crossover-v1.0-pilot` / 六字段 / 开放说明只用于历史数据读取，不覆盖

---

## 2. 服务器最低配置

- Ubuntu 22.04/24.04 LTS（或同等 Linux）
- 2 vCPU、4 GB RAM、40 GB SSD 起步；图片多时建议 4 vCPU/8 GB
- 2 GB swap（可选但推荐）
- Docker Engine 24+，Docker Compose v2（`docker compose` 插件）
- 出站 443 可访问文本/图片 provider
- 只开放 22（限制来源）、80、443；不要发布 5432/8000
- 时区/时间同步正常（TLS 与日志需要）

### 2.1 安装 Docker（Ubuntu 示例）

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg git ufw
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
# 重新登录 SSH 使 docker 组生效
docker compose version
```

### 2.2 防火墙

优先使用云厂商安全组：只放行 SSH 来源 IP、80、443。  
如果使用 UFW，注意 Docker 会自行写 iptables；不要让 UFW 给你“已保护 5432”的错觉：

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## 3. DNS 与 TLS

1. 在 DNS 添加 `A study.example.org -> <服务器 IPv4>`；有 IPv6 再加 AAAA。
2. 等待解析：
   ```bash
   dig +short study.example.org
   ```
3. 如果使用 Cloudflare：
   - 首次签发证书建议先“灰云”（DNS only），确认 Caddy 能完成 HTTP-01；
   - 或改用 DNS challenge；
   - 不要让代理层把 80 端口完全挡住。
4. Caddy 会自动申请/续期证书；`SITE_ADDRESS` 只写主机名，**不要写 `https://`**。
5. 确认 80/443 没有被 Nginx/Apache/其他进程占用。

---

## 4. 获取代码并配置 `.env`

```bash
sudo mkdir -p /opt/heritage-learning-studio
sudo chown "$USER":"$USER" /opt/heritage-learning-studio
git clone <PRIVATE_REPO_URL> /opt/heritage-learning-studio
cd /opt/heritage-learning-studio
# 或：把冻结的源码 tarball 解压到这里
```

### 4.1 生成 `.env`

```bash
cp .env.example .env
chmod 600 .env
python3 - <<'PY'
import secrets
for key in ("POSTGRES_PASSWORD", "ADMIN_PASSWORD", "ANON_CODE_PEPPER"):
    print(f"{key}={secrets.token_hex(24)}")
PY
```

把输出填入 `.env`。`POSTGRES_PASSWORD` 用十六进制/字母数字，避免 `DATABASE_URL` 的 URL 编码问题。

必须修改的项：

```dotenv
ENVIRONMENT=production
SITE_ADDRESS=study.example.org
PUBLIC_ORIGIN=https://study.example.org
COOKIE_SECURE=true

POSTGRES_DB=heritage
POSTGRES_USER=heritage
POSTGRES_PASSWORD=<生成的十六进制密码>
DATABASE_URL=postgresql+asyncpg://heritage:<同一个密码>@db:5432/heritage

ADMIN_PASSWORD=<至少16位，建议32位随机>
ANON_CODE_PEPPER=<至少16位，建议32位随机；开始后不要改>
AUTH_MODE=email

DATA_DIR=/data
AUTO_BOOTSTRAP=true
CLASS_COUNT=4
PARTICIPANTS_PER_CLASS=30
T1_DURATION_SECONDS=1440
T2_DURATION_SECONDS=1200

TEXT_MODEL_BASE_URL=https://api.deepseek.com
TEXT_MODEL_NAME=deepseek-flash
TEXT_MODEL_API_KEY=<文本 key>
TEXT_MODEL_THINKING=disabled

IMAGE_MODEL_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
IMAGE_MODEL_NAME=doubao-seedream-5-0-pro-260628
IMAGE_MODEL_API_KEY=<图片 key>
IMAGE_MODEL_RESPONSE_FORMAT=url
IMAGE_MODEL_WATERMARK=false
IMAGE_MAX_CONCURRENCY=2
IMAGE_JOB_LIMIT_PER_ROUND=0
```

注意：

- `DATABASE_URL` 与 `POSTGRES_PASSWORD` 必须一致；Compose 会用 `POSTGRES_*` 覆盖 api 的数据库 URL，但备份脚本使用 `POSTGRES_PASSWORD`。
- `PUBLIC_ORIGIN` 必须与浏览器地址完全一致（含 `https://`，不带末尾 `/`）；否则 POST 的 Origin 检查会 403。
- `COOKIE_SECURE=true` 时不能用 `http://IP` 测试；production 启动会拒绝非 https 的 `PUBLIC_ORIGIN`。
- `IMAGE_JOB_LIMIT_PER_ROUND=0` 表示不限；正式收集建议设正数控制成本。
- `.env` 不进入 Git，不进入备份 zip；单独用 secret manager/加密保存。
- 不要打印 `.env` 到日志/工单。

### 4.2 静态检查

```bash
sudo apt-get install -y python3-yaml
docker compose config --quiet
python3 scripts/check_deployment.py
```

`check_deployment.py` 只检查静态文件，不验证 Docker 构建、TLS 或公网可达性。

---

## 5. 首次部署

```bash
cd /opt/heritage-learning-studio
docker compose build --pull
docker compose up -d
docker compose ps
```

预期：`db` healthy、`api` healthy、`caddy` running。

查看启动日志：

```bash
docker compose logs --tail=200 api
docker compose logs --tail=100 caddy
```

API 容器启动时会自动执行 `alembic upgrade head`。确认：

```bash
docker compose exec api alembic current
# 期望：0013_assessment_v2 (head)
```

健康检查：

```bash
set -a; . ./.env; set +a
curl -fsS "https://$SITE_ADDRESS/api/health/live"
curl -fsS "https://$SITE_ADDRESS/api/health/ready"
```

`/api/health/ready` 应返回 `database: true`、`storage: true`、`text_model_configured: true`、`image_model_configured: true`。

> 如果 `api` 不健康：先看 `docker compose logs api`；不要直接改数据库或跳过迁移。

---

## 6. 导入并激活 V2 内容

**新部署必须用 `import-formal-v2`，不要用旧的 `import-formal`（v1）或 `seed-demo`。**

先 dry-run：

```bash
docker compose exec api python -m app.cli import-formal-v2 --dry-run
```

期望输出包含：

```text
{'dry_run': True, ..., 'instruments': 17}
```

正式导入并激活：

```bash
docker compose exec api python -m app.cli import-formal-v2 --activate
```

预期：

- 17 个 instrument（16 K forms + 1 survey）
- 16 条 form 映射
- 104 条 item key（96 MC + 8 短答 key）
- active protocol 的 `assessment_version = assessment_v2.0_pilot`
- 旧 active protocol 被置为 inactive；旧 run 的 `protocol_version_id` 不变

验证：

```bash
set -a; . ./.env; set +a
docker compose exec -e PGPASSWORD="$POSTGRES_PASSWORD" db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "select id, assessment_version, is_active, activated_at from protocol_versions order by created_at;"
```

> 如果提示 `assessment_v2_already_active`：说明已有 active V2；不要再导入。只有在确实要创建新版本时才用 `--force-new-version`，并先备份。

### 6.1 已有 v1.5 数据库的升级

如果是从旧 v1.5 数据库升级：

1. 先做数据库 + `/data` 备份（见第 10 节）；
2. `docker compose build --pull && docker compose up -d`，API 自动跑 `0013`；
3. `docker compose exec api python -m app.cli import-formal-v2 --activate`；
4. 旧 run 继续用旧 protocol；新 run 用 V2；不要删除旧 instrument。

**不要**在已有 run 的库上运行 `seed-demo`；不要覆盖 `formal_v1`。

---

## 7. 研究者后台与班级链接

打开：

```text
https://<SITE_ADDRESS>/admin
```

用 `ADMIN_PASSWORD` 登录。

### 7.1 准备检查

进入“准备检查”：

- active protocol 显示 `assessment_v2.0_pilot`；
- instruments 检查通过（K0–K3 + survey，16 forms）；
- 无 demo 内容；
- 文本/图片 provider 已配置；
- `/data` 可写。

注意：已有 run 时 `ready_to_activate` 可能是 false（协议锁），这是正常的；**不要因此点击“激活当前内容为新协议”**。V2 应通过 `import-formal-v2 --activate` 创建/激活；管理员按钮用于旧的 v1/demo 路径，可能生成没有 V2 rubric 的协议。

### 7.2 生成班级链接

研究者后台 → 研究材料 → 班级专属链接：

1. 选择班级 1–4；
2. 填写标签（如 `2026-11 Class 1`）；
3. 点“生成链接 / Generate”；
4. **立即复制**；完整 token 只显示一次；
5. 每班只发本班链接；链接会锁定班级，学生不再手动选班。

如果链接泄露：轮换（Rotate）或撤销（Revoke），重新分发。

直接访问 `/` 仍可让学生手动选班；正式收集建议只发班级链接。

---

## 8. 上线验收 / Smoke Test

**建议在 staging 做 smoke，不要在生产库制造测试参与者。** 如果只能在生产做，使用一个明确标记的测试邮箱，并在分析中排除；不要删除真实数据。

按以下顺序验收：

### 8.1 基础

- [ ] `https://domain/` 打开登录页，无证书错误
- [ ] `https://domain/api/health/ready` 返回 ok
- [ ] `/admin` 可登录
- [ ] 准备检查显示 `assessment_v2.0_pilot`

### 8.2 学生流程（一条完整链路）

- [ ] 用班级链接进入，输入测试邮箱
- [ ] K0：3 基线 + 6 单选 = 9 项；文物图片只在第二组出现
- [ ] T1：工作台三栏；三段作品说明（不是旧六字段）；可对话
- [ ] HLSF 组：出现 Observe/Explain/Create/Reflect、Hint、Next；Standard 组不出现
- [ ] K1：6 单选 + 1 短答；短答显示 0/180
- [ ] K2：6 单选
- [ ] T2：第二次创作；三段说明
- [ ] K3：6 单选 + 1 短答
- [ ] Survey：7 项；S7 为单选
- [ ] 提交后进入同伴互评等待页
- [ ] AI 问答有真实回复；图片生成成功或失败可重试

> 本机已做过的 3 场景 UI/真实 AI 测试结果与截图见 `test-artifacts/v2-ui/TEST_REPORT.md`，可作为验收对照，但其中的测试参与者/数据不要迁入生产。

### 8.3 导出

管理员导出 ZIP，检查：

- [ ] `analysis.csv` 有 `assessment_version`、`mc_max=6`、`posttest_short_score_0_2`
- [ ] `survey.csv` 有 S1–S7 + `round1_ai_condition` / `round2_ai_condition`
- [ ] `work_revisions.csv` 有 `rationale_fields_json`
- [ ] `protocol.json` 有 `assessment_version`
- [ ] `assessments.csv` 有 `short_answer_pending`

短答不会自动评分；`posttest_short_score_0_2` 初始为空，由研究者线下评分后合并。

---

## 9. 备份与恢复

### 9.1 备份

```bash
cd /opt/heritage-learning-studio
./scripts/backup.sh
```

产物：

```text
backups/<UTC timestamp>/
  database.dump
  appdata.tar.gz
  manifest.txt
  SHA256SUMS
```

- 备份包含数据库 + `/data`（文物、生成图、导出、私有文件）。
- **包含个人数据**；必须加密、限权、离机保存。
- `.env` 和密钥不在备份里；单独安全保存。
- 建议 cron 每天一次，并监控失败。

加密示例（任选其一）：

```bash
# 先打包整个备份目录；文件名为示例
tar -czf /tmp/hls-backup.tar.gz -C backups <UTC-timestamp>
age -p -o /tmp/hls-backup.tar.gz.age /tmp/hls-backup.tar.gz
# 或 gpg --symmetric --cipher-algo AES256 /tmp/hls-backup.tar.gz
```

### 9.2 恢复

`restore.sh` 是破坏性的：会停 API、清空 `/data`、`pg_restore --clean`。

```bash
CONFIRM_RESTORE=YES ./scripts/restore.sh /path/to/backup
```

只在 staging 先演练；恢复后检查 `/api/health/ready`、admin、一个已完成 run 的导出。  
**永远不要**在未备份的情况下跑 `docker compose down -v`。

---

## 10. 升级与回滚

### 10.1 升级

```bash
cd /opt/heritage-learning-studio
./scripts/backup.sh
git pull            # 或解压新 tarball
docker compose build --pull
docker compose up -d
docker compose logs --tail=200 api
docker compose exec api alembic current
```

API 启动时自动迁移。大版本升级前必须备份。

### 10.2 回滚

- 代码回滚：切回上一个源码版本，`docker compose up -d --build`。
- 数据库：如果新迁移不兼容，恢复升级前备份；不要只 downgrade 迁移而不验证数据。
- V2 已产生的数据不要删除；旧 v1.5 run 仍绑定旧 protocol。
- 如果只是想让新学生回到旧协议：先备份，然后在事务中把旧 protocol 设为 active、新 protocol 设为 inactive；不要删除 v2 instrument。

```sql
BEGIN;
UPDATE protocol_versions SET is_active = false WHERE is_active = true;
UPDATE protocol_versions SET is_active = true WHERE id = '<旧 protocol id>';
COMMIT;
```

执行前确认唯一 active 索引不会冲突；不会的话停 API 再操作。

---

## 11. 安全与数据保护（必须读）

1. **登录不是认证。** `AUTH_MODE=email` 只检查字符串包含 `polyu`；任何人都能伪造。公网部署前必须加：
   - Cloudflare Access / Tailscale / VPN / 机构 SSO；或
   - 反向代理层的基本认证 + IP allowlist（仅适合内部小范围）。
   - 班级链接是 bearer token，不是身份认证；不要公开转发。
2. **管理员后台**：强密码、限制来源 IP；不要公开暴露 `/admin` 给所有人。
3. **密钥**：`.env` 600；不进 Git、不进截图、不进工单；轮换 provider key 时更新容器。
4. **数据库**：只在内网；不要发布 5432；不要把 `db_data` 拷到不受控机器。
5. **备份**：加密、离机、限权；包含邮箱/对话/作品。
6. **AI provider**：确认数据处理/跨境/是否训练；不要把 API key 放前端。
7. **图片/文物权利**：当前图片 `rights_status=internal-research`；公网发布前需馆方/版权授权。
8. **伦理**：当前没有完整同意/撤回/删除流程；真实数据收集前必须完成 IRB/DPIA/参与者信息页。
9. **单 worker**：不要在 Compose 外增加多个 API 副本；聊天锁、限流、图片 worker 都是进程内。
10. **CSRF**：依赖 SameSite + Origin 检查，没有 CSRF token；高风险部署建议加 token 或放在受控网关后。

---

## 12. 常见故障

| 现象 | 检查 | 处理 |
|---|---|---|
| 改了 `.env` 不生效 | 容器仍用旧环境 | `docker compose up -d --force-recreate api`（不要只 restart 旧容器） |
| Caddy 502 | `docker compose ps`，api 是否 healthy | `docker compose logs api`；修 DB/provider；重启 |
| TLS 失败 | DNS、80/443、Cloudflare 代理 | 先灰云/DNS challenge；看 `docker compose logs caddy` |
| `study_setup_incomplete` | 没有 active protocol | 跑 `import-formal-v2 --activate` |
| `assessment_v2_already_active` | 已有 active V2 | 不要重复导入；需要新版本才 `--force-new-version` |
| `formal_content_missing` | 镜像内 content 缺失 | 重新 build；检查 `backend/app/content/formal_v1/media` |
| admin 激活按钮失败 | 有 run 时协议锁 | 不要点；用 CLI 导入/激活 |
| 登录 403/origin | `PUBLIC_ORIGIN` 不匹配 | 改成实际 `https://domain`，无末尾 `/`；重启 api |
| Cookie 不保存 | `COOKIE_SECURE`/HTTPS | production 必须 HTTPS；不要用 http IP |
| AI 401/timeout | key、出站、provider 配额 | 从服务器 `curl -I` provider；看 `ai_calls` |
| 图片很慢/失败 | provider 队列/超时 | 可先提交文字；设置 `IMAGE_JOB_LIMIT_PER_ROUND` 控制成本 |
| 互评一直等待 | 同班有人未结束 T2 | 这是自动班级闸门；等或按 runbook 处理缺席 |
| 磁盘满 | `/data` 生成图/备份 | 清理旧备份/导出；监控磁盘；不要删数据库卷 |
| 迁移失败 | `docker compose logs api` | 停止；恢复备份；不要手改 alembic 版本 |

---

## 13. 已知限制 / Go-No-Go

### 可以做的

- 内部工程演示、UI/流程验收、AI 辅助演示；
- 小范围、受控网络下的 Pilot（仍需伦理/内容审核）；
- 旧 v1.5 数据只读/导出。

### 还不能直接做的

- 公网、真实参与者、正式研究数据收集；
- 依赖当前邮箱门禁做身份认证；
- 把 V2 题本当作已等值/已验证量表；
- 自动评分短答或 T2 作品（目前手工）；
- 多副本/多 worker 横向扩展；
- 无备份/无监控的长期运行。

正式收集前的 P0：伦理/同意/DPIA、文物图片授权、内容专家审核、4–8 人认知访谈、Pilot、A/B 难度与信度检查、短答双评、备份恢复演练、真实 provider 压测、安全评审。

---

## 14. 交接证据

部署完成后，把以下内容记录到 `deployment-log.md`（**不要写密钥**）：

- 服务器/域名/部署时间/源码版本或 tarball SHA256；
- `docker compose ps` 输出；
- `alembic current` 输出；
- `import-formal-v2 --dry-run` 和正式导入输出（截取计数，不含 key）；
- `/api/health/live` 与 `/api/health/ready` 的 JSON（可脱敏）；
- admin 准备检查截图（显示 `assessment_v2.0_pilot`）；
- 一次学生 smoke 的 K0/K1/K2/K3/Survey 截图；
- 一次备份 manifest 与恢复演练记录；
- 未完成事项和负责人。

---

## 附录 A：命令速查

```bash
cd /opt/heritage-learning-studio
set -a; . ./.env; set +a

docker compose ps
docker compose logs -f --tail=200 api
docker compose logs -f --tail=100 caddy

curl -fsS "https://$SITE_ADDRESS/api/health/live"
curl -fsS "https://$SITE_ADDRESS/api/health/ready"

docker compose exec api alembic current
docker compose exec api python -m app.cli import-formal-v2 --dry-run
docker compose exec api python -m app.cli import-formal-v2 --activate

docker compose exec -e PGPASSWORD="$POSTGRES_PASSWORD" db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "select id, assessment_version, is_active from protocol_versions order by created_at;"

./scripts/backup.sh
CONFIRM_RESTORE=YES ./scripts/restore.sh /path/to/backup
```

## 附录 B：关键文件

| 文件 | 作用 |
|---|---|
| `docker-compose.yml` | db/api/caddy 拓扑 |
| `backend/Dockerfile` | API 镜像；启动自动迁移 |
| `Dockerfile.caddy` | 构建前端 + Caddy 镜像 |
| `Caddyfile` | TLS、静态站、/api 反代、安全头 |
| `.env.example` | 环境变量模板 |
| `backend/app/content/formal_v2/` | V2 题本、答案键、短答 rubric |
| `backend/app/content/formal_v1/` | 两件文物与媒体；V2 复用 |
| `backend/alembic/versions/0013_assessment_v2.py` | V2 迁移 |
| `scripts/backup.sh` / `restore.sh` | 备份/恢复 |
| `docs/ASSESSMENT_V2_PILOT.md` | V2 题本、计分、导出、限制 |
| `docs/ASSESSMENT_ITEM_BANK_V2_ZH.md` | 研究者题本全文 |
| `docs/SECURITY.md` | 安全边界 |

## 附录 C：环境变量最小表

| 变量 | 必填 | 说明 |
|---|---|---|
| `ENVIRONMENT` | 是 | `production` 触发安全校验 |
| `SITE_ADDRESS` | 是 | Caddy 域名，不带 scheme |
| `PUBLIC_ORIGIN` | 是 | 浏览器 origin，`https://`，无末尾 `/` |
| `COOKIE_SECURE` | 是 | production 必须 `true` |
| `POSTGRES_*` | 是 | 数据库凭据；密码用 hex |
| `DATABASE_URL` | 是 | Compose 内部连接串 |
| `ADMIN_PASSWORD` | 是 | ≥16 字符 |
| `ANON_CODE_PEPPER` | 是 | ≥16 字符；开始后不改 |
| `AUTH_MODE` | 是 | 当前 `email` |
| `DATA_DIR` | 是 | 容器内 `/data` |
| `AUTO_BOOTSTRAP` | 建议 | `true` 确保班级 1–4 |
| `T1_DURATION_SECONDS` / `T2_DURATION_SECONDS` | 是 | 1440 / 1200 |
| `TEXT_MODEL_*` | 是 | 文本 provider；app 追加 `/chat/completions` |
| `IMAGE_MODEL_*` | 是 | 图片 provider；app 追加 `/images/generations` |
| `IMAGE_JOB_LIMIT_PER_ROUND` | 建议 | 0=不限；生产建议正数 |
| `CLASS_COUNT` / `PARTICIPANTS_PER_CLASS` | 是 | 4 / 30 |
