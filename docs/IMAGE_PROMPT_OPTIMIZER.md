# Image Prompt Optimizer and Student-Authority Pipeline

日期：2026-11-08  
状态：已实现；默认**不自动注入文物内容**。仅当本地关键词或 DeepSeek 门控判断学生明确使用文物内容时，才加入紧凑文字参考，并把文物原图作为参考图发给图片模型；否则纯文生图。

## 1. 为什么改

旧流程会把学生描述、作品字段和整段文物阅读摘要一起拼成图片 prompt。这既产生 3000–5000 字符的长 prompt，也会让只写“白色 T 恤”的学生自动得到带方补纹样的成品，无法区分学生自己的能力。

新流程把学生输入作为唯一默认视觉依据；文物内容只在学生明确提及纹样/文物术语时加入紧凑参考。

## 2. 新流程

```text
学生图片描述 + 学生作品字段
        ↓
检查是否明确提到文物/纹样术语
  ├─ 否：只用学生文本，生成中性产品图 prompt；不带参考图
  └─ 是：加入紧凑的文物标题/对象事实参考；
          并把文物原图作为 image 参考发给图片模型
        ↓
文本模型：只压缩文字 prompt（≤180 字中文），不接收参考图
        ↓
图片模型：门控 true 时 text prompt + 文物参考图；false 时纯文生图
        ↓
ImageJob 保存 optimized prompt + source_prompt + reference_image_used
```

关键词示例：

- 方补：`方补`、`补子`、`鹭鸶`、`白鹭`、`莲塘`、`莲花`、`纱绣`、`彩云`、`文官`、`六品`
- 联珠格里芬锦：`联珠`、`团窠`、`格里芬`、`狮鹫`、`对兽`、`神兽`、`红地`、`织锦`、`唐锦`

门控流程：

1. 显式术语命中 → 直接 true；
2. 未命中 → 文本模型高精度语义判断；
3. 模型失败、输出格式错误或不确定 → false（fail closed）。

这样既能覆盖“祥云/对称/连续/串珠”等同义或局部描述，又不会因为泛泛的“白色 T 恤”自动补全文物设计。门控同时决定两件事：

- 是否在文字 prompt 中加入紧凑文物参考；
- 是否把文物原图作为 `image` 参考发给图片模型。

门控不替学生写设计；DeepSeek 的提示词优化器仍然只做文字压缩，不接收文物图，避免把学生没写到的纹样提取进 prompt。

## 3. Prompt 编辑规则

`backend/app/services/ai_text.py` 中的 `IMAGE_PROMPT_OPTIMIZER_SYSTEM`：

- 只输出一段简体中文；
- 保留学生明确写的产品、材质、颜色、构图、场景、氛围；
- 不替学生改产品类别；
- 不自行加入文物知识、纹样或文化符号；
- 不加文字、logo、水印、虚构铭文；
- 全文不超过 180 个汉字。

服务端还会再做一次 `_clean_optimized_prompt` 截断。

## 4. 文物参考

- 门控为 true 时，`_process_job` 调用 `_artifact_reference_data_url` 读取当前冻结文物的图片，生成 data URL，并传给 `_call_image_provider`；图片模型请求体出现 `image` 字段。
- 门控为 false 时，`reference_data_url=None`，图片模型只收到文字 prompt。
- 学生没有明确提到文物/纹样术语时，`source_prompt` 不包含文物标题、文物事实或阅读摘要，也不带参考图。
- 学生明确提到时，文字参考只加入：
  - 文物标题；
  - 少量对象级事实/证据；
  - 不加入整段 `sections_json` 阅读材料。
- **注意：** 正式文物的 `facts`/`evidence` 在导入时为空，策展内容存放在 `sections_json`。`_artifact_reference_summary` 只读 `facts`/`evidence`，因此当前“紧凑文字参考”通常只有文物标题/年代/类型；门控本身会读 `sections_json` 摘要（≤6000 字符）来判断是否相关。
- **参考图只发给图片模型，不发给 DeepSeek：**
  - 门控（`artifact_relevance`）只收到文物文字证据 + 学生文本，不收到文物图；
  - 提示词优化（`image_prompt_optimization`）只收到文字 prompt，不收到文物图；
  - 图片模型在门控 true 时收到 `image` 参考图。
- `IMAGE_REFERENCE_ENABLED=true` 是默认值；设为 `false` 是应急关闭参考图的开关（例如 Provider 拒绝 `image` 或账号权限变化）。
- 若 Provider 拒绝带 `image` 的请求，worker 会自动重试一次纯文生图，并把 `reference_image_used` 记为 `false`。
- `reference_image_used` 只有在图片模型请求实际带参考图并成功时才是 `true`。

## 5. 数据字段

`image_jobs` 新增：

- `source_prompt`：完整原始 prompt；
- `prompt`：最终发送给图片模型的优化 prompt；
- `prompt_optimizer_version`：`image-opt-v1` 或 `fallback-compact-v1`；
- `reference_image_used`：是否实际带参考图发送。

文本编辑调用记录在 `ai_calls`：

```text
purpose = image_prompt_optimization
prompt_version = image-opt-v1
```

不保存图片 base64 到数据库；`request_json` 只标记 `has_reference_image`。

## 6. 配置

```env
IMAGE_PROMPT_OPTIMIZER_ENABLED=true
TEXT_MODEL_VISION_ENABLED=true
IMAGE_REFERENCE_ENABLED=true
```

说明：

- `IMAGE_PROMPT_OPTIMIZER_ENABLED=true`：每次生图前先压缩文字提示词；
- `TEXT_MODEL_VISION_ENABLED=true`：预留参数；当前提示词优化器不接收参考图，因此不会把文物图给文本模型。若未来让优化器做多模态，文本模型不支持视觉时仍会回退纯文本压缩；
- `IMAGE_REFERENCE_ENABLED=true`：门控为 true 时把文物原图作为 `image` 参考发给图片模型；设为 `false` 可应急关闭。Provider 拒绝 `image` 时 worker 会回退纯文生图。

测试环境中 `IMAGE_PROMPT_OPTIMIZER_ENABLED=false`，避免旧图片测试依赖文本模型；参考图测试会单独打开相关路径。

## 7. 当前验证

- 后端 `76 passed, 4 skipped`；
- 前端 `6 files / 13 tests passed`；
- 单元/接口验证：
  - 仅写“白色 T 恤”时，source prompt 不含文物标题、方补、鹭鸶等，`reference_image_used=false`；
  - 明确写“方补里的鹭鸶”时，才加入紧凑文字参考；
  - 门控 true 时，图片模型 payload 带 `image` 参考图，`reference_image_used=true`；
  - 门控 false 时，payload 不含 `image`。

## 8. 运营注意

- 当前 Provider 的 `image` 参考图能力可能随模型/账号权限变化；若 Provider 拒绝，worker 会回退纯文生图并把 `reference_image_used` 记为 `false`，任务本身仍可成功；
- 图片 prompt 长度上限和 `image` 字段支持应在更换 Provider 时重新验证；
- 若要临时关闭参考图（例如 Provider 限流或账单异常），设置 `IMAGE_REFERENCE_ENABLED=false`；不需要改代码；
- 不要因为回退而删除 `source_prompt`；它用于研究审计和学生原始表达保留。
