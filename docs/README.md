# 校园人流量监测预警系统

> 应急场景下的校园人流量监测预警系统 —— 毕设项目

## 项目简介

基于 AI 视觉识别技术，实现校园重点区域的人流量实时监测与自动报警。系统由 ESP32-CAM 采集视频，YOLOv8 进行行人检测，Flask 提供 Web 可视化界面，并通过 TCP 无线控制 STM32 硬件报警。

## 系统架构

```
ESP32-CAM  →  HTTP MJPEG  →  PC (YOLOv8 + Flask)  →  浏览器 (Web 仪表盘)
                                              ↓
                                         TCP :8888
                                              ↓
                                    ESP8266 → UART → STM32 → LED + 蜂鸣器
```

## 项目结构

```
F:\bishe\
├── campus_monitor/          # ★ Python 后端（主项目）
│   ├── app.py               # Flask 入口，6 个 REST API 路由
│   ├── detector.py          # HTTP 读 MJPEG + YOLOv8 推理 + TCP 广播
│   ├── db.py                # SQLite 数据库层
│   ├── tcp_server.py        # TCP Server (端口 8888)
│   ├── templates/index.html # Web 前端仪表盘
│   └── data.db              # SQLite 数据库文件
├── stm32_serial_led/        # STM32F103ZET6 固件（Keil 项目）
│   └── Src/main.c           # AT 初始化 + 协议解析 + GPIO 控制
├── Arduino_camera/          # ESP32-CAM 固件（Arduino IDE）
├── docs/                    # 文档
│   ├── 项目开发问题总结.md       # 开发过程中的问题与解决方案
│   ├── 项目熟悉引导计划.md       # 从零理解项目的学习路线
│   ├── 演示流程清单.md          # 答辩演示操作步骤
│   ├── 答辩PPT内容.md           # 答辩 PPT 的文字素材
│   ├── ESP8266排错指南-自动生成版.md
│   ├── ESP8266透传模式选型指南.md
│   ├── ESP8266调试排错指南.md
│   └── CLAUDE.md
├── tests/                   # 测试脚本
├── start.bat                # 一键启动脚本
└── README.md                # 本文件
```

## 硬件清单

| 组件 | 型号 | 作用 |
|------|------|------|
| 摄像头 | ESP32-CAM (AI-THINKER) | 视频采集，MJPEG 推流，WiFi 热点 |
| PC | 笔记本 | 运行 YOLOv8 检测 + Flask Web 服务 |
| WiFi 桥 | ESP8266 ESP-01S | TCP 透传，桥接 PC 和 STM32 |
| 控制板 | STM32F103ZET6 | 驱动 LED 和蜂鸣器 |

## 快速启动

1. 给所有设备上电，PC 连接 WiFi：`test` / `wxh708023`
2. 双击 `start.bat`
3. 浏览器打开 `http://localhost:5000`

或手动启动：

```bash
cd F:\bishe\campus_monitor
C:\Users\DayMer\miniconda3\python.exe app.py
```

## 通信协议

```
PC → ESP8266 → STM32:  COUNT:人数,ALARM:0/1\n
例: COUNT:3,ALARM:0  (3人，正常)
    COUNT:5,ALARM:1  (5人，触发报警)
```

## 关键技术参数

| 参数 | 数值 |
|------|------|
| 检测模型 | YOLOv8n (nano) |
| 检测帧率 | ~10-15 FPS (CPU) |
| 报警阈值 | 默认 5 人（可动态调节） |
| 报警防抖 | 连续 3 帧确认 + 3 秒锁定 |
| TCP 端口 | 8888 |
| Web 端口 | 5000 |

## 网络拓扑

所有设备连接 ESP32-CAM 自建的 WiFi 热点：
- **SSID**: `test`
- **密码**: `wxh708023`
- **PC IP**: `192.168.4.140`（固定）
- **ESP32-CAM**: `192.168.4.121:81/stream`
