# CLAUDE.md

## 项目概述
毕设：应急场景下的校园人流量监控管理系统。双输入：ESP32-CAM + YOLOv8（远程AI）和火焰传感器（本地应急）。

## 当前状态
_更新于 2026-05-17_
- [软件]: v7 火焰传感器去硬编码 + 手动报警修复 + 火焰按钮动态化 → 软件功能完整
- [AI]: YOLO 训练脚本就绪（train.py + merge_datasets.py），数据集已合并 → 待跑
- [硬件]: main.c 已恢复舵机/蜂鸣器 → 待烧录联调
- [论文]: 旧版作废，以三通道系统重写第1-4章，工具链已就绪

## 运行命令
`cd F:\bishe\campus_monitor && /c/Users/DayMer/miniconda3/python.exe app.py` → http://localhost:5000

## 项目结构
`campus_monitor/` (主版本) | `Arduino_camera/` (ESP32/ESP8266) | `stm32_serial_led/` (STM32) | `ppt-slides/` (PPT)

## 协作流程
- **主对话**：架构决策 + diff 审查 + 合并执行 + 进度管理
- **子对话**：帧率优化 / 数据传输修复（产出 `_fixed`）/ 论文写作（内容生成，非代码）
- 子对话读入口文档获取上下文，完成后更新"协作进度"段落
- 合并流程 & 启动模板详见 `docs/协作流程.md`

## 架构决策
- 双输入通道：远程AI（YOLO） + 本地应急（火焰传感器，不依赖网络）
- MQTT 双向通信：broker-cn.emqx.io:1883
- 三级报警+火焰防抖，详见 docs/architecture.md

## 参考文档
| 文档 | 内容 |
|------|------|
| [YOLO自训练](docs/YOLO模型自训练.md) | 校园监控视角标注 + 微调 YOLOv8，解决漏检 |

## 待办事项
- [ ] 硬件实物联调（烧录 main.c + ESP8266）
- [ ] YOLO 模型自训练（新子对话）
- [ ] 终期答辩 PPT + 演示流程
- [ ] 论文第1-4章（旧版1-2章作废，需以三通道系统重写）

## 已知问题
- mDNS 未实现（detector.py + ESP32 固件），IP 变化时需手动改代码

## 技术栈
Python: Flask, PyTorch, YOLOv8, OpenCV, paho-mqtt | Arduino: ESP8266WiFi, PubSubClient | STM32: HAL UART/GPIO, TIM3 PWM | 前端: Chart.js, 原生 JS

## 论文写作
_入口：新论文对话启动时读本节 + `docs/writing.md`_

> ⚠️ **旧版第1-2章作废**：之前生成的 `论文草稿_第1-2章.docx` 基于旧单通道系统。当前已升级为三通道联动+多出口疏散，论文需以**当前版本**重新撰写。旧文件仅参考格式（docx 生成方式），内容不可复用。

### 工具链
- npm `docx` 包生成 .docx，不用 python-docx
- 环境：`F:\bishe\output\`（已有 `package.json` + `node_modules`）
- 生成脚本：`output/gen_thesis.js`，运行 `node gen_thesis.js`

### 格式常量（gen_thesis.js 已定义）
| 常量 | 值 | 含义 |
|------|-----|------|
| SIMSUN / SIMHEI | "SimSun" / "SimHei" | 正文/标题字体 |
| PT12 / PT14 / PT15 | 24 / 28 / 30 | 小四/四号/小三 (half-pts) |
| LINE_SPACING | 360 | 1.5倍行距 |
| A4 | 11906×16838 | 纸张尺寸 (DXA) |
| MARGIN | 1440 / 1800 | 上下2.54cm / 左右3.17cm |

### 生成模式
- 三个 helper：`bodyPara(text)` 宋体小四+缩进、`h2(text)`/`h3(text)` 黑体加粗
- 内容推入 `children[]` 数组，末位 `new Document({sections:[{children}]})` 打包
- 输出路径：`F:/bishe/output/论文草稿_第X-Y章.docx`
- ~~已生成：第1-2章~~（旧版单通道，作废）
- 待生成：第1-4章（以当前三通道联动系统为基础）

### 避坑
- F: 盘 npm 偶发找不到本地模块，`output/` 内自建 package.json 解决
- 不用 heredoc 写 .js，用 Write 工具直接写入

## 参考文档
| 文档 | 内容 |
|------|------|
| [协作流程](docs/协作流程.md) | 多对话并行协作规范 |
| [系统架构](docs/architecture.md) | 通信协议、三级报警、实现细节 |
| [传输修复指南](docs/传输修复指南.md) | 修复清单 + 合并步骤 |
| [帧率问题](docs/ESP32-CAM帧率问题.md) | ESP32-CAM 帧率分析+优化（子对话A入口） |
| [传输问题](docs/数据传输问题总结.md) | HTTP/MQTT/DB 传输汇总（子对话B入口） |
| [多场景改造](docs/多场景模拟改造.md) | 三通道联动模拟（子对话入口） |
| [STM32适配](docs/STM32三通道适配问题.md) | STM32 手动绑定 + 协议适配（子对话入口） |
| [应急模式](docs/仪表盘应急模式.md) | 仪表盘正常/紧急双态切换（子对话入口） |
| [进度日志](docs/PROGRESS.md) | 完整开发进度 |
| [硬件引脚](docs/hardware.md) | STM32 引脚定义 |
| [文档写作](docs/writing.md) | 论文格式、PPT 工作流 |
