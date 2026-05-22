# 第5课：MQTT 通信层 — communication.py

## 这段代码解决什么问题

STM32 不直接联网，靠 ESP8266 桥接。Python 要和多个 STM32 设备通信，需要：
- 自动发现设备（不硬编码设备ID）
- 知道谁在线、谁的火焰传感器触发了
- 向特定设备发指令

## MQTT 话题体系

```
订阅（Python 收）:
  bishe/99257/+/status    ← 设备上线/离线
  bishe/99257/+/flame     ← 火焰传感器状态

发布（Python 发）:
  bishe/99257/{device_id}/alarm  →  LV:BUZ:SERVO 指令

Will（遗嘱）:
  bishe/99257/server/status  ← 服务器离线通知（保留消息）
```

## 设备自动发现

```python
# communication.py:62-67 — 连接成功时订阅通配符话题
def on_mqtt_connect(client, userdata, flags, reason_code, properties=None):
    client.subscribe("bishe/99257/+/status", qos=1)  # + 匹配任意 device_id
    client.subscribe("bishe/99257/+/flame", qos=1)
```

```python
# communication.py:83-120 — 收到消息时解析设备ID
def on_mqtt_message(client, userdata, msg):
    # msg.topic = "bishe/99257/stm32_01/status"
    device_id, field = _parse_topic(msg.topic)  # → ("stm32_01", "status")

    if device_id is None or device_id == 'server':
        return  # 过滤服务器自己的遗嘱消息

    _ensure_device(device_id)  # 不存在就创建 {"online": False, "flame": False}

    if field == "status":
        devices[device_id]["online"] = (payload == "online")
    elif field == "flame":
        devices[device_id]["flame"] = (payload.startswith("FLAME:1"))

    _recalc_aggregates()  # 更新 stm32_connected / flame_active
```

**关键设计：** 不需要在代码里写死设备列表。新 STM32 上电→ESP8266 发布 `online`→Python 自动在 `devices` 字典创建条目。前端绑定面板自动出现新设备。

## 广播 vs 定向发送

```python
# 旧方案：向所有在线设备广播同一条消息
mqtt_broadcast("LV:2,BUZ:1,SERVO:1")
# 问题：stm32_01 绑定通道A，stm32_02 绑定通道B
#      通道A红色但B正常 → 两个设备都收到相同指令 → B也开门

# 新方案：per-device 定向发送
for dev_id, ch in device_bindings.items():
    lv = 2 if snap[ch]['fire'] else snap[ch]['alarm_level']
    msg = f"LV:{lv},BUZ:{1 if lv>=1 else 0},SERVO:{1 if lv>=2 else 0}"
    mqtt_send_to(dev_id, msg)
# stm32_01→LV:2,BUZ:1,SERVO:1 (开门)
# stm32_02→LV:0,BUZ:0,SERVO:0 (关门)
```

## 节流保护

```python
# 每设备 MQTT 发送节流 0.5s
# 避免 coordinated_decision 每0.3s调用 → broker被刷爆（28个问题之一）
last_mqtt_send = {}  # {device_id: timestamp}
if now - last_mqtt_send.get(dev_id, 0) >= 0.5:
    mqtt_send_to(dev_id, msg)
```

## 聚合属性（向后兼容）

```python
# communication.py:30-31
stm32_connected = False   # 任一设备在线 → True
flame_active = False       # 任一设备火焰 → True

# _recalc_aggregates() 每次状态变化时更新
# detector.py / app.py / notify.py 都通过 communication.stm32_connected 读
```

## ESP8266 侧对应逻辑

```
ESP8266 上电 → WiFi连接 → MQTT连接
  → publish "online" to bishe/99257/{DEVICE_ID}/status
  → subscribe bishe/99257/{DEVICE_ID}/alarm
  → 收到 alarm → Serial.write(payload) → STM32 接收

主循环:
  if Serial.available():
      line = Serial.readStringUntil('\n')
      publish line to bishe/99257/{DEVICE_ID}/flame
  → STM32 发 "FLAME:1\n" → ESP8266 转发到 MQTT
```

Will 消息：ESP8266 断连时 broker 自动发布 `offline`，Python 端立即检测到设备离线。

## 你答辩时怎么说

> "MQTT 是系统的通信中枢。服务器用通配符话题 `+/status` 和 `+/flame` 自动发现 STM32 设备，新增设备零代码改动。下行指令采用定向发送，每个设备根据其绑定通道的状态收到独立的 LV:BUZ:SERVO 指令。加了 0.5 秒节流防止三通道同时报警时刷爆 broker。"
