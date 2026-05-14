# CLAUDE.md

## 项目概述
毕设：应急场景下的校园人流量监控管理系统。双输入：ESP32-CAM + YOLOv8（远程AI）和火焰传感器（本地应急）。

## 当前状态
_更新于 2026-05-12_
- [论文]: 第1-2章已生成，第3-4章待生成（详见 docs/PROGRESS.md）
- [PPT]: 11页中期答辩PPT已完成
- [硬件]: 火焰传感器+舵机+MQTT通信完成，待实物联调

## 运行命令

```bash
cd F:\bishe\campus_monitor
/c/Users/DayMer/miniconda3/python.exe app.py  # → http://localhost:5000
cd /f/bishe && git ...
```

## 项目结构

```
campus_monitor/            # 主版本
  app.py / detector.py / db.py / tcp_server.py
  templates/index.html     # 仪表盘
Arduino_camera/            # ESP32-CAM + ESP8266 固件
stm32_serial_led/          # STM32F103ZET6 固件
ppt-slides/                # 答辩PPT源码
```

## 架构决策
- 双输入通道：远程AI（YOLO） + 本地应急（火焰传感器，不依赖网络）
- MQTT 双向通信：broker-cn.emqx.io:1883
- 三级报警+火焰防抖，详见 docs/architecture.md

## 待办事项
- [ ] 论文第3章（系统设计与实现）
- [ ] 论文第4章（系统测试与分析）
- [ ] 火焰传感器+舵机实物联调
- [ ] ESP32-CAM 归还后整体联调
- [ ] 图表切换 ECharts

## 技术栈
Python: Flask, PyTorch, YOLOv8, OpenCV, paho-mqtt | Arduino: ESP8266WiFi, PubSubClient | STM32: HAL UART/GPIO, TIM3 PWM | 前端: Chart.js, 原生 JS

## 参考文档
| 文档 | 内容 |
|------|------|
| [系统架构](docs/architecture.md) | 通信协议、三级报警、实现细节 |
| [硬件引脚](docs/hardware.md) | STM32 引脚定义、固件文件 |
| [文档写作](docs/writing.md) | 论文格式、PPT 工作流 |
| [进度日志](docs/PROGRESS.md) | 完整开发进度 |
