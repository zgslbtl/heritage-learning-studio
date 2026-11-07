# Image Prompt Optimizer and Reference-Image Pipeline

日期：2026-11-07  
状态：已实现；当前图片 Provider 的参考图输入不稳定，自动回退到纯文生图

## 1. 为什么改

学生端会把以下内容一起拼成图片 prompt：

- 学生填写的视觉描述；
- 产品名称、类别、受众、设计概念；
- 六字段；
- 文物章节阅读摘要；
- 固定视觉方向。

这会形成 3000–5000 字符的 prompt，超过图片模型建议长度；实测长英文 prompt 会让 Provider 直接断开连接。

## 2. 新流程

```text
学生图片描述 + 作品字段 + 文物资料
        ↓
服务端生成 source_prompt（保留完整记录）
        ↓
文本模型：图像提示词编辑
  - 尽量同时参考文物图片
  - 输出简体中文
  - ≤ 180 个汉字
        ↓
optimized prompt
        ↓
图片模型
  - 尝试带文物参考图 image
  - 若 Provider 拒绝参考图，自动回退纯文生图
        ↓
ImageJob 保存 optimized prompt + source_prompt
```

## 3. Prompt 编辑规则

`backend/app/services/ai_text.py` 中的 `IMAGE_PROMPT_OPTIMIZER_SYSTEM`：

- 只输出一段简体中文；
- 保留学生明确写的产品、材质、颜色、构图、场景、氛围；
- 不替学生改产品类别；
- 可结合文物图片的可观察纹样关系；
- 不加文字、logo、水印、虚构铭文；
- 全文不超过 180 个汉字。

服务端还会再做一次 `_clean_optimized_prompt` 截断，避免模型输出超长。

## 4. 参考图

- 优先使用文物的 display JPEG（体积较小）；
- 以 `data:image/jpeg;base64,...` 传给图片模型的 `image` 字段；
- 图片模型支持时，`reference_image_used=true`；
- 当前火山方舟 Seedream 端点实测在带 `image` 字段时会 `RemoteProtocolError`（无论 base64 还是公开 URL），因此自动回退到不带 `image` 的纯文生图；
- 回退后 `reference_image_used=false`，但优化后的中文 prompt 仍保留文物视觉描述。

> 这不是把参考图“丢掉”，而是当前 Provider 不支持此输入时的降级路径；未来换用支持图生图的 Provider/模型时，不需要改业务流程。

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

- `IMAGE_PROMPT_OPTIMIZER_ENABLED=true`：每次生图前先压缩提示词；
- `TEXT_MODEL_VISION_ENABLED=true`：先尝试把文物图和长 prompt 一起给文本模型；文本模型不支持视觉时自动改用纯文本压缩；
- `IMAGE_REFERENCE_ENABLED=true`：尝试把文物图传给图片模型；Provider 不支持时自动回退。

测试环境中 `IMAGE_PROMPT_OPTIMIZER_ENABLED=false`，避免旧图片测试依赖文本模型；新增测试单独打开。

## 7. 当前验证

- 后端 `41 passed`；
- 前端 `4 files / 10 tests passed`；
- 真实图片生成：
  - 优化后 prompt：约 127 个汉字；
  - 图片生成成功；
  - 输出尺寸 2496×1664；
  - 当前 Provider 参考图失败，`reference_image_used=false`，已自动回退。

## 8. 运营注意

- 当前 Provider 的参考图能力可能随模型/账号权限变化；若恢复，`reference_image_used` 会变 true；
- 图片 prompt 长度上限和 `image` 字段支持应在更换 Provider 时重新验证；
- 不要因为回退而删除 `source_prompt`；它用于研究审计和学生原始表达保留。
