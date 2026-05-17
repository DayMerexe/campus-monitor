# CLAUDE.md

## 项目概述
毕设：应急场景下的校园人流量监控管理系统。双输入：ESP32-CAM + YOLOv8（远程AI）和火焰传感器（本地应急）。

## 当前状态
_更新于 2026-05-17_
- [软件]: v8 功能完整（多摄像头 MJPEG URL 输入 + 火焰传感器绑定 + 手动报警修复），15 API 路由，三通道联动正常
- [AI]: YOLO 训练 3330 张数据集就绪，仅跑 1/50 epoch → 需重跑完整训练（batch=8）
- [硬件]: STM32 + 火焰传感器 + 舵机 + 蜂鸣器全部验证通过，ESP32-CAM 待接入测试

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

## 待办事项
- [ ] YOLO 模型自训练（重跑完整 50 epoch）
- [ ] ESP32-CAM 摄像头接入测试
- [ ] 终期答辩 PPT + 演示流程
- [ ] 论文（待用户提供新材料后新开子对话）

## 已知问题
- mDNS 未实现（detector.py + ESP32 固件），IP 变化时需手动改代码

## 技术栈
Python: Flask, PyTorch, YOLOv8, OpenCV, paho-mqtt | Arduino: ESP8266WiFi, PubSubClient | STM32: HAL UART/GPIO, TIM3 PWM | 前端: Chart.js, 原生 JS

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
| [多摄像头](docs/MJPEG多摄像头支持.md) | v8 MJPEG URL 输入框，支持多 ESP32-CAM 接入 |
| [应急模式](docs/仪表盘应急模式.md) | 仪表盘正常/紧急双态切换（子对话入口） |
| [进度日志](docs/PROGRESS.md) | 完整开发进度 |
| [硬件引脚](docs/hardware.md) | STM32 引脚定义 |
