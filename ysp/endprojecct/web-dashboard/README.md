# DHT11 温湿度 Web 监控面板

配套 STM32F103 + RT-Thread DHT11 项目的 Web 监控端。

## 架构

```
STM32 → MQTT (broker.emqx.io) ← Python Backend (存 SQLite)
                ↑                       │
                │ MQTT.js (WebSocket)    │ REST API
                │                       ↓
             前端 HTML 页面 ←────────── 历史数据 / 告警
```

## 快速启动

```bash

# 1. 安装 Python 依赖
cd backend
pip install -r requirements.txt

# 2. 启动后端（自动连接 MQTT，端口 8000）
python main.py

# 3. 浏览器打开
# http://localhost:8000
```

## MQTT 数据格式

STM32 端需要向 `rtt123321123` 主题发布 JSON：

```json
{"temperature": 25, "humidity": 60}
```

- Broker: `broker.emqx.io`
- TCP 端口: 1883
- WebSocket 端口: 8083
- 用户名/密码: `rt-thread` / `rt-thread`

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/data/latest` | 最新一条温湿度 |
| GET | `/api/data/history?hours=24` | 历史数据 |
| GET | `/api/alerts/config` | 告警阈值配置 |
| PUT | `/api/alerts/config` | 更新告警阈值 |
| GET | `/api/alerts/log?limit=50` | 告警日志 |

## 功能

- 实时温湿度面板（MQTT.js 直连 broker）
- 历史趋势图表（ECharts 双 Y 轴）
- 告警阈值设置（温度/湿度上下限）
- 告警日志记录
- 暗色仪表盘风格
