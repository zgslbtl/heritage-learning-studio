# 班级0内测部署验收

日期：2026-11-07（Asia/Shanghai）。这是部署工程验收，所有验收输入均为明确标记的合成测试数据，不属于研究结果。

## 网络可达性复核

交付后用户在Chrome遇到`ERR_CONNECTION_TIMED_OUT`。在当前电脑复现：沿工具环境代理请求首页、班级入口和API均为200；关闭环境代理后直连项目域名超时，而Apple和Vercel官网可直连。本机DNS返回`38.121.72.166`，Google/Cloudflare的HTTPS解析返回不同的Vercel地址；指定公共解析地址直连时也出现连接重置或超时。因此此前公网验收证明了服务通过该代理路径可用，不能据此确认用户当前直连网络或周围用户的网络可达性。尚未修改本机代理/DNS配置，账户暂无已配置的自定义域名。

## 访问与登录

- 班级0入口：<https://heritage-learning-beta.vercel.app/join?token=UyjjI3gQmlET-7NBuBdItwe4YnR-7gXI>
- 研究者后台：<https://heritage-learning-beta.vercel.app/admin>
- 后台密码只保存在本机 `.local-runtime/vercel-beta-admin.txt`，未写入本文件或前端。
- 登录输入去除首尾空格并转为小写后，只需包含 `polyu`；不增加口令、验证码或邮箱验证。相同输入恢复相同进度。
- 班级链接固定为0；后台仍可撤销或轮换链接。服务端拒绝班级1–4。

## 最终资源与版本

| 项目 | 已部署配置 |
| --- | --- |
| Vercel空间 | `lisanlu666-6622` |
| 项目 | `heritage-learning-beta` / `prj_bXVmdeJgJDPfsxrcIRLFO7BU9HlI` |
| 最终部署 | `dpl_A3urEs5ZU3B27nBNJ7rc4YWmFyaA` |
| 数据库 | 独立Neon `heritage-learning-beta-db`，Free，sin1 |
| 私有文件 | Blob `heritage-learning-beta-media` / `store_UYTj5LAR4CRTsoTG` |
| 异步任务 | `heritage-beta-tasks`，私有订阅服务，图片全局并发2 |
| 模式 | `ENVIRONMENT=production` / `DEPLOYMENT_MODE=beta` |
| 数据库迁移 | `0015_beta_peer_snapshots` |

初始化只创建班级0并导入现有V2文物、题本和协议。未复制本地历史参与者、会话、作品或测试运行；未连接正式研究数据库。未升级付费套餐。

## 已验证结果

| 验收项 | 结果与证据边界 |
| --- | --- |
| 本地后端 | 62项测试通过，包括正式模式回归、迁移、班级隔离、个人互评快照、任务去重及文件授权 |
| 本地前端 | 11项测试通过，生产构建通过 |
| 公网登录 | 大写及首尾空格被正确归一化；不含polyu被拒绝；手动请求班级1被拒绝 |
| 完整流程 | 两位合成用户完成K0、教程、T1、K1、K2、T2、K3、问卷、互评和作品流；另一个浏览器用户停留K0未阻塞其他人 |
| 测评与时长 | K0/K1/K2/K3分别9/7/6/7题，问卷7题；T1为1440秒，T2为1200秒；保存草稿可恢复 |
| 真实文本 | 两轮均调用已配置真实文本服务并返回回复 |
| 真实图片 | 两轮PNG成功，分别2,588,967及2,315,984字节，私有Blob可授权读取 |
| 首次失败与重试 | T1首次供应商调用报`image_model_unavailable`；保留失败任务，显式手动重试成功，未自动重复调用 |
| 陆续参与 | 首位用户互评池为空，允许继续；后加入者得到1份其他用户作品并完成互评；退出再登录保持原run及完成状态 |
| 私有存储 | 私有对象匿名读取被拒绝；授权图片可读取；4,922,602字节合成PNG通过授权直传成功，未修改冻结文物版本 |
| 导出 | 后台异步导出成功，私有ZIP为4,961,697字节；清单标明beta、包含3位参与者、缺失文件为0，participants.csv未包含登录邮箱 |
| 浏览器 | 桌面与移动端K0及后台检查完成；后台导出按钮返回下载入口 |
| 最终部署与持久性 | 见下方最终复核状态及机器记录 |

最大6份互评、个人任务冻结、正式班级全班闸门、队列重复消息和权限边界已有本地自动化覆盖。公网互评池实际覆盖0份和1份；未声称完成6人互评池或大规模真实供应商并发压力验收。

导出通过授权Range读取ZIP目录、manifest和participants.csv，未为本次验收完整下载ZIP中所有图片并逐项执行CRC检查。

## 最终部署复核

最终部署为Ready，生产域名已指向该部署。`test-artifacts/vercel-beta/persistence.json` 为 `status=passed`：3位参与者的ID、run、进度、分组及协议版本在重新部署前后相同；两张生成图片与既有导出文件的长度、ETag和前1024字节哈希均一致。同时通过`/join`、`/admin`直接访问、班级链接解析、数据库/存储健康及未登录图片请求被拒绝的检查。

最终部署另行发起的新导出任务也已成功，确认新部署的私有队列消费者实际执行任务，记录在`test-artifacts/vercel-beta/final-deployment.json`。

## 测试记录与回滚

验收后保留3个明确标记的`deployment-qa-polyu-*`账号，2个已完成、1个停留K0。其合成回答及测试作品用于工程追踪，后续数据分析应排除；本次未删除任何记录。

- `test-artifacts/vercel-beta/acceptance.json`：真实流程、图片任务ID、手动重试及导出记录。
- `test-artifacts/vercel-beta/large-upload.json`：大文件直传检查。
- `test-artifacts/vercel-beta/persistence.json`：最终部署前后对照。
- `test-artifacts/vercel-beta/final-deployment.json`：最终部署的新队列任务验收。
- `test-artifacts/vercel-beta/deployment-source-manifest.json`：126个部署文件的长度及SHA256；部署包已排除密钥、历史数据、备份、参考文献和测试输出。
- `output/playwright/`：本机浏览器截图；不发布至公网。
- `.backups/vercel-beta-20261107T115941Z/`：改造前源代码备份，不包含密钥或历史数据。

代码回滚可在Vercel项目中把生产域名重新指向上一可运行部署`dpl_8WiXcW6qnMbNXkgHi43YfumbooZd`。保留当前Neon数据库、私有Blob、pepper和服务端配置；不执行破坏性downgrade，不删除测试或用户数据。迁移0015只修正班级0个人快照索引，保留正式班级的唯一活跃互评批次约束。

模型供应商仍可能返回瞬时错误；失败会显示给用户并允许手动重试。当前提供的是独立班级0内测部署，未据此宣称正式研究有效性或学习效果。
