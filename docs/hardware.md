# 硬件引脚 (STM32F103ZET6)

| 引脚 | 功能 | 备注 |
|------|------|------|
| PE5 | 黄灯 DS1 | 低有效 |
| PB5 | 红灯 DS0 | 低有效，兼 MQTT 收包闪烁 |
| PB8 | 蜂鸣器 | 高有效响 |
| PA0 | 火焰传感器 DO | 上拉，低电平=有火 |
| PA6 | SG90 舵机信号 | TIM3 CH1, 50Hz PWM |
| PA2/PA3 | USART2 ↔ ESP8266 | 115200 8N1 |
| PA9/PA10 | USART1 | 调试预留 |

## 硬件文件

| 路径 | 内容 |
|------|------|
| `Arduino_camera/ESP8266_MQTT/` | ESP8266 双向 MQTT 透传固件 |
| `Arduino_camera/CameraWebServer/` | ESP32-CAM 固件 |
| `stm32_serial_led/Src/main.c` | STM32 火焰传感器+舵机+MQTT解析+LED/蜂鸣器 |
| `stm32_serial_led/Inc/usart.h` | USART1/USART2 句柄导出 |
