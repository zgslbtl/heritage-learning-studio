# 京东云 OSS 与图片交付

本实现从京东云 Docker 部署合并回仓库，适用于 `STORAGE_BACKEND=jdcloud_oss`。
文物图片、生成图片及任务文件存入私有 OSS，数据库仍使用 PostgreSQL，队列可使用本地 worker。
密钥只由服务器读取；浏览器继续使用原有 `/api/files` 路由，先通过会话及作品权限检查。

## 配置

在自己的根目录 `.env` 中配置，不提交真实凭据：

```dotenv
STORAGE_BACKEND=jdcloud_oss
QUEUE_BACKEND=local
OSS_ENDPOINT_URL=https://s3.cn-south-1.jdcloud-oss.com
OSS_REGION=cn-south-1
OSS_BUCKET=your-private-bucket
OSS_ACCESS_KEY_ID=填写专用子用户凭证
OSS_SECRET_ACCESS_KEY=填写专用子用户凭证
```

Endpoint 不含桶名，并与自己的存储桶区域一致。凭证需要相应桶的读、写和查询权限；
桶保持私有，代码不设置公开 ACL。API 镜像仍挂载持久化 `app_data:/data`。

SDK 使用 S3 v4 签名及显式 OSS 凭据，供应商错误转换为不含签名或内部消息的应用错误。
OSS 模式不提供 Blob 直传签名链接；后台上传经认证 API 完成。

## 迁移已有文件

先备份 PostgreSQL、完整 `/data`、旧配置和应用镜像。先配置 OSS 凭据并保持
`STORAGE_BACKEND=local`，构建 API 镜像。在项目根目录运行：

```sh
docker compose build api
# 默认只预览，不上传。
docker compose run --rm -T --no-deps api python - < scripts/migrate_jdcloud_oss.py
# 明确执行上传，保存私有核查清单。
docker compose run --rm -T --no-deps api python - --apply --report /data/private/oss-migration.json < scripts/migrate_jdcloud_oss.py
```

脚本保留文件相对路径，上传后下载核对 SHA-256；已有同名对象必须一致，否则停止。
不会删除本地文件，不迁移 `private/`、配置或数据库。该脚本会上传
`artifacts/`、`keyframes/`、`uploads/`、`provider-results/` 和 `exports/` 中的有效文件。

切换前暂停 API 写入，并通过上述临时容器再核对一次增量；随后设置
`STORAGE_BACKEND=jdcloud_oss` 并重建 API 容器。检查就绪接口、登录后的图片访问与原图下载，
并核对导出。生产环境迁移与切换需要独立操作；合并代码不会自动执行这些步骤。

## 图片展示与原图

OSS 图片首次访问时缓存到持久化数据卷。大于 256 KiB 的适用图片生成最长边
1600 像素、质量 85 的 WebP 展示副本；若转换后更大则使用源文件。
副本保存在 `/data/private/image-previews/`，可删除后重建，不上传到 OSS。

`variant=original` 返回原图，`download=1` 请求附件下载；生成图片卡片提供
“下载高清原图 / Download original”链接。原始文件、AI 参考图及研究导出不被展示压缩修改。

响应设置 `Cache-Control: private, no-cache`、`Vary: Cookie, Authorization` 和 ETag。
每次请求（包括条件请求返回 304 前）均验证身份及作品权限。
Vercel Blob 保持原有签名跳转传输，不执行 OSS 的本地展示图转换。

## 回退与部署边界

代码回退时保留数据库、OSS 和原始本地文件。若改回 `STORAGE_BACKEND=local`，
先把切换后新增但尚未缓存到本地的文件下载至原路径，核对哈希后再切换。
只回退代码，不删除研究数据，不更换匿名化 pepper。

研究用 `study` 部署支持内部班级 0 和正式班 1–4；班级 0 持续报名并使用个人互评快照。
独立 `beta` 部署仍仅允许班级 0。正式班维持全班闸门和两轮互评规则。

API 构建默认使用 PyPI；有需要时可指定公开包镜像源：

```sh
docker compose build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple api
```

## 验证范围

`backend/tests/test_jdcloud_oss.py` 使用内存 S3 替身及 SDK Stubber 检查读写、冲突、
迁移、缓存、权限、原图下载和导出；不连接真实 OSS 或真实 AI。
本次合并的测试及线上只读核查见 [服务器变更合并记录](SERVER_SYNC_20261108.md)。
