"""
通信层 v2 — MQTT 多设备支持
通配符订阅 bishe/99257/+/status|flame，自动发现 STM32 设备
"""
import threading
import time
import paho.mqtt.client as mqtt

# MQTT 配置
MQTT_BROKER = "broker-cn.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC_PREFIX = "bishe/99257"          # 多设备前缀
MQTT_STATUS_WILDCARD = "bishe/99257/+/status"
MQTT_FLAME_WILDCARD = "bishe/99257/+/flame"
MQTT_CLIENT_ID = "bishe_server_01"

mqtt_client = None
mqtt_ready = False

# ── 多设备状态 ──────────────────────────────────────
# devices = {
#     "stm32_01": {"online": bool, "flame": bool},
#     "stm32_02": {"online": bool, "flame": bool},
# }
devices = {}
devices_lock = threading.Lock()

# ── 向后兼容聚合属性 ─────────────────────────────────
# detector.py / app.py 仍然通过模块级属性访问
stm32_connected = False   # 任一设备在线即为 True
flame_active = False       # 任一设备火焰触发即为 True


def _recalc_aggregates():
    """根据 devices 字典重新计算聚合状态"""
    global stm32_connected, flame_active
    with devices_lock:
        online = [d for d in devices.values() if d.get("online")]
        stm32_connected = len(online) > 0
        flame_active = any(d.get("flame", False) for d in devices.values())


def _parse_topic(topic):
    """从 topic 解析出 (device_id, field)。
    topic 格式: bishe/99257/{device_id}/{field}
    返回 (device_id, field) 或 (None, None)
    """
    parts = topic.split("/")
    if len(parts) >= 4 and parts[0] == "bishe" and parts[1] == "99257":
        return parts[2], parts[3]  # device_id, field
    return None, None


def _ensure_device(device_id):
    """确保设备在字典中存在"""
    with devices_lock:
        if device_id not in devices:
            devices[device_id] = {"online": False, "flame": False}
            print(f"🆕 发现新设备: {device_id}")


def on_mqtt_connect(client, userdata, flags, reason_code, properties=None):
    global mqtt_ready
    if reason_code == 0:
        client.subscribe(MQTT_STATUS_WILDCARD, qos=1)
        client.subscribe(MQTT_FLAME_WILDCARD, qos=1)
        mqtt_ready = True
        print(f"✅ MQTT 已连接 ({MQTT_BROKER})，通配符订阅: +/status, +/flame")
    else:
        mqtt_ready = False
        print(f"⚠️ MQTT 连接失败: {reason_code}")


def on_mqtt_disconnect(client, userdata, flags, reason_code, properties=None):
    global mqtt_ready
    mqtt_ready = False
    if reason_code is not None:
        print(f"⚠️ MQTT 断开 (code={reason_code})，10秒后自动重连...")
    else:
        print("⚠️ MQTT 断开，10秒后自动重连...")


def on_mqtt_message(client, userdata, msg):
    """通配符回调 — 解析 topic 中的 device_id，更新对应设备状态"""
    global stm32_connected, flame_active

    topic = msg.topic
    payload = msg.payload.decode()
    device_id, field = _parse_topic(topic)

    if device_id is None or device_id == 'server':
        return

    _ensure_device(device_id)

    if field == "status":
        if payload == "online":
            with devices_lock:
                if not devices[device_id].get("online"):
                    print(f"✅ {device_id} 已上线")
                devices[device_id]["online"] = True
        elif payload == "offline":
            with devices_lock:
                if devices[device_id].get("online"):
                    print(f"⚠️ {device_id} 已离线")
                devices[device_id]["online"] = False
        _recalc_aggregates()

    elif field == "flame":
        if payload.startswith("FLAME:1"):
            with devices_lock:
                if not devices[device_id].get("flame"):
                    print(f"🔥 {device_id} 火焰传感器触发！")
                devices[device_id]["flame"] = True
        elif payload.startswith("FLAME:0"):
            with devices_lock:
                if devices[device_id].get("flame"):
                    print(f"🔥 {device_id} 火焰传感器恢复正常")
                devices[device_id]["flame"] = False
        _recalc_aggregates()


def mqtt_broadcast(msg):
    """通过 MQTT 发布消息到 all 在线设备的 alarm topic"""
    global mqtt_client, mqtt_ready
    if not (mqtt_ready and mqtt_client):
        return False
    sent = False
    with devices_lock:
        for dev_id, dev in devices.items():
            if dev.get("online"):
                try:
                    topic = f"{MQTT_TOPIC_PREFIX}/{dev_id}/alarm"
                    mqtt_client.publish(topic, msg, qos=1)
                    sent = True
                except Exception:
                    pass
    if sent:
        short = msg.strip()
        print(f"📤 [MQTT] {short}")
    return sent


def mqtt_send_to(device_id, msg):
    """向指定设备发送消息"""
    global mqtt_client, mqtt_ready
    if mqtt_ready and mqtt_client:
        try:
            topic = f"{MQTT_TOPIC_PREFIX}/{device_id}/alarm"
            mqtt_client.publish(topic, msg, qos=1)
            short = msg.strip()
            print(f"📤 [MQTT→{device_id}] {short}")
            return True
        except Exception:
            return False
    return False


def mqtt_init():
    """初始化 MQTT 客户端"""
    global mqtt_client
    mqtt_client = mqtt.Client(
        client_id=MQTT_CLIENT_ID,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_disconnect = on_mqtt_disconnect
    mqtt_client.on_message = on_mqtt_message
    # will 只能设一个 topic，多设备场景由各 ESP8266 自己的 LWT 负责
    mqtt_client.will_set(f"{MQTT_TOPIC_PREFIX}/server/status", "offline", qos=1, retain=True)
    try:
        mqtt_client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        print(f"📡 MQTT 初始化中 ({MQTT_BROKER}:{MQTT_PORT})...")
    except Exception as e:
        print(f"⚠️ MQTT 初始化失败: {e}")


def broadcast(msg):
    """统一广播接口 — MQTT 多设备发布（兼容旧调用）"""
    mqtt_broadcast(msg)


# ── 以下为老接口占位（不启动 TCP，仅保留函数签名防止 import 报错）───

TCP_PORT = 8888


def tcp_server():
    """已废弃 — 多设备场景仅用 MQTT"""
    print("🔌 TCP Server 已禁用，使用纯 MQTT 通信")


def tcp_broadcast(msg):
    """已废弃"""
    pass
