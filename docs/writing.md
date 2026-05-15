# 文档写作

## 论文 (docx-js)

- 已生成第1-2章：`output/论文草稿_第1-2章.docx`
- 格式：A4，宋体正文小四，黑体标题，1.5倍行距，首行缩进2字符
- 待生成：第3章（系统设计与实现）、第4章（系统测试与分析）

## PPT (html2pptx)

- 已生成 11 页中期答辩 PPT：`ppt-slides/中期答辩.pptx`
- 工作流：HTML (720×405pt) → Playwright 渲染 → PptxGenJS → .pptx
- Windows 上 html2pptx.js 已改为 `channel: 'msedge'`，无需下载 Chromium
- 关键规则：`<p>` 不能有 border/background/shadow，必须用 `<div>` 包裹 `<p>`
- 运行：`NODE_PATH="...npm/node_modules" node ppt-slides/convert.js`
