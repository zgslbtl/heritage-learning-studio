# 正式文物内容与中性学生界面（v1.5）

> **历史文档：** 本文记录 `formal_v1` / 8 MC + 1 短答 / 六字段与开放说明的 v1.5 实现。当前新 run 使用 V2.0：`docs/ASSESSMENT_V2_PILOT.md` 与 `docs/ASSESSMENT_ITEM_BANK_V2_ZH.md`。`formal_v1` 保留用于历史数据读取，不要覆盖。

日期：2026-11-07  
状态：已接入正式文物资料、K0–K3 平行题本、T1/T2 任务文案、隐藏答案键与研究者量规。

## 1. 正式内容

- 两件文物：
  - M/X：明代纱绣彩云莲塘鹭鸶纹文官六品方补（`CH-HKPM.6`）
  - T/Y：唐代红地团窠联珠对格里芬纹锦（`CH-HKPM.2`）
- 内容包：`backend/app/content/formal_v1/`
  - `artifacts.json`：章节、来源、媒体映射
  - `instruments.json`：M/T × A/B 题本、K0 baseline、survey
  - `assessment_keys.json`：选择题答案与短答评分要点
  - `rubric.json`：T2 4×0–3 量规与过程编码
  - `media/`：7 张馆藏图（原图 + 显示变体）
- 学生页面只显示 M01–M08 / T01–T08、来源与未明信息；**不包含 M09/T09 或任何现代产品/设计方向建议**。
- 图片通过受保护的 `/api/files/artifacts/{id}/media/{key}` 提供；原图只在放大时读取，不在公共静态目录。
- T1/T2 右侧顶部有“用文字描述你希望的产品图”大输入框；学生描述是图片生成的主要视觉方向。
- 每轮可连续生成多张产品概念图，学生选择一张用于提交；互评/作品广场使用该选图。
- 作品不做人工审核；技术性提交成功的 T2 作品直接进入互评/作品广场。评论不做事前审核，保留研究者应急隐藏接口。
- T2 最终提交处底部有小字“提交即表示同意将今天的学习数据用于后续研究”；无勾选框。
- 图片权利状态为 `internal-research`；正式公网发布前仍需馆方授权。

## 2. 题本与分配

- 16 个 K form：`k0/k1/k2/k3` × `M/T` × `A/B`。
- K0 包含 6 道 baseline（不评分）+ 8 道知识题 + 1 道短答；K1–K3 为 8+1。
- K0/K1 使用 T1 文物；K2/K3 使用 T2 文物。
- `runs.test_form_order` 在组内平衡 AB/BA；K0/K1 使用不同 form，K2/K3 使用不同 form。
- `runs.object_order` 记录 MT/TM，便于审计。
- 学生界面不显示 form code、K 阶段编号、题目分值、答案键或自动得分。
- 短答和 T2 量规评分仍在平台外；平台导出原文、form 与研究者评分模板。

## 3. 学生界面语气

- K0 = “开始前的小问题”
- K1 = “刚才的学习回顾”
- K2 = “下一件文物之前”
- K3 = “最后的学习回顾”
- survey = “最后几个问题”
- T1/T2 = “第一次/第二次文物创作”
- 提交按钮 = “继续”
- 不显示版本号、题型、required 标记、分数、正确/错误反馈、K/T/HLSF 标签。
- K0 先显示 baseline，再进入文物知识题；文物图片只在知识组出现，且不显示名称/年代/类型。

## 4. 文物资料页

- 主图完整显示，点击可打开原图 lightbox。
- 章节点击展开；默认展开总览，每次只展开一个章节。
- 章节包含正文、来源 chip、关联细节图。
- 点击日志：
  - `section_open` / `section_close` + duration_ms
  - `media_open` + media_key/caption
  - `source_open` + source_id/section
  - 写入 `evidence_events.meta_json`
- 移动端单列；正文行高与字号以可读性优先。

## 5. 导入

```bash
cd backend
.venv/bin/python -m app.cli import-formal
```

- 只允许在没有任何 run 的新数据库上导入。
- 创建 2 个正式 artifact、17 个 instrument（16 K forms + survey）、正式 protocol 和 form 映射。
- 正式内容导入后，旧简化后台编辑器不允许保存正式章节/题本；修订需新建内容版本并重新导入。
- 本机预览可用：

```bash
HLS_FORMAL=1 HLS_API_PORT=8010 HLS_WEB_PORT=5174 \
  backend/.venv/bin/python scripts/dev_runtime.py
```

前端代理：

```bash
cd frontend
VITE_API_TARGET=http://127.0.0.1:8010 \
  node_modules/.bin/vite --host 127.0.0.1 --port 5174 --strictPort
```

## 6. 数据与测试

- 迁移：`0006_formal_content_forms_media`。
- 新表：`protocol_assessment_forms`、`assessment_item_keys`。
- `assessments.csv` 增加 object/form、研究者可见的选择题得分；`assessment_answers.csv` 增加 form/section。
- `evidence_events.csv` 增加 meta_json；`runs.csv` 增加 object_order/test_form_order；`protocol.json` 包含 sections/media/form 映射/rubric。
- 当前回归：后端 46 passed；前端 11 tests passed；`tsc --noEmit` 与 `vite build` 通过。
- 仍未完成：伦理/同意、正式图片授权、30 人真实 Provider 压测、Docker/Caddy 验证、Pilot、T2 评分工作台。
