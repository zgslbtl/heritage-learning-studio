# Student Portfolio PDF Export

日期：2026-11-08  
状态：已实现

## 1. 触发位置

学生完成互评、进入最终“作品广场”后，底部按钮为：

```text
完成浏览，结束工作坊，并导出我的作品 / Finish & Export My Work
```

点击后：

1. 先获取学生自己的 T1/T2 作品和已选图片；
2. 在浏览器内生成 PDF 并下载；
3. 再调用 `/api/student/social/complete` 完成工作坊。

如果 PDF 导出失败，不静默完成；页面显示错误并允许重试。

## 2. 数据接口

```text
GET /api/student/portfolio
```

返回当前参与者自己的：

- round_no；
- artifact_title；
- image_url；
- product_name；
- product_category；
- target_audience；
- design_concept；
- statement。

`statement` 来源：

- v2 rationale：三段式说明；
- v1 六字段：六字段拼接；
- 开放说明：open_statement。

不返回其他学生的数据、A/B 标签、分组或分数。

## 3. PDF 实现

- `html2canvas` + `jsPDF`；
- 使用浏览器字体渲染中文，避免服务端 PDF 中文字体依赖；
- 每个有作品的轮次一页；
- 页面内容：学生匿名编号、轮次、文物标题、产品名、类别/受众、图片、作品说明；
- 图片缺失时仍生成文字页；
- 文件名：

```text
hlsf-portfolio-<short-id>.pdf
```

## 4. 验收

- 最终按钮触发浏览器下载；
- PDF 文件头为 `%PDF`；
- 两条轮次作品生成 2 页；
- PDF 后再完成工作坊；
- 无作品时仍可生成文字页并完成；
- 不包含其他学生、A/B 或分数信息。
