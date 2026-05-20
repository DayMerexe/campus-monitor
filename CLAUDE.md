# CLAUDE.md

## 项目概述
毕设：应急场景下的校园人流量监控管理系统。双输入：ESP32-CAM + YOLOv8（远程AI）和火焰传感器（本地应急）。

## 当前状态
_更新于 2026-05-20_
- [论文]: 4张.drawio参考模板+手绘PNG备用已生成，5张照片已收集。用户手动重画4张图后即可全部插入终稿
- [软件]: v9 功能完整，前端+折线图、引导算法+钉钉通知、STM32通道独占三个优化模块已完成
- [硬件]: STM32×2 + 火焰传感器 + 舵机 + 蜂鸣器 + ESP8266×2 MQTT + ESP32-CAM 全部验证通过，支持多设备

## 运行命令
`cd F:\bishe\campus_monitor && /c/Users/DayMer/miniconda3/python.exe app.py` → http://localhost:5000

## 项目结构
`campus_monitor/` (主版本) | `Arduino_camera/` (ESP32/ESP8266) | `stm32_serial_led/` (STM32)

## 协作流程
- **主对话**：架构决策 + diff 审查 + 合并执行 + 进度管理
- **子对话**：git checkout -b feature/xxx 在分支内改原文件，commit 推送后由主对话审查合并
- 子对话读入口文档获取上下文，完成后更新入口文档
- 跨层任务采用"方案竞标"决定归属
- 合并流程 & 启动模板详见 `docs/协作流程.md`

## 架构决策
- 双输入通道：远程AI（YOLO） + 本地应急（火焰传感器，不依赖网络）
- MQTT 双向通信：broker-cn.emqx.io:1883
- 三级报警+火焰防抖，详见 docs/architecture.md

## 待办事项
- [ ] 论文：用户手动重画4张图 → 全部图片插入终稿
- [ ] 终期答辩 PPT + 演示流程

## 已知问题
- mDNS 未实现（detector.py + ESP32 固件），IP 变化时需手动改代码

## 技术栈
Python: Flask, PyTorch, YOLOv8, OpenCV, paho-mqtt | Arduino: ESP8266WiFi, PubSubClient | STM32: HAL UART/GPIO, TIM3 PWM | 前端: Chart.js, 原生 JS

## 参考文档
| 文档 | 内容 |
|------|------|
| [协作流程](docs/协作流程.md) | 多对话并行协作规范 |
| [前端与折线图](docs/前端与折线图.md) | 前端UI优化+折线图重设计（子对话入口） |
| [引导算法与通知](docs/引导算法与通知.md) | 人流引导算法+钉钉通知内容（子对话入口） |
| [系统功能总结](docs/系统功能总结.md) | 8 模块概述 + 全开发时间线 + 28 问题&方案 + 硬件清单 |
| [系统架构](docs/architecture.md) | 通信协议、三级报警、实现细节 |
| [传输修复指南](docs/传输修复指南.md) | 修复清单 + 合并步骤 |
| [图表草稿](论文/图表草稿.md) | 论文4张图ASCII草图+draw.io画法提示 |
| [进度日志](docs/PROGRESS.md) | 完整开发进度 |
| [硬件引脚](docs/hardware.md) | STM32 引脚定义 |
