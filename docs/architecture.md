# 系统架构

## 通信协议

```
PC → MQTT(broker-cn.emqx.io) → ESP8266 → USART2 → STM32:  "COUNT:X,ALARM:Y\n"
STM32 → USART2 → ESP8266 → MQTT(bishe/99257/flame) → PC: "FLAME:1\n" / "FLAME:0\n"
```

- MQTT broker: `broker-cn.emqx.io:1883`
- 主题: `bishe/99257/alarm`（下行）, `bishe/99257/status`（心跳）, `bishe/99257/flame`（火焰上行）
- ESP8266 遗嘱消息: 断线自动发 `offline`，上线发 `online`
- ESP8266 ↔ STM32: USART2, 115200 8N1
- STM32 USART1: 调试预留 (PA9/PA10)

## 三级报警

| 等级 | 触发条件 | 输出 |
|------|---------|------|
| 0 正常 | 人数 ≤ warn | 全灭 |
| 1 黄色 | warn < 人数 ≤ red | 黄灯闪烁 |
| 2 红色 | 人数 > red | 红灯+蜂鸣器+黄灯 |

- 默认阈值: red=5, warn=3（Web 可调）
- 报警防抖: 连续3帧确认，状态切换后锁定3秒
- 火焰报警优先级最高，不被 MQTT 覆盖

## 双输入通道

- **通道1（远程AI）**：ESP32-CAM → PC YOLOv8 → MQTT → ESP8266 → STM32
- **通道2（本地应急）**：火焰传感器 → STM32 直接响应（不依赖网络，优先级最高）

## 关键实现细节

- **ESP32-CAM 视频流**: HTTP raw 直读 MJPEG（不用 cv2.VideoCapture，FFmpeg 解析不兼容）
- **YOLO**: `yolov8n.pt`，帧缩小到 320×240 推理，框坐标按比例映射回原图
- **舵机控制**: 直接寄存器操作 TIM3（HAL_TIM 驱动文件缺失），非阻塞状态机
  - CCR1: 250=正转全速, 750=停止, 1250=反转全速, 持续1200ms
- **火焰防抖**: 100ms 周期，3帧确认，防止误触发
- **手动报警竞态修复**: 手动报警期间自动广播也发 ALARM:2，防止被 ALARM:0 覆盖
- **`import tcp_server`**: 必须用模块引用而非 `from import`，否则 stm32_connected/flame_active 是值快照
