# HLSF Crossover v1.0 Pilot — Protocol and Development Record

> **V2.0 测评更新（2026-11-07）：** 四组/文物/AI 条件不变；新 run 使用 `crossover-v1.1-assessment-v2-pilot`，K0=3 baseline+6 MC、K1/K3=6 MC+1 后测短答、K2=6 MC、Survey=7，T1/T2 统一三段作品说明。旧 `crossover-v1.0-pilot` 记录保留。详见 [ASSESSMENT_V2_PILOT.md](ASSESSMENT_V2_PILOT.md)。

日期：2026-11-07  
状态：正式 Pilot 版本；旧 v1.5 协议历史保留  
设计版本：`crossover-v1.0-pilot`  
HLSF 版本：`hlsf-v1.7.1-crossover-pilot`

> 这是一次四组平衡交叉设计。平台不重建，只扩展分组分配、T2 条件、HLSF 启用条件和数据导出。旧 run 没有 `design_version` 时继续按 v1.5（T2 全部 Standard AI）解释。

## 1. 设计

| 组别 | T1 | T2 |
|---|---|---|
| G1 | 文物 X + Standard AI | 文物 Y + HLSF + AI |
| G2 | 文物 Y + Standard AI | 文物 X + HLSF + AI |
| G3 | 文物 X + HLSF + AI | 文物 Y + Standard AI |
| G4 | 文物 Y + HLSF + AI | 文物 X + Standard AI |

- X：明代纱绣彩云莲塘鹭鸶纹文官六品方补（2024.CH-HKPM.6）
- Y：唐代红地联珠对格里芬纹锦（2024.CH-HKPM.2）
- 每名学生两轮使用不同文物；
- 每名学生恰好一次 A、一次 B；
- 学生端不显示 A/B 或组别。

## 2. 分配

四班各 30 人，班级内随机配额：

| 班级 | G1 | G2 | G3 | G4 |
|---|---:|---:|---:|---:|
| Class 1 | 8 | 7 | 7 | 8 |
| Class 2 | 7 | 8 | 8 | 7 |
| Class 3 | 8 | 7 | 7 | 8 |
| Class 4 | 7 | 8 | 8 | 7 |

每班 T1 条件：15 A / 15 B；T1 文物：15 X / 15 Y。  
四班合计：每组 30 人，共 120 人。

分配使用服务端 pepper + 班级 + 配额版本的确定性 HMAC 种子打乱配额槽位；不按登录顺序固定给某个条件。每名新 run 的 K0 `StageEvent.meta_json` 记录分配方法、配额、组别和 seed hash；学生重新登录继续原组别与进度。若实际人数不足 30，按实际分配记录偏差，不重新分配已开始实验的学生。

## 3. T1/T2 条件

| 组 | condition sequence | artifact sequence | test forms |
|---|---|---|---|
| G1 | AB | XY | K0/K2 first, K1/K3 second |
| G2 | AB | YX | same |
| G3 | BA | XY | same |
| G4 | BA | YX | same |

- `test_form_order` 在班级 × 组内交替 AB/BA，并加事务级 advisory lock，避免并发首登重复；
- 作品说明形式由 AI 条件决定：B 轮使用六字段结构化说明，A 轮使用开放说明；不再按 T1/T2 固定；
- 旧 v1.5 run（`design_version` 为空）仍按旧规则 T1 六字段 / T2 开放说明，避免破坏已开始的历史进度；
- K0/K1 使用 T1 文物；K2/K3 使用 T2 文物；
- HLSF 只由当前 round 的 condition=B 触发，与轮次无关；
- condition=A 明确使用 Standard AI 约束：不主动教学、不引入四阶段框架、不给“可以从……入手”的主动设计流程；
- T2 B 初始化新的 `HLSFState`，Reflect 使用开放作品说明；
- T2 不继承 T1 的 HLSF 状态、系统 Prompt 或对话记录。

## 4. 数据与导出

新增 run 字段：

- `design_version`：新 run = `crossover-v1.0-pilot`；旧 run 为空/legacy；
- `condition_sequence`：`AB` / `BA`；
- `artifact_sequence`：`XY` / `YX`。

`analysis.csv` 每个学生 × 轮一行，包含：

```text
student_id, class_id, group_id, design_version, round_no,
artifact_id, artifact_slot, ai_condition,
condition_sequence, artifact_sequence, test_form_sequence,
prompt_versions, stage_events, student_messages, assistant_messages,
design_versions, final_submission,
knowledge_pretest_score, knowledge_posttest_score,
task_start_time, task_end_time
```

研究后台：

```text
GET /api/admin/export                 # full zip, includes analysis.csv
GET /api/admin/analysis.csv           # filtered analysis view
  ?student_id=&class_id=&group=G1&round_no=1&artifact=X&ai_condition=A
```

## 5. 统计注意

- 240 个学生 × 轮记录不是 240 个独立学生；两轮是重复测量；
- T2 可能受 T1 学习经历、顺序和携带效应影响；
- T1 的 Standard vs HLSF 比较是 60 vs 60 的随机对照；
- 两轮差异不能直接解释为纯即时 HLSF 效应；
- 旧 v1.5 run 不能与新 crossover run 混在同一条件变量中。

## 6. 保留与不修改

保留登录、UUID、断点恢复、数据库持久化、AI API、图像队列、文物、题库、作品字段（B 六字段 / A 开放说明）、互评、模拟 Instagram 和既有后台功能。MaxDiff 不在本平台范围内。

## 7. 历史

旧 `PROTOCOL_V15_FINAL.md` 保留为 v1.5 历史冻结记录；新协议不覆盖旧记录。旧 run 的 `design_version` 为空时，导出标记为 `legacy-v1.5`，T2 仍按 Standard AI 解释。


## 8. 验证

- 后端：45 passed
- 前端：4 files / 11 tests passed
- `tsc --noEmit`、`vite build` 通过
- 迁移 0001 → 0012 在全新 PostgreSQL 上通过
- G1–G4 均完成 K0 → T1 → K1 → K2 → T2 → K3 流程测试
- T2 HLSF 的 Observe/Explain/Create/Reflect、Hint、Next/Skip 已覆盖
