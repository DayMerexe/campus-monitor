# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

毕设：应急场景下的校园人流量监控管理系统。数据管道：**ESP32-CAM → YOLOv8 → Flask Web → TCP → ESP8266 → STM32 → LED/蜂鸣器**。

## 运行命令

```bash
# Python 后端（主版本是 campus_monitor/，不是 campus2/ 或 main.py）
cd F:\bishe\campus_monitor
/c/Users/DayMer/miniconda3/python.exe app.py
# 访问 http://localhost:5000

# 独立测试脚本
/c/Users/DayMer/miniconda3/python.exe F:/bishe/test_tcp_server.py
/c/Users/DayMer/miniconda3/python.exe F:/bishe/tests/yolo_test.py [图片路径]

# Git 操作
cd /f/bishe && git ...
```

## 项目结构（仅关键文件）

```
campus_monitor/          # ★ 当前主版本 (MVC 模块化)
  app.py                 # Flask 入口 + /status /control /history /alarms 路由
  detector.py            # HTTP raw 读 MJPEG + YOLOv8 推理 + DB写入 + TCP广播
  db.py                  # SQLite: detection_records + alarm_events 表
  tcp_server.py          # TCP Server (0.0.0.0:8888)，管理客户端列表 + tcp_broadcast()
  templates/index.html   # Chart.js 仪表盘（左视频+右图表+底报警表格）
  main.py                # 旧版单体架构，保留参照，不使用
Arduino_camera/CameraWebServer/  # ESP32-CAM 固件（Arduino IDE 编译烧录）
  CameraWebServer.ino    # AI_THINKER 型号，VGA/quality=20/XCLK=30MHz
  app_httpd.cpp          # MJPEG stream handler (port 80/81)
stm32_serial_led/        # STM32F103ZET6 固件（Keil MDK-ARM）
  Src/main.c             # AT 初始化 + sscanf("COUNT:%d,ALARM:%d") 解析 + GPIO 控制
esp8266_bridge/          # 独立 ESP8266 透传桥（备用方案，非主线）
tests/                   # yolo_test.py, realtime_test.py
```

## 网络拓扑

所有设备连 ESP32-CAM 自建的 WiFi AP：SSID=`test`, 密码=`wxh708023`。

| 组件 | IP/端口 | 备注 |
|------|---------|------|
| ESP32-CAM | `192.168.4.183:81/stream` | DHCP 动态，查串口确认 |
| PC (Python) | `192.168.4.140:5000` (Web) `:8888` (TCP) | IP 硬编码在 STM32 的 `TCP_IP` 宏 |

## 通信协议

```
ESP32-CAM → PC:  HTTP MJPEG (直读 HTTP raw，不用 cv2.VideoCapture)
PC → Browser:    multipart MJPEG + JSON REST API
PC → ESP8266:    TCP raw "COUNT:3,ALARM:0\n"（端口 8888，每帧广播）
ESP8266 → STM32: UART2, 115200 8N1，透明转发
STM32 引脚:      PE5=黄灯, PB5=红灯, PB8=蜂鸣器（均为低有效亮灯，PB8 高有效响）
```

## YOLO 推理关键配置

- 模型：`yolov8n.pt`（首次自动下载，gitignore 了）
- 帧先缩小到 320×240 推理，框坐标按 `sx/sy` 比例映射回 VGA 原图
- 只检测 `PERSON_CLASS_ID = 0`，默认阈值 0.6
- 报警阈值 `ALARM_THRESHOLD = 5`（Web 页面可动态修改）
- 手动报警期间 `manual_alarm_active = True` 会暂停自动 TCP 广播，防止被覆盖

## 常见问题

- **ESP32-CAM 烧录后 Arduino IDE 卡死**：正常，串口被大量调试日志冲死，强关 IDE 即可，固件已烧入
- **Python 路径**：bash 里 `python` 不可用，用 `/c/Users/DayMer/miniconda3/python.exe`
- **`from detector import ALARM_THRESHOLD`**：会创建整数快照导致阈值设置无效，必须用 `import detector` + `detector.ALARM_THRESHOLD`
- **画质值方向**：ESP32 `set_quality(0-63)`，越小越清晰文件越大越慢，20 是平衡值
- **STM32 蜂鸣器 PB8**：不在 MX_GPIO_Init() 里，手动在 main.c 初始化
- **USART2 AT 回复残渣**：STM32 初始化后必须 flush 缓冲区，否则 `sscanf("COUNT:...")` 匹配不上
